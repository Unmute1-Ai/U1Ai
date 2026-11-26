"""Provider transport contract: the untrusted-input boundary.

Every provider — local or mock cloud — is reached through the
:class:`ProviderTransport` protocol: caller-injected, deadline-carrying,
with no base class and no registration mechanism (the NemoClaw
``ProposalClient`` pattern; sibling modules are the registry).

The transport owns the wire; it never owns the decision. ``call_transport``
wraps every attempt so that everything coming back is validated as
untrusted input: responses must match an exact whitelisted schema, deadline
violations fail closed, and any exception collapses to a generic snake_case
reason token — transport error text can carry secrets or attacker-controlled
fragments and is never surfaced. Nothing here dispatches an effect beyond
the single send the caller asked for.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

# Outcomes of one transport attempt.
DECISION_DELIVERED = "DELIVERED"
DECISION_REFUSED = "REFUSED"
DECISION_FAILED = "FAILED"

# Bounded sizes: a response that cannot fit these bounds is not processed.
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_TEXT_CHARS = 64 * 1024
MAX_RESPONSE_COST_UNITS = 1_000_000

# Fail-closed reason tokens (fixed vocabulary; never error text).
REASON_DEADLINE_EXCEEDED = "deadline_exceeded"
REASON_INVALID_RESPONSE_SCHEMA = "invalid_response_schema"
REASON_TRANSPORT_ERROR = "provider_transport_error"
REASON_PROVIDER_REFUSED = "provider_refused"


class ProviderRefusal(Exception):
    """Raised by an adapter when the provider declines the content.

    A refusal is an advisory rerouting signal, never U1's authorization
    decision: it can send the route elsewhere (ultimately local), but it can
    never widen what U1 permits. The exception message is deliberately
    generic — callers must not rely on (or surface) its text.
    """


class ProviderTransport(Protocol):
    """Caller-injected provider transport, deadline-carrying.

    The caller computes the monotonic deadline and passes it in; the
    transport applies it to its own I/O and must return a plain mapping.
    Any object with this method satisfies the protocol — no base class,
    no framework import.
    """

    def send(
        self, request: Mapping[str, Any], *, deadline_monotonic: float
    ) -> Mapping[str, Any]:
        """Send ``request`` and return the provider's raw response mapping."""
        ...


@dataclass(frozen=True)
class TransportResult:
    """One fail-closed transport attempt.

    ``clean_response`` is present only when ``decision`` is
    ``DECISION_DELIVERED``; it is the schema-validated response, never the
    raw mapping.
    """

    decision: str
    reason: str | None
    clean_response: dict[str, Any] | None


def validate_response(raw: object) -> TransportResult:
    """Whitelist the exact response schema; everything else fails closed.

    A valid response is exactly ``{"text": <non-empty bounded str>,
    "cost_units": <non-negative int>}`` — unknown keys, missing keys, empty
    or oversized text, booleans, or out-of-range cost are all rejected with
    the same reason token, so a malformed response can never be partially
    trusted.
    """
    if not isinstance(raw, Mapping):
        return TransportResult(DECISION_FAILED, REASON_INVALID_RESPONSE_SCHEMA, None)
    if set(raw) != {"text", "cost_units"}:
        return TransportResult(DECISION_FAILED, REASON_INVALID_RESPONSE_SCHEMA, None)
    text = raw["text"]
    cost_units = raw["cost_units"]
    if not isinstance(text, str) or not text or len(text) > MAX_RESPONSE_TEXT_CHARS:
        return TransportResult(DECISION_FAILED, REASON_INVALID_RESPONSE_SCHEMA, None)
    # bool is an int subclass; it is not a cost unit.
    if isinstance(cost_units, bool) or not isinstance(cost_units, int):
        return TransportResult(DECISION_FAILED, REASON_INVALID_RESPONSE_SCHEMA, None)
    if not 0 <= cost_units <= MAX_RESPONSE_COST_UNITS:
        return TransportResult(DECISION_FAILED, REASON_INVALID_RESPONSE_SCHEMA, None)
    return TransportResult(
        DECISION_DELIVERED, None, {"text": text, "cost_units": cost_units}
    )


def call_transport(
    transport: ProviderTransport,
    request: Mapping[str, Any],
    *,
    deadline_monotonic: float,
) -> TransportResult:
    """Run one transport attempt, failing closed at every exit.

    Deadline is enforced before the call and again after every return (a
    late response is a failed response). Exceptions become generic reason
    tokens: the except clause swallows the exception object deliberately and
    never returns its text.
    """
    if time.monotonic() >= deadline_monotonic:
        return TransportResult(DECISION_FAILED, REASON_DEADLINE_EXCEEDED, None)
    try:
        raw = transport.send(request, deadline_monotonic=deadline_monotonic)
    except ProviderRefusal:
        # Advisory signal: the provider declined. Rerouting is the router's
        # job; the refusal text is never echoed.
        return TransportResult(DECISION_REFUSED, REASON_PROVIDER_REFUSED, None)
    except Exception:
        return TransportResult(DECISION_FAILED, REASON_TRANSPORT_ERROR, None)
    if time.monotonic() >= deadline_monotonic:
        return TransportResult(DECISION_FAILED, REASON_DEADLINE_EXCEEDED, None)
    return validate_response(raw)
