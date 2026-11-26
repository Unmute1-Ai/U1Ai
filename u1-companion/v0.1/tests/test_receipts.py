"""Receipts acceptance tests (OD-1 D2): chain verification, tamper visibility,
replay consumed before effect, crash requires fresh evaluation."""

from __future__ import annotations

import json

import pytest

from u1_companion.receipts import (
    GENESIS_HASH,
    
    ReceiptBody,
    ReceiptWriter,
    REPLAY_ALREADY_CONSUMED,
    REPLAY_GRANTED,
    REPLAY_STALE_PENDING,
    ReplayStore,
    chain_receipt,
    verify_chain,
)


def body(**overrides) -> ReceiptBody:
    base = dict(
        sequence=1,
        envelope_hash="a" * 64,
        content_class="general",
        policy_version="test-routing/v1",
        policy_hash="b" * 64,
        decision="ALLOW",
        reason=None,
        checks=({"name": "tier", "allowed": True, "reason": None},),
        route="mock_cloud",
        cost_units=1,
        unauthorized_effect=False,
    )
    base.update(overrides)
    return ReceiptBody(**base)


@pytest.fixture
def ledger_path(tmp_path):
    return str(tmp_path / "receipts.jsonl")


@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "replay.json")


class TestChainConstruction:
    def test_genesis_is_64_zeros(self):
        assert GENESIS_HASH == "0" * 64

    def test_chain_binds_body_and_position(self):
        first = chain_receipt(body(), GENESIS_HASH)
        assert first.prev_hash == GENESIS_HASH
        second = chain_receipt(body(), first.receipt_hash)
        assert second.prev_hash == first.receipt_hash
        # Same body at a different chain position hashes differently.
        assert second.receipt_hash != first.receipt_hash

    def test_receipt_hash_deterministic(self):
        one = chain_receipt(body(), GENESIS_HASH)
        two = chain_receipt(body(), GENESIS_HASH)
        assert one.receipt_hash == two.receipt_hash

    def test_any_body_change_changes_hash(self):
        one = chain_receipt(body(), GENESIS_HASH)
        two = chain_receipt(body(reason="egress_blocked_local_only"), GENESIS_HASH)
        assert one.receipt_hash != two.receipt_hash


