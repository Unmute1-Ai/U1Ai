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

`aegis_q.nemoclaw_adapter.request_nemoclaw_proposal` accepts an object with a
`propose(request)` method. This deliberately avoids assuming a NemoClaw agent
variant or an undocumented runtime API. Configure the transport for the chosen
NemoClaw variant outside AEGIS-Q, with tools/effectors disabled or independently
bounded. The client response must contain exactly `action`, `parameters`,
`model_id`, `confidence`, and `evidence_refs`.

Supply an `evidence_verifier(ref)` backed by the existing Glass Box evidence
store. It must validate the referenced receipt's authenticity, digest, scope,
and provenance; a model-provided string by itself is not evidence. Missing or
invalid references, transport failures, malformed output, or invalid numeric
values return `DENY` without a proposal. The adapter recomputes a canonical
SHA-256 digest over the action, parameters, and verified evidence references.

For an admitted candidate, pass `result.proposal` to the existing Sentinel
authorization path. Bind any one-use authorization credential to that exact
digest, and have the effect adapter recompute it from `parameters_json` and
`evidence_refs` immediately before execution. The adapter itself never calls
Sentinel with elevated credentials and never dispatches an effect. A `PROPOSED`
result means only that schema and evidence-reference checks passed; Sentinel
must still decide.

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

