# Production Readiness

AEGIS-Q v0.1.1 hardens the local Sentinel admission boundary. It remains a
no-real-effects reference package. The original v0.1 test evidence did not
establish single-use credentials. This change replaces that implementation and
adds regression evidence; it does not certify the whole system for production.

Implemented and locally tested:
- Immutable canonical stored actions and server-computed digests.
- Trusted administrator issuance, authenticated-host session interface, exact grants.
- Opaque credentials with principal/proposal/scope binding, expiry and revocation.
- Durable atomic credential consumption plus an admission record.
- Concurrency, restart, substitution, revocation and transaction-failure tests.
- Trusted attestation records with proposal binding and expiry/revocation checks.
- Non-finite telemetry rejection and browser/Python motion-threshold parity.
- Exact PQ metadata algorithm validation (not cryptographic verification).
- CI workflow for Python 3.10 and 3.12 with Node-based browser evaluator tests.

Production blockers:
- [ ] Required CI checks pass on the published commit and branch protection is enabled.
- [ ] Real identity provider and reviewer service integrated and tested.
- [ ] Independent simulation and official-authority evidence verification integrated.
- [ ] Domain-specific effect adapters, idempotency and crash reconciliation verified.
- [ ] Host/process isolation, keys, monitoring, audit export and backup recovery reviewed.
- [ ] Target NVIDIA hardware/runtime and model provenance verified.
- [ ] Actual PQ signature verification and device trust roots integrated and reviewed.
- [ ] Independent security review and relevant physical/domain safety acceptance.

Effects remain disconnected. See [authorization operations](aegis-q/v0.1/docs/AUTHORIZATION.md).
