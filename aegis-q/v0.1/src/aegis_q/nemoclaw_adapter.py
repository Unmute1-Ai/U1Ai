"""Fail-closed boundary for proposals returned by a NemoClaw-hosted agent.

NemoClaw and its selected agent variant are deployment concerns. This module
deliberately defines no undocumented NemoClaw HTTP/CLI protocol: callers supply
their approved transport, while this boundary treats every response as
untrusted data and never dispatches effects.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time
from typing import Any, Callable, Mapping, Protocol

from .sentinel_bridge import ActionProposal


class ProposalClient(Protocol):
    """Configured client that applies the caller's monotonic deadline to I/O."""

    def propose(
        self,
        request: Mapping[str, Any],
        *,
        deadline_monotonic: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class EvidenceScope:
    """Immutable context a verifier must match against the referenced receipt."""

    request_sha256: str
    action: str
    parameters_json: str
    evidence_refs: tuple[str, ...]
    action_digest: str
    deadline_monotonic: float


EvidenceVerifier = Callable[[str, EvidenceScope], bool]
MAX_PROPOSAL_TIMEOUT_SECONDS = 30.0
MAX_REQUEST_BYTES = 64 * 1024
MAX_PARAMETER_BYTES = 64 * 1024
MAX_EVIDENCE_REFS = 64


@dataclass(frozen=True)
class ProposalBoundaryResult:
    decision: str
    reason: str
    proposal: ActionProposal | None = None
    evidence_refs: tuple[str, ...] = ()
    parameters_json: str | None = None
    request_sha256: str | None = None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(
    request_sha256: str,
    action: str,
    parameters: Mapping[str, Any],
    evidence_refs: tuple[str, ...],
) -> str:
    canonical = json.dumps(
        {
            "request_sha256": request_sha256,
            "action": action,
            "parameters": parameters,
            "evidence_refs": evidence_refs,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _valid_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_valid_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _valid_json_value(item) for key, item in value.items())
    return False


def request_nemoclaw_proposal(
    client: ProposalClient,
    request: Mapping[str, Any],
    *,
    evidence_verifier: EvidenceVerifier,
    timeout_seconds: float,
) -> ProposalBoundaryResult:
    """Obtain one bounded candidate and verify evidence against its exact scope.

    The client and verifier must enforce the supplied monotonic deadline in
    their own I/O operations. This synchronous boundary cannot interrupt a
    non-cooperative implementation, so late responses and explicit timeouts
    fail closed, while implementations remain responsible for bounded calls.
    Sentinel still makes the authorization decision.
    """
    if not callable(evidence_verifier):
        return ProposalBoundaryResult("DENY", "evidence_verifier_required")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0.0 < float(timeout_seconds) <= MAX_PROPOSAL_TIMEOUT_SECONDS
    ):
        return ProposalBoundaryResult("DENY", "invalid_timeout")
    started_monotonic = time.monotonic()
    deadline_monotonic = started_monotonic + float(timeout_seconds)
    if not math.isfinite(deadline_monotonic):
        return ProposalBoundaryResult("DENY", "invalid_timeout")
    if deadline_monotonic <= time.monotonic():
        return ProposalBoundaryResult("DENY", "deadline_expired")

    if not isinstance(request, Mapping):
        return ProposalBoundaryResult("DENY", "invalid_request")
    try:
        request_payload = dict(request)
        if not _valid_json_value(request_payload):
            return ProposalBoundaryResult("DENY", "invalid_request")
        request_json = _canonical_json(request_payload)
        if len(request_json.encode("utf-8")) > MAX_REQUEST_BYTES:
            return ProposalBoundaryResult("DENY", "request_too_large")
        request_sha256 = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        # Give the client a private JSON snapshot, not the caller's mutable mapping.
        request_snapshot = json.loads(request_json)
    except Exception:
        return ProposalBoundaryResult("DENY", "invalid_request")

    if time.monotonic() >= deadline_monotonic:
        return ProposalBoundaryResult("DENY", "deadline_expired")
    try:
        try:
            raw = client.propose(
                request_snapshot,
                deadline_monotonic=deadline_monotonic,
            )
        except TimeoutError:
            return ProposalBoundaryResult("DENY", "proposal_deadline_exceeded")
        if time.monotonic() >= deadline_monotonic:
            return ProposalBoundaryResult("DENY", "proposal_deadline_exceeded")
        if not isinstance(raw, Mapping) or set(raw) != {
            "action", "parameters", "model_id", "confidence", "evidence_refs"
        }:
            return ProposalBoundaryResult("DENY", "invalid_proposal_schema")

        action = raw["action"]
        model_id = raw["model_id"]
        parameters = raw["parameters"]
        confidence = raw["confidence"]
        refs = raw["evidence_refs"]
        if not isinstance(action, str) or not action.strip() or len(action) > 128:
            return ProposalBoundaryResult("DENY", "invalid_action")
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 256:
            return ProposalBoundaryResult("DENY", "invalid_model_id")
        if not isinstance(parameters, dict) or not _valid_json_value(parameters):
            return ProposalBoundaryResult("DENY", "invalid_parameters")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return ProposalBoundaryResult("DENY", "invalid_confidence")
        if not math.isfinite(float(confidence)) or not 0.0 <= float(confidence) <= 1.0:
            return ProposalBoundaryResult("DENY", "invalid_confidence")
        if not isinstance(refs, list) or not refs:
            return ProposalBoundaryResult("DENY", "evidence_required")
        if len(refs) > MAX_EVIDENCE_REFS:
            return ProposalBoundaryResult("DENY", "too_many_evidence_references")
        if any(not isinstance(ref, str) or not ref.strip() or len(ref) > 512 for ref in refs):
            return ProposalBoundaryResult("DENY", "invalid_evidence_reference")

        evidence_refs = tuple(sorted(set(refs)))
        if len(evidence_refs) != len(refs):
            return ProposalBoundaryResult("DENY", "duplicate_evidence_reference")

        # Canonical JSON prevents values changing meaning across the authority hop.
        action = action.strip()
        parameters_json = _canonical_json(parameters)
        if len(parameters_json.encode("utf-8")) > MAX_PARAMETER_BYTES:
            return ProposalBoundaryResult("DENY", "parameters_too_large")
        canonical_parameters = json.loads(parameters_json)
        action_digest = _digest(
            request_sha256, action, canonical_parameters, evidence_refs
        )
        evidence_scope = EvidenceScope(
            request_sha256=request_sha256,
            action=action,
            parameters_json=parameters_json,
            evidence_refs=evidence_refs,
            action_digest=action_digest,
            deadline_monotonic=deadline_monotonic,
        )
        for ref in evidence_refs:
            if time.monotonic() >= deadline_monotonic:
                return ProposalBoundaryResult("DENY", "evidence_deadline_exceeded")
            try:
                verified = evidence_verifier(ref, evidence_scope)
            except TimeoutError:
                return ProposalBoundaryResult("DENY", "evidence_deadline_exceeded")
            if time.monotonic() >= deadline_monotonic:
                return ProposalBoundaryResult("DENY", "evidence_deadline_exceeded")
            if verified is not True:
                return ProposalBoundaryResult("DENY", "evidence_not_verified")

        candidate = ActionProposal(
            action=action,
            action_digest=action_digest,
            model_id=model_id,
            confidence=float(confidence),
        )
        return ProposalBoundaryResult(
            "PROPOSED", "evidence_verified_sentinel_required", candidate,
            evidence_refs, parameters_json, request_sha256,
        )
    except Exception:
        # Do not return exception text: transports can include secrets or
        # attacker-controlled response fragments in their errors.
        return ProposalBoundaryResult("DENY", "proposal_or_evidence_validation_failed")
