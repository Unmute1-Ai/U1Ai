from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha3_256
import json, time, uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SENSITIVE = {"payment", "health", "identity", "smart_home", "physical", "official_alert"}
RAW_SENSOR_TYPES = {"raw_audio", "raw_video", "camera_frame", "sensor_stream", "voice_embedding", "face_embedding", "biometric_embedding"}

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def digest(obj) -> str:
    return sha3_256(canonical(obj)).hexdigest()

@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    artifact_digest: str
    issuer: str
    deployment_class: str
    cyber_capability: str = "standard"
    hardware_family: str = "unknown"
    hardware_attestation: str | None = None

@dataclass(frozen=True)
class ComponentManifest:
    component_id: str
    component_digest: str
    issuer: str
    capabilities: tuple[str, ...]
    external_inspector_verdict: str = "unknown"

@dataclass(frozen=True)
class Proposal:
    principal: str
    action: str
    resource: str
    source_domain: str
    target_domain: str
    model_id: str
    model_digest: str
    component_id: str
    consequential: bool = False
    physical: bool = False
    simulated: bool = True
    official_alert: bool = False

class SentinelV3:
    def __init__(self, trusted_issuers: set[str], policy: dict[str, set[str]]):
        self.trusted_issuers = trusted_issuers
        self.policy = policy
        self.models: dict[str, ModelManifest] = {}
        self.components: dict[str, ComponentManifest] = {}
        self.used_credentials: set[str] = set()
        self.receipts: list[dict] = []
        self.receipt_key = Ed25519PrivateKey.generate()
        self.last_receipt_hash = "0" * 64

    def admit_model(self, manifest: ModelManifest, signer: Ed25519PrivateKey, pub: Ed25519PublicKey):
        if manifest.issuer not in self.trusted_issuers:
            raise PermissionError("untrusted_model_issuer")
        sig = signer.sign(canonical(asdict(manifest)))
        pub.verify(sig, canonical(asdict(manifest)))
        if manifest.cyber_capability == "critical" and not manifest.hardware_attestation:
            raise PermissionError("critical_model_requires_hardware_attestation")
        self.models[manifest.model_id] = manifest

    def admit_component(self, manifest: ComponentManifest):
        if manifest.issuer not in self.trusted_issuers:
            raise PermissionError("untrusted_component_issuer")
        forbidden = {"grant_authority", "override_policy", "mint_credentials"}
        if forbidden.intersection(manifest.capabilities):
            raise PermissionError("authority_capability_forbidden")
        self.components[manifest.component_id] = manifest

    def authorize(self, p: Proposal, *, consent: bool = False, agent_identity_verified: bool = False,
                  independent_eval_attested: bool = False, official_issuer_authenticated: bool = False) -> dict:
        model = self.models.get(p.model_id)
        component = self.components.get(p.component_id)
        if not model or model.artifact_digest != p.model_digest:
            return self._deny(p, "model_provenance_mismatch")
        if not component:
            return self._deny(p, "component_not_admitted")
        if model.cyber_capability == "critical" and not independent_eval_attested:
            return self._deny(p, "critical_model_independent_eval_required")
        if p.action not in self.policy.get(p.principal, set()):
            return self._deny(p, "principal_not_authorized")
        if p.source_domain != p.target_domain and p.target_domain in SENSITIVE and not consent:
            return self._deny(p, "explicit_cross_domain_consent_required")
        if p.target_domain == "payment" and not agent_identity_verified:
            return self._deny(p, "verified_agent_identity_required")
        if p.physical and not p.simulated:
            return self._deny(p, "simulation_before_live_required")
        if p.official_alert and not official_issuer_authenticated:
            return self._deny(p, "official_issuer_authentication_required")
        cred = self._mint_credential(p) if p.consequential else None
        return self._receipt(p, "ALLOW", "policy_satisfied", cred)

    def consume(self, credential: str, p: Proposal) -> bool:
        if credential in self.used_credentials:
            return False
        nonce = credential.split(":")[-1]
        expected = sha3_256(canonical({"p": asdict(p), "nonce": nonce})).hexdigest()
        if not credential.startswith(expected + ":"):
            return False
        self.used_credentials.add(credential)
        return True

    def _mint_credential(self, p: Proposal) -> str:
        nonce = uuid.uuid4().hex
        body_hash = sha3_256(canonical({"p": asdict(p), "nonce": nonce})).hexdigest()
        return f"{body_hash}:{nonce}"

    def _deny(self, p: Proposal, reason: str) -> dict:
        return self._receipt(p, "DENY", reason, None)

    def _receipt(self, p: Proposal, decision: str, reason: str, credential: str | None) -> dict:
        body = {"ts": int(time.time()), "proposal": asdict(p), "decision": decision, "reason": reason,
                "credential_issued": credential is not None, "prev": self.last_receipt_hash}
        body_hash = digest(body)
        sig = self.receipt_key.sign(bytes.fromhex(body_hash)).hex()
        rec = {**body, "receipt_hash": body_hash, "signature_ed25519": sig}
        self.receipts.append(rec)
        self.last_receipt_hash = body_hash
        if credential:
            rec["credential"] = credential
        return rec
