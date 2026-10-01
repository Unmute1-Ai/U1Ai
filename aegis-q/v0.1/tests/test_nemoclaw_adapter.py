import hashlib
import json

from aegis_q.nemoclaw_adapter import request_nemoclaw_proposal
from aegis_q.sentinel_bridge import Principal, authorize_reference


class FakeProposalClient:
    def __init__(self, result):
        self.result = result

    def propose(self, request):
        return self.result


def proposal(**overrides):
    result = {
        "action": "read_state",
        "parameters": {"device_id": "watch-7"},
        "model_id": "nemoclaw-agent",
        "confidence": 0.99,
        "evidence_refs": ["glassbox:receipt:123"],
    }
    result.update(overrides)
    return result


def test_verified_nemoclaw_candidate_still_requires_sentinel_authority():
    result = request_nemoclaw_proposal(
        FakeProposalClient(proposal()), {"task": "read"},
        evidence_verifier=lambda ref: ref == "glassbox:receipt:123",
    )

    assert result.decision == "PROPOSED"
    assert result.reason == "evidence_verified_sentinel_required"
    assert result.proposal is not None
    body = {
        "action": "read_state",
        "parameters": {"device_id": "watch-7"},
        "evidence_refs": ["glassbox:receipt:123"],
    }
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert result.proposal.action_digest == expected
    assert result.parameters_json == '{"device_id":"watch-7"}'

    # Proposal acceptance never bypasses the existing authority boundary.
    denied = authorize_reference(Principal("agent", frozenset()), result.proposal)
    assert denied.decision == "DENY"


def test_missing_or_unverified_evidence_fails_closed():
    missing = request_nemoclaw_proposal(
        FakeProposalClient(proposal(evidence_refs=[])), {}, evidence_verifier=lambda _: True
    )
    forged = request_nemoclaw_proposal(
        FakeProposalClient(proposal()), {}, evidence_verifier=lambda _: False
    )
    assert (missing.decision, missing.reason) == ("DENY", "evidence_required")
    assert (forged.decision, forged.reason) == ("DENY", "evidence_not_verified")
    assert missing.proposal is None and forged.proposal is None


def test_malformed_or_nonfinite_output_fails_closed():
    malformed = request_nemoclaw_proposal(
        FakeProposalClient(proposal(extra="authority")), {}, evidence_verifier=lambda _: True
    )
    nonfinite = request_nemoclaw_proposal(
        FakeProposalClient(proposal(confidence=float("nan"))), {}, evidence_verifier=lambda _: True
    )
    assert malformed.decision == "DENY"
    assert nonfinite.decision == "DENY"
    assert malformed.proposal is None and nonfinite.proposal is None


def test_non_json_parameter_objects_are_not_admitted():
    result = request_nemoclaw_proposal(
        FakeProposalClient(proposal(parameters={"device_id": object()})),
        {}, evidence_verifier=lambda _: True,
    )
    assert result.decision == "DENY"
    assert result.proposal is None


def test_transport_exception_is_not_exposed_or_admitted():
    class FailingClient:
        def propose(self, request):
            raise RuntimeError("secret-bearing transport detail")

    result = request_nemoclaw_proposal(FailingClient(), {}, evidence_verifier=lambda _: True)
    assert result.decision == "DENY"
    assert result.reason == "proposal_or_evidence_validation_failed"
    assert result.proposal is None

