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
from typing import Any, Callable, Mapping, Protocol

from .sentinel_bridge import ActionProposal


class ProposalClient(Protocol):
    """Minimal contract implemented by a configured NemoClaw agent client."""

    def propose(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


EvidenceVerifier = Callable[[str], bool]
MAX_PARAMETER_BYTES = 64 * 1024
MAX_EVIDENCE_REFS = 64


@dataclass(frozen=True)
class ProposalBoundaryResult:
    decision: str
    reason: str
    proposal: ActionProposal | None = None
    evidence_refs: tuple[str, ...] = ()
    parameters_json: str | None = None


def _digest(action: str, parameters: Mapping[str, Any], evidence_refs: tuple[str, ...]) -> str:
    canonical = json.dumps(
        {"action": action, "parameters": parameters, "evidence_refs": evidence_refs},
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
) -> ProposalBoundaryResult:
    """Obtain one candidate and verify its evidence; Sentinel still decides.

    A missing verifier, malformed response, unverified evidence, transport
    failure, or invalid field returns DENY. The model's confidence is preserved
    as metadata only; it never grants permission.
    """
    if not callable(evidence_verifier):
        return ProposalBoundaryResult("DENY", "evidence_verifier_required")
    try:
        raw = client.propose(request)
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
        if not all(evidence_verifier(ref) is True for ref in evidence_refs):
            return ProposalBoundaryResult("DENY", "evidence_not_verified")

        # Ensure parameters are canonicalizable JSON, with no NaN or custom
        # Python objects that could change meaning across the authorization hop.
        json.dumps(parameters, sort_keys=True, separators=(",", ":"), allow_nan=False)
        action = action.strip()
        parameters_json = json.dumps(
            parameters, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if len(parameters_json.encode("utf-8")) > MAX_PARAMETER_BYTES:
            return ProposalBoundaryResult("DENY", "parameters_too_large")
        action_digest = _digest(action, json.loads(parameters_json), evidence_refs)
        candidate = ActionProposal(
            action=action,
            action_digest=action_digest,
            model_id=model_id,
            confidence=float(confidence),
        )
        return ProposalBoundaryResult(
            "PROPOSED", "evidence_verified_sentinel_required", candidate,
            evidence_refs, parameters_json,
        )
    except Exception:
        # Do not return exception text: transports can include secrets or
        # attacker-controlled response fragments in their errors.
        return ProposalBoundaryResult("DENY", "proposal_or_evidence_validation_failed")

