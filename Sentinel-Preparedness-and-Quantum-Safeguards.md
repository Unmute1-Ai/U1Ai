# U1 Sentinel: Preparedness and Quantum Safeguards

Version 0.1 | 2026-09-09 | Coverage specification and evidence plan

## Status and scope

This report maps all three Tracked Categories, all five Research Categories, and the evaluation, safeguard, security, and governance processes of OpenAI’s Preparedness Framework v2 (April 15, 2025). Quantum security and product-specific controls are U1 extensions, not categories attributed to OpenAI. This is a specification, not certification or a completed evaluation. No Sentinel source code, deployment, cryptographic implementation, or benchmark was tested for this report. Prior reported results require their original artifacts and reproducible execution before acceptance.

Coverage means every identified area has a requirement and evidence path; it does not mean all possible risks have been discovered or eliminated. Baseline is the supplied v2 document, without asserting it is the latest OpenAI framework.

## 1. Framework coverage

All rows start UNVERIFIED. Mark a row VERIFIED only against identified evidence; use NOT APPLICABLE only with a documented rationale and review trigger.

| Category | Sentinel assessment and control requirement | Required evidence |
| --- | --- | --- |
| Biological and Chemical — tracked | Assess model assistance and access to external laboratory, procurement, or physical tools; gate sensitive capabilities and deny unapproved effects | Qualified evaluation with safe fixtures; tool-access inventory; misuse and autonomous-action cases |
| Cybersecurity — tracked | Measure end-to-end capability separately from containment; enforce exact target scope, budgets, and effect permissions | Authorized sandbox campaigns; independent state observations; both permitted and denied actions |
| AI Self-improvement — tracked | Separate model/code recommendations from authority to change weights, policies, builds, or deployment | Unauthorized update and self-promotion tests; signed change approvals; reproducible build provenance |
| Long-range Autonomy — research | Enforce cumulative time, action, compute, and spending limits across sessions and delegated agents | Multi-step tests, restart tests, distributed budget accounting, stop latency |
| Sandbagging — research | Check discrepancies between evaluation and deployment behavior; vary tasks and scaffolds; preserve uncertainty | Held-out tasks, multiple elicitation configurations, evaluator independence, raw results |
| Autonomous Replication and Adaptation — research | Control spawning, persistence, credentials, resource acquisition, and restart behavior | Unauthorized replication and shutdown-resistance tests in isolation; revocation across descendants |
| Undermining Safeguards — research | Protect policy, monitors, audit storage, and approval mechanisms against tampering and collusion | Adversarial policy-edit, monitor-disable, forged-approval, audit-erasure, and collusion scenarios |
| Nuclear and Radiological — research | Assess relevant informational and tool pathways with appropriate specialists and safe test materials | Documented applicability assessment, escalation ownership, scoped access tests |

The source framework focuses on severe frontier harms. U1 must additionally address ordinary privacy, accessibility, fraud, reliability, and physical-safety failures even when below those thresholds. Persuasion is outside v2’s tracked/research categories; product-level manipulation risks remain in scope here.

## 2. Cross-cutting safeguard coverage

