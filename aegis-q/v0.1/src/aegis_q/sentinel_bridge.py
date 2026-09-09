from dataclasses import dataclass
from typing import FrozenSet

CONSEQUENTIAL = frozenset({
    "physical_actuation",
    "financial_transaction",
    "health_system_write",
    "official_emergency_alert",
    "destructive_action",
})

@dataclass(frozen=True)
class Principal:
    principal_id: str
    capabilities: FrozenSet[str]

@dataclass(frozen=True)
class ActionProposal:
    action: str
    action_digest: str
    model_id: str
    confidence: float

@dataclass(frozen=True)
class SentinelDecision:
    decision: str
    reason: str

def authorize_reference(
    principal: Principal,
    proposal: ActionProposal,
    *,
    exact_single_use_credential: str | None = None,
    verified_simulation: bool = False,
    authenticated_official_authority: bool = False,
) -> SentinelDecision:
    if proposal.action not in principal.capabilities:
        return SentinelDecision("DENY", "principal_lacks_capability")

    if proposal.action in CONSEQUENTIAL:
        if exact_single_use_credential != proposal.action_digest:
            return SentinelDecision("DENY", "exact_scoped_single_use_credential_required")

    if proposal.action == "physical_actuation" and not verified_simulation:
        return SentinelDecision("DENY", "simulation_required_before_live_physical_effect")

    if proposal.action == "official_emergency_alert" and not authenticated_official_authority:
        return SentinelDecision("DENY", "authenticated_official_authority_required")

    return SentinelDecision("ALLOW", "authorized_reference_decision")

def authority_vector(principal: Principal) -> tuple[str, tuple[str, ...]]:
    return principal.principal_id, tuple(sorted(principal.capabilities))
