"""Provider adapters: sibling modules, no registry.

Each adapter is a plain module implementing the ``ProviderTransport``
protocol from ``base``; extension is by adding a sibling module (the
NemoClaw precedent — no plugin registry, no import-time registration).
Every adapter treats provider responses as untrusted data and never
dispatches effects beyond the single send the router asks for.
"""

from u1_companion.providers.base import (
    DECISION_DELIVERED,
    DECISION_FAILED,
    DECISION_REFUSED,
    ProviderRefusal,
    ProviderTransport,
    TransportResult,
    call_transport,
    validate_response,
)
from u1_companion.providers.local import LocalAdapter, PROVIDER_NAME as LOCAL_PROVIDER_NAME
from u1_companion.providers.mock_cloud import (
    DEFAULT_COST_PER_CALL,
    MockCloudAdapter,
    MockCloudConfig,
    PROVIDER_NAME as MOCK_CLOUD_PROVIDER_NAME,
)

__all__ = [
    "DECISION_DELIVERED",
    "DECISION_FAILED",
    "DECISION_REFUSED",
    "DEFAULT_COST_PER_CALL",
    "LOCAL_PROVIDER_NAME",
    "MOCK_CLOUD_PROVIDER_NAME",
    "LocalAdapter",
    "MockCloudAdapter",
    "MockCloudConfig",
    "ProviderRefusal",
    "ProviderTransport",
    "TransportResult",
    "call_transport",
    "validate_response",
]
