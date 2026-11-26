"""Content-class routing policy: frozen, versioned, hashable, default-deny.

The routing table is data owned by U1Si-Q governance, not code: it is
versioned, validated at construction, and hashable so every receipt can name
the exact policy that produced a decision. Classes absent from the table are
denied — the table can only ever say where content may go, never invent new
places. Policy changes are configuration, not code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from u1_companion.envelope import ContentClass, Tier, canonical_json, sha256_hex


class PolicyValidationError(ValueError):
    """Raised when a policy would not validate at construction.

    A policy that cannot be validated is never stored, hashed, or consulted:
    fail closed at the boundary, not at decision time.
    """


@dataclass(frozen=True)
class ClassRoute:
    """One row of the content-class routing table.

    Attributes:
        content_class: the class this row governs.
        external_allowed: whether the class may leave U1's control at all.
            ``False`` means local/U1-controlled processing only, regardless
            of any provider's willingness.
        floor_tier: the minimum effective tier for the class; a caller's
            declared tier can raise it, never lower it.
    """

    content_class: str
    external_allowed: bool
    floor_tier: Tier


@dataclass(frozen=True)
class ProviderBudget:
    """Cost headroom for one provider, in abstract cost units."""

    provider: str
    max_cost_units: int


@dataclass(frozen=True)
class RoutingPolicy:
    """The deterministic routing policy evaluated before any provider call.

    Frozen and fully hashable (tuple fields only) so it can be hashed for
    audit and passed by value. Unknown content classes deny by construction:
    ``route_for`` returns ``None`` for anything absent from the table.
    """

    version: str
    routes: tuple[ClassRoute, ...] = ()
    blocked_classifications: tuple[str, ...] = ()
    provider_budgets: tuple[ProviderBudget, ...] = ()
    session_budget_units: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise PolicyValidationError("policy_version_empty")
        seen: set[str] = set()
        for route in self.routes:
            if not isinstance(route, ClassRoute):
                raise PolicyValidationError("route_not_class_route")
            # Table keys must be known classes: a policy that names a class
            # outside the governed vocabulary is malformed, not permissive.
            try:
                ContentClass(route.content_class)
            except ValueError as exc:
                raise PolicyValidationError("unknown_content_class_in_table") from exc
            if route.content_class in seen:
                raise PolicyValidationError("duplicate_content_class")
            seen.add(route.content_class)
            if route.floor_tier not in (Tier.LOCAL, Tier.U1_CONTROLLED, Tier.EXTERNAL):
                raise PolicyValidationError("invalid_floor_tier")
            if route.external_allowed and route.floor_tier < Tier.EXTERNAL:
                # A class allowed to leave U1 cannot have a floor below the
                # external tier — that would let a low declaration bypass
                # the external-processing tier.
                raise PolicyValidationError("external_route_floor_below_external")
        for classification in self.blocked_classifications:
            if not isinstance(classification, str) or not classification:
                raise PolicyValidationError("invalid_blocked_classification")
        seen_providers: set[str] = set()
        for budget in self.provider_budgets:
            if not isinstance(budget, ProviderBudget) or not budget.provider:
                raise PolicyValidationError("invalid_provider_budget")
            if budget.provider in seen_providers:
                raise PolicyValidationError("duplicate_provider_budget")
            if budget.max_cost_units < 0:
                raise PolicyValidationError("negative_provider_budget")
            seen_providers.add(budget.provider)
        if self.session_budget_units < 0:
            raise PolicyValidationError("negative_session_budget")

    # -- Lookups (pure, total: every input gets a decision) -----------------

    def route_for(self, content_class: str | ContentClass) -> ClassRoute | None:
        """The table row for ``content_class``, or ``None`` when unknown.

        ``None`` means deny: an unknown class has no permitted route.
        """
        name = content_class.value if isinstance(content_class, ContentClass) else content_class
        for route in self.routes:
            if route.content_class == name:
                return route
        return None

    def egress_decision(self, content_class: str | ContentClass) -> tuple[bool, str | None]:
        """Whether the class may leave U1, with a snake_case reason token on
        denial (``unknown_content_class``, ``egress_blocked_local_only``)."""
        route = self.route_for(content_class)
        if route is None:
            return False, "unknown_content_class"
        if not route.external_allowed:
            return False, "egress_blocked_local_only"
        return True, None

    def effective_tier(self, content_class: str | ContentClass, declared: Tier | int) -> Tier:
        """``max(policy_floor, declared)`` — under-declaring buys nothing."""
        route = self.route_for(content_class)
        if route is None:
            # An unknown class has no floor to max against; the caller gets
            # the highest tier, which the gate (later deliverable) will
            # treat as external-processing tier for a class that can never
            # egress. Denial is the gate's job; the policy never invents a
            # route for an unknown class.
            declared_tier = Tier(int(declared))
            return max(declared_tier, Tier.EXTERNAL)
        return max(route.floor_tier, Tier(int(declared)))

    def provider_budget(self, provider: str) -> ProviderBudget | None:
        for budget in self.provider_budgets:
            if budget.provider == provider:
                return budget
        return None

    # -- Audit --------------------------------------------------------------

    @property
    def policy_hash(self) -> str:
        """SHA-256 over the canonical JSON of the whole policy.

        Receipts carry this hash so "why did this route" is answerable
        against the exact table version that decided it.
        """
        body: dict[str, Any] = {
            "version": self.version,
            "routes": [
                {
                    "content_class": r.content_class,
                    "external_allowed": r.external_allowed,
                    "floor_tier": int(r.floor_tier),
                }
                for r in self.routes
            ],
            "blocked_classifications": list(self.blocked_classifications),
            "provider_budgets": [
                {"provider": b.provider, "max_cost_units": b.max_cost_units}
                for b in self.provider_budgets
            ],
            "session_budget_units": self.session_budget_units,
        }
        return sha256_hex(canonical_json(body))


def build_default_policy() -> RoutingPolicy:
    """The v0.1 content-class routing table (spec §6).

    Mirrors ``configs/u1_companion_v0.1.yaml``, which documents these
    invariants declaratively; there is deliberately no runtime YAML loader
    (repo precedent: config YAML documents invariants, code embeds them).
    """
    return RoutingPolicy(
        version="u1-companion-routing/v0.1",
        routes=(
            # Everyday conversation may use permitted providers, tier-checked.
            ClassRoute(
                content_class=ContentClass.GENERAL.value,
                external_allowed=True,
                floor_tier=Tier.EXTERNAL,
            ),
            # Adult-themed content may go external only with valid,
            # envelope-bound consent; a provider refusal reroutes, it never
            # widens or narrows what U1 permits.
            ClassRoute(
                content_class=ContentClass.ADULT_THEMED.value,
                external_allowed=True,
                floor_tier=Tier.EXTERNAL,
            ),
            # Explicit expression stays on the local/U1-controlled path.
            # Policy denies egress regardless of provider willingness.
            ClassRoute(
                content_class=ContentClass.EXPLICIT.value,
                external_allowed=False,
                floor_tier=Tier.LOCAL,
            ),
        ),
        blocked_classifications=(),
        provider_budgets=(
            ProviderBudget(provider="mock_cloud", max_cost_units=100),
        ),
        session_budget_units=1000,
    )
