"""Router acceptance tests (OD-1 D3): routing decisions per content class.

- ``general`` → mock cloud.
- ``adult_themed`` → consent, then cloud; a provider refusal is an advisory
  rerouting signal, never a block.
- ``explicit`` → local only; no cloud adapter is ever touched.
"""

from __future__ import annotations

import json

from u1_companion.consent import ConsentService
from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.policy import build_default_policy
from u1_companion.providers.local import PROVIDER_NAME as LOCAL
from u1_companion.providers.mock_cloud import (
    PROVIDER_NAME as MOCK_CLOUD,
    MockCloudAdapter,
    MockCloudConfig,
)
from u1_companion.receipts import ReceiptWriter, ReplayStore, verify_chain
from u1_companion.router import Router

SIGNING_KEY = b"router-test-key"


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


def consent_pair(env: RouteEnvelope):
    service = ConsentService(signing_key=SIGNING_KEY)
    service.register_approver("approver:human", max_tier=Tier.EXTERNAL)
    token = service.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
    return service, token


def read_receipts(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class TestPlan:
    def test_general_plan_cloud_then_local(self):
        router = Router(build_default_policy(), cloud_adapters={MOCK_CLOUD: MockCloudAdapter()})
        assert router.route_plan(ContentClass.GENERAL) == (MOCK_CLOUD, LOCAL)

    def test_explicit_plan_is_local_only(self):
        router = Router(build_default_policy(), cloud_adapters={MOCK_CLOUD: MockCloudAdapter()})
        assert router.route_plan(ContentClass.EXPLICIT) == (LOCAL,)


class TestGeneralClass:
    def test_general_routes_to_mock_cloud(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        cloud = MockCloudAdapter()
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: cloud},
            receipt_writer=ReceiptWriter(receipts_path),
        )
        result = router.route(envelope(ContentClass.GENERAL))
        assert result.delivered is True
        assert result.provider == MOCK_CLOUD
        assert result.text == "[mock_cloud] hello"
        assert cloud.calls_made == 1
        # The decision evidence exists and chains.
        assert verify_chain(receipts_path) == (True, None)
        receipts = read_receipts(receipts_path)
        assert any(
            r["body"]["decision"] == "ALLOW" and r["body"]["route"] == MOCK_CLOUD
            for r in receipts
        )


class TestAdultThemedClass:
    def test_consent_then_cloud(self, tmp_path):
        env = envelope(ContentClass.ADULT_THEMED)
        service, token = consent_pair(env)
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: MockCloudAdapter()},
            consent_service=service,
            receipt_writer=ReceiptWriter(str(tmp_path / "receipts.jsonl")),
        )
        result = router.route(env, consent_token=token)
        assert result.delivered is True
        assert result.provider == MOCK_CLOUD

    def test_without_consent_reroutes_local(self, tmp_path):
        env = envelope(ContentClass.ADULT_THEMED)
        cloud = MockCloudAdapter()
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: cloud},
            receipt_writer=ReceiptWriter(str(tmp_path / "receipts.jsonl")),
        )
        result = router.route(env)
        # No consent → the gate denies the external attempt → local delivery.
        assert result.delivered is True
        assert result.provider == LOCAL
        # The cloud adapter was never touched.
        assert cloud.calls_made == 0

    def test_provider_refusal_is_advisory_reroute(self, tmp_path):
        env = envelope(ContentClass.ADULT_THEMED)
        service, token = consent_pair(env)
        receipts_path = str(tmp_path / "receipts.jsonl")
        # The provider's content policy declines adult_themed.
        cloud = MockCloudAdapter(MockCloudConfig(refuse_classes=(ContentClass.ADULT_THEMED.value,)))
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: cloud},
            consent_service=service,
            receipt_writer=ReceiptWriter(receipts_path),
        )
        result = router.route(env, consent_token=token)
        # The refusal reroutes; it never blocks — the user's words still land.
        assert result.delivered is True
        assert result.provider == LOCAL
        assert result.text == env.payload["text"]
        assert cloud.calls_made == 1  # attempted exactly once, then rerouted
        receipts = read_receipts(receipts_path)
        advisory = [r for r in receipts if r["body"]["reason"] == "advisory_refusal"]
        assert len(advisory) == 1
        assert advisory[0]["body"]["route"] == MOCK_CLOUD
        assert advisory[0]["body"]["decision"] == "DENY"
        assert verify_chain(receipts_path) == (True, None)


class TestExplicitClass:
    def test_explicit_routes_local_only(self, tmp_path):
        cloud = MockCloudAdapter()
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: cloud},
            receipt_writer=ReceiptWriter(str(tmp_path / "receipts.jsonl")),
        )
        result = router.route(envelope(ContentClass.EXPLICIT))
        assert result.delivered is True
        assert result.provider == LOCAL
        # A dead cloud must never have been consulted: policy denies egress
        # for explicit content regardless of any provider's willingness.
        assert cloud.calls_made == 0
        receipts = read_receipts(str(tmp_path / "receipts.jsonl"))
        assert receipts
        assert all(r["body"]["route"] == LOCAL for r in receipts)
        assert verify_chain(str(tmp_path / "receipts.jsonl")) == (True, None)


class TestReplayDiscipline:
    def test_successful_route_confirms_replay(self, tmp_path):
        store = ReplayStore(str(tmp_path / "replay.json"))
        writer_path = str(tmp_path / "receipts.jsonl")
        router = Router(
            build_default_policy(),
            cloud_adapters={MOCK_CLOUD: MockCloudAdapter()},
            receipt_writer=ReceiptWriter(writer_path),
            replay_store=store,
        )
        result = router.route(envelope(ContentClass.GENERAL))
        assert result.delivered is True
        # Every consumed receipt was confirmed: nothing left pending.
        assert all(state == "confirmed" for state in store._entries.values())
