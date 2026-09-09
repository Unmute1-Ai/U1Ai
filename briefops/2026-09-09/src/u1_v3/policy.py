from __future__ import annotations
from dataclasses import dataclass
from .security import ScopedCredential

SENSITIVE = {"payment", "health", "smart_home", "physical", "identity"}

@dataclass(frozen=True)
class Decision:
    outcome: str
    reason: str
    credential: ScopedCredential | None = None


def authorize(*, principal: str, source_domain: str, target_domain: str, action: dict,
              consent: bool = False, physical_sim_verified: bool = False,
              official_alert: bool = False, authenticated_issuer: bool = False) -> Decision:
    if official_alert and not authenticated_issuer:
        return Decision("DENY", "official_alert_requires_authenticated_issuer")
    if target_domain == "physical" and action.get("live", False) and not physical_sim_verified:
        return Decision("DENY", "live_physical_effect_requires_simulation_verification")
    if source_domain != target_domain and target_domain in SENSITIVE and not consent:
        return Decision("REQUIRE_CONSENT", "explicit_consent_required")
    cred = ScopedCredential.issue(principal, action)
    return Decision("ALLOW", "authorized", cred)
