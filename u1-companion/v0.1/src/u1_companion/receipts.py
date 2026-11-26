"""Hash-chained receipts and the consume-before-effect replay store.

Every routing decision — allowed or denied — is itself evidence (the Glass
Box receipt discipline): a JSONL line recording the envelope hash, content
class, policy version, per-check decisions, chosen route, cost data, and an
``unauthorized_effect`` flag, chained by SHA-256 over the previous hash and
the canonical body. Tampering with any line is mechanically visible.

The replay store enforces at-most-once effects: a receipt is consumed
*before* the provider call and confirmed after; a crash between the two
leaves a pending marker that requires a fresh evaluation — the effect of
the interrupted attempt is unknown, so its receipt is never reusable.
"""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass, replace
from typing import Any

from u1_companion.envelope import canonical_json, sha256_hex

GENESIS_HASH = "0" * 64

# Replay-store states for a receipt hash.
REPLAY_GRANTED = "granted"
REPLAY_ALREADY_CONSUMED = "already_consumed"
REPLAY_STALE_PENDING = "stale_pending_fresh_evaluation_required"

_STORE_CONFIRMED = "confirmed"
_STORE_PENDING = "pending"


@dataclass(frozen=True)
class ReceiptBody:
    """The decision data one receipt records. Hashed as canonical JSON."""

    sequence: int
    envelope_hash: str
    content_class: str
    policy_version: str
    policy_hash: str
    decision: str  # "ALLOW" | "DENY"
    reason: str | None
    checks: tuple[dict[str, Any], ...] = ()
    route: str | None = None
    cost_units: int = 0
    unauthorized_effect: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "envelope_hash": self.envelope_hash,
            "content_class": self.content_class,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "decision": self.decision,
            "reason": self.reason,
            "checks": [dict(check) for check in self.checks],
            "route": self.route,
            "cost_units": self.cost_units,
            "unauthorized_effect": self.unauthorized_effect,
        }


@dataclass(frozen=True)
class Receipt:
    """One chained receipt: the body, the hash it chains from, its own hash."""

    body: ReceiptBody
    prev_hash: str
    receipt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "body": self.body.to_dict(),
            "prev_hash": self.prev_hash,
            "receipt_hash": self.receipt_hash,
        }


def chain_receipt(body: ReceiptBody, prev_hash: str) -> Receipt:
    """Bind ``body`` to ``prev_hash``.

    ``receipt_hash = SHA-256(prev_hash || SHA-256(canonical_json(body)))`` —
    the Glass Box chain construction. Changing any body byte or the chain
    position changes the receipt hash.
    """
    body_hash = sha256_hex(canonical_json(body.to_dict()))
    receipt_hash = sha256_hex(prev_hash + body_hash)
    return Receipt(body=body, prev_hash=prev_hash, receipt_hash=receipt_hash)


class ReceiptWriter:
    """Appends receipts as JSONL, keeping the chain tip in memory.

    Single-writer by design (the Glass Box single-process boundary note):
    production hardening needs process isolation — recorded in the README's
    non-claims section.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._prev_hash = GENESIS_HASH
        self._sequence = 0

    @property
    def head_hash(self) -> str:
        return self._prev_hash

    def append(self, body: ReceiptBody) -> Receipt:
        self._sequence += 1
        receipt = chain_receipt(replace(body, sequence=self._sequence), self._prev_hash)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(canonical_json(receipt.to_dict()) + "\n")
        self._prev_hash = receipt.receipt_hash
        return receipt


def verify_chain(path: str) -> tuple[bool, int | None]:
    """Recompute the whole chain from ``path``.

    Returns ``(True, None)`` when every line chains correctly from genesis;
    ``(False, index)`` pointing at the first broken line otherwise. Any
    body mutation, deletion, or reordering shows up as a break.
    """
    prev = GENESIS_HASH
    with open(path, "r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                body = ReceiptBody(**record["body"])
                stored_prev = record["prev_hash"]
                stored_hash = record["receipt_hash"]
            except (json.JSONDecodeError, KeyError, TypeError):
                return False, index
            if stored_prev != prev:
                return False, index
            recomputed = chain_receipt(body, stored_prev).receipt_hash
            if not hmac.compare_digest(recomputed, stored_hash):
                return False, index
            prev = stored_hash
    return True, None


class ReplayStore:
    """Consume-before-effect store: at-most-once, crash-visible.

    ``consume`` grants exactly once per receipt hash and marks it pending.
    ``confirm`` records that the effect completed. A pending entry found by
    a later consumer means the prior effect's outcome is unknown — the
    store refuses to grant again and the caller must run a fresh evaluation
    (a new gate decision and a new receipt), never reuse the old one.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._entries: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        # Only known-state keys are honored: an unreadable or foreign store
        # fails closed as empty rather than granting anything.
        for receipt_hash, state in raw.items():
            if state in (_STORE_PENDING, _STORE_CONFIRMED):
                self._entries[receipt_hash] = state

    def _flush(self) -> None:
        temp_path = f"{self._path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(self._entries, handle, sort_keys=True)
        os.replace(temp_path, self._path)

    def status(self, receipt_hash: str) -> str | None:
        return self._entries.get(receipt_hash)

    def consume(self, receipt_hash: str) -> str:
        """Attempt to reserve the single effect for ``receipt_hash``.

        Returns ``REPLAY_GRANTED`` on first use (write lands on disk before
        the caller proceeds to the effect), ``REPLAY_ALREADY_CONSUMED`` for
        a confirmed receipt, or ``REPLAY_STALE_PENDING`` when a prior
        attempt never confirmed — that caller must re-evaluate from scratch.
        """
        state = self._entries.get(receipt_hash)
        if state == _STORE_CONFIRMED:
            return REPLAY_ALREADY_CONSUMED
        if state == _STORE_PENDING:
            return REPLAY_STALE_PENDING
        self._entries[receipt_hash] = _STORE_PENDING
        self._flush()
        return REPLAY_GRANTED

    def confirm(self, receipt_hash: str) -> None:
        if self._entries.get(receipt_hash) == _STORE_PENDING:
            self._entries[receipt_hash] = _STORE_CONFIRMED
            self._flush()
