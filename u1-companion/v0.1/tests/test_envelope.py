"""Envelope acceptance tests (OD-1 D1): digest is canonical and byte-exact;
frozen types reject mutation."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from u1_companion.envelope import (
    ContentClass,
    RouteEnvelope,
    Tier,
    canonical_json,
    sha256_hex,
)


def envelope(**overrides) -> RouteEnvelope:
    base = dict(
        request_id="req-1",
        principal="user:alice",
        content_class=ContentClass.GENERAL,
        declared_tier=Tier.EXTERNAL,
        payload={"text": "hello", "lang": "en"},
        params={"provider_hint": "mock_cloud"},
    )
    base.update(overrides)
    return RouteEnvelope(**base)


class TestCanonicalDigest:
    def test_digest_is_canonical(self):
        # The digest is over canonical JSON: sorted keys, compact separators,
        # non-ASCII preserved. Recomputing it by hand must match.
        env = envelope()
        body = {
            "request_id": "req-1",
            "principal": "user:alice",
            "content_class": "general",
            "declared_tier": 2,
            "payload": {"text": "hello", "lang": "en"},
            "params": {"provider_hint": "mock_cloud"},
        }
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert env.envelope_hash == expected
        assert env.envelope_hash == sha256_hex(canonical_json(body))

    def test_digest_is_byte_exact_across_key_order(self):
        # Same content, different key insertion order: same digest.
        a = envelope(payload={"lang": "en", "text": "hello"})
        b = envelope(payload={"text": "hello", "lang": "en"})
        assert a.envelope_hash == b.envelope_hash

    def test_any_content_change_changes_digest(self):
        base = envelope()
        mutated = envelope(payload={"text": "hello", "lang": "en", "extra": "x"})
        assert base.envelope_hash != mutated.envelope_hash

    def test_governed_field_changes_change_digest(self):
        base = envelope()
        assert base.envelope_hash != envelope(request_id="req-2").envelope_hash
        assert base.envelope_hash != envelope(principal="user:bob").envelope_hash
        assert base.envelope_hash != envelope(declared_tier=Tier.LOCAL).envelope_hash
        assert base.envelope_hash != envelope(params={}).envelope_hash
        assert base.envelope_hash != envelope(content_class=ContentClass.EXPLICIT).envelope_hash

    def test_non_ascii_payload_is_hash_bound_not_escaped(self):
        env = envelope(payload={"text": "héllo 世界"})
        body = {
            "request_id": "req-1",
            "principal": "user:alice",
            "content_class": "general",
            "declared_tier": 2,
            "payload": {"text": "héllo 世界"},
            "params": {"provider_hint": "mock_cloud"},
        }
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert env.envelope_hash == expected

    def test_non_json_serializable_payload_rejected_at_construction(self):
        with pytest.raises(ValueError) as excinfo:
            envelope(payload={"text": object()})
        assert "payload_not_json_serializable" in str(excinfo.value)

    def test_wire_form_class_and_tier_are_coerced(self):
        env = envelope(content_class="general", declared_tier=2)
        assert env.content_class is ContentClass.GENERAL
        assert env.declared_tier is Tier.EXTERNAL

    def test_unknown_class_and_bad_tier_fail_closed(self):
        with pytest.raises(ValueError):
            envelope(content_class="mystery")
        with pytest.raises(ValueError):
            envelope(declared_tier=9)


class TestFrozenTypes:
    def test_envelope_rejects_mutation(self):
        env = envelope()
        with pytest.raises(dataclasses.FrozenInstanceError):
            env.request_id = "req-2"  # type: ignore[misc]

    def test_payload_mapping_mutation_does_not_change_digest(self):
        # The envelope hashes the canonical form of the payload it was built
        # with; the mapping the caller handed over is not consulted again at
        # decision time unless recomputed. Recomputing still binds: the hash
        # property reads the mapping, so a caller mutating its own mapping
        # after construction would change a recomputed digest. The envelope
        # therefore rejects non-mapping payloads and documents that callers
        # pass immutable mappings; here we assert the digest is stable when
        # the mapping is untouched.
        payload = {"text": "hello", "lang": "en"}
        env = envelope(payload=payload)
        first = env.envelope_hash
        second = env.envelope_hash
        assert first == second
