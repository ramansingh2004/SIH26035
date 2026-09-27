# Phase 25 Fix 10 — verified-v1 Assembly Contract

The evaluator/runtime implementation remains unchanged. Fix 10 closes the
review-to-assembly integration gap discovered when exercising the first real
`verified-v1` build.

The old external-review pack reviewed only the seven placeholder candidate
rules. A production artifact needs the concrete rule identifiers consumed by
the evaluators and services.

Fix 10 therefore:

- derives the exact executable rule surface from the current evaluator registry;
- gives all catalog tests an explicit applicability-policy slot;
- includes all concrete evaluator-required rules;
- includes the service-level `RETEST_SELECTION` policy;
- includes eight structural Section 16 construction-rule slots;
- adds a separate India provenance dependency for the Section 1 standard-weight
  substitution branch;
- refuses v2 procedure-policy selection where the current evaluator still
  consumes only v1;
- exports `07_executable_rule_review.csv`;
- exports `08_final_regulatory_declaration.json`;
- validates those files fail-closed;
- adds `scripts.assemble_phase25_verified_v1`, which can only stage an artifact
  after the completed review pack has zero blockers and which then runs the
  actual Stage 7 production intake.

Fresh exports remain PENDING. No regulatory value, verifier identity,
independence declaration, source digest, signoff, or runtime choice is generated
by this fix.
