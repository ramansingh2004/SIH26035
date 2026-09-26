# Phase 25 Stage 2C1 — v2 policy dispatch plumbing

Stage 2B introduced parameterized v2 policy schemas. Stage 2C1 makes those
schema kinds visible to the deterministic engine's regulatory dependency and
evaluator-registration layers while preserving all existing v1 registrations.

## Runtime changes

The regulatory supported-kind allow-list now recognizes:

- `mpe_profile_set_v2`
- `weighing_procedure_v2`
- `temperature_zero_procedure_v2`
- `eccentricity_procedure_v2`
- `discrimination_procedure_v2`
- `sensitivity_procedure_v2`
- `repeatability_procedure_v2`

The Sections 1–5 evaluator registrations now advertise both their existing v1
schema and the corresponding v2 schema.

## Important boundary

Stage 2C1 is dispatch plumbing only.

Existing evaluator mechanics still resolve their v1 policies. Stage 2C2 will
add deterministic v2-to-resolved-policy adapters and synthetic v2 execution
contracts. Keeping this split prevents a large simultaneous change from hiding
regressions.

## Regulatory safety state

Unchanged:

- candidate-v1 remains DRAFT;
- official rule YAML is not promoted;
- `supported_test_codes` remains empty;
- no rule is marked VERIFIED;
- no source digest or independent sign-off is fabricated;
- no activation/report gate is weakened.
