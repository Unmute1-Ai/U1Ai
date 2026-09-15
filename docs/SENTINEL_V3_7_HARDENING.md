# Sentinel v3.7 hardening

## Mandatory invariants

1. **Understanding != authority.** Agent reasoning is untrusted proposal text. It never becomes roles, scopes, consent, credentials, grants, or executable privilege.
2. **Exact target binding.** Authorization binds principal + action + resource + domains + parameters using SHA-256. The target digest is revalidated immediately before executor invocation. Production envelopes additionally require Ed25519 authority signature verification.
3. **Fail closed.** Unknown schemas, malformed payloads, missing proofs, invalid signatures, expired envelopes/policies/credentials, target mismatch, and replay are hard denials. There is no best-effort authority fallback.
4. **Receipt-before-completion.** A PREPARED receipt is emitted before executor invocation and binds the execution ID, envelope ID, and authorized target digest. The attempt closes with COMMITTED or ABORTED. Production receipts are SHA3-256 chained and Ed25519 signed.
5. **Offline does not mean ungoverned.** Edge execution requires a locally verifiable signed and unexpired policy. If an action requires online authority and that authority cannot be reached, execution is denied. Telemetry loss never increases authority.

## Authority boundary

Models propose. Authenticated principals authorize. Sentinel verifies. Executors receive only the exact cryptographically bound effect. Models, inspectors, evaluators, and components cannot mint or elevate authority.

## Safety boundary

No destructive action, live physical actuation, financial transaction, health write, or unauthenticated official alert is authorized by this hardening release.
