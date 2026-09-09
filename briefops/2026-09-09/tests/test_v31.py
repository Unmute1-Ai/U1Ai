from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from u1_v3.security import ModelManifest, sign_manifest, verify_manifest, Component, admit_component, ReceiptLedger
from u1_v3.policy import authorize
from u1_v3.accessibility import normalize
from u1_v3.annealmesh import BackendDescriptor
from u1_v3.briefops import delta_for


def test_model_provenance_valid():
    k=Ed25519PrivateKey.generate(); m=ModelManifest("m","abc","u1","edge","samsung-nextgen","attested")
    s=sign_manifest(m,k); assert verify_manifest(s,k.public_key(),{"u1"},"abc")[0]

def test_model_digest_tamper_denied():
    k=Ed25519PrivateKey.generate(); m=ModelManifest("m","abc","u1","edge")
    s=sign_manifest(m,k); assert verify_manifest(s,k.public_key(),{"u1"},"xyz")[1]=="runtime_model_digest_mismatch"

def test_hardware_never_grants_authority():
    d=authorize(principal="p",source_domain="email",target_domain="payment",action={"op":"pay"},consent=False)
    assert d.outcome=="REQUIRE_CONSENT"

def test_component_inspector_is_not_authority():
    c=Component("tool","d","evil",("read",),"PASS")
    assert admit_component(c,{"u1"})[0] is False

def test_policy_override_component_denied():
    c=Component("tool","d","u1",("policy_override",),"PASS")
    assert admit_component(c,{"u1"})[1]=="forbidden_authority_capability"

def test_voice_normalization_drops_raw_by_rejection():
    n=normalize({"modality":"speech","transcript":"open captions","confidence":.9})
    assert n.intent=="open captions" and not n.raw_retained

def test_raw_audio_retention_denied():
    try: normalize({"modality":"speech","transcript":"x","raw_audio":"bytes"})
    except ValueError as e: assert str(e)=="raw_sensor_retention_denied"
    else: raise AssertionError

def test_live_physical_requires_simulation():
    d=authorize(principal="p",source_domain="text",target_domain="physical",action={"live":True},consent=True,physical_sim_verified=False)
    assert d.outcome=="DENY"

def test_single_use_credential_replay_denied():
    a={"op":"caption.render"}; d=authorize(principal="p",source_domain="text",target_domain="text",action=a)
    assert d.credential.consume("p",a)[0]
    assert d.credential.consume("p",a)[1]=="credential_replay_detected"

def test_quantum_advantage_requires_evidence():
    b=BackendDescriptor("q","quantum-hpc","pilot",True,None,hybrid_classical_peer="Fugaku")
    assert b.validate()[1]=="verified_advantage_requires_evidence"

def test_energy_descriptor_valid():
    b=BackendDescriptor("fi-edge","gpu","commercial",False,None,1.2,45.0,"FI")
    assert b.validate()[0]

def test_receipt_chain_ed25519_sha3():
    l=ReceiptLedger(Ed25519PrivateKey.generate()); l.append({"decision":"ALLOW"}); l.append({"decision":"DENY"})
    assert l.verify()==(True,"receipt_chain_valid")

def test_funding_signal_no_authority_change():
    d=delta_for("cognition-series-e")
    assert "No security/product code change" in d["change"]
