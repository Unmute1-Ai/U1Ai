"""Policy-driven provider selection with explicit failover ordering.

The router is the only caller of external adapters. For each envelope it
builds a failover plan — cloud adapters in insertion order, local last —
and walks it: the deterministic gate decides whether an external attempt
may start at all; a replay consume bounds the effect to at-most-once; a
failed or refused attempt records an advisory receipt and moves to the
next adapter. The local path is always last and never fails for content
reasons, so a dead, refusing, or over-budget cloud never disables
essential communication.

The router adds no judgment of its own: routing order and every
allow/deny come from the policy and the gate. Provider output is treated
as untrusted data end to end.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

from u1_companion.consent import ConsentService, ConsentToken
from u1_companion.envelope import ContentClass, RouteEnvelope
from u1_companion.gate import (
    CostLedger,
    DEFAULT_COST_UNITS,
    evaluate,
)
from u1_companion.policy import RoutingPolicy
from u1_companion.providers.base import (
    DECISION_DELIVERED,
    DECISION_REFUSED,
    ProviderTransport,
    call_transport,
)
from u1_companion.providers.local import PROVIDER_NAME as LOCAL_PROVIDER
from u1_companion.providers.local import LocalAdapter
from u1_companion.receipts import (
    REPLAY_GRANTED,
    ReceiptBody,
    ReceiptWriter,
    ReplayStore,
)

DEFAULT_TIMEOUT_SECONDS = 5.0

# Advisory receipts record why an external attempt did not deliver.
ADVISORY_REFUSAL = "advisory_refusal"


@dataclass(frozen=True)
class AttemptRecord:
    """One adapter attempt, carried on the result for the caller."""

    provider: str
    outcome: str  # "delivered" | "failed" | "refused" | "gate_denied"
    reason: str | None
    text: str | None = None


@dataclass(frozen=True)
class RouteResult:
    """The outcome of routing one envelope.

    ``delivered`` means the user's message reached a provider — cloud or
    local. A route that ends on the local path is still a delivery: the
    essential path never reports failure just because no cloud answered.
    """

    delivered: bool
    provider: str | None
    text: str | None
    attempts: tuple[AttemptRecord, ...]
    envelope_hash: str


class Router:
    """Selects the adapter per policy with local-last failover.

    Args:
        policy: the routing policy (owns every allow/deny).
        cloud_adapters: name → transport for external providers, in the
            order they should be attempted. Empty means cloud-free by
            configuration — everything routes local.
        local_adapter: the terminal local/U1-controlled adapter.
        receipt_writer: when supplied, every gate decision and advisory
            outcome is appended to the hash chain.
        replay_store: when supplied, each allowed external effect is
            consumed-before-effect (at-most-once).
        consent_service: required for consent-gated classes.
        timeout_seconds: per-attempt deadline budget.
    """

    def __init__(
        self,
        policy: RoutingPolicy,
        *,
        cloud_adapters: Mapping[str, ProviderTransport] | None = None,
        local_adapter: ProviderTransport | None = None,
        receipt_writer: ReceiptWriter | None = None,
        replay_store: ReplayStore | None = None,
        consent_service: ConsentService | None = None,
        cost_ledger: CostLedger | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("invalid_timeout")
        self._policy = policy
        self._cloud: dict[str, ProviderTransport] = dict(cloud_adapters or {})
        self._local: ProviderTransport = local_adapter or LocalAdapter()
        self._writer = receipt_writer
        self._replay = replay_store
        self._consent_service = consent_service
        self._cost_ledger = cost_ledger if cost_ledger is not None else CostLedger(policy)
        self._timeout_seconds = timeout_seconds

    # -- Plan ----------------------------------------------------------------

    def route_plan(self, content_class: str | ContentClass) -> tuple[str, ...]:
        """Failover ordering for a class: cloud adapters first when the
        policy permits egress, then local last. Local-only classes (e.g.
        ``explicit``) produce a plan of exactly one local step."""
        egress_ok, _ = self._policy.egress_decision(content_class)
        cloud = tuple(self._cloud) if egress_ok else ()
        return cloud + (LOCAL_PROVIDER,)

    # -- Routing ---------------------------------------------------------------

    def route(
        self,
        envelope: RouteEnvelope,
        *,
        consent_token: ConsentToken | None = None,
        now: float | None = None,
    ) -> RouteResult:
        """Route ``envelope`` through the failover plan; never raises for a
        routing reason — the last resort is local delivery."""
        attempts: list[AttemptRecord] = []
        for provider in self.route_plan(envelope.content_class):
            if provider == LOCAL_PROVIDER:
                return self._deliver_local(envelope, attempts)
            attempt = self._attempt_cloud(
                envelope, provider, consent_token=consent_token, now=now
            )
            attempts.append(attempt)
            if attempt.outcome == "delivered":
                return RouteResult(
                    delivered=True,
                    provider=provider,
                    text=attempt.text,
                    attempts=tuple(attempts),
                    envelope_hash=envelope.envelope_hash,
                )
        # Unreachable in practice: the plan always ends with local, whose
        # attempt is terminal — but fail closed rather than invent a route.
        return RouteResult(
            delivered=False,
            provider=None,
            text=None,
            attempts=tuple(attempts),
            envelope_hash=envelope.envelope_hash,
        )

    # -- Steps -----------------------------------------------------------------

    def _attempt_cloud(
        self,
        envelope: RouteEnvelope,
        provider: str,
        *,
        consent_token: ConsentToken | None,
        now: float | None,
    ) -> AttemptRecord:
        adapter = self._cloud[provider]
        cost_units = getattr(adapter, "cost_per_call", DEFAULT_COST_UNITS)

        # 1. The deterministic gate owns whether this external attempt may
        # start. Its receipt (if a writer is supplied) predates the effect.
        decision = evaluate(
            envelope,
            self._policy,
            consent_service=self._consent_service,
            consent_token=consent_token,
            cost_ledger=self._cost_ledger,
            provider=provider,
            cost_units=cost_units,
            now=now,
            receipt_writer=self._writer,
        )
        receipt_hash = self._writer.head_hash if self._writer is not None else ""
        if not decision.allowed:
            # Budget exhaustion and consent gaps reroute locally; they are
            # never hard user-facing failures.
            return AttemptRecord(
                provider=provider, outcome="gate_denied", reason=decision.reason
            )

        # 2. Consume-before-effect: at-most-once. A non-grant means a prior
        # attempt's outcome is unknown — this receipt is dead, and the
        # route degrades (fresh evaluation happens on the next call).
        if self._replay is not None and receipt_hash:
            state = self._replay.consume(receipt_hash)
            if state != REPLAY_GRANTED:
                return AttemptRecord(
                    provider=provider,
                    outcome="failed",
                    reason="replay_fresh_evaluation_required",
                )

        # 3. The effect. All output is untrusted boundary data.
        result = call_transport(
            adapter,
            self._transport_request(envelope),
            deadline_monotonic=time.monotonic() + self._timeout_seconds,
        )
        if result.decision == DECISION_DELIVERED:
            # Realized spend recorded after the effect, per the policy.
            self._cost_ledger.record(provider, cost_units)
            if self._replay is not None and receipt_hash:
                self._replay.confirm(receipt_hash)
            return AttemptRecord(
                provider=provider,
                outcome="delivered",
                reason=None,
                text=result.clean_response["text"],
            )

        # 4. Failure or refusal: advisory evidence, then the next adapter.
        # A refusal is advisory rerouting only — it never changes what U1
        # permits; a failure never becomes a user-facing hard error while
        # the local path stands.
        self._append_advisory(
            envelope,
            provider=provider,
            reason=(
                ADVISORY_REFUSAL
                if result.decision == DECISION_REFUSED
                else result.reason or "provider_failed"
            ),
        )
        return AttemptRecord(
            provider=provider,
            outcome="refused" if result.decision == DECISION_REFUSED else "failed",
            reason=result.reason,
        )

    def _deliver_local(
        self, envelope: RouteEnvelope, attempts: list[AttemptRecord]
    ) -> RouteResult:
        result = call_transport(
            self._local,
            self._transport_request(envelope),
            deadline_monotonic=time.monotonic() + self._timeout_seconds,
        )
        if result.decision == DECISION_DELIVERED:
            outcome, reason, text = "delivered", None, result.clean_response["text"]
        else:
            # Local is the floor; its failure is the only true delivery
            # failure the router can report (and it still names a token).
            outcome, reason, text = "failed", result.reason, None
        attempts.append(AttemptRecord(provider=LOCAL_PROVIDER, outcome=outcome, reason=reason))
        if self._writer is not None:
            self._writer.append(
                ReceiptBody(
                    sequence=0,  # overwritten by the writer's chain ordering
                    envelope_hash=envelope.envelope_hash,
                    content_class=envelope.content_class.value,
                    policy_version=self._policy.version,
                    policy_hash=self._policy.policy_hash,
                    decision="ALLOW" if outcome == "delivered" else "DENY",
                    reason=reason,
                    checks=(),
                    route=LOCAL_PROVIDER,
                    cost_units=0,
                    unauthorized_effect=False,
                )
            )
        return RouteResult(
            delivered=outcome == "delivered",
            provider=LOCAL_PROVIDER if outcome == "delivered" else None,
            text=text,
            attempts=tuple(attempts),
            envelope_hash=envelope.envelope_hash,
        )

    # -- Helpers -----------------------------------------------------------------

    def _transport_request(self, envelope: RouteEnvelope) -> dict[str, Any]:
        """A private snapshot of the governed fields — not the caller's
        mutable mapping."""
        return {
            "envelope_hash": envelope.envelope_hash,
            "content_class": envelope.content_class.value,
            "payload": dict(envelope.payload),
            "params": dict(envelope.params),
        }

    def _append_advisory(
        self, envelope: RouteEnvelope, *, provider: str, reason: str
    ) -> None:
        if self._writer is None:
            return
        self._writer.append(
            ReceiptBody(
                sequence=0,
                envelope_hash=envelope.envelope_hash,
                content_class=envelope.content_class.value,
                policy_version=self._policy.version,
                policy_hash=self._policy.policy_hash,
                decision="DENY",
                reason=reason,
                checks=(),
                route=provider,
                cost_units=0,
                unauthorized_effect=False,
            )
        )
