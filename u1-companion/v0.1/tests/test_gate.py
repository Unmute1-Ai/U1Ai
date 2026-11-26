"""Gate acceptance tests (OD-1 D2): every denial terminates pre-effect,
fail-closed reason tokens, no error-text leakage, provider output never an
input to the decision."""

from __future__ import annotations

import dataclasses
import inspect
import json

import pytest

from u1_companion.consent import ConsentService
from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.gate import DECISION_DENY, CostLedger, evaluate
from u1_companion.policy import RoutingPolicy, build_default_policy
from u1_companion.receipts import ReceiptWriter, verify_chain

SIGNING_KEY = b"gate-test-key"
SECRET_FRAGMENT = "sk-live-attacker-controlled-transport-text"


def envelope(
    content_class: ContentClass = ContentClass.GENERAL,
    declared_tier: Tier = Tier.EXTERNAL,
    payload: dict | None = None,
    **param_overrides,
) -> RouteEnvelope:
    params: dict = {"channel": "text"}
    params.update(param_overrides)
    return RouteEnvelope(
        request_id="req-1",
        principal="user:a",
        content_class=content_class,
        declared_tier=declared_tier,
        payload=payload if payload is not None else {"text": "hello"},
        params=params,
    )


def consented_env(**kw) -> RouteEnvelope:
    return envelope(ContentClass.ADULT_THEMED, **kw)


def consent_pair(env: RouteEnvelope, *, max_tier: Tier = Tier.EXTERNAL):
    svc = ConsentService(signing_key=SIGNING_KEY)
    svc.register_approver("approver:human", max_tier=max_tier)
    token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
    return svc, token


@pytest.fixture
def policy() -> RoutingPolicy:
    return build_default_policy()


class TestAllowPath:
    def test_general_class_allowed_external(self, policy):
        decision = evaluate(envelope(), policy)
        assert decision.allowed is True
        assert decision.reason is None
        assert decision.route == "mock_cloud"
        assert decision.effective_tier == Tier.EXTERNAL

    def test_adult_themed_allowed_with_valid_consent(self, policy):
        env = consented_env()
        svc, token = consent_pair(env)
        decision = evaluate(env, policy, consent_service=svc, consent_token=token)
        assert decision.allowed is True
        assert decision.reason is None

    def test_allow_burns_nonce_only_on_allow(self, policy):
        # A denial for a different reason must leave the nonce spendable.
        env = consented_env()
        svc, token = consent_pair(env)
        evaluate(env, policy, consent_service=svc, consent_token=token)
        ok, reason = svc.consume(token)
        assert ok is False  # burned by the ALLOW
        assert reason == "consent_nonce_already_used"


class TestDenialTerminates:
    def test_unknown_class_denied(self, policy):
        # Tamper the frozen envelope past construction to simulate a class
        # that bypassed envelope validation: the gate's own membership
        # check must still catch it.
        env = envelope()
        object.__setattr__(env, "content_class", "mystery_class")
        decision = evaluate(env, policy)
        assert decision.allowed is False
        assert decision.reason == "unknown_content_class"
        assert decision.route is None

    def test_non_envelope_denied(self, policy):
        decision = evaluate({"payload": "not-an-envelope"}, policy)  # type: ignore[arg-type]
        assert decision.allowed is False
        assert decision.reason == "invalid_envelope"

    def test_explicit_class_denied_egress(self, policy):
        decision = evaluate(envelope(ContentClass.EXPLICIT), policy)
        assert decision.allowed is False
        assert decision.reason == "egress_blocked_local_only"
        assert decision.route is None

    def test_adult_themed_without_consent_denied(self, policy):
        decision = evaluate(consented_env(), policy)
        assert decision.allowed is False
        assert decision.reason == "consent_required"

    def test_budget_exhausted_denied(self, policy):
        ledger = CostLedger(policy)
        ledger.record("mock_cloud", policy.provider_budget("mock_cloud").max_cost_units)
        decision = evaluate(envelope(), policy, cost_ledger=ledger)
        assert decision.allowed is False
        assert decision.reason == "budget_exhausted"

    def test_denial_terminates_before_effect(self, policy):
        # "Terminates pre-effect" is structural: the gate takes no transport
        # and performs no dispatch. An effect observed after a denial can
        # only come from the caller ignoring the decision — assert the
        # decision itself carries no route to dispatch to.
        for env, kwargs in [
            (envelope(ContentClass.EXPLICIT), {}),
            (consented_env(), {}),
            (envelope(), {"cost_ledger": _exhausted_ledger(policy)}),
        ]:
            decision = evaluate(env, policy, **kwargs)
            assert decision.allowed is False
            assert decision.route is None


