# Production Readiness

U1AI is an umbrella engineering workspace. Each subproject requires its own validation and deployment evidence.

## AEGIS-Q v0.1

**Repository inspection:** the source is present at [aegis-q/v0.1/](aegis-q/v0.1/). This records source availability, not production approval.

Before a production release:

- [ ] Record passing CI for the exact release commit.
- [ ] Validate issuer-controlled, scoped, expiring authorization and atomic single-use enforcement.
- [ ] Publish authorization, replay-prevention, and action-binding test evidence.
- [ ] Test the TensorRT/Jetson runtime on named target hardware.
- [ ] Verify any cuPQC implementation independently; distinguish contracts from working cryptography.
- [ ] Pin model and component artifact provenance and digests.
- [ ] Publish reproducible AuthorityBench-Embodied evidence.
- [ ] Keep physical effects simulated until separately authorized and validated.
- [ ] Verify the deployed demo and publish its supported configuration.
- [ ] Review accessibility, privacy, operational monitoring, and rollback behavior.

Unchecked items identify required evidence; this document does not assert that each item has been tested and failed.

See [AEGIS-Q setup](aegis-q/v0.1/README.md) and [safeguard requirements](Sentinel-Preparedness-and-Quantum-Safeguards.md).

## u1-companion v0.1 (provider adapter layer)

**Repository inspection:** the source is present at [u1-companion/v0.1/](u1-companion/v0.1/), with test evidence in [u1-companion/v0.1/evidence/](u1-companion/v0.1/evidence/) and CI in [.github/workflows/u1-companion.yml](.github/workflows/u1-companion.yml). This records source availability, not production approval.

Before a production release:

- [ ] Record passing CI for the exact release commit.
- [ ] Replace every stub/mock adapter with a reviewed provider transport; no live vendor integration exists in v0.1.
- [ ] Add automated content-class classification; v0.1 relies on caller-declared classes checked against policy floors, with `explicit` local-only by construction.
- [ ] Isolate the receipt writer and replay store (v0.1 is a single-process, single-writer boundary).
- [ ] Move consent issuance to a hardened trusted service with durable approval storage and key management (v0.1 issues in-process only).
- [ ] Publish replay, tamper-visibility, and failover test evidence for the release commit, including negative claims (`external_effects_enabled: false`).
- [ ] Validate provider-refusal handling against real provider behavior: refusals must remain advisory rerouting signals, never authority decisions.
- [ ] Verify per-provider and session budget enforcement under load, and confirm budget exhaustion degrades to local delivery rather than failing the user.
- [ ] Review accessibility, privacy, operational monitoring, and rollback behavior.
