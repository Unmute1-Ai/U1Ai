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
    """Validate metadata only. Does NOT verify a signature or device identity."""
    return (
        isinstance(env, DeviceIdentityEnvelope)
        and env.pq_kem == "ML-KEM-768"
        and env.pq_signature == "ML-DSA-65"
        and all(isinstance(v, str) and 0 < len(v) <= 1024
                for v in (env.principal_id, env.device_id, env.device_class))
        and isinstance(env.firmware_digest, str)
        and len(env.firmware_digest) == 64
        and all(c in "0123456789abcdef" for c in env.firmware_digest)
        and isinstance(env.session_nonce, str)
        and 8 <= len(env.session_nonce) <= 256
    )
