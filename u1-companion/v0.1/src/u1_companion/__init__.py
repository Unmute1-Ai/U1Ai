"""U1 Adult Companion provider adapter layer (v0.1).

Trust stance: providers are integrations, never authorities. Deterministic
U1 policy owns every allow/deny decision; a provider's availability, pricing,
or content policy can add a denial (advisory rerouting) but never lift one.

"Model capability can change. Principal authority does not."

This v0.1 slice ships (deliverables D1–D2):

- ``envelope`` — the frozen, hash-bound request envelope every decision
  is attached to.
- ``policy`` — the frozen, versioned, hashable content-class routing policy.
- ``gate`` — the deterministic pre-effect check sequence (shape, class,
  tier, egress, consent, cost); denials terminate the path pre-effect.
- ``receipts`` — hash-chained JSONL decision receipts and the
  consume-before-effect replay store.
- ``consent`` — signed, envelope-bound, single-use consent tokens with
  per-approver tier ceilings; trusted-service issuance only.

Not present yet (later deliverables): the router, provider adapters, and
the essential no-cloud path. Nothing here performs any external effect.
"""

from u1_companion.consent import ConsentIssuanceError, ConsentService, ConsentToken
from u1_companion.envelope import (
    ContentClass,
    RouteEnvelope,
    Tier,
    canonical_json,
    sha256_hex,
)
from u1_companion.gate import CostLedger, GateDecision, evaluate
from u1_companion.policy import (
    ClassRoute,
    PolicyValidationError,
    ProviderBudget,
    RoutingPolicy,
    build_default_policy,
)
from u1_companion.receipts import ReceiptBody, ReceiptWriter, ReplayStore, verify_chain

__all__ = [
    "ClassRoute",
    "ConsentIssuanceError",
    "ConsentService",
    "ConsentToken",
    "ContentClass",
    "CostLedger",
    "GateDecision",
    "PolicyValidationError",
    "ProviderBudget",
    "ReceiptBody",
    "ReceiptWriter",
    "ReplayStore",
    "RouteEnvelope",
    "RoutingPolicy",
    "Tier",
    "build_default_policy",
    "canonical_json",
    "evaluate",
    "sha256_hex",
    "verify_chain",
]
