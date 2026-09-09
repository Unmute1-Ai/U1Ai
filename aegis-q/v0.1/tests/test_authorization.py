from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import sqlite3
import pytest
from aegis_q.sentinel_bridge import ActionProposal, SentinelStore

@pytest.fixture
def setup(tmp_path):
    key = secrets.token_urlsafe(32)
    path = str(tmp_path / 'authority.db')
    store = SentinelStore(path, admin_key=key)
    store.grant(admin_key=key, principal_id='alice', action='financial_transaction', resource='sandbox-account')
    session = store.open_session(admin_key=key, principal_id='alice')
    return store, key, session, path


def proposal(store, session, model='m', parameters=None):
    return store.propose(session=session, proposal=ActionProposal('financial_transaction',
        'sandbox-account', {'amount_cents': 10} if parameters is None else parameters, model, .9))


def issue(store, key, session, pid):
    return store.issue_credential(admin_key=key, session=session, proposal_id=pid)


def admit(store, session, pid, credential):
    return store.authorize(session=session, proposal_id=pid, credential=credential)


def test_single_use_and_restart(setup):
    store, key, session, path = setup
    pid = proposal(store, session)
    credential = issue(store, key, session, pid)
    first = admit(store, session, pid, credential)
    assert first.decision == 'ALLOW' and first.reason == 'admitted_no_effect'
    assert json.loads(first.proposal_json)['parameters'] == {'amount_cents': 10}
    restarted = SentinelStore(path, admin_key=key)
    assert admit(restarted, session, pid, credential).decision == 'DENY'
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT status FROM executions').fetchall() == [('ADMITTED_NO_EFFECT',)]
        assert credential not in str(db.execute('SELECT * FROM credentials').fetchall())


def test_concurrent_replay_across_connections(setup):
    store, key, session, path = setup
    pid = proposal(store, session)
    token = issue(store, key, session, pid)
    workers = [SentinelStore(path, admin_key=key) for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda worker: admit(worker, session, pid, token).decision, workers))
    assert results.count('ALLOW') == 1
    assert results.count('DENY') == 11


def test_two_credentials_same_proposal_only_one_admission(setup):
    store, key, session, _ = setup
    pid = proposal(store, session)
    a, b = issue(store, key, session, pid), issue(store, key, session, pid)
    assert admit(store, session, pid, a).decision == 'ALLOW'
    assert admit(store, session, pid, b).decision == 'DENY'
    with pytest.raises(PermissionError):
        issue(store, key, session, pid)


def test_issuer_and_session_cannot_be_forged(setup):
    store, key, session, _ = setup
    pid = proposal(store, session)
    with pytest.raises(PermissionError):
        issue(store, 'not-admin', session, pid)
    with pytest.raises(PermissionError):
        store.open_session(admin_key='not-admin', principal_id='alice')
    with pytest.raises(PermissionError):
        proposal(store, 'alice')
    assert admit(store, session, pid, 'abc').decision == 'DENY'


def test_cross_principal_and_proposal_substitution(setup):
    store, key, session, _ = setup
    pid, other_pid = proposal(store, session), proposal(store, session, parameters={'amount_cents': 999})
    credential = issue(store, key, session, pid)
    other_session = store.open_session(admin_key=key, principal_id='bob')
    assert admit(store, other_session, pid, credential).decision == 'DENY'
    assert admit(store, session, other_pid, credential).decision == 'DENY'
    assert admit(store, session, pid, credential).decision == 'ALLOW'


def test_immutable_snapshot_and_digest_not_credential(setup):
    store, key, session, path = setup
    parameters = {'amount_cents': 10}
    pid = proposal(store, session, parameters=parameters)
    parameters['amount_cents'] = 9000
    with sqlite3.connect(path) as db:
        digest = db.execute('SELECT digest FROM proposals WHERE id=?', (pid,)).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE proposals SET body='{}' WHERE id=?", (pid,))
    assert admit(store, session, pid, digest).decision == 'DENY'
    result = admit(store, session, pid, issue(store, key, session, pid))
    assert json.loads(result.proposal_json)['parameters']['amount_cents'] == 10


@pytest.mark.parametrize('target', ['credential', 'session', 'grant'])
def test_revocation(setup, target):
    store, key, session, _ = setup
    pid = proposal(store, session)
    credential = issue(store, key, session, pid)
    if target == 'credential':
        store.revoke(admin_key=key, credential=credential)
    elif target == 'session':
        store.revoke_session(admin_key=key, session=session)
    else:
        store.revoke_grant(admin_key=key, principal_id='alice', action='financial_transaction', resource='sandbox-account')
    assert admit(store, session, pid, credential).decision == 'DENY'


@pytest.mark.parametrize('target', ['credentials', 'sessions'])
def test_expiry(setup, target):
    store, key, session, path = setup
    pid = proposal(store, session)
    credential = issue(store, key, session, pid)
    with sqlite3.connect(path) as db:
        db.execute(f'UPDATE {target} SET expires=0')
    assert admit(store, session, pid, credential).decision == 'DENY'


