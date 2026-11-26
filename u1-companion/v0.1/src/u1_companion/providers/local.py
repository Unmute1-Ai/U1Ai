"""The no-cloud adapter: essential text-first communication on the local path.

This adapter works with zero external providers configured — it is the
route every failover chain ends on and the only route local-only content
classes ever take. Composition is pure and deterministic: the user's words
pass through unchanged, and when a payload carries no deliverable text a
fixed local acknowledgment is composed instead (never invented content, no
model, no network). Processing is local/U1-controlled only: nothing here
egresses, and it costs nothing.
"""

from __future__ import annotations

from typing import Any, Mapping

PROVIDER_NAME = "local"

# A payload with no deliverable text still gets a deterministic local
# acknowledgment — the essential path never goes silent.
_LOCAL_ACKNOWLEDGMENT = "[u1] message held locally"


def compose_local_text(payload: Mapping[str, Any]) -> str:
    """Pure text-first composition: the user's words, unchanged.

    Deterministic by construction — same payload in, same text out, with no
    dependence on any provider, model, or clock.
    """
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return _LOCAL_ACKNOWLEDGMENT


class LocalAdapter:
    """Local/U1-controlled processing; satisfies ``ProviderTransport``.

    Never touches a network and never raises for content reasons: the local
    path is the floor every other route degrades to, so it fails only when
    the caller's own deadline has already passed.
    """

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def cost_per_call(self) -> int:
        # Local processing is free: the cost ledger never charges for it.
        return 0

    def send(
        self, request: Mapping[str, Any], *, deadline_monotonic: float
    ) -> Mapping[str, Any]:
        # Deadline enforcement is the boundary's uniform rule (pre-call and
        # post-call); the local adapter, like the mock, does not self-report.
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}
        return {"text": compose_local_text(payload), "cost_units": 0}
