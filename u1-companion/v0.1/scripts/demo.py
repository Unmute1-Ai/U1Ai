"""Runnable example: route one envelope through the v0.1 policy vocabulary.

D1 placeholder — the full gate walkthrough (receipts, consent, provider
selection) lands with D2–D4. This script exercises only what exists today:
envelope construction, digest binding, and policy lookups. It performs no
external effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Runnable without installing: put the src layout on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from u1_companion import (  # noqa: E402  (path bootstrap must run first)
    ContentClass,
    RouteEnvelope,
    Tier,
    build_default_policy,
)


def main() -> int:
    policy = build_default_policy()
    print(f"policy: {policy.version}  hash: {policy.policy_hash}")

    for class_name, declared in [
        (ContentClass.GENERAL, Tier.LOCAL),
        (ContentClass.ADULT_THEMED, Tier.EXTERNAL),
        (ContentClass.EXPLICIT, Tier.EXTERNAL),
    ]:
        envelope = RouteEnvelope(
            request_id=f"demo-{class_name.value}",
            principal="user:demo",
            content_class=class_name,
            declared_tier=declared,
            payload={"text": "demo payload"},
            params={},
        )
        allowed, reason = policy.egress_decision(envelope.content_class)
        tier = policy.effective_tier(envelope.content_class, envelope.declared_tier)
        print(
            f"{envelope.request_id}: class={envelope.content_class.value} "
            f"tier={tier.name} egress={allowed} reason={reason} "
            f"envelope_hash={envelope.envelope_hash[:16]}..."
        )

    # Unknown classes deny at the policy: no route, no egress.
    print(f"mystery: egress_decision={policy.egress_decision('mystery')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
