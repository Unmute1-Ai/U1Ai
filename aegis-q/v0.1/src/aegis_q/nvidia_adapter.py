from dataclasses import dataclass

@dataclass(frozen=True)
class NvidiaRuntimeDescriptor:
    platform: str = "Jetson Thor"
    inference_runtime: str = "TensorRT"
    crypto_runtime: str = "cuPQC"
    local_only: bool = True
    runtime_digest_verified: bool = False

    @property
    def admitted(self) -> bool:
        return self.local_only and self.runtime_digest_verified

def build_runtime_plan(desc: NvidiaRuntimeDescriptor) -> dict:
    return {
        "platform": desc.platform,
        "inference_runtime": desc.inference_runtime,
        "crypto_runtime": desc.crypto_runtime,
        "local_only": desc.local_only,
        "runtime_digest_verified": desc.runtime_digest_verified,
        "admitted": desc.admitted,
        "note": "Integration contract only; no claim that NVIDIA runtimes are installed in this reference environment.",
    }
