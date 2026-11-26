"""Cost acceptance tests (OD-1 D3): per-provider and session budget
enforcement with receipts. Over budget never fails hard — the route
degrades to local — and every enforcement decision lands on the chain."""

from __future__ import annotations

import json

from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.policy import (
    ClassRoute,
    ProviderBudget,
    RoutingPolicy,
)
from u1_companion.providers.local import PROVIDER_NAME as LOCAL
from u1_companion.providers.mock_cloud import (
    PROVIDER_NAME as MOCK_CLOUD,
    MockCloudAdapter,
    MockCloudConfig,
)
from u1_companion.receipts import ReceiptWriter, verify_chain
from u1_companion.router import Router


def envelope(request_id: str = "req-1") -> RouteEnvelope:
    return RouteEnvelope(
        request_id=request_id,
        principal="user:a",
        content_class=ContentClass.GENERAL,
        declared_tier=Tier.EXTERNAL,
        payload={"text": "hello"},
        params={"channel": "text"},
    )


def policy_with(provider_budget: int, session_budget: int) -> RoutingPolicy:
    return RoutingPolicy(
        version="cost-test/v1",
        routes=(
            ClassRoute(
                content_class=ContentClass.GENERAL.value,
                external_allowed=True,
                floor_tier=Tier.EXTERNAL,
            ),
            ClassRoute(
                content_class=ContentClass.ADULT_THEMED.value,
                external_allowed=True,
                floor_tier=Tier.EXTERNAL,
            ),
            ClassRoute(
                content_class=ContentClass.EXPLICIT.value,
                external_allowed=False,
                floor_tier=Tier.LOCAL,
            ),
        ),
        provider_budgets=(ProviderBudget(provider=MOCK_CLOUD, max_cost_units=provider_budget),),
        session_budget_units=session_budget,
    )


def read_receipts(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class TestProviderBudget:
    def test_provider_budget_enforced_with_receipts(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        # Provider budget of 2 units, 1 unit per call: two cloud calls fit,
        # the third is denied and degrades to local.
        cloud = MockCloudAdapter(MockCloudConfig(cost_per_call=1))
        router = Router(
            policy_with(provider_budget=2, session_budget=1000),
            cloud_adapters={MOCK_CLOUD: cloud},
            receipt_writer=ReceiptWriter(receipts_path),
        )
        results = [router.route(envelope(f"req-{i}")) for i in range(3)]
        assert [r.provider for r in results] == [MOCK_CLOUD, MOCK_CLOUD, LOCAL]
        assert results[-1].delivered is True  # degraded, not failed
        # The denial names the provider that was refused headroom (on the
        # attempt record — a denial receipt's route is null by design: the
        # gate chose nothing) and records zero spend.
        denied_attempt = results[-1].attempts[0]
        assert (denied_attempt.provider, denied_attempt.reason) == (
            MOCK_CLOUD,
            "budget_exhausted",
        )
        receipts = read_receipts(receipts_path)
        denials = [
            r
            for r in receipts
            if r["body"]["decision"] == "DENY" and r["body"]["reason"] == "budget_exhausted"
        ]
        assert len(denials) == 1
        assert denials[0]["body"]["cost_units"] == 0
        assert verify_chain(receipts_path) == (True, None)

    def test_realized_spend_recorded_on_allow_receipts(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        cloud = MockCloudAdapter(MockCloudConfig(cost_per_call=3))
        router = Router(
            policy_with(provider_budget=10, session_budget=1000),
            cloud_adapters={MOCK_CLOUD: cloud},
            receipt_writer=ReceiptWriter(receipts_path),
        )
        router.route(envelope())
        receipts = read_receipts(receipts_path)
        allows = [r for r in receipts if r["body"]["decision"] == "ALLOW"]
        assert allows and all(r["body"]["cost_units"] == 3 for r in allows)


class TestSessionBudget:
    def test_session_budget_spans_providers_and_degrades(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        # Per-provider budget 1, session budget 2, each call bills 1: the
        # first call exhausts cloud_a, the second reroutes to cloud_b, the
        # third exhausts the session and routes local. Delivery never fails.
        cloud_a = MockCloudAdapter(MockCloudConfig(cost_per_call=1))
        cloud_b = MockCloudAdapter(MockCloudConfig(cost_per_call=1))
        router = Router(
            RoutingPolicy(
                version="cost-test-session/v1",
                routes=(
                    ClassRoute(
                        content_class=ContentClass.GENERAL.value,
                        external_allowed=True,
                        floor_tier=Tier.EXTERNAL,
                    ),
                    ClassRoute(
                        content_class=ContentClass.ADULT_THEMED.value,
                        external_allowed=True,
                        floor_tier=Tier.EXTERNAL,
                    ),
                    ClassRoute(
                        content_class=ContentClass.EXPLICIT.value,
                        external_allowed=False,
                        floor_tier=Tier.LOCAL,
                    ),
                ),
                provider_budgets=(
                    ProviderBudget(provider="cloud_a", max_cost_units=1),
                    ProviderBudget(provider="cloud_b", max_cost_units=1),
                ),
                session_budget_units=2,
            ),
            cloud_adapters={"cloud_a": cloud_a, "cloud_b": cloud_b},
            receipt_writer=ReceiptWriter(receipts_path),
        )
        first = router.route(envelope("req-a"))
        second = router.route(envelope("req-b"))
        third = router.route(envelope("req-c"))
        assert (first.provider, second.provider) == ("cloud_a", "cloud_b")
        assert third.provider == LOCAL
        assert third.delivered is True
        assert verify_chain(receipts_path) == (True, None)

    def test_local_delivery_is_free(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        router = Router(
            policy_with(provider_budget=0, session_budget=0),
            cloud_adapters={},
            receipt_writer=ReceiptWriter(receipts_path),
        )
        result = router.route(envelope())
        assert result.delivered is True
        receipts = read_receipts(receipts_path)
        assert all(r["body"]["cost_units"] == 0 for r in receipts)
