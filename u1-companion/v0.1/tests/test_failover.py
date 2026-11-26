"""Failover acceptance tests (OD-1 D3): cloud failure, timeout, and budget
exhaustion degrade to local; zero cloud providers configured → essentials
still deliver text-first communication."""

from __future__ import annotations

from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.essentials import EssentialsPath
from u1_companion.policy import (
    ClassRoute,
    ProviderBudget,
    RoutingPolicy,
    build_default_policy,
)
from u1_companion.providers.local import PROVIDER_NAME as LOCAL
from u1_companion.providers.mock_cloud import (
    PROVIDER_NAME as MOCK_CLOUD,
    MockCloudAdapter,
    MockCloudConfig,
)
from u1_companion.receipts import ReceiptWriter, ReplayStore
from u1_companion.router import Router


def envelope(
    content_class: ContentClass = ContentClass.GENERAL,
    payload: dict | None = None,
) -> RouteEnvelope:
    return RouteEnvelope(
        request_id=f"req-{content_class.value}",
        principal="user:a",
        content_class=content_class,
        declared_tier=Tier.EXTERNAL,
        payload=payload if payload is not None else {"text": "hello"},
        params={"channel": "text"},
    )


def policy_with(provider_budget: int, session_budget: int) -> RoutingPolicy:
    """The v0.1 routing table with explicit cost budgets for the test."""
    return RoutingPolicy(
        version="failover-test/v1",
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


class TestCloudFailure:
    def test_transport_outage_degrades_to_local(self):
        cloud = MockCloudAdapter(MockCloudConfig(fail_first_calls=1))
        router = Router(
            policy_with(provider_budget=100, session_budget=1000),
            cloud_adapters={MOCK_CLOUD: cloud},
        )
        result = router.route(envelope())
        assert result.delivered is True
        assert result.provider == LOCAL
        assert result.text == "hello"
        attempts = [(a.provider, a.outcome, a.reason) for a in result.attempts]
        assert attempts == [
            (MOCK_CLOUD, "failed", "provider_transport_error"),
            (LOCAL, "delivered", None),
        ]

    def test_deadline_exceeded_degrades_to_local(self):
        # Simulated latency (50 ms) far exceeds the attempt budget (10 ms):
        # the deadline fails closed and the route degrades to local.
        cloud = MockCloudAdapter(MockCloudConfig(latency_ms=50))
        router = Router(
            policy_with(provider_budget=100, session_budget=1000),
            cloud_adapters={MOCK_CLOUD: cloud},
            timeout_seconds=0.01,
        )
        result = router.route(envelope())
        assert result.delivered is True
        assert result.provider == LOCAL
        attempts = [(a.provider, a.outcome, a.reason) for a in result.attempts]
        assert attempts == [
            (MOCK_CLOUD, "failed", "deadline_exceeded"),
            (LOCAL, "delivered", None),
        ]

    def test_budget_exhaustion_degrades_to_local(self):
        cloud = MockCloudAdapter()
        router = Router(
            policy_with(provider_budget=0, session_budget=1000),
            cloud_adapters={MOCK_CLOUD: cloud},
        )
        result = router.route(envelope())
        assert result.delivered is True
        assert result.provider == LOCAL
        # Over budget, the cloud is never touched at all.
        assert cloud.calls_made == 0
        attempts = [(a.provider, a.outcome, a.reason) for a in result.attempts]
        assert attempts == [
            (MOCK_CLOUD, "gate_denied", "budget_exhausted"),
            (LOCAL, "delivered", None),
        ]


class TestZeroCloud:
    def test_router_with_no_cloud_adapters_delivers_local(self):
        router = Router(build_default_policy(), cloud_adapters={})
        result = router.route(envelope(ContentClass.GENERAL))
        assert result.delivered is True
        assert result.provider == LOCAL
        assert result.text == "hello"

    def test_essentials_deliver_with_zero_providers_configured(self):
        # No router, no adapters, no policy — essentials work alone.
        path = EssentialsPath()
        env = envelope(
            ContentClass.EXPLICIT,
            payload={"text": "words only I control"},
        )
        result = path.deliver(env)
        assert result.delivered is True
        assert result.text == "words only I control"


class TestReplayCrashRecovery:
    def test_unconfirmed_receipt_demands_fresh_evaluation_which_delivers(self, tmp_path):
        # A transport failure after consume leaves the receipt pending (the
        # interrupted effect's outcome is unknown). The next route call is a
        # fresh evaluation — a new receipt — which delivers via cloud.
        store = ReplayStore(str(tmp_path / "replay.json"))
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: MockCloudAdapter(MockCloudConfig(fail_first_calls=1))},
            receipt_writer=ReceiptWriter(str(tmp_path / "receipts.jsonl")),
            replay_store=store,
        )
        first = router.route(envelope())
        assert first.delivered is True  # degraded to local
        assert any(state == "pending" for state in store._entries.values())
        second = router.route(envelope())
        assert second.delivered is True
        assert second.provider == MOCK_CLOUD
