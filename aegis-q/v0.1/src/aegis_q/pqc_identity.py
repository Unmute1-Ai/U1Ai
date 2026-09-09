from dataclasses import dataclass
import hashlib
import json

@dataclass(frozen=True)
class DeviceIdentityEnvelope:
    principal_id: str
    device_id: str
    device_class: str
    firmware_digest: str
    session_nonce: str
    pq_kem: str = "ML-KEM-768"
    pq_signature: str = "ML-DSA-65"

    def canonical_bytes(self) -> bytes:
        payload = {
            "device_class": self.device_class,
            "device_id": self.device_id,
            "firmware_digest": self.firmware_digest,
            "pq_kem": self.pq_kem,
            "pq_signature": self.pq_signature,
            "principal_id": self.principal_id,
            "session_nonce": self.session_nonce,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def sha3_commitment(self) -> str:
        return hashlib.sha3_256(self.canonical_bytes()).hexdigest()

def verify_reference_envelope(env: DeviceIdentityEnvelope) -> bool:
    return (
        env.pq_kem.startswith("ML-KEM")
        and env.pq_signature.startswith("ML-DSA")
        and len(env.firmware_digest) >= 16
        and len(env.session_nonce) >= 8
    )
