from __future__ import annotations

DELTA_RULES = {
    "google-finland-infrastructure": {
        "targets": ["AnnealMesh", "BriefOps"],
        "change": "Add energy/carbon/region fields to backend descriptors; authority unchanged.",
    },
    "openai-samsung-chip-cooperation": {
        "targets": ["Sentinel", "AuthorityBench"],
        "change": "Record hardware-family/attestation in signed model provenance; hardware identity never grants authority.",
    },
    "cognition-series-e": {
        "targets": ["BriefOps"],
        "change": "No security/product code change. Record funding/competitive signal only.",
    },
    "ibm-quantum-hpc-protein": {
        "targets": ["AnnealMesh", "AuthorityBench"],
        "change": "Add hybrid classical peer and require evidence before marking verified quantum advantage.",
    },
    "google-workspace-voice": {
        "targets": ["OmniSign", "SIGNAL", "PRIMER", "Sentinel"],
        "change": "Normalize voice intent without raw audio retention; consequential cross-domain actions still require Sentinel authorization.",
    },
}


def delta_for(story_id: str) -> dict:
    return DELTA_RULES[story_id]
