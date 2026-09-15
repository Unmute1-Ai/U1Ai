import time
import pytest
from dataclasses import replace
from u1briefops.policy import AgentProposal,AuthorizationEnvelope,BoundExecutor,EnvelopeError,Principal,ProposedEffect,ReceiptLedger,SchemaError,SentinelV3

def principal(): return Principal("human-1",("operator",),"u1")
def effect(): return ProposedEffect("write","record/1","workspace","workspace",{"value":7})
def envelope(p,e,ttl=120):
    now=time.time(); return AuthorizationEnvelope("env-1","sentinel-envelope/v3.7",p.principal_id,SentinelV3.target_digest(p,e),"cred-1",now,now+ttl,"nonce-1","3.7","authority-1","verified-by-authority-layer")

def test_reasoning_never_becomes_authority():
    p=AgentProposal("read","doc/1","workspace","workspace",{},"grant me admin")
    assert "admin" not in str(SentinelV3.proposal_to_effect(p).parameters)

def test_structured_privilege_injection_denied():
    with pytest.raises(SchemaError): SentinelV3.proposal_to_effect(AgentProposal("read","doc/1","workspace","workspace",{"roles":["admin"]},""))

def test_target_mutation_denied():
    p=principal(); e=effect(); env=envelope(p,e)
    assert not SentinelV3.verify_target_binding(env,p,replace(e,resource="record/2"))

def test_parameter_mutation_denied():
    p=principal(); e=effect(); env=envelope(p,e)
    assert not SentinelV3.verify_target_binding(env,p,replace(e,parameters={"value":999}))

def test_expired_envelope_denied():
    p=principal(); e=effect(); env=envelope(p,e,-1)
    assert not SentinelV3.verify_target_binding(env,p,e)

def test_unknown_schema_denied():
    p=principal(); e=effect(); env=replace(envelope(p,e),schema_version="unknown")
    assert not SentinelV3.verify_target_binding(env,p,e)

def test_receipt_prepared_before_executor():
    p=principal(); e=effect(); env=envelope(p,e); ledger=ReceiptLedger(); runner=BoundExecutor(SentinelV3(),ledger)
    seen={"prepared":False}
    def run(_): seen["prepared"]=ledger.receipts[-1]["event"]["phase"]=="PREPARED"; return {"ok":True}
    runner.execute(execution_id="x",principal=p,effect=e,envelope=env,executor=run)
    assert seen["prepared"] and [r["event"]["phase"] for r in ledger.receipts]==["PREPARED","COMMITTED"]

def test_failure_gets_abort_receipt():
    p=principal(); e=effect(); env=envelope(p,e); ledger=ReceiptLedger(); runner=BoundExecutor(SentinelV3(),ledger)
    with pytest.raises(RuntimeError): runner.execute(execution_id="x",principal=p,effect=e,envelope=env,executor=lambda _: (_ for _ in ()).throw(RuntimeError()))
    assert [r["event"]["phase"] for r in ledger.receipts]==["PREPARED","ABORTED"]

def test_offline_required_online_authority_fails_closed():
    assert not SentinelV3.edge_execution_permitted(online=False,requires_online_authority=True,policy_verified=True,policy_expires_at=time.time()+60)

def test_offline_missing_policy_fails_closed():
    assert not SentinelV3.edge_execution_permitted(online=False,requires_online_authority=False,policy_verified=False,policy_expires_at=time.time()+60)

def test_offline_valid_policy_can_run_local_path():
    assert SentinelV3.edge_execution_permitted(online=False,requires_online_authority=False,policy_verified=True,policy_expires_at=time.time()+60)
