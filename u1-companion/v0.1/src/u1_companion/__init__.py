"""U1 Adult Companion provider adapter layer (v0.1).

Trust stance: providers are integrations, never authorities. Deterministic
U1 policy owns every allow/deny decision; a provider's availability, pricing,
or content policy can add a denial (advisory rerouting) but never lift one.

"Model capability can change. Principal authority does not."

This v0.1 slice ships (deliverables D1–D3):

- ``envelope`` — the frozen, hash-bound request envelope every decision
  is attached to.
- ``policy`` — the frozen, versioned, hashable content-class routing policy.
- ``gate`` — the deterministic pre-effect check sequence (shape, class,
  tier, egress, consent, cost); denials terminate the path pre-effect.
- ``receipts`` — hash-chained JSONL decision receipts and the
  consume-before-effect replay store.
- ``consent`` — signed, envelope-bound, single-use consent tokens with
  per-approver tier ceilings; trusted-service issuance only.
- ``providers`` — the fail-closed transport boundary, the no-cloud local
  adapter, and a deterministic mock cloud adapter (stub only).
- ``router`` — policy-driven provider selection with explicit failover
  ordering; the local path is always the last resort.
- ``essentials`` — the essential no-cloud path: text-first composition
  and delivery that never touches a cloud adapter.

Every provider is a stub or a deterministic mock. Nothing here performs
any external effect.
"""

from u1_companion.consent import ConsentIssuanceError, ConsentService, ConsentToken
from u1_companion.envelope import (
    ContentClass,
    RouteEnvelope,
    Tier,
    canonical_json,
    sha256_hex,
)
from u1_companion.essentials import (
    EssentialResult,
    EssentialsPath,
    compose_essential_text,
)
from u1_companion.gate import CostLedger, GateDecision, evaluate
from u1_companion.policy import (
    ClassRoute,
    PolicyValidationError,
    ProviderBudget,
    RoutingPolicy,
    build_default_policy,
)
from u1_companion.providers.local import LocalAdapter
from u1_companion.providers.mock_cloud import MockCloudAdapter, MockCloudConfig
from u1_companion.receipts import ReceiptBody, ReceiptWriter, ReplayStore, verify_chain
from u1_companion.router import AttemptRecord, RouteResult, Router

__all__ = [
    "AttemptRecord",
    "ClassRoute",
    "ConsentIssuanceError",
    "ConsentService",
    "ConsentToken",
    "ContentClass",
    "CostLedger",
    "EssentialResult",
    "EssentialsPath",
    "GateDecision",
    "LocalAdapter",
    "MockCloudAdapter",
    "MockCloudConfig",
    "PolicyValidationError",
    "ProviderBudget",
    "ReceiptBody",
    "ReceiptWriter",
    "ReplayStore",
    "RouteEnvelope",
    "RouteResult",
    "Router",
    "RoutingPolicy",
    "Tier",
    "build_default_policy",
    "canonical_json",
    "compose_essential_text",
    "evaluate",
    "sha256_hex",
    "verify_chain",
]
