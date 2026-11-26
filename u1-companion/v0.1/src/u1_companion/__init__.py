"""U1 Adult Companion provider adapter layer (v0.1).

Trust stance: providers are integrations, never authorities. Deterministic
U1 policy owns every allow/deny decision; a provider's availability, pricing,
or content policy can add a denial (advisory rerouting) but never lift one.

"Model capability can change. Principal authority does not."

This v0.1 slice (deliverable D1) ships the vocabulary the rest of the layer
is built on:

- ``envelope`` — the frozen, hash-bound request envelope every decision
  is attached to.
- ``policy`` — the frozen, versioned, hashable content-class routing policy.

Not present yet (later deliverables): the pre-effect gate, hash-chained
receipts, consent tokens, the router, provider adapters, and the essential
no-cloud path. Nothing here performs any external effect.
"""

from u1_companion.envelope import (
    ContentClass,
    RouteEnvelope,
    Tier,
    canonical_json,
    sha256_hex,
)
from u1_companion.policy import (
    ClassRoute,
    PolicyValidationError,
    ProviderBudget,
    RoutingPolicy,
    build_default_policy,
)

__all__ = [
    "ClassRoute",
    "ContentClass",
    "PolicyValidationError",
    "ProviderBudget",
    "RouteEnvelope",
    "RoutingPolicy",
    "Tier",
    "build_default_policy",
    "canonical_json",
    "sha256_hex",
]
