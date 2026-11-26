# U1AI

**Engineering workspace for accessibility, edge intelligence, and accountable AI.**

[Portfolio](https://github.com/Unmute1-Ai/Unmute1ai#readme) · [Engineering](https://github.com/Unmute1-Ai/U1Ai#readme) · [Security evidence](https://github.com/Unmute1-Ai/glass-box#readme)

U1AI connects the Unmute1AI architecture with its reference implementations. The current checked-in build track is **AEGIS-Q v0.1**, an embodied security scaffold for wearable, robotic, and multimodal sensing use cases.

## Start here

| Goal | Resource |
| --- | --- |
| Install the Ubuntu desktop foundation | [Unmute1AI OS 0.1](unmute1ai-os/) |
| Understand the portfolio | [Unmute1AI project directory](https://github.com/Unmute1-Ai/Unmute1ai#readme) |
| Explore the reference implementation | [AEGIS-Q v0.1](aegis-q/v0.1/) |
| Run the reference demo | [AEGIS-Q setup](aegis-q/v0.1/README.md) |
| Review the governed provider adapter layer | [u1-companion v0.1](u1-companion/v0.1/) |
| Review release requirements | [Production readiness](PRODUCTION_READINESS.md) |
| Review safeguard requirements | [Preparedness and quantum safeguards](Sentinel-Preparedness-and-Quantum-Safeguards.md) |
| Inspect evaluation evidence | [Glass Box](https://github.com/Unmute1-Ai/glass-box) |

## AEGIS-Q status

The v0.1 source is present on the default branch. It produces advisory security states and action proposals. The reference build excludes real physical actuation, financial transactions, health-system writes, destructive actions, and official emergency alerts.

NVIDIA, TensorRT, CUDA, Jetson, and cuPQC interfaces are integration targets or contracts; this scaffold does not demonstrate those runtimes or a deployed post-quantum security system.

## u1-companion status

The v0.1 provider adapter layer ([u1-companion/v0.1](u1-companion/v0.1/)) is present on the default branch. It routes content-class envelopes through a deterministic pre-effect gate (shape, class, tier, egress, consent, cost), issues signed consent grants, and records every decision as a hash-chained receipt consumed before any effect. Providers are integrations, never authorities: a provider's availability, pricing, or content policy can reroute a request (ultimately to the local path), never change what a user may express.

Every adapter in this build is a stub or deterministic mock — no live vendor integration exists, and the essential text-first path runs with zero external providers configured.

## Design principle

> Model capability can change. Principal authority does not.

Perception and reasoning can propose actions. A separately enforced authorization boundary must decide whether an action may execute. Model confidence and evaluator scores do not grant permissions.

## Contributing

Identify the component and the behavior you want to improve. Include reproduction steps for bugs and evidence for changes to security or performance claims. Consult the subproject's setup and readiness documentation before proposing deployment.

---

**Unmute1AI · Making every signal accessible to all.**