| Surface | Requirement | Verification |
| --- | --- | --- |
| Identity and authorization | Bind caller, agent, tool, resource, action arguments, policy version, audience, issue/expiry times, and nonce to authenticated authorization | Cross-tenant, argument substitution, audience mismatch, expired/replayed token, clock rollback tests |
| Executor | Enforce permissions before effects; validate actual resource resolution; mediate every privileged route | Direct-tool bypass, alternate API, path/symlink, race, and confused-deputy tests |
| Delegation | Child authority is a subset of parent authority; inherited cumulative budgets and revocation | Multi-hop escalation, sibling credential reuse, parent revocation tests |
| Sensitive actions | Explicit independent approval where required, bound to the exact action; no agent self-approval | Forgery, mutation after approval, duplicate effect, approval expiry tests |
| Isolation and egress | OS permissions, network restrictions, filesystem separation, process limits, and credential isolation | Attempted boundary crossings and independent host/network observations |
| Prompt injection and memory | Treat retrieved instructions and tool output as untrusted; scope memory reads/writes; prevent unauthorized disclosure | Indirect injection, poisoned memory, cross-session and cross-user tests |
| Audit | Authenticated receipts, protected append-only retention, sequence checks, independently retained checkpoints | Editing, deletion, truncation, reordering, rollback, and checkpoint verification |
| Supply chain | Pin and verify dependencies, models, containers, firmware, and updates; maintain inventory and provenance | Tampered artifact rejection; rollback protection; reproducible package verification |
| Incident response | Detect, revoke, contain, preserve evidence, restore, and verify recovery | Revocation delay, containment success, recovery integrity, escalation exercises |
| Availability | Bounded queues, resource quotas, safe failure modes, offline policy, and backpressure | Resource exhaustion, network loss, power loss, monitor outage tests |
| Privacy | Minimize retention and disclosure; map every external destination and deletion path | Egress capture, logging inspection, deletion verification; embeddings alone are not a privacy proof |
| Accessibility | Accessible consent, status, errors, recovery, and emergency controls | Screen-reader, keyboard, contrast, reduced-motion, plain-language, and representative user testing |
| Wearables and robotics | Separate language-model proposals from actuator authority; independent limits and emergency stop | Simulation first; supervised hardware tests with defined force, speed, temperature, and stop limits |

Hash chains alone do not prevent an attacker who controls storage from rewriting history. External authenticated checkpoints and protected keys are part of the evidence design.

## 3. Quantum-security extension

### Cryptographic scope

NIST FIPS 203 specifies ML-KEM for establishing shared secret keys; FIPS 204 specifies ML-DSA signatures; FIPS 205 specifies SLH-DSA signatures. These are distinct functions. Key establishment must be integrated with authentication, key derivation, and authenticated encryption through reviewed protocols.

Proposed evaluation profiles: ML-KEM-768 for key establishment and ML-DSA-65 for signatures; assess SLH-DSA as an alternative signature family. These are candidates requiring deployment-specific review, not a claim of implemented or validated cryptography.

| Risk or requirement | Design requirement | Acceptance evidence |
| --- | --- | --- |
| Harvest-now, decrypt-later | Inventory long-lived sensitive data, network links, backups, and exposed key exchanges; prioritize migration by confidentiality lifetime | Complete crypto inventory with owner, data lifetime, algorithm, protocol, and migration state |
| Forged authority or updates | Authenticate envelopes, release manifests, policy updates, and audit checkpoints using the selected approved profile | Known-answer and interoperability tests; modified message, wrong key, invalid signature, and truncated input rejection |
| Downgrade and mixed deployments | Bind negotiated algorithms and protocol version to authenticated session state; prohibit silent fallback | Stripped PQ negotiation and legacy-only fallback attempts rejected where PQ is mandatory |
| Hybrid migration | Use a reviewed protocol construction; explicitly define which components must verify | Failure of either required component rejects the operation; no ad hoc concatenation or permissive OR logic |
| Key lifecycle | Separate signing and session keys; define generation, storage, rotation, revocation, compromise recovery, and destruction | Rotation/revocation drills, backup recovery, role isolation, key-exposure assessment |
| Randomness and implementation leakage | Use maintained cryptographic providers, adequate entropy, and implementation-specific side-channel review | Entropy failure handling, constant-time review where applicable, malformed-input and fault testing |
| Replay and rollback | Maintain durable replay protection and update monotonicity independent of algorithm strength | Restart/power-loss replay tests and old signed firmware/policy rejection |
| Edge feasibility | Measure full-protocol cost on each claimed device, including wearable and robotic targets | p50/p95/p99 latency, RAM, bandwidth, battery/energy, thermal load, and failure behavior |
| Crypto agility | Maintain algorithm identifiers, key versions, migration policy, and emergency replacement procedure | Controlled algorithm retirement with no silent downgrade or authority expansion |
| Validation claims | Distinguish standardized algorithms, correct implementations, and independently validated modules | Exact provider/version, test evidence, and applicable validation records before public claims |

