# U1 AEGIS-Q v0.1

**Adaptive Embodied Guardian Intelligence & Security — Quantum-Resilient**

AEGIS-Q is an NVIDIA-edge-first embodied security model scaffold for wearables, robots, and local multimodal sensing.

> Model capability can change. Principal authority does not.

## v0.1 goals

- Normalize wearable/robot/sensor telemetry into a local security state.
- Detect suspicious identity, sensor, network, and robot-state conditions.
- Keep AEGIS-Q outputs advisory: threat labels and action proposals only.
- Enforce consequential effects through U1 Sentinel.
- Define a post-quantum device identity envelope targeting ML-KEM / ML-DSA.
- Keep raw biometric/audio/video data local by default.
- Define NVIDIA adapter boundaries for Jetson Thor, TensorRT, CUDA, and cuPQC.

## Safety profile

This reference build performs no real physical actuation, financial transactions,
health-system writes, destructive actions, or official emergency alerts.

The NVIDIA/cuPQC interfaces are integration contracts only. This repository does not claim
a live Jetson, TensorRT, CUDA, or cuPQC runtime.

## Run

```bash
cd aegis-q/v0.1
python -m pip install -e .
pytest -q
python scripts/demo.py
```

## v0.1.1 security update

The folder stays `v0.1` for existing links. Package version is now 0.1.1.
Legacy `authorize_reference` always denies. The replacement `SentinelStore` binds
random credentials to immutable stored proposals and trusted principals, then
atomically records single-use admission. It provides no effect execution.

Install tests with `python -m pip install -e '.[test]'`; Node.js is required for
browser/Python parity tests. Run `python scripts/authorization_demo.py` for a
no-effects admission/replay demonstration. Review [AUTHORIZATION.md](docs/AUTHORIZATION.md)
before integration, especially the host identity, verifier and isolation requirements.

**Production effects remain blocked.** Exact PQ metadata validation is not actual
PQ cryptography; NVIDIA runtime descriptors are not runtime attestations.
