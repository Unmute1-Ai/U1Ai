from __future__ import annotations
from dataclasses import dataclass

ALLOWED_MODALITIES = {"asl", "aac", "speech", "text", "caption", "gesture", "switch", "haptic", "derived_wrist"}
RAW_KEYS = {"raw_audio", "raw_video", "raw_biometric", "raw_sensor", "frames", "waveform"}

@dataclass(frozen=True)
class NormalizedIntent:
    modality: str
    intent: str
    confidence: float
    raw_retained: bool = False


def normalize(payload: dict) -> NormalizedIntent:
    modality = payload.get("modality")
    if modality not in ALLOWED_MODALITIES:
        raise ValueError("unsupported_modality")
    if any(k in payload for k in RAW_KEYS) or payload.get("retain_raw", False):
        raise ValueError("raw_sensor_retention_denied")
    text = (payload.get("intent") or payload.get("transcript") or "").strip()
    if not text:
        raise ValueError("missing_accessible_intent")
    return NormalizedIntent(modality, text, float(payload.get("confidence", 1.0)), False)
