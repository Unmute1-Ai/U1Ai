import pytest
from u1briefops.policy import *


def sentinel():
    return SentinelV3({"u1-registry"}, {"u1-components"})


def model(**kw):
    base = dict(model_id="m", artifact_digest="sha3-256:abc", issuer="u1-registry", deployment_class="standard", jurisdiction="US")
    base.update(kw)
    return ModelManifest(**base)


def component(**kw):
    base = dict(component_id="c", artifact_digest="sha3-256:def", capabilities=("read",), issuer="u1-components")
    base.update(kw)
    return ComponentManifest(**base)


def principal(*roles, org=None):
    return Principal("human:1", tuple(roles), org)


def effect(**kw):
    base = dict(action="read", resource="r", source_domain="productivity", target_domain="productivity")
    base.update(kw)
    return ProposedEffect(**base)


def test_signed_model_provenance_required():
    assert sentinel().admit_model(model())
    assert not sentinel().admit_model(model(issuer="unknown"))


def test_critical_model_requires_independent_eval():
    s = sentinel()
    assert not s.admit_model(model(deployment_class="critical-capability"))
    assert s.admit_model(model(deployment_class="critical-capability", independent_eval_ref="eval:2026-09-11"))


def test_component_cannot_grant_authority():
    assert not sentinel().admit_component(component(capabilities=("read", "grant_authority")))


def test_cross_domain_sensitive_transition_requires_consent():
    d = sentinel().evaluate(principal(), effect(target_domain="identity"), model_admitted=True, components_admitted=True)
    assert d.reason == "cross_domain_consent_required"


def test_desktop_agent_payment_requires_identity_and_consent():
    s = sentinel(); p = principal()
    e = effect(target_domain="payments", action="purchase")
    assert s.evaluate(p, e, model_admitted=True, components_admitted=True).verdict == "DENY"
    assert s.evaluate(p, e, model_admitted=True, components_admitted=True, explicit_consent=True).reason == "verified_agent_identity_required"
    assert s.evaluate(p, e, model_admitted=True, components_admitted=True, explicit_consent=True, agent_identity_verified=True).verdict == "ALLOW"


def test_public_sector_cyber_remediation_requires_scope_and_role():
    s = sentinel(); e = effect(target_domain="cyber_remediation", action="isolate-host")
    p = principal("cyber-operator", org="city:nyc")
    assert s.evaluate(p, e, model_admitted=True, components_admitted=True, explicit_consent=True).reason == "public_sector_scope_verification_required"
    assert s.evaluate(p, e, model_admitted=True, components_admitted=True, explicit_consent=True, public_sector_scope_verified=True).verdict == "ALLOW"


def test_threat_signal_can_only_reduce_authority():
    s = sentinel(); sig = ThreatSignal("self_modifying_payload", "critical", "anthropic:2026-09-10")
    d = s.evaluate(principal(), effect(), model_admitted=True, components_admitted=True, threat_signals=[sig])
    assert d.reason == "critical_threat_signal_quarantine"


def test_official_alert_requires_authenticated_issuer():
    s = sentinel(); e = effect(target_domain="official_alert", official_claim=True)
    assert s.evaluate(principal(), e, model_admitted=True, components_admitted=True, explicit_consent=True).reason == "official_issuer_auth_required"


def test_physical_requires_simulation_before_live():
    s = sentinel(); e = effect(target_domain="physical", physical_live=True)
    assert s.evaluate(principal(), e, model_admitted=True, components_admitted=True, explicit_consent=True).reason == "simulation_before_live_required"


def test_raw_sensor_retention_denied():
    s = sentinel()
    with pytest.raises(ValueError):
        s.normalize_accessibility(AccessibilityIntent("speech", "open calendar", ("raw_audio",)))
    assert s.normalize_accessibility(AccessibilityIntent("asl", "open calendar", ())).normalized_intent == "open calendar"


def test_single_use_credential_replay_denied():
    s = sentinel(); p = principal(); d = s.evaluate(p, effect(), model_admitted=True, components_admitted=True)
    c = s.issue_single_use_credential(d, p)
    assert s.consume(c.credential_id, p, d.action_digest)
    assert not s.consume(c.credential_id, p, d.action_digest)


def test_quantum_memory_requires_evidence_and_descriptors():
    bad = AnnealBackend("q", "quantum-memory", "US", "on-prem", "research", quantum_memory_access_mode="random")
    assert not validate_backend(bad)
    good = AnnealBackend("q", "quantum-memory", "US", "on-prem", "research", False, "nature:s41567-026-03418-w", "random", 8, 1.0)
    assert validate_backend(good)


def test_verified_advantage_requires_evidence():
    assert not validate_backend(AnnealBackend("q", "quantum", "US", "local", "prototype", True))


def test_receipt_chain_ed25519_sha3():
    ledger = ReceiptLedger()
    ledger.append({"decision":"DENY","reason":"cross_domain_consent_required"})
    ledger.append({"decision":"ALLOW","reason":"policy_satisfied"})
    assert ledger.verify()
    ledger.receipts[0]["event"]["decision"] = "ALLOW"
    assert not ledger.verify()
