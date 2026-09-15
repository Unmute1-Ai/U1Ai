RAW_TYPES = {"raw_audio", "raw_video", "camera_frame", "sensor_stream", "voice_embedding", "face_embedding", "biometric_embedding"}
SUPPORTED = {"asl", "aac", "speech", "text", "caption", "switch", "gesture", "haptic", "hearing_device"}

def normalize_accessible_intent(modality: str, intent_text: str, *, retain_raw: bool = False, raw_type: str | None = None) -> dict:
    if modality not in SUPPORTED:
        raise ValueError("unsupported_modality")
    if retain_raw or raw_type in RAW_TYPES:
        raise PermissionError("raw_sensor_retention_denied")
    return {"modality": modality, "intent": intent_text.strip(), "raw_retained": False}
