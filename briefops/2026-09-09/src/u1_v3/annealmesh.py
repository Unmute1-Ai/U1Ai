from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class BackendDescriptor:
    backend_id: str
    modality: str
    fabrication_maturity: str
    verified_advantage: bool
    advantage_evidence: str | None
    energy_kwh_per_1k_tasks: float | None = None
    carbon_g_per_kwh: float | None = None
    region: str | None = None
    hybrid_classical_peer: str | None = None
    hardware_family: str | None = None

    def validate(self) -> tuple[bool, str]:
        if self.verified_advantage and not self.advantage_evidence:
            return False, "verified_advantage_requires_evidence"
        if self.fabrication_maturity not in {"lab", "pilot", "foundry-scale", "commercial"}:
            return False, "invalid_fabrication_maturity"
        return True, "backend_descriptor_valid"
