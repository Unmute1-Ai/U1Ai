# Sentinel durable authorization — v0.1.1

Status: hardened local admission library; no effect adapters. This release is not a
production certification of AEGIS-Q or its NVIDIA/PQ integrations.

## Trust boundary

Run SentinelStore in a dedicated trusted host process under a separate OS account
from models, tools and browsers. Only that host may read the database or the
administrator key. Python object encapsulation is not a sandbox. Giving arbitrary
model code access to the host process, its files, or its environment defeats this
boundary. Do not expose grant, open_session, record_attestation or issue_credential
as unauthenticated model tools or HTTP routes.

The host must authenticate a user using its real identity provider before calling
open_session. Principal strings in requests are not authentication. The resulting
opaque session is a bearer secret; the host should retain it server-side and must
not give it to the model. Keep sessions and credentials out of logs and URLs.

A separately trusted reviewer calls issue_credential with the exact persisted
proposal ID after approving its complete contents. Possession of a session or an
action digest cannot issue a credential. Admin key possession authorizes control
plane operations; distribute it only to the trusted service, never end users.

## Admission protocol

1. Configure exact principal/action/resource grants with the administrator key.
2. Establish a session after external identity verification (maximum one hour).
3. propose validates, canonicalizes and snapshots the action, opaque resource ID,
   and parameters. The host computes SHA-256. SQL triggers reject proposal edits.
4. Physical proposals require a simulation attestation; official alerts require
   an official-authority attestation. A trusted verifier must independently check
   evidence before recording it. The store binds the opaque attestation ID to the
   principal and proposal, with expiry and revocation. Recording an evidence hash
   does not itself verify simulator output or government authority.
5. Trusted approval issues a random 256-bit credential scoped to the exact stored
   proposal, principal, action and resource. Only its hash is stored.
6. authorize resolves trusted state, rechecks the grant/session/attestation and
   credential expiry, then atomically consumes the credential and writes an
   ADMITTED_NO_EFFECT record using BEGIN IMMEDIATE. At most one admission is
   permitted per proposal, even if the issuer minted multiple credentials.
7. The return value includes the exact stored JSON and execution ID. No adapter is
   called. ALLOW means admission only; it is not a portable execution token.

All actions, including read_state, now require a trusted credential. The legacy
caller-asserted authorize_reference API always returns DENY. ActionProposal no
longer accepts action_digest. Neither model_id nor confidence grants authority.

## Canonicalization contract

sentinel/action/v1 uses sorted ASCII-escaped compact JSON. Parameters support
string-keyed objects, lists, strings, booleans, null and integers bounded by
2^53-1; use explicit integer units such as amount_cents or speed_mm_per_second.
Floats, arbitrary objects, excessive depth and payloads over 64 KiB are rejected.
This deliberately restricted profile is not advertised as RFC 8785. Action schemas
and domain limits still belong to a reviewed host/adapter integration. Resources
are opaque exact IDs, not paths, globs, URLs or patterns to expand at execution.

## Storage and recovery

Supported deployment: a POSIX host with a private directory (0700), a local durable
SQLite database (0600) and reliable locking/fsync. Keep the administrator key stable
in the host secret manager. The database binds to its hash; another key cannot
reopen it through the library. Do not put the DB on NFS or share it across hosts.
Protect directory ownership and avoid untrusted symlinks. Do not let tools change
the clock, database, backup, schema or permissions. Expiry uses the host wall clock.
There is no automatic key rotation endpoint in this release.

Consumption and the admission record commit together. A failed transaction denies
and rolls back both. An uncertain outcome must be reconciled by trusted operators
against the durable execution record; do not mint a replacement and execute again.
Restoring an older database can resurrect unused credentials: invalidate sessions
and credentials before restarting any restored instance. DB loss, stale backups,
clock rollback, or restoring disk snapshots requires operator recovery, not a
fail-open fallback. Admission records are local records, not tamper-proof receipts.

Future effect execution requires an authenticated dispatcher that loads stored
proposals and checks its durable execution state, plus adapter idempotency keyed
by execution ID, crash reconciliation, domain validation, resource version checks,
and independently verified safety controls. Do not execute returned JSON in a
browser or caller-selected tool. No exactly-once external-effect guarantee is made.

## Release gates remaining

- Integrate and test the real identity provider and trusted reviewer service.
- Integrate independent simulation/official-authority evidence verifiers.
- Validate adapter-specific parameter bounds and current resource state.
- Implement dispatcher, idempotency, audit export, monitoring and recovery drills.
- Independently review the host isolation and operational key management.
- Implement actual PQ signature verification and trusted device-key provenance.
- Verify NVIDIA runtime/model artifacts and target hardware behavior.

The PQ envelope function validates exact metadata identifiers only (ML-KEM-768 and
ML-DSA-65). A SHA3 commitment is not a signature and does not authenticate a device.
NVIDIA runtime descriptors and sensor provenance booleans remain advisory fixture
inputs, not authenticated evidence. They must never be treated as authorization.
