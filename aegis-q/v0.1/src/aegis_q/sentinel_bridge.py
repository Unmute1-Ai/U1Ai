"""Durable admission boundary. Run in a trusted process, never inside the model.

The host authenticates identities before administrator-only session issuance.
No effect adapters are provided. An ALLOW is an admission record, not execution.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
import stat
import secrets
import sqlite3
import time
from typing import FrozenSet

CONSEQUENTIAL = frozenset({"physical_actuation", "financial_transaction",
    "health_system_write", "official_emergency_alert", "destructive_action"})
ACTIONS = CONSEQUENTIAL | {"read_state"}
ATTESTATIONS = {"physical_actuation": "simulation", "official_emergency_alert": "official_authority"}

@dataclass(frozen=True)
class Principal:
    principal_id: str
    capabilities: FrozenSet[str]

@dataclass(frozen=True)
class ActionProposal:
    action: str
    resource: str
    parameters: dict
    model_id: str
    confidence: float

@dataclass(frozen=True)
class SentinelDecision:
    decision: str
    reason: str
    execution_id: str | None = None
    proposal_json: str | None = None


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 1024 and not any(ord(c) < 32 for c in value)


def _json_value(value, depth=0):
    # Deliberately restricted JSON profile: integers, strings, booleans, null,
    # lists and string-keyed objects. Use integer physical units (e.g. mm/s).
    # This is versioned Python canonical JSON, not an RFC 8785 implementation.
    if depth > 20:
        raise ValueError("parameters_too_deep")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int and abs(value) <= 2**53 - 1:
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            _json_value(item, depth + 1)
        return
    raise ValueError("unsupported_parameter_type")


def canonical_proposal(proposal):
    if proposal.action not in ACTIONS or not _text(proposal.resource) or not _text(proposal.model_id):
        raise ValueError("invalid_proposal")
    if type(proposal.confidence) not in (int, float) or not math.isfinite(proposal.confidence) or not 0 <= proposal.confidence <= 1:
        raise ValueError("invalid_confidence")
    if type(proposal.parameters) is not dict:
        raise ValueError("parameters_must_be_object")
    _json_value(proposal.parameters)
    # Model identity/confidence are advisory metadata, never authority inputs.
    body = json.dumps({"schema": "sentinel/action/v1", "action": proposal.action,
        "resource": proposal.resource, "parameters": proposal.parameters},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    if len(body.encode()) > 65536:
        raise ValueError("proposal_too_large")
    return body


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class SentinelStore:
    """SQLite authority store for one trusted host on a local durable filesystem.

    Protect the database and administrator key from all model/tool processes.
    Administrator methods are provisioning interfaces, not public endpoints.
    Scope matching is exact against opaque resource IDs; adapters must resolve
    these IDs themselves, never treat them as caller-controlled filesystem paths.
    """
    def __init__(self, path: str, *, admin_key: str):
        if not isinstance(admin_key, str) or len(admin_key) < 43:
            raise ValueError("admin_key_requires_at_least_43_characters_from_a_csprng")
        if str(path) == ":memory:":
            raise ValueError("durable_database_required")
        self.path = str(path)
        self._admin_hash = _hash(admin_key)
        # Local POSIX deployment only: credentials and proposal contents are private.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError:
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PermissionError("authority_database_requires_owner_only_regular_file")
        else:
            os.close(fd)
        with self._tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS grants(principal TEXT, action TEXT, resource TEXT,
                PRIMARY KEY(principal, action, resource));
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, principal TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, principal TEXT NOT NULL,
                body TEXT NOT NULL, digest TEXT NOT NULL, model TEXT NOT NULL, confidence REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS attestations(id TEXT PRIMARY KEY, proposal TEXT NOT NULL,
                principal TEXT NOT NULL, kind TEXT NOT NULL, evidence TEXT NOT NULL,
                expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS credentials(token TEXT PRIMARY KEY, principal TEXT NOT NULL,
                proposal TEXT NOT NULL, digest TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL,
                expires REAL NOT NULL, attestation TEXT, consumed INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0);
            CREATE UNIQUE INDEX IF NOT EXISTS one_consumption_per_proposal
                ON credentials(proposal) WHERE consumed=1;
            CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, proposal TEXT UNIQUE NOT NULL,
                principal TEXT NOT NULL, body TEXT NOT NULL, admitted REAL NOT NULL,
                status TEXT NOT NULL CHECK(status='ADMITTED_NO_EFFECT'));
            CREATE TRIGGER IF NOT EXISTS immutable_proposal_update BEFORE UPDATE ON proposals
                BEGIN SELECT RAISE(ABORT, 'immutable_proposal'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_proposal_delete BEFORE DELETE ON proposals
                BEGIN SELECT RAISE(ABORT, 'immutable_proposal'); END;
            ''')
            # Initialization DDL may commit implicitly; bind the issuer separately.
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT value FROM metadata WHERE key='issuer'").fetchone()
            if existing and not hmac.compare_digest(existing["value"], self._admin_hash):
                raise PermissionError("administrator_key_does_not_match_store")
            db.execute("INSERT OR IGNORE INTO metadata VALUES('issuer',?)", (self._admin_hash,))

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _admin(self, key):
        if not isinstance(key, str) or not hmac.compare_digest(_hash(key), self._admin_hash):
            raise PermissionError("trusted_administrator_required")

    @staticmethod
    def _expiry(ttl):
        if type(ttl) not in (int, float) or not math.isfinite(ttl) or not 0 < ttl <= 3600:
            raise ValueError("ttl_must_be_between_0_and_3600_seconds")
        return time.time() + ttl

    @staticmethod
    def _principal(db, session):
        if not isinstance(session, str) or len(session) > 256:
            raise PermissionError("authenticated_session_required")
        row = db.execute("SELECT principal FROM sessions WHERE token=? AND expires>?",
            (_hash(session), time.time())).fetchone()
        if row is None:
            raise PermissionError("authenticated_session_required")
        return row["principal"]

    @staticmethod
    def _grant(db, principal, body):
        if not db.execute("SELECT 1 FROM grants WHERE principal=? AND action=? AND resource=?",
                (principal, body["action"], body["resource"])).fetchone():
            raise PermissionError("principal_lacks_scoped_capability")

    def grant(self, *, admin_key, principal_id, action, resource):
        self._admin(admin_key)
        if not _text(principal_id) or action not in ACTIONS or not _text(resource):
            raise ValueError("invalid_grant")
        with self._tx() as db:
            db.execute("INSERT OR IGNORE INTO grants VALUES(?,?,?)", (principal_id, action, resource))

    def revoke_grant(self, *, admin_key, principal_id, action, resource):
        self._admin(admin_key)
        with self._tx() as db:
            db.execute("DELETE FROM grants WHERE principal=? AND action=? AND resource=?", (principal_id, action, resource))

    def open_session(self, *, admin_key, principal_id, ttl=300):
        """Host calls only after authenticating principal_id through its IdP."""
        self._admin(admin_key)
        if not _text(principal_id):
            raise ValueError("invalid_principal")
        expires, token = self._expiry(ttl), secrets.token_urlsafe(32)
        with self._tx() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (_hash(token), principal_id, expires))
        return token

    def revoke_session(self, *, admin_key, session):
        self._admin(admin_key)
        with self._tx() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (_hash(session),))

    def propose(self, *, session, proposal):
        body = canonical_proposal(proposal)
        proposal_id = secrets.token_urlsafe(32)
        with self._tx() as db:
            principal = self._principal(db, session)
            self._grant(db, principal, json.loads(body))
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?)", (proposal_id, principal,
                body, _hash(body), proposal.model_id, proposal.confidence))
        return proposal_id

    def record_attestation(self, *, admin_key, proposal_id, kind, evidence_digest, ttl=120):
        """Trusted verifier records evidence after verification, never on model request.

        The host must verify simulator/official-authority evidence independently.
        A digest locates that evidence; this method does not verify it itself.
        """
        self._admin(admin_key)
        if kind not in set(ATTESTATIONS.values()) or not isinstance(evidence_digest, str) or len(evidence_digest) != 64 or any(c not in "0123456789abcdef" for c in evidence_digest):
            raise ValueError("invalid_attestation")
        expiry, identifier = self._expiry(ttl), secrets.token_urlsafe(32)
        with self._tx() as db:
            row = db.execute("SELECT principal,body FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if row is None or ATTESTATIONS.get(json.loads(row["body"])["action"]) != kind:
                raise PermissionError("attestation_proposal_mismatch")
            db.execute("INSERT INTO attestations(id,proposal,principal,kind,evidence,expires) VALUES(?,?,?,?,?,?)",
                (identifier, proposal_id, row["principal"], kind, evidence_digest, expiry))
        return identifier

    @staticmethod
    def _attestation(db, identifier, proposal_id, principal, action):
        kind = ATTESTATIONS.get(action)
        if kind and not db.execute("SELECT 1 FROM attestations WHERE id=? AND proposal=? AND principal=? AND kind=? AND expires>? AND revoked=0",
                (identifier, proposal_id, principal, kind, time.time())).fetchone():
            raise PermissionError("trusted_attestation_required")

    def issue_credential(self, *, admin_key, session, proposal_id, attestation_id=None, ttl=60):
        """Trusted approval service issues only after reviewing the stored proposal."""
        self._admin(admin_key)
        expires, token = self._expiry(ttl), secrets.token_urlsafe(32)
        with self._tx() as db:
            principal = self._principal(db, session)
            row = db.execute("SELECT * FROM proposals WHERE id=? AND principal=?", (proposal_id, principal)).fetchone()
            if row is None:
                raise PermissionError("unknown_owned_proposal")
            body = json.loads(row["body"])
            self._grant(db, principal, body)
            self._attestation(db, attestation_id, proposal_id, principal, body["action"])
            if db.execute("SELECT 1 FROM executions WHERE proposal=?", (proposal_id,)).fetchone():
                raise PermissionError("proposal_already_admitted")
            db.execute("INSERT INTO credentials(token,principal,proposal,digest,action,resource,expires,attestation) VALUES(?,?,?,?,?,?,?,?)",
                (_hash(token), principal, proposal_id, row["digest"], body["action"], body["resource"], expires, attestation_id))
        return token

    def revoke(self, *, admin_key, credential=None, attestation_id=None):
        self._admin(admin_key)
        with self._tx() as db:
            if credential is not None:
                db.execute("UPDATE credentials SET revoked=1 WHERE token=?", (_hash(credential),))
            if attestation_id is not None:
                db.execute("UPDATE attestations SET revoked=1 WHERE id=?", (attestation_id,))

    def authorize(self, *, session, proposal_id, credential):
        """Atomically admit at most once; only the exact persisted body is returned."""
        try:
            if not isinstance(credential, str) or len(credential) > 256 or not isinstance(proposal_id, str):
                raise PermissionError("invalid_credential")
            with self._tx() as db:
                principal = self._principal(db, session)
                row = db.execute("SELECT * FROM proposals WHERE id=? AND principal=?", (proposal_id, principal)).fetchone()
                cred = db.execute("SELECT * FROM credentials WHERE token=?", (_hash(credential),)).fetchone()
                if row is None or cred is None:
                    raise PermissionError("invalid_credential")
                body = json.loads(row["body"])
                if (cred["principal"] != principal or cred["proposal"] != proposal_id or
                    cred["digest"] != _hash(row["body"]) or cred["digest"] != row["digest"] or
                    cred["action"] != body["action"] or cred["resource"] != body["resource"] or
                    cred["expires"] <= time.time() or cred["consumed"] or cred["revoked"]):
                    raise PermissionError("invalid_credential")
                self._grant(db, principal, body)
                self._attestation(db, cred["attestation"], proposal_id, principal, body["action"])
                if db.execute("SELECT 1 FROM executions WHERE proposal=?", (proposal_id,)).fetchone():
                    raise PermissionError("proposal_already_admitted")
                changed = db.execute("UPDATE credentials SET consumed=1 WHERE token=? AND consumed=0 AND revoked=0 AND expires>?",
                    (_hash(credential), time.time())).rowcount
                if changed != 1:
                    raise PermissionError("invalid_credential")
                execution_id = secrets.token_urlsafe(32)
                db.execute("INSERT INTO executions VALUES(?,?,?,?,?,?)", (execution_id,
                    proposal_id, principal, row["body"], time.time(), "ADMITTED_NO_EFFECT"))
                result = SentinelDecision("ALLOW", "admitted_no_effect", execution_id, row["body"])
            return result
        except PermissionError as error:
            return SentinelDecision("DENY", str(error))
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            return SentinelDecision("DENY", "authority_state_unavailable_or_invalid")


def authorize_reference(*args, **kwargs) -> SentinelDecision:
    """Legacy caller-asserted authority API is permanently fail-closed."""
    return SentinelDecision("DENY", "legacy_authorization_disabled_use_trusted_store")


def authority_vector(principal: Principal) -> tuple[str, tuple[str, ...]]:
    return principal.principal_id, tuple(sorted(principal.capabilities))
