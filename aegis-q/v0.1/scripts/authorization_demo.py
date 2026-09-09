"""Trusted-host admission demonstration. No effects, network, or real accounts."""
import json
import secrets
import tempfile
from pathlib import Path
from aegis_q.sentinel_bridge import ActionProposal, SentinelStore

with tempfile.TemporaryDirectory() as directory:
    # Demonstration only. A deployed host loads a stable secret from its secret manager.
    admin = secrets.token_urlsafe(32)
    store = SentinelStore(str(Path(directory) / 'authority.db'), admin_key=admin)
    store.grant(admin_key=admin, principal_id='demo-user', action='read_state', resource='demo-device')
    session = store.open_session(admin_key=admin, principal_id='demo-user')
    proposal = store.propose(session=session, proposal=ActionProposal('read_state', 'demo-device', {}, 'advisory-model', .9))
    credential = store.issue_credential(admin_key=admin, session=session, proposal_id=proposal)
    first = store.authorize(session=session, proposal_id=proposal, credential=credential)
    replay = store.authorize(session=session, proposal_id=proposal, credential=credential)
    print(json.dumps({'first': first.decision, 'replay': replay.decision,
                      'execution_status': first.reason, 'effects_enabled': False}))
    assert first.decision == 'ALLOW' and replay.decision == 'DENY'
