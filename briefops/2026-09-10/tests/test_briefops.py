import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from u1_briefops import SentinelV3, Proposal, ModelManifest, ComponentManifest, normalize_accessible_intent, BackendDescriptor

@pytest.fixture
def s():
    x=SentinelV3({"u1","lab"},{"user:A":{"read_mail","pay","simulate_move","issue_alert"}})
    k=Ed25519PrivateKey.generate(); pub=k.public_key()
    x.admit_model(ModelManifest("m1","abc","lab","frontier","critical","nvidia-rtx","attested"),k,pub)
    x.admit_component(ComponentManifest("c1","def","u1",("read","propose"),"pass"))
    return x

def P(**kw):
    d=dict(principal="user:A",action="read_mail",resource="r",source_domain="email",target_domain="email",model_id="m1",model_digest="abc",component_id="c1")
    d.update(kw); return Proposal(**d)

def test_signed_model_and_component(s): assert "m1" in s.models and "c1" in s.components
def test_inspector_not_authority():
    x=SentinelV3({"u1"},{})
    with pytest.raises(PermissionError): x.admit_component(ComponentManifest("x","d","evil",("read",),"pass"))
def test_forbidden_component_authority(s):
    with pytest.raises(PermissionError): s.admit_component(ComponentManifest("bad","d","u1",("grant_authority",),"pass"))
def test_digest_tamper_denied(s): assert s.authorize(P(model_digest="zzz"))["decision"]=="DENY"
def test_critical_needs_independent_eval(s): assert s.authorize(P())["reason"]=="critical_model_independent_eval_required"
def test_basic_allow(s): assert s.authorize(P(),independent_eval_attested=True)["decision"]=="ALLOW"
def test_cross_domain_consent(s):
    p=P(action="pay",target_domain="payment",consequential=True)
    assert s.authorize(p,independent_eval_attested=True,agent_identity_verified=True)["decision"]=="DENY"
    assert s.authorize(p,independent_eval_attested=True,agent_identity_verified=True,consent=True)["decision"]=="ALLOW"
def test_payment_agent_identity(s):
    p=P(action="pay",target_domain="payment",consequential=True)
    assert s.authorize(p,independent_eval_attested=True,consent=True)["reason"]=="verified_agent_identity_required"
def test_single_use_replay(s):
    p=P(action="pay",target_domain="payment",consequential=True)
    r=s.authorize(p,independent_eval_attested=True,consent=True,agent_identity_verified=True)
    c=r["credential"]
    assert s.consume(c,p) is True and s.consume(c,p) is False
def test_physical_simulation_first(s):
    p=P(action="simulate_move",target_domain="physical",physical=True,simulated=False)
    assert s.authorize(p,independent_eval_attested=True,consent=True)["reason"]=="simulation_before_live_required"
def test_official_alert_auth(s):
    p=P(action="issue_alert",target_domain="official_alert",official_alert=True)
    assert s.authorize(p,independent_eval_attested=True,consent=True)["reason"]=="official_issuer_authentication_required"
def test_no_raw_sensor_retention():
    with pytest.raises(PermissionError): normalize_accessible_intent("speech","hello",retain_raw=True)
def test_modality_normalization(): assert normalize_accessible_intent("asl","help")["raw_retained"] is False
def test_quantum_advantage_evidence():
    with pytest.raises(ValueError): BackendDescriptor("q","quantum","prototype",True).validate()
def test_qkd_turbulence_model():
    with pytest.raises(ValueError): BackendDescriptor("qkd","quantum-network","research",False,None,qkd_link=True).validate()
def test_qkd_valid(): assert BackendDescriptor("qkd","quantum-network","research",False,None,"orbit",False,"time-evolving-turbulence-v1",True).validate()
def test_receipt_chain(s):
    s.authorize(P(),independent_eval_attested=True); s.authorize(P(model_digest="bad"))
    assert s.receipts[1]["prev"]==s.receipts[0]["receipt_hash"]
