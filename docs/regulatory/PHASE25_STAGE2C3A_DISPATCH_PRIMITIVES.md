# Phase 25 Stage 2C3A — dual v1/v2 regulatory dispatch primitives

Stage 2C2 proved that parameterized v2 policies can be deterministically
resolved into existing evaluator contracts where the conversion is lossless.

Stage 2C3A adds the regulatory dispatch primitives needed to let runtime
evaluators choose between a legacy v1 policy and a parameterized v2 policy
without weakening verification gates.

## Added runtime primitives

`rule_policy_variant(...)`

- resolves the existing verified rule dependency first;
- selects a schema only from an explicit caller-provided allow-list;
- returns the actual rule kind with the validated typed policy;
- rejects unrecognized kinds with `RegulatoryBlocked`.

`calculate_mpe_compatible(...)`

- accepts either `mpe_profile_v1` or `mpe_profile_set_v2`;
- for v2, resolves the exact class/evaluation-context profile;
- reuses the same exact Decimal MPE band comparison semantics;
- fails closed for missing/ambiguous profile coverage.

## Why this is separate from evaluator wiring

Sections 1–5 currently call their v1 loaders directly. Stage 2C3B will replace
those call sites with the compatibility dispatch plus the Stage 2C2 adapters.
Keeping the primitive and wiring stages separate makes failures easier to
isolate and preserves the already accepted v1 synthetic behavior.

## Regulatory safety state

Unchanged:

- candidate-v1 remains unverified;
- official `supported_test_codes` remains empty;
- no source digest, verifier identity, or evidence is fabricated;
- no activation, approval, report-generation, or report-issue gate is changed.