@pytest.mark.parametrize('action,kind', [('physical_actuation', 'simulation'), ('official_emergency_alert', 'official_authority')])
def test_attestation_binding_revalidation(setup, action, kind):
    store, key, session, _ = setup
    store.grant(admin_key=key, principal_id='alice', action=action, resource='simulator')
    def propose():
        return store.propose(session=session, proposal=ActionProposal(action, 'simulator', {}, 'm', .9))
    pid, other = propose(), propose()
    with pytest.raises(PermissionError):
        issue(store, key, session, pid)
    with pytest.raises(PermissionError):
        store.record_attestation(admin_key='model', proposal_id=pid, kind=kind, evidence_digest='a'*64)
    attestation = store.record_attestation(admin_key=key, proposal_id=pid, kind=kind, evidence_digest='a'*64)
    with pytest.raises(PermissionError):
        store.issue_credential(admin_key=key, session=session, proposal_id=other, attestation_id=attestation)
    token = store.issue_credential(admin_key=key, session=session, proposal_id=pid, attestation_id=attestation)
    store.revoke(admin_key=key, attestation_id=attestation)
    assert admit(store, session, pid, token).decision == 'DENY'


def test_scope_is_exact_and_model_does_not_grant_authority(setup):
    store, key, session, _ = setup
    for model in ['small', 'frontier']:
        with pytest.raises(PermissionError):
            store.propose(session=session, proposal=ActionProposal('physical_actuation', 'robot', {}, model, 1.0))
        with pytest.raises(PermissionError):
            store.propose(session=session, proposal=ActionProposal('financial_transaction', 'another-account', {}, model, 1.0))
        pid = proposal(store, session, model=model)
        assert admit(store, session, pid, issue(store, key, session, pid)).decision == 'ALLOW'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 1.2, {'x': object()}])
def test_reject_ambiguous_parameters(setup, value):
    store, _, session, _ = setup
    with pytest.raises(ValueError):
        proposal(store, session, parameters={'amount': value})


def test_transaction_rolls_back_consumption_on_record_failure(setup):
    store, key, session, path = setup
    pid = proposal(store, session)
    token = issue(store, key, session, pid)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_record BEFORE INSERT ON executions BEGIN SELECT RAISE(ABORT, 'disk_failure'); END")
    assert admit(store, session, pid, token).decision == 'DENY'
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT consumed FROM credentials').fetchone()[0] == 0
        db.execute('DROP TRIGGER fail_record')
    assert admit(store, session, pid, token).decision == 'ALLOW'


def test_store_rejects_wrong_issuer_on_restart(setup):
    _, _, _, path = setup
    with pytest.raises(PermissionError):
        SentinelStore(path, admin_key=secrets.token_urlsafe(32))


def test_database_permissions(setup):
    import os
    store, key, session, path = setup
    assert os.stat(path).st_mode & 0o777 == 0o600
    os.chmod(path, 0o644)
    with pytest.raises(PermissionError):
        SentinelStore(path, admin_key=key)


@pytest.mark.parametrize('expired', [False, True])
def test_attestation_expiry_and_success(setup, expired):
    store, key, session, path = setup
    store.grant(admin_key=key, principal_id='alice', action='physical_actuation', resource='simulator')
    pid = store.propose(session=session, proposal=ActionProposal('physical_actuation', 'simulator', {}, 'm', .9))
    aid = store.record_attestation(admin_key=key, proposal_id=pid, kind='simulation', evidence_digest='a'*64)
    token = store.issue_credential(admin_key=key, session=session, proposal_id=pid, attestation_id=aid)
    if expired:
        with sqlite3.connect(path) as db:
            db.execute('UPDATE attestations SET expires=0')
    assert admit(store, session, pid, token).decision == ('DENY' if expired else 'ALLOW')


@pytest.mark.parametrize('ttl', [0, -1, float('nan'), float('inf'), 3601, True])
def test_invalid_credential_lifetime(setup, ttl):
    store, key, session, _ = setup
    pid = proposal(store, session)
    with pytest.raises(ValueError):
        store.issue_credential(admin_key=key, session=session, proposal_id=pid, ttl=ttl)


def test_storage_failure_denies(setup):
    store, key, session, path = setup
    pid = proposal(store, session)
    token = issue(store, key, session, pid)
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE credentials')
    assert admit(store, session, pid, token).decision == 'DENY'


def test_parameters_key_order_has_same_digest(setup):
    store, _, session, path = setup
    a = proposal(store, session, parameters={'a':1,'b':2})
    b = proposal(store, session, parameters={'b':2,'a':1})
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT digest FROM proposals WHERE id IN (?,?)', (a,b)).fetchall()
    assert rows[0] == rows[1]
