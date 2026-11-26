"""Request envelope: the frozen, hash-bound unit every decision attaches to.

Every routing, consent, privacy, and cost decision in the adapter layer is
bound to the exact bytes of a ``RouteEnvelope`` via its canonical-JSON
SHA-256 digest (the U1Si-Q ActionEnvelope / NemoClaw request-hashing
pattern). Canonicalization is what makes the digest byte-exact rather than
identity-dependent: two dicts that differ only in key insertion order or
whitespace normalize to the same bytes, so a decision made on one is a
decision made on the other.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Mapping

# Tier ladder for any route leaving more of U1's control. Ordered by how far
# the data travels: local processing, U1-controlled processing, external
# provider. The policy layer may raise a declared tier; it can never be
# talked below its own floor.
TIER_0_LOCAL = 0
TIER_1_U1CONTROLLED = 1
TIER_2_EXTERNAL = 2
MAX_TIER = TIER_2_EXTERNAL


class Tier(IntEnum):
    LOCAL = TIER_0_LOCAL
    U1_CONTROLLED = TIER_1_U1CONTROLLED
    EXTERNAL = TIER_2_EXTERNAL


class ContentClass(str, Enum):
    """What the payload expresses. Classes route differently; they are not
    refused for being adult. Classification is caller-declared in v0.1 and
    policy-floor-checked (see policy.py); automated classification is a
    later milestone."""

    GENERAL = "general"
    ADULT_THEMED = "adult_themed"
    EXPLICIT = "explicit"


def canonical_json(value: Any) -> str:
    """Serialize ``value`` to canonical JSON: sorted keys, compact separators,
    non-ASCII characters preserved.

    Raises:
        ValueError: if the value contains anything JSON cannot represent.
            Raised, never silently coerced — an envelope that cannot be
            canonicalized cannot be hash-bound, so it cannot be governed.
    """
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("payload_not_json_serializable") from exc


def sha256_hex(text: str) -> str:
    """SHA-256 of the UTF-8 encoding of ``text``, as lowercase hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coerce_content_class(value: Any) -> ContentClass:
    # Accept the raw string form ("general") as well as the enum member so
    # callers building envelopes from wire data do not have to import the
    # enum — but anything else fails closed.
    if isinstance(value, ContentClass):
        return value
    try:
        return ContentClass(value)
    except ValueError as exc:
        raise ValueError("unknown_content_class") from exc


def _coerce_tier(value: Any) -> Tier:
    if isinstance(value, Tier):
        return value
    try:
        tier = Tier(int(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_tier") from exc
    if tier not in (Tier.LOCAL, Tier.U1_CONTROLLED, Tier.EXTERNAL):
        raise ValueError("invalid_tier")
    return tier


@dataclass(frozen=True)
class RouteEnvelope:
    """A frozen routing request bound to its own canonical digest.

    Attributes:
        request_id: caller-chosen identifier, carried through receipts.
        principal: the principal the request acts for (identity is context
            for policy; it is never permission by itself).
        content_class: what the payload expresses (``ContentClass`` or its
            string value).
        declared_tier: the tier the caller claims to need. ``tier =
            max(policy_floor, declared)`` — under-declaring buys nothing.
        payload: the request body. Canonicalized and hashed, never mutated.
        params: declared routing parameters, hashed with the payload.
    """

    request_id: str
    principal: str
    content_class: ContentClass
    declared_tier: Tier
    payload: Mapping[str, Any]
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id:
            raise ValueError("request_id_empty")
        if not isinstance(self.principal, str) or not self.principal:
            raise ValueError("principal_empty")
        # Frozen dataclass: normalize wire-form values in place.
        object.__setattr__(self, "content_class", _coerce_content_class(self.content_class))
        object.__setattr__(self, "declared_tier", _coerce_tier(self.declared_tier))
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload_not_mapping")
        if not isinstance(self.params, Mapping):
            raise ValueError("params_not_mapping")
        # Compute the digest eagerly so an un-canonicalizable payload fails
        # at construction, not at decision time.
        self.envelope_hash

    @property
    def envelope_hash(self) -> str:
        """SHA-256 over the canonical JSON of this envelope's governed fields.

        Byte-exact: identical envelopes produce identical digests regardless
        of key insertion order; any byte-level difference in content (or any
        change to class, tier, principal, or params) produces a different
        digest — which is what voids a consent token bound to it.
        """
        body = {
            "request_id": self.request_id,
            "principal": self.principal,
            "content_class": self.content_class.value,
            "declared_tier": int(self.declared_tier),
            "payload": self.payload,
            "params": self.params,
        }
        return sha256_hex(canonical_json(body))
