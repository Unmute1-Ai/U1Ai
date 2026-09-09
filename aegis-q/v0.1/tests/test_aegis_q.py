from aegis_q.core import *
from aegis_q.sentinel_bridge import *
from aegis_q.pqc_identity import *
from aegis_q.nvidia_adapter import *

def test_normal_verified_state():
    f = SensorFrame("glasses","vision",1,True,True,.95)
    assert evaluate_security_state([f]).label == ThreatLabel.NORMAL

def test_unverified_sensor_fails_to_spoofed_state():
    f = SensorFrame("glasses","vision",1,False,True,.95)
    assert evaluate_security_state([f]).label == ThreatLabel.SPOOFED_SENSOR

def test_robot_firmware_mismatch_is_anomaly():
    f = SensorFrame("watch","imu",1,True,True,.9)
    r = RobotState("r1","good","bad",0.2,0.2)
    s = evaluate_security_state([f], r)
    assert s.label == ThreatLabel.ROBOT_ANOMALY
    assert "robot_firmware_digest_mismatch" in s.reasons

def test_robot_motion_deviation_is_anomaly():
    f = SensorFrame("watch","imu",1,True,True,.9)
    r = RobotState("r1","x","x",0.1,1.2)
    assert evaluate_security_state([f], r).label == ThreatLabel.ROBOT_ANOMALY

def test_cross_modal_disagreement_requires_review():
    a = SensorFrame("glasses","vision",1,True,True,.99)
    b = SensorFrame("watch","imu",1,True,True,.30)
    assert "cross_modal_disagreement" in evaluate_security_state([a,b]).reasons

def test_model_swap_does_not_change_authority():
    p = Principal("u", frozenset({"read_state"}))
    a = ActionProposal("read_state","d1","small-model",.5)
    b = ActionProposal("read_state","d1","frontier-model",.99)
    assert authority_vector(p) == authority_vector(p)
    assert authorize_reference(p,a) == authorize_reference(p,b)

def test_model_cannot_invent_robot_authority():
    p = Principal("u", frozenset({"read_state"}))
    a = ActionProposal("physical_actuation","d","frontier-model",1.0)
    assert authorize_reference(p,a).decision == "DENY"

def test_physical_action_requires_exact_credential_and_simulation():
    p = Principal("u", frozenset({"physical_actuation"}))
    a = ActionProposal("physical_actuation","abc","m",.99)
    assert authorize_reference(p,a).reason == "exact_scoped_single_use_credential_required"
    assert authorize_reference(p,a,exact_single_use_credential="abc").reason == "simulation_required_before_live_physical_effect"
    assert authorize_reference(p,a,exact_single_use_credential="abc",verified_simulation=True).decision == "ALLOW"

def test_official_alert_requires_authenticated_authority():
    p = Principal("u", frozenset({"official_emergency_alert"}))
    a = ActionProposal("official_emergency_alert","abc","m",.99)
    assert authorize_reference(p,a,exact_single_use_credential="abc").reason == "authenticated_official_authority_required"

def test_pqc_envelope_commitment_is_deterministic():
    e = DeviceIdentityEnvelope("u","watch-1","wearable","f"*64,"nonce-1234")
    assert verify_reference_envelope(e)
    assert e.sha3_commitment() == e.sha3_commitment()
    assert len(e.sha3_commitment()) == 64

def test_unverified_nvidia_runtime_not_admitted():
    assert NvidiaRuntimeDescriptor(runtime_digest_verified=False).admitted is False

def test_verified_local_nvidia_runtime_admitted():
    assert NvidiaRuntimeDescriptor(runtime_digest_verified=True).admitted is True
