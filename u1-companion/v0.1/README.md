# u1-companion v0.1 — provider adapter layer

U1 Adult Companion's provider adapter layer: content-class routing policy,
pre-effect gate, consent, hash-chained receipts, and provider adapters.
Providers are **integrations, never authorities** — a provider's
availability, pricing, or content policy never determines what a user can
express. Deterministic U1 policy owns every allow/deny; a provider refusal
is an advisory rerouting signal only (it can add a denial, never lift one).

> Model capability can change. Principal authority does not.

The gate is consent, legality, and safety — not propriety. Adult vocabulary
and desire expression are default-complete in this layer's design contract;
content classes route differently, they are not refused for being adult.

## Status (v0.1, deliverable D1)

This slice ships the governance vocabulary the rest of the layer builds on:

- `src/u1_companion/envelope.py` — frozen `RouteEnvelope`; canonical-JSON
  SHA-256 digest binds every decision to exact bytes.
- `src/u1_companion/policy.py` — frozen, versioned, hashable
  `RoutingPolicy`: content-class routing table (default-deny), tier ladder
  (`TIER_0_LOCAL < TIER_1_U1CONTROLLED < TIER_2_EXTERNAL`),
  `tier = max(policy, declared)`, per-provider cost budgets. Validated at
  construction; unknown classes deny.

Later deliverables (same milestone): the pre-effect gate, hash-chained
receipts, consent tokens, the router with local failover, provider
adapters (stub/mock only), and the essential no-cloud path.

## Run

```bash
python -m pip install -e .
pytest -q
python scripts/demo.py
```

## What this does not claim

- **No live vendor integration exists.** Every provider in v0.1 is a stub
  or deterministic mock; no billing, no live calls, no network effects.
- **No real-time voice, creative generation, or companion UI** ships here.
- **The content-class classifier is caller-declared** in v0.1 and
  policy-floor-checked; automated classification is a later milestone.
  Until then the routing table enforces conservative floors and `explicit`
  is local-only by construction.
- **Receipts are single-process** (single-writer boundary); production
  needs process isolation.
- **Nothing here executes an external effect.** D1 contains no transport,
  no gate dispatch, and no provider call path at all.
