"""The deterministic pre-effect gate: every denial terminates the path.

Checked in order, before any external adapter is touched (spec §7): shape →
content-class membership → tier → privacy/egress → consent → cost. The gate
is pure with respect to providers: it takes no provider transport, reads no
provider or evaluator output, and returns only its own decision. Provider
availability, pricing, or content policy can add a denial downstream
(advisory rerouting) but are never an input here — a provider's ALLOW can
never lift a deterministic DENY.

Denials are snake_case reason tokens from a fixed vocabulary. Transport
error text is never echoed: it can carry secrets or attacker-controlled
fragments (the NemoClaw adapter discipline).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from u1_companion.consent import ConsentService, ConsentToken
from u1_companion.envelope import ContentClass, RouteEnvelope, Tier
from u1_companion.policy import RoutingPolicy
from u1_companion.receipts import ReceiptBody, ReceiptWriter

DECISION_ALLOW = "ALLOW"
DECISION_DENY = "DENY"

# Classes that cannot leave U1 without a valid, envelope-bound consent
# grant. Data, not discretion: extending this set is a policy change.
CONSENT_REQUIRED_CLASSES = frozenset({ContentClass.ADULT_THEMED.value})

DEFAULT_PROVIDER = "mock_cloud"
DEFAULT_COST_UNITS = 1

# Fail-closed denial reasons (snake_case tokens; never error text).
REASON_INVALID_ENVELOPE = "invalid_envelope"
REASON_UNKNOWN_CONTENT_CLASS = "unknown_content_class"
REASON_EGRESS_BLOCKED = "egress_blocked_local_only"
REASON_CONSENT_REQUIRED = "consent_required"
REASON_BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class CheckResult:
    """One gate check's outcome, recorded verbatim on the receipt."""

    name: str
    allowed: bool
    reason: str | None


@dataclass(frozen=True)
class GateDecision:
    """The gate's verdict for one envelope's *external* route.

    ``allowed`` governs only the external path: a denial here terminates
    the external route pre-effect; the caller's local fallback is a routing
    concern (the router deliverable), never a re-evaluation.
    """

    allowed: bool
    reason: str | None
    route: str | None
    effective_tier: Tier | None
    envelope_hash: str
    policy_version: str
    policy_hash: str
    checks: tuple[CheckResult, ...]


class CostLedger:
    """Per-provider and session cost state checked by the gate's cost step.

    Spending is checked for headroom before the effect and recorded after
    it. A zero session budget denies all external spend — fail closed by
    default; budgets are set explicitly in policy.
    """

    def __init__(self, policy: RoutingPolicy) -> None:
        self._policy = policy
        self._provider_spend: dict[str, int] = {}
        self._session_spend = 0

    def headroom(self, provider: str, units: int) -> tuple[bool, str | None]:
        if not isinstance(units, int) or units < 0:
            return False, "invalid_cost_units"
        budget = self._policy.provider_budget(provider)
        spent = self._provider_spend.get(provider, 0)
        if budget is not None and spent + units > budget.max_cost_units:
            return False, REASON_BUDGET_EXHAUSTED
        if self._session_spend + units > self._policy.session_budget_units:
            return False, REASON_BUDGET_EXHAUSTED
        return True, None

    def record(self, provider: str, units: int) -> None:
        """Record realized spend after an effect. Negative spend is refused:
        the ledger can only ever count upward."""
        if not isinstance(units, int) or units < 0:
            raise ValueError("invalid_cost_units")
        self._provider_spend[provider] = self._provider_spend.get(provider, 0) + units
        self._session_spend += units

    @property
    def session_spend(self) -> int:
        return self._session_spend

    def provider_spend(self, provider: str) -> int:
        return self._provider_spend.get(provider, 0)


