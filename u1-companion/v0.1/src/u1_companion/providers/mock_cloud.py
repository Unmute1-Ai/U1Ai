"""Deterministic mock external adapter — no network, ever.

This is the only external-tier adapter in v0.1: a stub for tests and the
demo. Behavior is fully configured up front (latency, leading failures,
refused classes, per-call cost) and fully reproducible — the same config
and the same call sequence always produce the same outcome, so tests never
flame and the demo never varies.

It simulates the failure modes a real cloud adapter would surface: a
transport outage (raises, which the boundary collapses to a generic
token), a deadline overrun (simulated latency past the caller's deadline),
and a content-policy refusal (raises :class:`ProviderRefusal` — an advisory
rerouting signal, never an authority decision).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

from u1_companion.providers.base import ProviderRefusal

PROVIDER_NAME = "mock_cloud"
DEFAULT_COST_PER_CALL = 1


@dataclass(frozen=True)
class MockCloudConfig:
    """Deterministic failure/refusal/cost schedule.

    Attributes:
        fail_first_calls: the first N calls raise a simulated transport
            outage; after that the adapter succeeds.
        refuse_classes: content classes this provider's content policy
            declines (advisory refusal on every call, not just the first).
        latency_ms: simulated processing time per call. ``0`` means
            instantaneous; the deadline check still applies.
        cost_per_call: abstract cost units billed for a successful call.
    """

    fail_first_calls: int = 0
    refuse_classes: tuple[str, ...] = ()
    latency_ms: int = 0
    cost_per_call: int = DEFAULT_COST_PER_CALL


@dataclass
class _CallState:
    """Mutable call counter — the only state a deterministic mock needs."""

    count: int = 0


class MockCloudAdapter:
    """Deterministic mock cloud adapter; satisfies ``ProviderTransport``."""

    def __init__(self, config: MockCloudConfig | None = None) -> None:
        self._config = config if config is not None else MockCloudConfig()
        self._state = _CallState()

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def cost_per_call(self) -> int:
        return self._config.cost_per_call

    @property
    def calls_made(self) -> int:
        return self._state.count

    def send(
        self, request: Mapping[str, Any], *, deadline_monotonic: float
    ) -> Mapping[str, Any]:
        self._state.count += 1
        if self._config.latency_ms:
            time.sleep(self._config.latency_ms / 1000)
        # No deadline self-reporting here: a real provider returns late, it
        # does not refuse to answer. The boundary's post-call deadline
        # check classifies a late return as ``deadline_exceeded``.
        if self._state.count <= self._config.fail_first_calls:
            raise ConnectionError("simulated provider outage")
        content_class = request.get("content_class", "")
        if content_class in self._config.refuse_classes:
            # Advisory refusal: rerouting signal only. The generic message
            # is deliberate — the boundary never echoes provider text.
            raise ProviderRefusal("content policy declined")
        payload = request.get("payload")
        text = payload.get("text", "") if isinstance(payload, Mapping) else ""
        return {
            "text": f"[mock_cloud] {text}",
            "cost_units": self._config.cost_per_call,
        }
