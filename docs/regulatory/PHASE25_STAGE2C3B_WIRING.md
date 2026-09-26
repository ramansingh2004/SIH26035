# Phase 25 Stage 2C3B — Sections 1–5 dual policy wiring

Stage 2C3A introduced verified v1/v2 dispatch primitives. Stage 2C3B wires the
implemented Sections 1–5 evaluator paths to those primitives.

## Runtime wiring

The following procedure policies now accept either their existing v1 schema or
the corresponding parameterized v2 schema:

- Section 1 weighing;
- Section 2 temperature zero;
- Section 3 eccentricity;
- Section 4 discrimination;
- Section 4 sensitivity;
- Section 5 repeatability.

When a v2 policy is selected, the Stage 2C2 compatibility adapter resolves it
against the immutable instrument snapshot and procedure evaluation context.

Sections 1, 3 and 5 also use the Stage 2C3A compatible MPE resolver so a verified
`mpe_profile_set_v2` can be used without changing the exact Decimal comparison
mechanics.

## Fail-closed boundaries retained

Stage 2C3B does not silently approximate v2 constructs that the existing v1
evaluator mechanics cannot represent. The adapter still blocks:

- geometry-derived eccentricity position strategies;
- multi-load discrimination;
- multi-load sensitivity;
- Section 4 MPE-based mass expressions without an explicit MPE input.

Those cases remain for native-v2 evaluator work in Stage 2C3C.

## Compatibility

Existing v1 policy kinds remain registered and accepted. No v1 synthetic
fixture files are changed, so the full backend suite remains the regression
gate for legacy deterministic behavior.

## Regulatory safety state

Unchanged:

- candidate-v1 remains unverified;
- official `supported_test_codes` remains empty;
- no candidate rule is marked VERIFIED;
- no source digest or verifier evidence is fabricated;
- activation, approval, official report generation and issue gates are not
  weakened.
