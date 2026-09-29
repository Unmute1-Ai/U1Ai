# U1 Evidence Gate

A zero-dependency reference artifact for the U1 thesis:

**Signal -> Representation -> Interpretation -> Evidence -> Verification -> Authority -> Action**

## Falsifiability test

1. Run the default fixture. It should authorize.
2. Change `Provenance: recorded` to `Provenance: missing`.
3. Run verification again.
4. Confidence remains unchanged, but authority becomes **BLOCKED**.

The model score cannot grant authority.

This is a reference artifact, not a production-security claim. Production use requires authenticated provenance, cryptographic evidence, independent verification, policy evaluation, audit logging, and enforcement outside the model process.