def _run_checks(
    envelope: object,
    policy: RoutingPolicy,
    consent_service: ConsentService | None,
    consent_token: ConsentToken | None,
    cost_ledger: CostLedger | None,
    provider: str,
    cost_units: int,
    now: float | None,
) -> tuple[bool, str | None, list[CheckResult], Tier | None, str | None]:
    """The ordered check sequence. Returns (allowed, reason, checks,
    effective_tier, content_class); the first failing check terminates.
    """
    checks: list[CheckResult] = []

    def deny(
        name: str, token: str
    ) -> tuple[bool, str | None, list[CheckResult], Tier | None, str | None]:
        checks.append(CheckResult(name=name, allowed=False, reason=token))
        # Denial receipts must still name the class that was denied —
        # evidence that hides the subject of its own denial is not evidence.
        # The shape check runs before the class is readable (the input may
        # not be an envelope at all), so it records None rather than guessing.
        known_class = (
            envelope.content_class.value
            if isinstance(envelope, RouteEnvelope)
            and isinstance(envelope.content_class, ContentClass)
            else None
        )
        return False, token, checks, None, known_class

    # 1. Shape: the gate accepts constructed envelopes only; construction
    # already validates fields and computes the canonical digest.
    if not isinstance(envelope, RouteEnvelope):
        return deny("shape", REASON_INVALID_ENVELOPE)
    content_class = (
        envelope.content_class.value
        if isinstance(envelope.content_class, ContentClass)
        else str(envelope.content_class)
    )

    # 2. Content-class membership: the table is default-deny.
    if policy.route_for(envelope.content_class) is None:
        return deny("content_class", REASON_UNKNOWN_CONTENT_CLASS)
    checks.append(CheckResult(name="content_class", allowed=True, reason=None))

    # 3. Tier: max(policy_floor, declared) — under-declaring buys nothing.
    effective_tier = policy.effective_tier(envelope.content_class, envelope.declared_tier)
    checks.append(CheckResult(name="tier", allowed=True, reason=None))

    # 4. Privacy/egress: the policy, not any provider, owns what may leave U1.
    egress_ok, egress_reason = policy.egress_decision(envelope.content_class)
    if not egress_ok:
        return deny("egress", egress_reason or REASON_EGRESS_BLOCKED)
    checks.append(CheckResult(name="egress", allowed=True, reason=None))

    # 5. Consent: external processing of sensitive classes needs a valid,
    # unconsumed grant bound to this exact envelope.
    if content_class in CONSENT_REQUIRED_CLASSES:
        if consent_service is None or consent_token is None:
            return deny("consent", REASON_CONSENT_REQUIRED)
        current = time.time() if now is None else now
        consent_ok, consent_reason = consent_service.validate(
            consent_token, envelope.envelope_hash, effective_tier, now=current
        )
        if not consent_ok:
            return deny("consent", consent_reason or REASON_CONSENT_REQUIRED)
        checks.append(CheckResult(name="consent", allowed=True, reason=None))

    # 6. Cost: per-provider and session headroom; over budget denies the
    # external route (the caller reroutes locally — never a hard failure).
    if cost_ledger is not None:
        cost_ok, cost_reason = cost_ledger.headroom(provider, cost_units)
        if not cost_ok:
            return deny("cost", cost_reason or REASON_BUDGET_EXHAUSTED)
        checks.append(CheckResult(name="cost", allowed=True, reason=None))

    # 7. ALLOW: the nonce burns only here, so unrelated denials never force
    # re-approval. The caller still owes the replay consume before the effect.
    if consent_service is not None and consent_token is not None:
        consent_service.consume(consent_token)
    checks.append(CheckResult(name="decision", allowed=True, reason=None))
    return True, None, checks, effective_tier, content_class


def evaluate(
    envelope: RouteEnvelope,
    policy: RoutingPolicy,
    *,
    consent_service: ConsentService | None = None,
    consent_token: ConsentToken | None = None,
    cost_ledger: CostLedger | None = None,
    provider: str = DEFAULT_PROVIDER,
    cost_units: int = DEFAULT_COST_UNITS,
    now: float | None = None,
    receipt_writer: ReceiptWriter | None = None,
) -> GateDecision:
    """Run the full pre-effect check sequence for ``envelope``'s external route.

    Every evaluation — allowed or denied — writes a receipt when a writer
    is supplied. The receipt exists before any provider call; the caller
    must consume the replay store against its hash before dispatching the
    effect (at-most-once) and confirm afterwards.
    """
    allowed, reason, checks, effective_tier, content_class = _run_checks(
        envelope, policy, consent_service, consent_token, cost_ledger, provider, cost_units, now
    )
    # A tampered envelope that cannot even hash (defense-in-depth path)
    # still gets its denial — recorded without a digest rather than crashing.
    envelope_hash = ""
    if isinstance(envelope, RouteEnvelope):
        try:
            envelope_hash = envelope.envelope_hash
        except AttributeError:
            envelope_hash = ""
    decision = GateDecision(
        allowed=allowed,
        reason=reason,
        route=provider if allowed else None,
        effective_tier=effective_tier,
        envelope_hash=envelope_hash,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
        checks=tuple(checks),
    )
    if receipt_writer is not None:
        # Written here — before the caller ever reaches a provider — so the
        # decision evidence always predates the effect it governs.
        receipt_writer.append(
            ReceiptBody(
                sequence=0,  # overwritten by the writer's chain ordering
                envelope_hash=decision.envelope_hash,
                content_class=content_class or "unknown",
                policy_version=policy.version,
                policy_hash=policy.policy_hash,
                decision=DECISION_ALLOW if allowed else DECISION_DENY,
                reason=reason,
                checks=tuple(
                    {"name": c.name, "allowed": c.allowed, "reason": c.reason} for c in checks
                ),
                route=decision.route,
                cost_units=cost_units if allowed else 0,
                unauthorized_effect=False,
            )
        )
    return decision
