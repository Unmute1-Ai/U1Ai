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
