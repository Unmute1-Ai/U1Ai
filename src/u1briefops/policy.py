from __future__ import annotations

# Sentinel v3.7 hardened policy engine
# Full source is versioned in the release artifact; this repository copy
# establishes the hardened execution invariants for the BriefOps branch.

from dataclasses import dataclass, field
from hashlib import sha256, sha3_256
import json, time
from typing import Any, Mapping

PRIVILEGE_KEYS={"role","roles","scope","scopes","permission","permissions","authority","authorize","credential","credentials","consent","grant","grants","capability_grant"}
RAW_SENSOR_TYPES={"raw_audio","raw_video","camera_frame","face_landmarks","hand_landmarks","biometric_embedding","sensor_stream"}

class SentinelError(Exception): pass
class SchemaError(SentinelError): pass
class EnvelopeError(SentinelError): pass
class ReceiptError(SentinelError): pass

def canonical_json(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha256_digest(v:Any)->str: return "sha256:"+sha256(canonical_json(v)).hexdigest()
def sha3_digest(v:Any)->str: return "sha3-256:"+sha3_256(canonical_json(v)).hexdigest()

@dataclass(frozen=True)
class AgentProposal:
    action:str; resource:str; source_domain:str; target_domain:str
    parameters:Mapping[str,Any]=field(default_factory=dict)
    reasoning:str="" # NEVER authority-bearing

@dataclass(frozen=True)
class ProposedEffect:
    action:str; resource:str; source_domain:str; target_domain:str
    parameters:Mapping[str,Any]=field(default_factory=dict)
    def bound_payload(self,principal_id:str)->dict[str,Any]:
        return {"principal_id":principal_id,"action":self.action,"resource":self.resource,"source_domain":self.source_domain,"target_domain":self.target_domain,"parameters":dict(self.parameters)}

@dataclass(frozen=True)
class Principal:
    principal_id:str; roles:tuple[str,...]; organization_id:str|None=None

@dataclass(frozen=True)
class AuthorizationEnvelope:
    envelope_id:str; schema_version:str; principal_id:str; action_digest_sha256:str
    credential_id:str; issued_at:float; expires_at:float; nonce:str; policy_version:str
    signer_id:str; signature_ed25519:str

@dataclass(frozen=True)
class SignedPolicyBundle:
    policy_id:str; version:str; issued_at:float; expires_at:float; rules_digest:str
    signer_id:str; signature_ed25519:str

@dataclass
class ReceiptLedger:
    previous_hash:str="GENESIS"
    receipts:list[dict[str,Any]]=field(default_factory=list)
    def append(self,event:Mapping[str,Any])->dict[str,Any]:
        payload={"event":dict(event),"previous_hash":self.previous_hash}
        h=sha3_digest(payload)
        r={**payload,"event_hash":h}
        self.receipts.append(r); self.previous_hash=h; return r
    def prepare(self,execution_id:str,envelope_id:str,action_digest_sha256:str):
        return self.append({"phase":"PREPARED","execution_id":execution_id,"envelope_id":envelope_id,"action_digest_sha256":action_digest_sha256,"timestamp":time.time()})
    def commit(self,execution_id:str,prepared_receipt_hash:str,result_digest:str):
        return self.append({"phase":"COMMITTED","execution_id":execution_id,"prepared_receipt_hash":prepared_receipt_hash,"result_digest":result_digest,"timestamp":time.time()})
    def abort(self,execution_id:str,prepared_receipt_hash:str,reason:str):
        return self.append({"phase":"ABORTED","execution_id":execution_id,"prepared_receipt_hash":prepared_receipt_hash,"reason":reason,"timestamp":time.time()})

class SentinelV3:
    @staticmethod
    def proposal_to_effect(p:AgentProposal)->ProposedEffect:
        # Understanding != authority. Never parse reasoning into privileges.
        if PRIVILEGE_KEYS.intersection(p.parameters):
            raise SchemaError("agent_privilege_injection_denied")
        return ProposedEffect(p.action,p.resource,p.source_domain,p.target_domain,dict(p.parameters))
    @staticmethod
    def target_digest(principal:Principal,effect:ProposedEffect)->str:
        return sha256_digest(effect.bound_payload(principal.principal_id))
    @staticmethod
    def verify_target_binding(envelope:AuthorizationEnvelope,principal:Principal,effect:ProposedEffect,now:float|None=None)->bool:
        now=time.time() if now is None else now
        if envelope.schema_version!="sentinel-envelope/v3.7": return False
        if now>=envelope.expires_at: return False
        if envelope.principal_id!=principal.principal_id: return False
        return envelope.action_digest_sha256==SentinelV3.target_digest(principal,effect)
    @staticmethod
    def edge_execution_permitted(*,online:bool,requires_online_authority:bool,policy_verified:bool,policy_expires_at:float,now:float|None=None)->bool:
        now=time.time() if now is None else now
        if not policy_verified or now>=policy_expires_at: return False
        if not online and requires_online_authority: return False
        return True

class BoundExecutor:
    """PREPARE receipt -> verify exact target -> execute -> COMMIT/ABORT."""
    def __init__(self,sentinel:SentinelV3,ledger:ReceiptLedger): self.sentinel=sentinel; self.ledger=ledger
    def execute(self,*,execution_id:str,principal:Principal,effect:ProposedEffect,envelope:AuthorizationEnvelope,executor):
        if not self.sentinel.verify_target_binding(envelope,principal,effect):
            raise EnvelopeError("authorization_envelope_invalid")
        prepared=self.ledger.prepare(execution_id,envelope.envelope_id,envelope.action_digest_sha256)
        try:
            # Revalidate immediately before mutation to prevent TOCTOU substitution.
            if not self.sentinel.verify_target_binding(envelope,principal,effect):
                raise EnvelopeError("target_digest_mismatch")
            result=executor(effect)
            self.ledger.commit(execution_id,prepared["event_hash"],sha3_digest(result))
            return result
        except Exception as exc:
            self.ledger.abort(execution_id,prepared["event_hash"],type(exc).__name__)
            raise
