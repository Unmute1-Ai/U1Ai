from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha3_256
import json
import time
import uuid
from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SENSITIVE_DOMAINS = {"payments", "health", "identity", "smart_home", "physical", "official_alert", "cyber_remediation"}
FORBIDDEN_COMPONENT_CAPS = {"grant_authority", "override_policy", "mint_credentials"}
RAW_SENSOR_TYPES = {"raw_audio", "raw_video", "camera_frame", "face_landmarks", "hand_landmarks", "biometric_embedding", "sensor_stream"}


def canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return "sha3-256:" + sha3_256(canon(value)).hexdigest()


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    artifact_digest: str
    issuer: str
    deployment_class: str
    jurisdiction: str
    hardware_family: str | None = None
    hardware_attestation: str | None = None
    independent_eval_ref: str | None = None


@dataclass(frozen=True)
class ComponentManifest:
    component_id: str
    artifact_digest: str
    capabilities: tuple[str, ...]
    issuer: str


@dataclass(frozen=True)
class Principal:
    principal_id: str
    roles: tuple[str, ...]
    organization_id: str | None = None


@dataclass(frozen=True)
class ProposedEffect:
    action: str
    resource: str
    source_domain: str
    target_domain: str
    data_class: str = "internal"
    official_claim: bool = False
    physical_live: bool = False
    simulated_first: bool = False


@dataclass
class Decision:
    verdict: str
    reason: str
    action_digest: str


@dataclass
class SingleUseCredential:
    credential_id: str
    principal_id: str
    action_digest: str
    expires_at: float
    consumed: bool = False


@dataclass(frozen=True)
class AccessibilityIntent:
    modality: str
    normalized_intent: str
    retained_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnealBackend:
    backend_id: str
    compute_modality: str
    jurisdiction: str
    data_residency: str
    fabrication_maturity: str
    verified_advantage: bool = False
    advantage_evidence_ref: str | None = None
    quantum_memory_access_mode: str | None = None
    quantum_memory_capacity_qubits: int | None = None
    quantum_memory_coherence_ms: float | None = None


@dataclass(frozen=True)
class ThreatSignal:
    signal_type: str
    severity: str
    evidence_ref: str


class SentinelV3:
    def __init__(self, trusted_model_issuers: Iterable[str], trusted_component_issuers: Iterable[str]):
        self.trusted_model_issuers = set(trusted_model_issuers)
        self.trusted_component_issuers = set(trusted_component_issuers)
        self._credentials: dict[str, SingleUseCredential] = {}

    def admit_model(self, manifest: ModelManifest) -> bool:
        if manifest.issuer not in self.trusted_model_issuers:
            return False
        if not manifest.artifact_digest.startswith("sha3-256:"):
            return False
        if manifest.deployment_class == "critical-capability" and not manifest.independent_eval_ref:
            return False
        return True

    def admit_component(self, manifest: ComponentManifest) -> bool:
        if manifest.issuer not in self.trusted_component_issuers:
            return False
        if FORBIDDEN_COMPONENT_CAPS.intersection(manifest.capabilities):
            return False
        return manifest.artifact_digest.startswith("sha3-256:")

    def normalize_accessibility(self, intent: AccessibilityIntent) -> AccessibilityIntent:
        if RAW_SENSOR_TYPES.intersection(intent.retained_types):
            raise ValueError("raw_sensor_retention_denied")
        return intent

    def evaluate(
        self,
        principal: Principal,
        effect: ProposedEffect,
        *,
        model_admitted: bool,
        components_admitted: bool,
        explicit_consent: bool = False,
        agent_identity_verified: bool = False,
        official_issuer_authenticated: bool = False,
        public_sector_scope_verified: bool = False,
        threat_signals: Iterable[ThreatSignal] = (),
    ) -> Decision:
        action_digest = digest(effect.__dict__)
        if not model_admitted or not components_admitted:
            return Decision("DENY", "unadmitted_runtime", action_digest)

        # Threat signals can only reduce authority. They never grant it.
        if any(s.severity == "critical" for s in threat_signals):
            return Decision("DENY", "critical_threat_signal_quarantine", action_digest)

        if effect.source_domain != effect.target_domain and effect.target_domain in SENSITIVE_DOMAINS and not explicit_consent:
            return Decision("DENY", "cross_domain_consent_required", action_digest)

        if effect.target_domain == "payments" and not agent_identity_verified:
            return Decision("DENY", "verified_agent_identity_required", action_digest)

        if effect.target_domain == "cyber_remediation":
            if not public_sector_scope_verified and principal.organization_id:
                return Decision("DENY", "public_sector_scope_verification_required", action_digest)
            if "cyber-operator" not in principal.roles:
                return Decision("DENY", "cyber_operator_role_required", action_digest)

        if effect.official_claim and not official_issuer_authenticated:
            return Decision("DENY", "official_issuer_auth_required", action_digest)

        if effect.physical_live and not effect.simulated_first:
            return Decision("DENY", "simulation_before_live_required", action_digest)

        return Decision("ALLOW", "policy_satisfied", action_digest)

    def issue_single_use_credential(self, decision: Decision, principal: Principal, ttl_s: int = 60) -> SingleUseCredential:
        if decision.verdict != "ALLOW":
            raise ValueError("credential_requires_allow")
        cred = SingleUseCredential(str(uuid.uuid4()), principal.principal_id, decision.action_digest, time.time() + ttl_s)
        self._credentials[cred.credential_id] = cred
        return cred

    def consume(self, credential_id: str, principal: Principal, action_digest: str) -> bool:
        cred = self._credentials.get(credential_id)
        if not cred or cred.consumed or cred.expires_at < time.time():
            return False
        if cred.principal_id != principal.principal_id or cred.action_digest != action_digest:
            return False
        cred.consumed = True
        return True


def validate_backend(backend: AnnealBackend) -> bool:
    if backend.verified_advantage and not backend.advantage_evidence_ref:
        return False
    if backend.compute_modality == "quantum-memory":
        return all([
            backend.quantum_memory_access_mode,
            backend.quantum_memory_capacity_qubits is not None,
            backend.quantum_memory_coherence_ms is not None,
            backend.advantage_evidence_ref,
        ])
    return True


@dataclass
class ReceiptLedger:
    private_key: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)
    previous_hash: str = "GENESIS"
    receipts: list[dict] = field(default_factory=list)

    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    def append(self, event: dict) -> dict:
        payload = {"event": event, "previous_hash": self.previous_hash}
        event_hash = digest(payload)
        signature = self.private_key.sign(canon({"event_hash": event_hash})).hex()
        receipt = {**payload, "event_hash": event_hash, "signature_ed25519": signature}
        self.receipts.append(receipt)
        self.previous_hash = event_hash
        return receipt

    def verify(self) -> bool:
        prev = "GENESIS"
        pub = self.public_key()
        for receipt in self.receipts:
            payload = {"event": receipt["event"], "previous_hash": prev}
            if digest(payload) != receipt["event_hash"]:
                return False
            try:
                pub.verify(bytes.fromhex(receipt["signature_ed25519"]), canon({"event_hash": receipt["event_hash"]}))
            except Exception:
                return False
            prev = receipt["event_hash"]
        return True
