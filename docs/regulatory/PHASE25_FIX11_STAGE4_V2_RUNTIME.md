# Phase 25 Fix 11 — Stage 4 Native-v2 Verified Runtime

## Purpose

Executable-rule review exposed four rule slots that were intentionally restricted
to legacy v1 procedure policies:

- `SECTION11_VOLTAGE_PROCEDURE`
- `SECTION13_DAMP_HEAT_PROCEDURE`
- `SECTION14_SPAN_STABILITY_PROCEDURE`
- `SECTION15_ENDURANCE_PROCEDURE`

The v1 schemas require instrument-bound absolute values in places where the
controlled R 76 source uses relative/source-native semantics such as `e`, `Max`,
declared voltage, declared temperature, and MPE.

Fix 11 removes that engineering mismatch without supplying or auto-verifying any
regulatory values.

## Engineering changes

- adds explicit verified-v2 policy contracts for Sections 11, 13, 14 and 15;
- supports relative voltage targets and load requirements for Section 11;
- wires the existing Stage-4 native-v2 mechanics into production evaluator
  registrations while preserving the legacy v1 path;
- adds explicit runtime confirmation facts for source wording such as
  `near Max` and `approximately 50 % of Max`;
- exposes the v2 procedure kinds in the executable-rule review blueprint;
- bumps the four evaluator implementation identities so prior runtime-binding
  review is invalidated deterministically;
- keeps `candidate-v1` unactivated;
- adds no database migration;
- does not modify the seven Section-12 IEC/ISO evidence blockers.

## Regulatory boundary

This is an engineering/runtime fix only.

It does **not**:
- mark any review row `VERIFIED`;
- infer independent reviewer identity;
- activate `verified-v1`;
- convert missing IEC/ISO evidence into regulatory evidence;
- hard-code a final verified OIML policy.

After the patch passes tests, regenerate the external-review pack. The old
`06_runtime_schema_review.csv` and `07_executable_rule_review.csv` are stale
because implementation/runtime-binding identities and executable policy schemas
have changed.

## Required post-patch sequence

1. Run Ruff and targeted Fix 11 tests.
2. Run the full backend test suite against the isolated PostgreSQL test database.
3. Run `python -m scripts.verify_phase25_fix11`.
4. Re-export a fresh Phase 25 external-review pack.
5. Re-review `06_runtime_schema_review.csv`.
6. Rebuild `07_executable_rule_review.csv` against the new blueprint.
7. Keep the seven Section-12 external-standard rows unresolved until their
   controlled IEC/ISO evidence is available.