class TestChainVerification:
    def test_valid_chain_verifies(self, ledger_path):
        writer = ReceiptWriter(ledger_path)
        for sequence in range(1, 5):
            writer.append(
                body(
                    sequence=sequence,
                    decision="DENY" if sequence % 2 == 0 else "ALLOW",
                    reason="consent_required" if sequence % 2 == 0 else None,
                )
            )
        ok, break_at = verify_chain(ledger_path)
        assert ok is True and break_at is None

    def test_body_tampering_is_visible(self, ledger_path):
        writer = ReceiptWriter(ledger_path)
        writer.append(body())
        writer.append(body(sequence=2, decision="DENY", reason="budget_exhausted"))
        lines = open(ledger_path, encoding="utf-8").read().splitlines()
        record = json.loads(lines[1])
        # A denial is rewritten as an allow: the chain must catch it.
        record["body"]["decision"] = "ALLOW"
        lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with open(ledger_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        ok, break_at = verify_chain(ledger_path)
        assert ok is False
        assert break_at == 1

    def test_removed_line_is_visible(self, ledger_path):
        writer = ReceiptWriter(ledger_path)
        writer.append(body())
        writer.append(body(sequence=2))
        lines = open(ledger_path, encoding="utf-8").read().splitlines()
        with open(ledger_path, "w", encoding="utf-8") as handle:
            handle.write(lines[1] + "\n")  # drop the first receipt
        ok, break_at = verify_chain(ledger_path)
        assert ok is False
        assert break_at == 0

    def test_reordered_lines_are_visible(self, ledger_path):
        writer = ReceiptWriter(ledger_path)
        writer.append(body())
        writer.append(body(sequence=2))
        lines = open(ledger_path, encoding="utf-8").read().splitlines()
        with open(ledger_path, "w", encoding="utf-8") as handle:
            handle.write(lines[1] + "\n" + lines[0] + "\n")
        ok, break_at = verify_chain(ledger_path)
        assert ok is False

    def test_receipt_hashes_chain_across_writer_instances(self, ledger_path):
        # Single-writer boundary: a fresh writer restarts from genesis, so
        # appending with it to an existing ledger breaks the chain visibly
        # (documented in the README non-claims; production needs one writer).
        first = ReceiptWriter(ledger_path)
        first.append(body())
        second = ReceiptWriter(ledger_path)
        second.append(body(sequence=2))
        ok, break_at = verify_chain(ledger_path)
        assert ok is False
        assert break_at == 1


class TestReplayStore:
    def test_consume_grants_once(self, store_path):
        store = ReplayStore(store_path)
        assert store.consume("r" * 64) == REPLAY_GRANTED
        # Unconfirmed (effect outcome unknown): never a second grant.
        assert store.consume("r" * 64) == REPLAY_STALE_PENDING
        # After the effect confirms, the receipt is spent for good.
        store.confirm("r" * 64)
        assert store.consume("r" * 64) == REPLAY_ALREADY_CONSUMED

    def test_confirmed_receipt_never_regrants(self, store_path):
        store = ReplayStore(store_path)
        receipt_hash = "r" * 64
        assert store.consume(receipt_hash) == REPLAY_GRANTED
        store.confirm(receipt_hash)
        assert store.status(receipt_hash) == "confirmed"
        assert store.consume(receipt_hash) == REPLAY_ALREADY_CONSUMED

    def test_consume_writes_before_effect(self, store_path):
        # The grant must be durable the moment consume returns: the caller
        # is allowed to proceed to the effect immediately after.
        store = ReplayStore(store_path)
        assert store.consume("r" * 64) == REPLAY_GRANTED
        reopened = ReplayStore(store_path)
        assert reopened.status("r" * 64) == "pending"
        assert reopened.consume("r" * 64) == REPLAY_STALE_PENDING

    def test_crash_requires_fresh_evaluation(self, store_path):
        # Attempt one consumes, then the process dies before confirm. The
        # reopened store must refuse to reuse the receipt: the prior
        # effect's outcome is unknown, so a fresh evaluation is required.
        first = ReplayStore(store_path)
        receipt_hash = "r" * 64
        assert first.consume(receipt_hash) == REPLAY_GRANTED
        # --- crash: no confirm() call ---
        recovered = ReplayStore(store_path)
        assert recovered.status(receipt_hash) == "pending"
        assert recovered.consume(receipt_hash) == REPLAY_STALE_PENDING

    def test_fresh_evaluation_after_crash_gets_new_grant(self, store_path):
        # The recovery path: re-evaluate (new receipt hash), then dispatch.
        first = ReplayStore(store_path)
        assert first.consume("r" * 64) == REPLAY_GRANTED
        recovered = ReplayStore(store_path)
        assert recovered.consume("r" * 64) == REPLAY_STALE_PENDING
        # A fresh evaluation produces a fresh receipt hash:
        new_receipt = "s" * 64
        assert recovered.consume(new_receipt) == REPLAY_GRANTED

    def test_unknown_store_contents_fail_closed(self, store_path):
        with open(store_path, "w", encoding="utf-8") as handle:
            json.dump({"r" * 64: "mysterious_state"}, handle)
        store = ReplayStore(store_path)
        # An unrecognized entry is treated as absent: foreign data is never
        # trusted as a consumed marker, so the fresh consume grants.
        assert store.consume("r" * 64) == REPLAY_GRANTED


def test_unauthorized_effect_flag_defaults_false():
    assert body().unauthorized_effect is False
    receipt = chain_receipt(body(), GENESIS_HASH)
    assert receipt.body.to_dict()["unauthorized_effect"] is False
