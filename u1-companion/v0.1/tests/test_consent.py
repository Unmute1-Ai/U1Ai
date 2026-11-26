"""Consent acceptance tests (OD-1 D2): envelope-bound tokens void on changed
params, single-use nonces, expiry denies, approver tier ceilings enforced,
trusted-service-only issuance."""

from __future__ import annotations

import dataclasses

import pytest

from u1_companion.consent import (
    ConsentIssuanceError,
    ConsentService,
)
from u1_companion.envelope import ContentClass, RouteEnvelope, Tier

KEY = b"test-signing-key"


def envelope(**param_overrides) -> RouteEnvelope:
    params: dict = {"channel": "text"}
    params.update(param_overrides)
    return RouteEnvelope(
        request_id="req-1",
        principal="user:a",
        content_class=ContentClass.ADULT_THEMED,
        declared_tier=Tier.EXTERNAL,
        payload={"text": "hello"},
        params=params,
    )


def service() -> ConsentService:
    svc = ConsentService(signing_key=KEY)
    svc.register_approver("approver:human", max_tier=Tier.EXTERNAL)
    return svc


class TestEnvelopeBinding:
    def test_valid_token_validates(self):
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL)
        assert ok is True
        assert reason is None

    def test_changed_params_void_token(self):
        svc = service()
        token = svc.issue(envelope().envelope_hash, "approver:human", ttl_seconds=300)
        other = envelope(channel="voice")
        assert other.envelope_hash != envelope().envelope_hash
        ok, reason = svc.validate(token, other.envelope_hash, Tier.EXTERNAL)
        assert ok is False
        assert reason == "consent_envelope_mismatch"

    def test_tampered_field_invalidates_signature(self):
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
        forged = dataclasses.replace(token, approver_id="approver:other")
        ok, reason = svc.validate(forged, env.envelope_hash, Tier.EXTERNAL)
        assert ok is False
        assert reason == "consent_invalid_signature"

    def test_forged_signature_rejected(self):
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
        forged = dataclasses.replace(token, signature="0" * 64)
        ok, reason = svc.validate(forged, env.envelope_hash, Tier.EXTERNAL)
        assert ok is False
        assert reason == "consent_invalid_signature"


class TestExpiry:
    def test_expired_token_denied(self):
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=10, now=1000.0)
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL, now=1010.0)
        assert ok is False
        assert reason == "consent_expired"

    def test_boundary_time_is_expired(self):
        # At exactly expires_at the grant is over: no off-by-one grace.
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=10, now=1000.0)
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL, now=1010.0)
        assert ok is False and reason == "consent_expired"


class TestSingleUse:
    def test_nonce_burns_once(self):
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
        ok, reason = svc.consume(token)
        assert (ok, reason) == (True, None)
        ok, reason = svc.consume(token)
        assert ok is False
        assert reason == "consent_nonce_already_used"

    def test_denial_does_not_burn_nonce(self):
        # An expired-token denial must not consume the nonce of a fresh
        # token for the same envelope: denials are not approvals.
        svc = service()
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:human", ttl_seconds=10, now=1000.0)
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL, now=2000.0)
        assert ok is False
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL, now=1000.0)
        assert ok is True and reason is None


class TestTierCeiling:
    def test_approver_ceiling_enforced(self):
        svc = ConsentService(signing_key=KEY)
        svc.register_approver("approver:limited", max_tier=Tier.U1_CONTROLLED)
        env = envelope()
        token = svc.issue(env.envelope_hash, "approver:limited", ttl_seconds=300)
        assert token.max_tier == Tier.U1_CONTROLLED
        ok, reason = svc.validate(token, env.envelope_hash, Tier.EXTERNAL)
        assert ok is False
        assert reason == "consent_approver_tier_insufficient"

    def test_grant_within_ceiling_accepted(self):
        svc = ConsentService(signing_key=KEY)
        svc.register_approver("approver:limited", max_tier=Tier.U1_CONTROLLED)
        env = env_u1_controlled()
        token = svc.issue(env.envelope_hash, "approver:limited", ttl_seconds=300)
        ok, reason = svc.validate(token, env.envelope_hash, Tier.U1_CONTROLLED)
        assert ok is True and reason is None


def env_u1_controlled() -> RouteEnvelope:
    return RouteEnvelope(
        request_id="req-2",
        principal="user:a",
        content_class=ContentClass.ADULT_THEMED,
        declared_tier=Tier.U1_CONTROLLED,
        payload={"text": "hello"},
        params={"channel": "text"},
    )


class TestTrustedIssuanceOnly:
    def test_unregistered_approver_cannot_issue(self):
        svc = ConsentService(signing_key=KEY)
        with pytest.raises(ConsentIssuanceError) as excinfo:
            svc.issue(envelope().envelope_hash, "stranger", ttl_seconds=300)
        assert "approver_not_registered" in str(excinfo.value)

    def test_ttl_out_of_bounds_rejected(self):
        svc = service()
        for bad_ttl in (0, -5, 3601):
            with pytest.raises(ConsentIssuanceError) as excinfo:
                svc.issue(envelope().envelope_hash, "approver:human", ttl_seconds=bad_ttl)
            assert "ttl_out_of_bounds" in str(excinfo.value)

    def test_empty_signing_key_rejected(self):
        with pytest.raises(ConsentIssuanceError):
            ConsentService(signing_key=b"")

    def test_token_is_frozen(self):
        svc = service()
        token = svc.issue(envelope().envelope_hash, "approver:human", ttl_seconds=300)
        with pytest.raises(dataclasses.FrozenInstanceError):
            token.nonce = "forged"  # type: ignore[misc]


def test_non_token_object_fails_closed():
    svc = service()
    ok, reason = svc.validate("not-a-token", envelope().envelope_hash, Tier.EXTERNAL)  # type: ignore[arg-type]
    assert ok is False
    assert reason == "consent_invalid_signature"
