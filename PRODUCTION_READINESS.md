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
