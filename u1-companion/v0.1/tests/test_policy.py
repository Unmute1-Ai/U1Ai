"""Policy acceptance tests (OD-1 D1): construction validation, default-deny
for unknown classes, tier = max(policy, declared), explicit egress denied."""

from __future__ import annotations

import dataclasses

import pytest

from u1_companion.envelope import ContentClass, Tier
from u1_companion.policy import (
    ClassRoute,
    PolicyValidationError,
    ProviderBudget,
    RoutingPolicy,
    build_default_policy,
)


def policy(**overrides) -> RoutingPolicy:
    base = dict(
        version="test-routing/v1",
        routes=(
            ClassRoute(
                content_class=ContentClass.GENERAL.value,
                external_allowed=True,
                floor_tier=Tier.EXTERNAL,
            ),
            ClassRoute(
                content_class=ContentClass.EXPLICIT.value,
                external_allowed=False,
                floor_tier=Tier.LOCAL,
            ),
        ),
    )
    base.update(overrides)
    return RoutingPolicy(**base)


class TestConstructionValidation:
    def test_empty_version_rejected(self):
        with pytest.raises(PolicyValidationError) as excinfo:
            policy(version="")
        assert "policy_version_empty" in str(excinfo.value)

    def test_non_string_version_rejected(self):
        with pytest.raises(PolicyValidationError):
            policy(version=123)  # type: ignore[arg-type]

    def test_unknown_class_in_table_rejected(self):
        with pytest.raises(PolicyValidationError) as excinfo:
            policy(
                routes=(
                    ClassRoute(
                        content_class="mystery", external_allowed=True, floor_tier=Tier.EXTERNAL
                    ),
                )
            )
        assert "unknown_content_class_in_table" in str(excinfo.value)

    def test_duplicate_class_in_table_rejected(self):
        route = ClassRoute(
            content_class=ContentClass.GENERAL.value,
            external_allowed=True,
            floor_tier=Tier.EXTERNAL,
        )
        with pytest.raises(PolicyValidationError):
            policy(routes=(route, route))

    def test_external_route_with_local_floor_rejected(self):
        # A class allowed to egress cannot carry a floor below the external
        # tier; that would let a low declaration bypass external processing.
        with pytest.raises(PolicyValidationError):
            policy(
                routes=(
                    ClassRoute(
                        content_class=ContentClass.GENERAL.value,
                        external_allowed=True,
                        floor_tier=Tier.LOCAL,
                    ),
                )
            )

    def test_negative_budget_rejected(self):
        with pytest.raises(PolicyValidationError):
            policy(provider_budgets=(ProviderBudget(provider="p", max_cost_units=-1),))
        with pytest.raises(PolicyValidationError):
            policy(session_budget_units=-1)

    def test_policy_is_hashable_and_frozen(self):
        pol = policy()
        assert hash(pol) == hash(policy())
        assert pol.policy_hash == policy().policy_hash
        with pytest.raises(dataclasses.FrozenInstanceError):
            pol.version = "other"  # type: ignore[misc]

    def test_policy_hash_changes_with_table(self):
        pol = policy()
        altered = policy(
            routes=(
                ClassRoute(
                    content_class=ContentClass.GENERAL.value,
                    external_allowed=True,
                    floor_tier=Tier.EXTERNAL,
                ),
                ClassRoute(
                    content_class=ContentClass.ADULT_THEMED.value,
                    external_allowed=True,
                    floor_tier=Tier.EXTERNAL,
                ),
            )
        )
        assert pol.policy_hash != altered.policy_hash


class TestDefaultDeny:
    def test_unknown_class_denies(self):
        pol = policy()
        allowed, reason = pol.egress_decision("mystery")
        assert allowed is False
        assert reason == "unknown_content_class"

    def test_unknown_class_has_no_route(self):
        assert policy().route_for("mystery") is None


class TestTierLadder:
    def test_tier_is_max_of_policy_floor_and_declared(self):
        pol = policy()
        assert pol.effective_tier(ContentClass.GENERAL, Tier.LOCAL) is Tier.EXTERNAL
        assert pol.effective_tier(ContentClass.GENERAL, Tier.EXTERNAL) is Tier.EXTERNAL

    def test_local_floor_class_with_high_declaration_stays_max(self):
        pol = policy()
        assert pol.effective_tier(ContentClass.EXPLICIT, Tier.EXTERNAL) is Tier.EXTERNAL
        assert pol.effective_tier(ContentClass.EXPLICIT, Tier.LOCAL) is Tier.LOCAL

    def test_declaring_below_floor_buys_nothing(self):
        pol = policy()
        assert pol.effective_tier(ContentClass.GENERAL, 0) is Tier.EXTERNAL


class TestEgress:
    def test_explicit_class_denies_egress(self):
        pol = build_default_policy()
        allowed, reason = pol.egress_decision(ContentClass.EXPLICIT)
        assert allowed is False
        assert reason == "egress_blocked_local_only"

    def test_explicit_denies_egress_even_declaring_external(self):
        pol = build_default_policy()
        # The tier a caller declares never widens egress: the table decides.
        assert pol.effective_tier(ContentClass.EXPLICIT, Tier.EXTERNAL) is Tier.EXTERNAL
        assert pol.egress_decision(ContentClass.EXPLICIT) == (False, "egress_blocked_local_only")

    def test_general_and_adult_themed_allow_egress(self):
        pol = build_default_policy()
        assert pol.egress_decision(ContentClass.GENERAL) == (True, None)
        assert pol.egress_decision(ContentClass.ADULT_THEMED) == (True, None)


class TestDefaultPolicyTable:
    def test_default_policy_matches_spec_table(self):
        pol = build_default_policy()
        assert pol.version == "u1-companion-routing/v0.1"
        general = pol.route_for(ContentClass.GENERAL)
        adult = pol.route_for(ContentClass.ADULT_THEMED)
        explicit = pol.route_for(ContentClass.EXPLICIT)
        assert general is not None and general.external_allowed
        assert adult is not None and adult.external_allowed
        assert explicit is not None and not explicit.external_allowed
        assert explicit.floor_tier is Tier.LOCAL
