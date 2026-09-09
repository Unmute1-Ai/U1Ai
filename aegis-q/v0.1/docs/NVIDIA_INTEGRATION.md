# NVIDIA Integration Contract

AEGIS-Q is designed for NVIDIA edge deployment but v0.1 does not claim a live
Jetson/cuPQC/TensorRT runtime.

```text
Sensor adapters
   -> CUDA preprocessing
   -> TensorRT AEGIS-Q engine
   -> threat/action proposal
   -> U1 Sentinel
   -> cuPQC-authenticated device/action envelope
   -> simulated effect adapter
```

Hardware target: Jetson Thor.

Required production checks:
- signed model artifact digest
- TensorRT engine digest
- CUDA/cuPQC runtime provenance
- device attestation
- ML-DSA signature verification
- ML-KEM session binding
- one-action credential consumption
