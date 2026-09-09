# Evidence-linked update manifest — 2026-09-09

| Story | Evidence | U1 target | Delta | Authority impact |
|---|---|---|---|---|
| Google Finland AI infrastructure + nuclear PPA | https://blog.google/innovation-and-ai/infrastructure-and-cloud/global-network/clean-energy-finland/ | AnnealMesh, BriefOps | Added region + energy/carbon descriptors for compute routing. | None |
| OpenAI + Samsung next-gen chips | https://www.reuters.com/world/asia-pacific/openai-says-working-with-samsung-next-generation-chips-deepening-cooperation-2026-09-09/ | Sentinel, AuthorityBench | Model provenance can record hardware family/attestation. Hardware identity cannot grant authority. | None |
| Cognition AI $2B Series E | https://www.reuters.com/technology/cognition-ai-raises-2-billion-48-billion-valuation-2026-09-08/ | BriefOps | Competitive/funding signal only. **No product/security code change.** | None |
| IBM/RIKEN/Cleveland Clinic quantum-HPC protein simulation | https://www.ibm.com/quantum/blog/gordon-bell-finalists-2026 | AnnealMesh, AuthorityBench | Added hybrid-classical peer; `verified_advantage=true` requires evidence. | None |
| Google Workspace voice features | https://blog.google/products-and-platforms/products/workspace/voice-features-gmail-docs-keep/ | OmniSign, SIGNAL, PRIMER, Sentinel | Added voice-intent normalization while rejecting raw audio retention. Cross-domain effects still require Sentinel authorization. | None |

## Non-negotiable security invariants

1. A model, hardware platform, inspector, agent, or component cannot grant itself authority.
2. Sensitive cross-domain transitions require explicit consent.
3. Consequential effects require a scoped, single-use credential.
4. Physical live effects require prior simulation verification; this build executes no real physical effects.
5. Accessibility normalization retains intent, not raw sensor material.
6. Receipt evidence is SHA3-256 hash-linked and Ed25519 signed.
