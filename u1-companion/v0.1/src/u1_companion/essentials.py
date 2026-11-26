"""The essential no-cloud path: text-first communication that never egresses.

Essential expression must not depend on the cloud (spec principle 3). This
module bypasses external routing entirely — it consults no cloud adapter,
no consent token, and no cost ledger, and it works with zero external
providers configured. Composition is a pure function of the payload: the
user's words pass through unchanged or the delivery fails closed with a
reason token — nothing is ever invented on the user's behalf.

Any receipt written here records the local route only. A cloud adapter is
never touched and no external receipt is ever appended.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from u1_companion.envelope import RouteEnvelope
from u1_companion.providers.local import PROVIDER_NAME as LOCAL_ROUTE
from u1_companion.receipts import ReceiptBody, ReceiptWriter

# Fail-closed reason tokens (fixed vocabulary; never error text).
REASON_INVALID_ESSENTIAL_PAYLOAD = "invalid_essential_payload"

DECISION_ALLOW = "ALLOW"
DECISION_DENY = "DENY"


@dataclass(frozen=True)
class EssentialResult:
    """The outcome of one essential delivery."""

    delivered: bool
    text: str | None
    reason: str | None


def compose_essential_text(payload: Mapping[str, Any]) -> str | None:
    """Pure text-first composition from the payload.

    Returns the user's words unchanged when a deliverable ``text`` field is
    present, and ``None`` when nothing deliverable exists — the caller
    fails closed rather than composing content the user did not write.
    """
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return None


class EssentialsPath:
    """Essential text-first composition and delivery, cloud-free by design.

    This path shares nothing with the router: no cloud adapter list, no
    gate evaluation, no consent requirement, no budget. Even ``explicit``
    content — which policy keeps local regardless of any provider —
    delivers here with no consent ceremony, because nothing leaves U1.

    Args:
        receipt_writer: optional writer for local-route receipts. When
            supplied, every delivery (allowed or denied) is recorded with
            ``route="local"`` — never an external receipt.
    """

    def __init__(self, receipt_writer: ReceiptWriter | None = None) -> None:
        self._writer = receipt_writer

    def compose(self, envelope: RouteEnvelope) -> str | None:
        """The deliverable text for ``envelope``, or ``None`` when the
        payload carries nothing deliverable."""
        return compose_essential_text(envelope.payload)

    def deliver(self, envelope: RouteEnvelope) -> EssentialResult:
        """Deliver ``envelope``'s text on the local path, failing closed.

        Never touches a cloud adapter and never raises for content
        reasons: an undeliverable payload is a recorded denial, not an
        exception — evidence, not silence.
        """
        text = self.compose(envelope)
        if text is None:
            self._record(envelope, delivered=False, reason=REASON_INVALID_ESSENTIAL_PAYLOAD)
            return EssentialResult(
                delivered=False, text=None, reason=REASON_INVALID_ESSENTIAL_PAYLOAD
            )
        self._record(envelope, delivered=True, reason=None)
        return EssentialResult(delivered=True, text=text, reason=None)

    def _record(
        self, envelope: RouteEnvelope, *, delivered: bool, reason: str | None
    ) -> None:
        if self._writer is None:
            return
        self._writer.append(
            ReceiptBody(
                sequence=0,  # overwritten by the writer's chain ordering
                envelope_hash=envelope.envelope_hash,
                content_class=envelope.content_class.value,
                policy_version="u1-companion-essentials/v0.1",
                policy_hash="",
                decision=DECISION_ALLOW if delivered else DECISION_DENY,
                reason=reason,
                checks=(),
                route=LOCAL_ROUTE,
                cost_units=0,
                unauthorized_effect=False,
            )
        )
