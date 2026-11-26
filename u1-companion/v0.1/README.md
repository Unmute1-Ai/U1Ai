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

## Status (v0.1, complete: deliverables D1–D4)

The layer is complete for this milestone. What ships:

- `src/u1_companion/envelope.py` — frozen `RouteEnvelope`; canonical-JSON
  SHA-256 digest binds every decision to exact bytes.
- `src/u1_companion/policy.py` — frozen, versioned, hashable
  `RoutingPolicy`: content-class routing table (default-deny), tier ladder
  (`TIER_0_LOCAL < TIER_1_U1CONTROLLED < TIER_2_EXTERNAL`),
  `tier = max(policy, declared)`, per-provider cost budgets. Validated at
  construction; unknown classes deny.
- `src/u1_companion/gate.py` — the deterministic pre-effect check
  sequence (shape → class → tier → egress → consent → cost). Every denial
  terminates the path before any side effect; provider or evaluator
  output is never an input.
- `src/u1_companion/receipts.py` — hash-chained JSONL receipts and the
  consume-before-effect replay store (at-most-once; a crash requires a
  fresh evaluation, never a receipt retry).
- `src/u1_companion/consent.py` — signed, envelope-bound, single-use
  `ConsentToken` with per-approver tier ceilings; trusted-service
  issuance only, no public endpoint.
- `src/u1_companion/router.py` — policy-driven provider selection with
  explicit failover ordering; local is always last and never fails for
  content reasons.
- `src/u1_companion/providers/` — the fail-closed transport boundary,
  the no-cloud `LocalAdapter`, and a deterministic `MockCloudAdapter`
  (stub; no network, ever).
- `src/u1_companion/essentials.py` — the essential no-cloud path:
  text-first composition and delivery that never touches a cloud
  adapter, with zero external providers configured.

CI (`.github/workflows/u1-companion.yml`) runs the full pytest suite on
Python 3.10 and 3.12 plus the end-to-end demo on every push and PR that
touches `u1-companion/**`.

## Run

```bash
python -m pip install -e .
pytest -q
python scripts/demo.py            # end-to-end gate walkthrough
python scripts/demo.py evidence   # same, keeping the receipt chain on disk
```

The demo routes six envelopes through the full pipeline — cloud delivery,
gate denial to local failover, consent-gated cloud delivery, advisory
refusal rerouting, local-only egress, and the cloud-free essentials path
— then verifies the receipt chain. It performs no external effect and no
network I/O.

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
- **Consent issuance exists only as a trusted in-process service.** There
  is no public issuance endpoint, no key management, and no durable
  approval store — those are production hardening, later milestones.
- **Nothing here executes an external effect.** Every adapter is a stub
  or deterministic mock; no transport connects to a real vendor.
