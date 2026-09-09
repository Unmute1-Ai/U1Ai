from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha3_256
import base64, json, time, secrets
from typing import Iterable
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def digest(obj: object) -> str:
    return sha3_256(canonical(obj)).hexdigest()

@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    artifact_digest: str
    issuer: str
    deployment_class: str
    hardware_family: str = "unknown"
    hardware_attestation: str | None = None

    def payload(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class SignedManifest:
    manifest: ModelManifest
    signature_b64: str


def sign_manifest(manifest: ModelManifest, key: Ed25519PrivateKey) -> SignedManifest:
    sig = key.sign(canonical(manifest.payload()))
    return SignedManifest(manifest, base64.b64encode(sig).decode())


def verify_manifest(signed: SignedManifest, key: Ed25519PublicKey, trusted_issuers: Iterable[str], observed_digest: str) -> tuple[bool, str]:
    if signed.manifest.issuer not in set(trusted_issuers):
        return False, "untrusted_model_issuer"
    if signed.manifest.artifact_digest != observed_digest:
        return False, "runtime_model_digest_mismatch"
    try:
        key.verify(base64.b64decode(signed.signature_b64), canonical(signed.manifest.payload()))
    except Exception:
        return False, "invalid_model_signature"
    return True, "model_provenance_verified"

@dataclass(frozen=True)
class Component:
    component_id: str
    digest: str
    issuer: str
    declared_capabilities: tuple[str, ...]
    inspector_verdict: str = "unknown"


def admit_component(component: Component, trusted_issuers: Iterable[str]) -> tuple[bool, str]:
    # Inspector verdict is evidence only. It can never create authority.
    if component.issuer not in set(trusted_issuers):
        return False, "untrusted_component_issuer"
    if any("policy_override" in c or "self_authorize" in c for c in component.declared_capabilities):
        return False, "forbidden_authority_capability"
    if any(ord(ch) in range(0x202A, 0x202F) for ch in component.component_id):
        return False, "hidden_unicode_rejected"
    return True, "component_admitted"

@dataclass
class ScopedCredential:
    token: str
    principal: str
    action_digest: str
    expires_at: float
    consumed: bool = False

    @classmethod
    def issue(cls, principal: str, action: dict, ttl_seconds: int = 60) -> "ScopedCredential":
        return cls(secrets.token_urlsafe(24), principal, digest(action), time.time() + ttl_seconds)

    def consume(self, principal: str, action: dict) -> tuple[bool, str]:
        if self.consumed:
            return False, "credential_replay_detected"
        if time.time() > self.expires_at:
            return False, "credential_expired"
        if principal != self.principal or digest(action) != self.action_digest:
            return False, "credential_scope_mismatch"
        self.consumed = True
        return True, "credential_consumed"

@dataclass(frozen=True)
class Receipt:
    index: int
    previous_hash: str
    event: dict
    event_hash: str
    signature_b64: str

class ReceiptLedger:
    def __init__(self, key: Ed25519PrivateKey):
        self.key = key
        self.public_key = key.public_key()
        self.receipts: list[Receipt] = []

    def append(self, event: dict) -> Receipt:
        prev = self.receipts[-1].event_hash if self.receipts else "GENESIS"
        event_hash = digest({"previous_hash": prev, "event": event})
        sig = self.key.sign(event_hash.encode())
        receipt = Receipt(len(self.receipts) + 1, prev, event, event_hash, base64.b64encode(sig).decode())
        self.receipts.append(receipt)
        return receipt

    def verify(self) -> tuple[bool, str]:
        prev = "GENESIS"
        for r in self.receipts:
            if r.previous_hash != prev:
                return False, "broken_receipt_chain"
            expected = digest({"previous_hash": prev, "event": r.event})
            if expected != r.event_hash:
                return False, "receipt_hash_mismatch"
            try:
                self.public_key.verify(base64.b64decode(r.signature_b64), r.event_hash.encode())
            except Exception:
                return False, "receipt_signature_invalid"
            prev = r.event_hash
        return True, "receipt_chain_valid"
