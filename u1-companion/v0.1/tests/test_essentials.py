"""Essentials acceptance tests (OD-1 D3): the no-cloud path — text-first
composition and delivery that never touches a cloud adapter, and never
appends an external receipt."""

from __future__ import annotations

import json

from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.essentials import (
    REASON_INVALID_ESSENTIAL_PAYLOAD,
    EssentialsPath,
    compose_essential_text,
)
from u1_companion.providers.local import PROVIDER_NAME as LOCAL
from u1_companion.receipts import ReceiptWriter, verify_chain


def envelope(
    content_class: ContentClass = ContentClass.EXPLICIT,
    payload: dict | None = None,
) -> RouteEnvelope:
    return RouteEnvelope(
        request_id=f"req-{content_class.value}",
        principal="user:a",
        content_class=content_class,
        declared_tier=Tier.LOCAL,
        payload=payload if payload is not None else {"text": "my own words"},
        params={"channel": "text"},
    )


def read_receipts(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class TestComposition:
    def test_user_words_pass_through_unchanged(self):
        assert compose_essential_text({"text": "my own words"}) == "my own words"

    def test_whitespace_only_payload_has_nothing_deliverable(self):
        assert compose_essential_text({"text": "   "}) is None

    def test_missing_or_wrong_type_has_nothing_deliverable(self):
        assert compose_essential_text({}) is None
        assert compose_essential_text({"text": 7}) is None


class TestDelivery:
    def test_delivers_user_words_on_every_content_class(self):
        # No consent, no gate ceremony, no providers: even explicit content
        # delivers locally, because nothing leaves U1.
        path = EssentialsPath()
        for content_class in (
            ContentClass.GENERAL,
            ContentClass.ADULT_THEMED,
            ContentClass.EXPLICIT,
        ):
            result = path.deliver(envelope(content_class))
            assert result.delivered is True
            assert result.text == "my own words"
            assert result.reason is None

    def test_undeliverable_payload_fails_closed_with_token(self):
        path = EssentialsPath()
        result = path.deliver(envelope(payload={"no_text_here": True}))
        assert result.delivered is False
        assert result.text is None
        assert result.reason == REASON_INVALID_ESSENTIAL_PAYLOAD

    def test_works_with_zero_providers_configured(self):
        # The whole point: expression does not depend on the cloud.
        path = EssentialsPath()
        assert path.deliver(envelope()).delivered is True


class TestReceiptDiscipline:
    def test_no_cloud_path_never_appends_an_external_receipt(self, tmp_path):
        receipts_path = str(tmp_path / "receipts.jsonl")
        writer = ReceiptWriter(receipts_path)
        path = EssentialsPath(receipt_writer=writer)
        path.deliver(envelope(ContentClass.EXPLICIT))
        path.deliver(envelope(payload={}))  # denial is evidence too
        receipts = read_receipts(receipts_path)
        assert len(receipts) == 2
        # Every receipt is a local-route receipt: no external provider is
        # ever named, and cost is always zero.
        for receipt in receipts:
            assert receipt["body"]["route"] == LOCAL
            assert receipt["body"]["cost_units"] == 0
            assert receipt["body"]["unauthorized_effect"] is False
        reasons = {r["body"]["reason"] for r in receipts}
        assert reasons == {None, REASON_INVALID_ESSENTIAL_PAYLOAD}
        assert verify_chain(receipts_path) == (True, None)
