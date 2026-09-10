from dataclasses import dataclass

@dataclass(frozen=True)
class BackendDescriptor:
    backend_id: str
    modality: str
    fabrication_maturity: str
    verified_advantage: bool = False
    evidence_ref: str | None = None
    region: str = "unknown"
    edge_capable: bool = False
    turbulence_model: str | None = None
    qkd_link: bool = False

    def validate(self):
        if self.verified_advantage and not self.evidence_ref:
            raise ValueError("verified_advantage_requires_evidence")
        if self.qkd_link and not self.turbulence_model:
            raise ValueError("qkd_link_requires_time_evolving_channel_model")
        return True
