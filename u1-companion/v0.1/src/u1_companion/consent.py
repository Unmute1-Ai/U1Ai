"""Consent tokens: signed, envelope-bound, single-use, tier-ceilinged.

External processing of sensitive content classes requires a consent grant
from a registered approver, bound to the exact envelope being processed
(the U1Si-Q ConsentToken pattern). Binding to the envelope hash means any
change to the payload, params, class, tier, or principal voids the grant:
a token approved for one request is never a token approved for another.

Issuance is trusted-service-only — there is deliberately no public
issuance endpoint (the SQLiteApprovalStore precedent). The service holds
the signing key; approvers are registered at construction time, each with
a maximum tier the grant can never exceed. Nonces are burned only on
ALLOW so unrelated denials never force re-approval.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, replace
from typing import Any

from u1_companion.envelope import Tier, canonical_json

SIGNATURE_VERSION = "u1-consent/v0.1"
MIN_CONSENT_TTL_SECONDS = 1
MAX_CONSENT_TTL_SECONDS = 3600
_NONCE_BYTES = 16

# Fail-closed validation reasons (snake_case tokens; never error text).
REASON_INVALID_SIGNATURE = "consent_invalid_signature"
REASON_ENVELOPE_MISMATCH = "consent_envelope_mismatch"
REASON_EXPIRED = "consent_expired"
REASON_TIER_INSUFFICIENT = "consent_approver_tier_insufficient"
REASON_NONCE_USED = "consent_nonce_already_used"


class ConsentIssuanceError(ValueError):
    """Raised when a consent grant cannot be issued on the trusted path.

    Issuance misuse is a programming or configuration error, not an
    untrusted input, so it surfaces as an exception instead of a denial
    reason: a silently unissued token would look like a denial and hide
    the real problem.
    """


def _sign(key: bytes, body: dict[str, Any]) -> str:
    digest = hmac.new(key, canonical_json(body).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


@dataclass(frozen=True)
class ConsentToken:
    """A signed consent grant bound to one exact envelope hash.

    Attributes:
        envelope_hash: the RouteEnvelope digest this grant covers. Any
            byte-level change to the governed fields voids the grant.
        approver_id: the registered approver who issued the grant.
        max_tier: the highest tier this grant authorizes; the approver's
            registered ceiling, never raised by the requester.
        issued_at / expires_at: wall-clock bounds (epoch seconds).
        nonce: single-use value, burned on ALLOW.
        signature: HMAC-SHA256 over the canonical signing body.
    """

    envelope_hash: str
    approver_id: str
    max_tier: Tier
    issued_at: float
    expires_at: float
    nonce: str
    signature: str

    def signing_body(self) -> dict[str, Any]:
        """The exact fields the signature covers (everything but itself)."""
        return {
            "version": SIGNATURE_VERSION,
            "envelope_hash": self.envelope_hash,
            "approver_id": self.approver_id,
            "max_tier": int(self.max_tier),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }


class ConsentService:
    """Trusted-service issuer and verifier of consent tokens.

    The signing key never leaves the service; the gate (an untrusted
    caller by comparison) can only validate tokens and burn nonces.
    """

    def __init__(self, signing_key: bytes) -> None:
        if not signing_key:
            raise ConsentIssuanceError("signing_key_empty")
        self._key = bytes(signing_key)
        self._approver_tiers: dict[str, Tier] = {}
        self._used_nonces: set[str] = set()

    # -- Trusted issuance (no public endpoint; callers here are the service) -

    def register_approver(self, approver_id: str, max_tier: Tier) -> None:
        """Register an approver with the ceiling their grants can never exceed."""
        if not isinstance(approver_id, str) or not approver_id:
            raise ConsentIssuanceError("approver_id_empty")
        if max_tier not in (Tier.LOCAL, Tier.U1_CONTROLLED, Tier.EXTERNAL):
            raise ConsentIssuanceError("invalid_approver_max_tier")
        self._approver_tiers[approver_id] = max_tier

    def issue(
        self,
        envelope_hash: str,
        approver_id: str,
        *,
        ttl_seconds: int,
        now: float | None = None,
    ) -> ConsentToken:
        """Issue a token bound to ``envelope_hash`` for a registered approver.

        The token's ``max_tier`` is the approver's registered ceiling — the
        requester never chooses the tier of their own grant.
        """
        if not isinstance(envelope_hash, str) or len(envelope_hash) != 64:
            raise ConsentIssuanceError("invalid_envelope_hash")
        if approver_id not in self._approver_tiers:
            # An unregistered approver has no ceiling to enforce; fail the
            # issuance rather than defaulting to any tier.
            raise ConsentIssuanceError("approver_not_registered")
        if not isinstance(ttl_seconds, int) or not (
            MIN_CONSENT_TTL_SECONDS <= ttl_seconds <= MAX_CONSENT_TTL_SECONDS
        ):
            raise ConsentIssuanceError("ttl_out_of_bounds")
        issued_at = time.time() if now is None else now
        token = ConsentToken(
            envelope_hash=envelope_hash,
            approver_id=approver_id,
            max_tier=self._approver_tiers[approver_id],
            issued_at=issued_at,
            expires_at=issued_at + ttl_seconds,
            nonce=secrets.token_hex(_NONCE_BYTES),
            signature="",
        )
        signature = _sign(self._key, token.signing_body())
        return replace(token, signature=signature)

    # -- Validation (callable from the gate; untrusted-token tolerant) ------

    def validate(
        self,
        token: ConsentToken,
        envelope_hash: str,
        required_tier: Tier,
        *,
        now: float | None = None,
    ) -> tuple[bool, str | None]:
        """Fail-closed validation of a token against this exact envelope.

        Returns ``(True, None)`` or ``(False, snake_case_reason)``. Order:
        signature first (any tampered field fails here), then envelope
        binding, then expiry, then the approver tier ceiling.
        """
        if not isinstance(token, ConsentToken):
            return False, REASON_INVALID_SIGNATURE
        expected = _sign(self._key, token.signing_body())
        if not hmac.compare_digest(expected, token.signature):
            return False, REASON_INVALID_SIGNATURE
        if token.envelope_hash != envelope_hash:
            return False, REASON_ENVELOPE_MISMATCH
        current = time.time() if now is None else now
        if current >= token.expires_at:
            return False, REASON_EXPIRED
        if required_tier > token.max_tier:
            return False, REASON_TIER_INSUFFICIENT
        return True, None

    def consume(self, token: ConsentToken) -> tuple[bool, str | None]:
        """Burn the nonce, at-most-once.

        Called only on ALLOW: unrelated denials must not force re-approval.
        """
        if token.nonce in self._used_nonces:
            return False, REASON_NONCE_USED
        self._used_nonces.add(token.nonce)
        return True, None
