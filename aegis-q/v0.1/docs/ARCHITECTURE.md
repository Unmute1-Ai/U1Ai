# AEGIS-Q Architecture v0.1

## Perception plane
Inputs are local frames from wearable camera, microphone-derived features, IMU,
robot telemetry, network/process telemetry, and authenticated device identity.

Raw camera/audio/biometric material is not needed by the authority layer.

## AEGIS-Q cognition plane
The model predicts:
- security state
- threat class
- confidence
- recommended safe action

It cannot grant capabilities or credentials.

## Post-quantum identity plane
The reference contract targets:
- ML-KEM-768 for session establishment
- ML-DSA-65 for device/action signatures
- SHA3-256 for deterministic commitments

v0.1 contains structural interfaces only. Real cryptographic execution should use an
audited cuPQC integration on supported NVIDIA hardware.

## Authority plane
Every consequential action crosses U1 Sentinel v3.

## NVIDIA target
Primary target:
- Jetson Thor
- TensorRT inference
- CUDA acceleration
- cuPQC post-quantum cryptography

The first trained model should be small enough for local continuous execution, with
larger teacher models used only for offline training/evaluation.
