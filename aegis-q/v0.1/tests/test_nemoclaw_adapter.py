import hashlib
import json
import time

import aegis_q.nemoclaw_adapter as nemoclaw_adapter
from aegis_q.nemoclaw_adapter import request_nemoclaw_proposal
from aegis_q.sentinel_bridge import Principal, authorize_reference


class FakeProposalClient:
    def __init__(self, result):
        self.result = result
        self.deadline_monotonic = None

    def propose(self, request, *, deadline_monotonic):
        self.deadline_monotonic = deadline_monotonic
        return self.result


def request_proposal(client, request, verifier):
    return request_nemoclaw_proposal(
        client,
        request,
        evidence_verifier=verifier,
        timeout_seconds=5.0,
    )


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
    request = {"task": "read"}
    observed_scope = []

    def verify(ref, scope):
        observed_scope.append((ref, scope))
        return ref == "glassbox:receipt:123" and scope.action == "read_state"

    client = FakeProposalClient(proposal())
    result = request_proposal(client, request, verify)

    assert result.decision == "PROPOSED"
    assert result.reason == "evidence_verified_sentinel_required"
    assert result.proposal is not None
    body = {
        "request_sha256": hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        "action": "read_state",
        "parameters": {"device_id": "watch-7"},
        "evidence_refs": ["glassbox:receipt:123"],
    }
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert result.proposal.action_digest == expected
    assert result.parameters_json == '{"device_id":"watch-7"}'
    assert result.request_sha256 == body["request_sha256"]
    assert client.deadline_monotonic is not None
    assert client.deadline_monotonic == observed_scope[0][1].deadline_monotonic
    assert observed_scope[0][1].request_sha256 == body["request_sha256"]
    assert observed_scope[0][1].action == "read_state"
    assert observed_scope[0][1].parameters_json == result.parameters_json
    assert observed_scope[0][1].evidence_refs == result.evidence_refs
    assert observed_scope[0][1].action_digest == result.proposal.action_digest

    # Proposal acceptance never bypasses the existing authority boundary.
    denied = authorize_reference(Principal("agent", frozenset()), result.proposal)
    assert denied.decision == "DENY"


def test_missing_or_unverified_evidence_fails_closed():
    missing = request_proposal(
        FakeProposalClient(proposal(evidence_refs=[])), {}, lambda _ref, _scope: True
    )
    forged = request_proposal(
        FakeProposalClient(proposal()), {}, lambda _ref, _scope: False
    )
    assert (missing.decision, missing.reason) == ("DENY", "evidence_required")
    assert (forged.decision, forged.reason) == ("DENY", "evidence_not_verified")
    assert missing.proposal is None and forged.proposal is None


def test_malformed_or_nonfinite_output_fails_closed():
    malformed = request_proposal(
        FakeProposalClient(proposal(extra="authority")), {}, lambda _ref, _scope: True
    )
    nonfinite = request_proposal(
        FakeProposalClient(proposal(confidence=float("nan"))), {}, lambda _ref, _scope: True
    )
    assert malformed.decision == "DENY"
    assert nonfinite.decision == "DENY"
    assert malformed.proposal is None and nonfinite.proposal is None


def test_non_json_parameter_objects_are_not_admitted():
    result = request_proposal(
        FakeProposalClient(proposal(parameters={"device_id": object()})),
        {}, lambda _ref, _scope: True,
    )
    assert result.decision == "DENY"
    assert result.proposal is None


def test_transport_exception_is_not_exposed_or_admitted():
    class FailingClient:
        def propose(self, request, *, deadline_monotonic):
            raise RuntimeError("secret-bearing transport detail")

    result = request_proposal(FailingClient(), {}, lambda _ref, _scope: True)
    assert result.decision == "DENY"
    assert result.reason == "proposal_or_evidence_validation_failed"
    assert result.proposal is None


def test_receipt_from_different_request_action_or_parameters_is_rejected():
    request = {"task": "read"}
    expected_scope = {
        "request_sha256": hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        "action": "read_state",
        "parameters_json": '{"device_id":"watch-7"}',
    }
    mismatches = (
        ("request_sha256", hashlib.sha256(b'{"task":"write"}').hexdigest()),
        ("action", "write_state"),
        ("parameters_json", '{"device_id":"other-watch"}'),
    )

    for field, wrong_value in mismatches:
        receipt_scope = dict(expected_scope)
        receipt_scope[field] = wrong_value

        def verify(ref, scope, receipt_scope=receipt_scope):
            return (
                ref == "glassbox:receipt:123"
                and scope.request_sha256 == receipt_scope["request_sha256"]
                and scope.action == receipt_scope["action"]
                and scope.parameters_json == receipt_scope["parameters_json"]
            )

        result = request_proposal(FakeProposalClient(proposal()), request, verify)

        assert result.decision == "DENY", field
        assert result.reason == "evidence_not_verified", field
        assert result.proposal is None, field


def test_client_deadline_timeout_is_denied_without_exposing_transport_error():
    class TimedOutClient:
        def __init__(self):
            self.deadline = None

        def propose(self, request, *, deadline_monotonic):
            self.deadline = deadline_monotonic
            raise TimeoutError("private endpoint details")

    client = TimedOutClient()
    result = request_proposal(client, {}, lambda _ref, _scope: True)

    assert result.decision == "DENY"
    assert result.reason == "proposal_deadline_exceeded"
    assert result.proposal is None
    assert client.deadline is not None


def test_unbounded_timeout_does_not_call_client():
    class NeverCalledClient:
        def propose(self, request, *, deadline_monotonic):
            raise AssertionError("expired request reached the transport")

    result = request_nemoclaw_proposal(
        NeverCalledClient(),
        {},
        evidence_verifier=lambda _ref, _scope: True,
        timeout_seconds=31.0,
    )

    assert result.decision == "DENY"
    assert result.reason == "invalid_timeout"
    assert result.proposal is None


def test_late_client_response_is_denied():
    class LateClient:
        def propose(self, request, *, deadline_monotonic):
            return proposal()

    original_monotonic = nemoclaw_adapter.time.monotonic
    readings = iter((100.0, 100.0, 100.0, 101.0))
    nemoclaw_adapter.time.monotonic = lambda: next(readings)
    try:
        result = request_nemoclaw_proposal(
            LateClient(),
            {},
            evidence_verifier=lambda _ref, _scope: True,
            timeout_seconds=0.5,
        )
    finally:
        nemoclaw_adapter.time.monotonic = original_monotonic

    assert result.decision == "DENY"
    assert result.reason == "proposal_deadline_exceeded"
    assert result.proposal is None


def test_evidence_verifier_timeout_is_denied():
    def timed_out_verifier(_ref, _scope):
        raise TimeoutError("private evidence store details")

    result = request_proposal(FakeProposalClient(proposal()), {}, timed_out_verifier)

    assert result.decision == "DENY"
    assert result.reason == "evidence_deadline_exceeded"
    assert result.proposal is None