Quantum-inspired annealing belongs in a separate optimization experiment: compare against classical baselines under equal budgets. It provides no cryptographic protection by itself. Quantum-computing hardware experiments require named hardware or simulator, reproducible jobs, and honest simulation labels. No claim of quantum advantage, entanglement-based agent messaging, or unconditional quantum security is established by this report.

## 4. Evaluation and evidence protocol

1. Record source commit, model identity, scaffold, tool versions, OS, hardware, crypto provider, policy digest, and deployment configuration.
2. Describe assets, actors, trust boundaries, misuse paths, autonomous failure paths, external exposure, and uncertainty.
3. Measure capabilities with appropriate elicitation and expert review; do not infer capability limits from refusals. Treat a one-time result as incomplete evidence about maximum capability.
4. Assess safeguards separately against each risk pathway. Include positive controls so an executor that denies everything cannot pass.
5. For every campaign, specify authorized targets, permitted effects, maximum calls, duration, concurrency, data handling, and stop conditions. Stop on unexpected out-of-scope effects.
6. Observe actual state and network effects independently of agent narratives and receipts. Preserve the full denominator and failures.
7. Repeat meaningful cases across model swaps, tool changes, restarts, concurrent requests, and offline operation. Verify authority invariants while allowing different model behavior.
8. Use external review for high-consequence claims and specialized categories. Record evaluator limitations and unresolved disagreement.

Required metrics: unauthorized effects / unauthorized attempts; authorized-action success / valid attempts; detection recall and false positives; containment and revocation latency; audit completeness; test coverage; crypto rejection counts; resource cost. Report confidence intervals when statistically justified, with assumptions. Zero observed failures is not proof of zero risk.

## 5. Decision gates and governance

Assign named owners before deployment: evaluation lead, security lead, product/accessibility lead, and accountable release decision-maker. The acting agent cannot approve its own scope expansion. Record independent review and escalation authority.

- Any observed unauthorized privileged effect, audit bypass, or required-crypto downgrade blocks the affected release until fixed and retested.
- Missing evidence remains UNVERIFIED; no fabricated pass rates or inherited claims across untested versions.
- Adopt the source distinction: High capability requires sufficiently effective safeguards before deployment; Critical capability also requires safeguards during development. The source table calls for halting further development until applicable Critical safeguard and security-control standards are specified.
- Define numerical latency, availability, privacy, and physical-safety limits for the actual deployment before execution; this report does not invent universal values.
- Evaluate residual and marginal risk, including accessible alternatives, without using competitors’ weaknesses to waive U1 controls.
- Reassess after model, tool, permission, crypto-provider, firmware, deployment, or threat-model changes; maintain periodic review and incident-triggered emergency review.
- Publish a capability report, safeguards report, limitations, reproducibility instructions, and appropriate external findings without disclosing secrets or sensitive exploit details.

## 6. Completion record

Coverage specification: COMPLETE for the supplied framework’s named categories and processes, plus the U1 extensions above.
Implementation review: NOT PERFORMED.
Sandbox campaign: NOT RUN.
Quantum implementation and hardware benchmarks: NOT RUN.
Deployment approval or certification: NOT ESTABLISHED.

Next execution dependency: identify the exact Glass Box source revision and authorized runnable environment, then populate this report with actual evidence. Preserve this specification as the baseline and version subsequent results.

## Sources

- OpenAI, Preparedness Framework v2, April 15, 2025, §§2–5 and Appendices A–C: https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf
- NIST, FIPS 203, ML-KEM: https://csrc.nist.gov/pubs/fips/203/final
- NIST, FIPS 204, ML-DSA: https://csrc.nist.gov/pubs/fips/204/final
- NIST, approval of FIPS 203/204/205: https://csrc.nist.gov/news/2024/postquantum-cryptography-fips-approved
- NIST, algorithm roles and SLH-DSA alternative: https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards
