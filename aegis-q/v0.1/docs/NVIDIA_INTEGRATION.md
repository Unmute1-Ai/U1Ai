# NVIDIA Integration Contract

AEGIS-Q v0.1 does not claim a deployed NVIDIA runtime. NemoClaw can supply an
agent proposal through an application-selected client, but the agent remains a
reasoning component. It never receives execution authority from its model,
runtime, policy score, or confidence value.

```text
Evidence-backed request -> configured NemoClaw client -> untrusted proposal
                                              -> Glass Box evidence verifier
                                              -> U1 Sentinel authorization
                                              -> separately bounded effect adapter
```

## NemoClaw proposal boundary

`aegis_q.nemoclaw_adapter.request_nemoclaw_proposal` accepts a client whose
`propose(request, *, deadline_monotonic=...)` method returns a mapping. This
deliberately avoids assuming a NemoClaw agent variant or an undocumented runtime
API. Configure the transport for the chosen NemoClaw variant outside AEGIS-Q,
with tools/effectors disabled or independently bounded. The client response
must contain exactly `action`, `parameters`, `model_id`, `confidence`, and
`evidence_refs`.

The caller must provide `timeout_seconds` in the range `(0, 30]`. The boundary
turns it into one absolute deadline from the process's monotonic clock and
shares that deadline with the client and verifier. The client must enforce it
across connection, response, and retry work, raise `TimeoutError` when the
budget expires, and reject late results. Do not send the monotonic timestamp
over the network; convert the remaining budget to the selected transport's
timeout settings. This boundary cannot interrupt a non-cooperative synchronous
client, so an unbounded client does not satisfy the contract.

Supply an `evidence_verifier(ref, scope)` backed by the existing Glass Box
evidence store. For every reference it must check authenticity, provenance, and
exact equality with `scope.request_sha256`, `scope.action`,
`scope.parameters_json`, and `scope.action_digest`; it must also honor
`scope.deadline_monotonic` and raise `TimeoutError` on expiry. A model-provided
reference string by itself is not evidence. The request must be JSON data and
is canonicalized before sending; the reference and parameters are bounded in
size. Missing or mismatched receipts, deadline expiry, transport failures,
malformed output, or invalid numeric values return `DENY` without a proposal.
The adapter recomputes a canonical SHA-256 digest over the request digest,
action, parameters, and evidence references.

For an admitted candidate, pass `result.proposal` to the existing Sentinel
authorization path. Bind any one-use authorization credential to that exact
digest, and have the effect adapter recompute it from `request_sha256`, the
proposal action, `parameters_json`, and `evidence_refs` immediately before
execution. The adapter itself never calls Sentinel with elevated credentials
and never dispatches an effect. A `PROPOSED` result means only that schema and
scope-bound evidence checks passed; Sentinel must still decide.

## NVIDIA edge runtime track

```text
Sensor adapters -> CUDA preprocessing -> TensorRT AEGIS-Q engine
                -> threat/action proposal -> U1 Sentinel
                -> verified device/action envelope -> simulated effect adapter
```

Hardware target: Jetson Thor. Required production checks remain: signed model
artifact digest, TensorRT engine digest, CUDA/cuPQC runtime provenance, device
attestation, ML-DSA signature verification, ML-KEM session binding, and
single-use credential consumption. These are requirements, not claims that the
reference environment currently implements or verifies them.
