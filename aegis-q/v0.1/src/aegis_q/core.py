from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

class ThreatLabel(str, Enum):
    NORMAL = "NORMAL"
    IDENTITY_DRIFT = "IDENTITY_DRIFT"
    SPOOFED_SENSOR = "SPOOFED_SENSOR"
    ROBOT_ANOMALY = "ROBOT_ANOMALY"
    UNTRUSTED_TOOL = "UNTRUSTED_TOOL"
    NETWORK_ANOMALY = "NETWORK_ANOMALY"
    USER_DISTRESS = "USER_DISTRESS"
    ACCESSIBILITY_INTENT = "ACCESSIBILITY_INTENT"

@dataclass(frozen=True)
class SensorFrame:
    source_id: str
    modality: str
    timestamp_ms: int
    provenance_verified: bool
    integrity_ok: bool
    confidence: float
    features: tuple[float, ...] = ()
    contains_raw_biometric: bool = False

@dataclass(frozen=True)
class RobotState:
    robot_id: str
    expected_firmware_digest: str
    runtime_firmware_digest: str
    commanded_speed_mps: float
    observed_speed_mps: float

@dataclass(frozen=True)
class SecurityState:
    label: ThreatLabel
    risk: float
    reasons: tuple[str, ...]
    proposal: str | None = None

def evaluate_security_state(frames: Iterable[SensorFrame], robot: RobotState | None = None) -> SecurityState:
    reasons = []
    risk = 0.0
    frames = tuple(frames)

    if not frames:
        return SecurityState(ThreatLabel.NETWORK_ANOMALY, 0.80, ("no_sensor_frames",), "quarantine_input_path")
    if any(not f.provenance_verified for f in frames):
        reasons.append("unverified_sensor_provenance")
        risk = max(risk, 0.90)
    if any(not f.integrity_ok for f in frames):
        reasons.append("sensor_integrity_failure")
        risk = max(risk, 0.95)
    if any(f.contains_raw_biometric for f in frames):
        reasons.append("raw_biometric_present")
        risk = max(risk, 0.85)

    modalities = {f.modality for f in frames if f.provenance_verified and f.integrity_ok}
    if len(modalities) >= 2:
        confs = [f.confidence for f in frames]
        if max(confs) - min(confs) > 0.45:
            reasons.append("cross_modal_disagreement")
            risk = max(risk, 0.75)

    if robot:
        if robot.expected_firmware_digest != robot.runtime_firmware_digest:
            reasons.append("robot_firmware_digest_mismatch")
            risk = max(risk, 0.98)
        if abs(robot.commanded_speed_mps - robot.observed_speed_mps) > 0.5:
            reasons.append("robot_motion_deviation")
            risk = max(risk, 0.92)

    if "robot_firmware_digest_mismatch" in reasons or "robot_motion_deviation" in reasons:
        return SecurityState(ThreatLabel.ROBOT_ANOMALY, risk, tuple(reasons), "request_robot_safe_state")
    if "sensor_integrity_failure" in reasons or "unverified_sensor_provenance" in reasons:
        return SecurityState(ThreatLabel.SPOOFED_SENSOR, risk, tuple(reasons), "quarantine_sensor")
    if reasons:
        return SecurityState(ThreatLabel.NETWORK_ANOMALY, risk, tuple(reasons), "require_human_review")
    return SecurityState(ThreatLabel.NORMAL, 0.02, ("verified_local_state",), None)
