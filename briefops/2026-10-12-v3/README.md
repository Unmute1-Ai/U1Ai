# U1 BriefOps v3.6 — 2026-10-12

Evidence-linked daily delta using U1 Sentinel v3 as the security baseline.

## Contents

- `briefing.md` — exactly five dated news items with evidence links.
- `update-manifest.json` — per-source and per-component disposition, including explicit no-change records.
- `u1_briefops_v3.py` — pure reference policy helpers for signed provenance, component admission, scoped credentials, modality normalization, AnnealMesh descriptors, and Ed25519/SHA3 receipts.
- `tests/test_u1_briefops_v3.py` — AuthorityBench-style negative and positive policy tests.
- `validate_manifest.py` — manifest/briefing consistency checks.
- `evidence/` — test output and SHA3-256 file digests.

## Run

Python 3.11+ is recommended. Install the test dependency, then run:

```bash
python -m pip install cryptography pytest
python validate_manifest.py
pytest -q
```

This package is a reference policy/evidence delta, not production runtime wiring. It has no network, physical-actuation, financial, health-write, destructive, or emergency-alert adapter. A successful policy decision only returns `AUTHORIZED_FOR_EXTERNAL_AUTHORITY_CHECK_ONLY`; the owning authority/controller must independently authorize and execute any real effect.

**Invariant:** Capability may change. Authority does not. Models, inspectors, evaluators, providers, and components cannot grant themselves authority.