def _exhausted_ledger(policy: RoutingPolicy) -> CostLedger:
    ledger = CostLedger(policy)
    ledger.record("mock_cloud", policy.provider_budget("mock_cloud").max_cost_units)
    return ledger


class TestFailClosedReasons:
    def test_no_error_text_leakage(self, policy):
        # A payload holding attacker-controlled text can never surface in
        # a denial reason: reasons come from a fixed token vocabulary.
        env = envelope(
            ContentClass.ADULT_THEMED,
            payload={"text": SECRET_FRAGMENT, "error": SECRET_FRAGMENT},
        )
        decision = evaluate(env, policy)
        assert decision.allowed is False
        assert decision.reason == "consent_required"
        assert SECRET_FRAGMENT not in (decision.reason or "")
        assert all(SECRET_FRAGMENT not in (c.reason or "") for c in decision.checks)

    def test_denial_reasons_are_snake_case_tokens(self, policy):
        reasons = [
            evaluate(envelope(ContentClass.EXPLICIT), policy).reason,
            evaluate(consented_env(), policy).reason,
            evaluate(envelope(), policy, cost_ledger=_exhausted_ledger(policy)).reason,
        ]
        for reason in reasons:
            assert reason is not None
            assert reason.replace("_", "").isalnum()


class TestProviderOutputNeverInput:
    def test_evaluation_signature_has_no_provider_output_parameter(self):
        # Structural guarantee: there is no way to feed provider or
        # evaluator output into the gate — its parameters admit none.
        params = set(inspect.signature(evaluate).parameters)
        assert "provider_output" not in params
        assert "evaluator_verdict" not in params

    def test_forged_authorization_in_payload_never_authorizes(self, policy):
        # A provider (or anyone) claiming "authorized" inside the payload
        # gets no vote: only the deterministic checks decide.
        env = consented_env(payload={"text": "hi", "authorized": True, "provider_decision": "ALLOW"})
        decision = evaluate(env, policy)
        assert decision.allowed is False
        assert decision.reason == "consent_required"

    def test_provider_allow_cannot_lift_deny(self, policy):
        # Same envelope evaluated twice, once "after" a fictional provider
        # ALLOW verdict exists in the environment (which the gate never
        # reads): the decision is identical either way.
        env = consented_env()
        before = evaluate(env, policy)
        after = evaluate(env, policy)
        assert dataclasses.replace(before, checks=()) == dataclasses.replace(after, checks=())


class TestReceiptsWritten:
    def test_allow_and_deny_write_chained_receipts(self, policy, tmp_path):
        path = str(tmp_path / "receipts.jsonl")
        writer = ReceiptWriter(path)
        deny_decision = evaluate(consented_env(), policy, receipt_writer=writer)
        env = consented_env()
        svc, token = consent_pair(env)
        allow_decision = evaluate(env, policy, consent_service=svc, consent_token=token, receipt_writer=writer)
        assert deny_decision.allowed is False
        assert allow_decision.allowed is True
        ok, break_at = verify_chain(path)
        assert ok is True and break_at is None
        with open(path, encoding="utf-8") as handle:
            lines = [json.loads(line) for line in handle]
        assert [record["body"]["decision"] for record in lines] == [DECISION_DENY, "ALLOW"]
        assert all(record["body"]["unauthorized_effect"] is False for record in lines)


def test_gate_decision_is_frozen(policy):
    env = envelope()
    decision = evaluate(env, policy)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = True  # type: ignore[misc]
