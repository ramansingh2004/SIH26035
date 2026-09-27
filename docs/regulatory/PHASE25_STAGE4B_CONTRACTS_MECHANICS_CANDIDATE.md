# Phase 25 Stage 4B — v2 contracts, mechanics and controlled candidate bundle

Stage 4B is the main implementation step for Sections 11–15.

Added:
- parameterized v2 policy contracts for voltage variation, all seven
  electrical-disturbance families, damp heat, span stability and endurance;
- native v2 context/observation schemas;
- deterministic native mechanics with explicit caller-supplied limits;
- a controlled candidate bundle for REG-12, REG-13 and REG-14;
- ten synthetic mechanics vectors, pass/fail for each top-level family;
- safe v1/v2 policy/schema registration;
- a fail-closed Stage 4 dispatch helper.

Existing v1 evaluator mechanics remain unchanged.

Every Stage 4 candidate fact remains
`SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF` with
`activation_allowed = false`.

The synthetic vectors remain `NON_AUTHORITATIVE_MECHANICS_ONLY` and
`PENDING_INDEPENDENT_REVIEW`.

The Stage 4 candidate bundle is not runtime-loaded and native-v2 authoritative
execution remains blocked until independent verification and activation.
