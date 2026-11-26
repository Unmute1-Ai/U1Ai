"""Runnable example: route envelopes through every gate, end to end.

Walks representative envelopes through the full v0.1 pipeline — policy,
pre-effect gate, consent, replay-consume, adapters, advisory rerouting,
local failover — writing a hash-chained receipt for every decision, then
verifies the chain. Every provider is a stub or deterministic mock; the
demo performs no external effect and no network I/O.

Run: ``python scripts/demo.py`` (receipts to a temp directory), or
``python scripts/demo.py <output-dir>`` to keep the receipt chain on disk.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Runnable without installing: put the src layout on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from u1_companion import (  # noqa: E402  (path bootstrap must run first)
    ContentClass,
    ConsentService,
    EssentialsPath,
    LocalAdapter,
    MockCloudAdapter,
    MockCloudConfig,
    ReceiptWriter,
    ReplayStore,
    RouteEnvelope,
    Router,
    Tier,
    build_default_policy,
    verify_chain,
)


def envelope(request_id: str, content_class: ContentClass) -> RouteEnvelope:
    return RouteEnvelope(
        request_id=request_id,
        principal="user:demo",
        content_class=content_class,
        declared_tier=Tier.EXTERNAL,
        payload={"text": f"demo payload ({content_class.value})"},
        params={},
    )


def show(label: str, *, delivered: bool, provider: str | None, attempts) -> None:
    trail = " -> ".join(f"{a.provider}:{a.outcome}" for a in attempts)
    print(f"{label}: delivered={delivered} route={provider or '-'} [{trail}]")


def main() -> int:
    # Without an argument the receipts land in a throwaway temp directory;
    # with one, the demo writes them there (how evidence/receipts.jsonl is
    # regenerated: ``python scripts/demo.py evidence``).
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    if len(sys.argv) > 1:
        out_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = str(out_dir / "receipts.jsonl")
    replay_path = str(out_dir / "replay.json")
    if Path(receipts_path).exists():
        # A fresh ReceiptWriter starts at genesis; appending into an
        # existing chain file would produce a broken (misleading) chain.
        # Refuse instead: remove the directory or pick a new one.
        print(
            f"refusing to append into an existing chain: {receipts_path} "
            "exists — remove it or choose another output directory",
            file=sys.stderr,
        )
        return 2

    policy = build_default_policy()
    consent = ConsentService(signing_key=b"demo-signing-key")
    consent.register_approver("approver:human", max_tier=Tier.EXTERNAL)
    writer = ReceiptWriter(receipts_path)
    replay = ReplayStore(replay_path)

    def make_router(*, refusing: bool) -> Router:
        config = (
            MockCloudConfig(refuse_classes=(ContentClass.ADULT_THEMED.value,))
            if refusing
            else MockCloudConfig()
        )
        return Router(
            policy,
            cloud_adapters={"mock_cloud": MockCloudAdapter(config)},
            local_adapter=LocalAdapter(),
            receipt_writer=writer,
            replay_store=replay,
            consent_service=consent,
        )

    router = make_router(refusing=False)

    # 1. general: gate ALLOW (shape, class, tier, egress, cost) -> cloud.
    result = router.route(envelope("demo-general", ContentClass.GENERAL))
    show("general", delivered=result.delivered, provider=result.provider, attempts=result.attempts)

    # 2. adult_themed without consent: gate denies (consent_required), the
    #    external path dies pre-effect, the router degrades local.
    result = router.route(envelope("demo-adult-no-consent", ContentClass.ADULT_THEMED))
    show(
        "adult_themed (no consent)",
        delivered=result.delivered,
        provider=result.provider,
        attempts=result.attempts,
    )

    # 3. adult_themed with a valid, envelope-bound consent token:
    #    gate ALLOW, replay consumed before the effect, cloud delivers.
    env = envelope("demo-adult-consent", ContentClass.ADULT_THEMED)
    token = consent.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
    result = router.route(env, consent_token=token)
    show(
        "adult_themed (consent)",
        delivered=result.delivered,
        provider=result.provider,
        attempts=result.attempts,
    )

    # 4. adult_themed refused by the provider's content policy: an advisory
    #    refusal receipt, then reroute to the local path. A separate router
    #    instance models the same provider after its policy change — the
    #    refusal reroutes, it never blocks.
    refusing_router = make_router(refusing=True)
    env = envelope("demo-adult-refused", ContentClass.ADULT_THEMED)
    token = consent.issue(env.envelope_hash, "approver:human", ttl_seconds=300)
    result = refusing_router.route(env, consent_token=token)
    show(
        "adult_themed (provider refusal)",
        delivered=result.delivered,
        provider=result.provider,
        attempts=result.attempts,
    )

    # 5. explicit: the policy denies egress outright — the plan is local
    #    only and no external attempt is ever started.
    result = router.route(envelope("demo-explicit", ContentClass.EXPLICIT))
    show("explicit", delivered=result.delivered, provider=result.provider, attempts=result.attempts)

    # 6. The essential no-cloud path: zero cloud adapters configured,
    #    text-first delivery still works.
    essentials = EssentialsPath()
    env = envelope("demo-essential", ContentClass.EXPLICIT)
    essential = essentials.deliver(env)
    print(
        f"essentials (no cloud configured): delivered={essential.delivered} "
        f"text={essential.text!r}"
    )

    # 7. Evidence: the full chain recomputes from genesis.
    ok, broken_at = verify_chain(receipts_path)
    print(f"receipt chain verified: {ok}" + ("" if ok else f" (broke at line {broken_at})"))
    with open(receipts_path, "r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            body = record["body"]
            print(
                f"  #{body['sequence']} {body['decision']:<5} "
                f"class={body['content_class']:<13} route={str(body['route']):<10} "
                f"reason={body['reason']} hash={record['receipt_hash'][:16]}..."
            )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
