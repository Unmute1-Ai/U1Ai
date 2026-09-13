# U1 BriefOps v3.5 Evidence-Linked Update Manifest

Run date: 2026-09-13
Baseline: U1 Sentinel v3

## Security invariants retained
- Signed model provenance using SHA3-256 artifact digests.
- Component admission before runtime.
- No model, inspector, evaluator, or component may grant itself authority.
- Cross-domain authority gating with explicit consent for sensitive transitions.
- Scoped single-use credentials with replay denial.
- Physical simulation-before-live enforcement.
- Accessibility modality normalization without raw audio/video/biometric/sensor retention.
- AnnealMesh fabrication-maturity and verified-advantage descriptors.
- Ed25519 signatures over SHA3-linked effect receipts.

## Evidence to delta mapping

S1 — Anthropic safety / independent evaluation. Reuters, 2026-09-12. UPDATE: evaluator attestations may inform model admission but cannot grant authority. AuthorityBench adds an evaluator-self-authority denial regression. OmniSign, SIGNAL, PRIMER, AnnealMesh: NO CHANGE.

S2 — OpenAI agents and RubyGems. Reuters, 2026-09-11. UPDATE: software-supply-chain external writes are treated as sensitive, require explicit consent, and are destination-bound. AuthorityBench adds consent and destination regressions. OmniSign, SIGNAL, PRIMER, AnnealMesh: NO CHANGE.

S3 — Google / Mechanize talent deal. Business Insider, 2026-09-12. NO CHANGE: corporate staffing and acquisition activity is a market signal, not authority or capability evidence.

S4 — NVIDIA NVLink Fusion + d-Matrix Raptor. NVIDIA and d-Matrix, 2026-09-10. UPDATE: AnnealMesh pre-silicon/tapeout-pending backends require fabrication evidence and a distinct availability horizon. Hardware maturity remains authority-neutral.

S5 — quantum field-theory scattering simulation. Nature Physics, 2026-09-11. NO CHANGE: current AnnealMesh research-stage, benchmark-scope, and verified-advantage evidence fields already cover it.

## Product disposition
- OmniSign: NO CHANGE. Existing modality normalization and raw-sensor retention prohibition remain sufficient.
- SIGNAL: NO CHANGE. Receives normalized intent only.
- PRIMER: NO CHANGE. No evidence justifies expanded learner-data or action authority.
- Sentinel v3: evaluator self-authority prohibition; software-supply-chain external-write gate.
- AuthorityBench v3: five added regressions covering evaluator authority, supply-chain writes, and fabrication evidence.
- AnnealMesh: fabrication evidence plus availability horizon for immature hardware.
- BriefOps: five-source evidence manifest with explicit no-change decisions.

## Verification
21/21 local tests passed. External effects: 0. Destructive actions: 0. Real physical actions: 0. Financial transactions: 0. Health writes: 0. Official alerts: 0.

## GitHub publication note
Repository write permission was confirmed before publication. Runtime policy source upload was blocked by the platform safety layer, so this branch contains the evidence manifest and daily summary; the complete tested package is available as the accompanying downloadable artifact.
