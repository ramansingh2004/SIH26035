# Phase 26 Stage 2 — Typed Runs for Sections 1–15

Stage 2 introduces a new run-ready synthetic artifact while preserving the
Stage 1 V1 artifact unchanged.

## New artifact

- Artifact: `sih26035_full_flow_demo_v2`
- Version: `SYNTHETIC_TEST_SIH26035_FULL_FLOW_V2`
- Status: synthetic/demo-only, never authoritative, never activatable

## Stage 2 behavior

The run-ready artifact still produces all 28 applicability slots across all
17 sections.  The existing confirmation workflow now has enough information to
create exactly 23 typed executable leaf runs across Sections 1–15.

Stage 2 pins every executable test to:
- a real evaluator procedure variant,
- an explicit procedure schema version,
- an explicit observation schema version,
- a synthetic evaluator registration.

Section 1 is changed only in V2 to `EACH_RANGE` applicability because the
existing run initializer requires an explicit range.

Sections 16 and 17 remain specialized construction/checklist workflows and do
not receive numeric `TestRun` records.

## Safety boundaries

Stage 2 does not:
- change production OIML rules,
- activate a synthetic ruleset,
- permit synthetic official reports,
- fabricate observations or results,
- complete Sections 16/17,
- add a migration,
- change frontend code.

## Validation

From `D:\SIH\sih26035\backend`:

```powershell
uv run ruff check `
  app/compliance/demo.py `
  app/compliance/full_demo.py `
  app/services/rulesets.py `
  app/services/testing.py `
  scripts/verify_phase26_stage2.py `
  domain_tests/test_phase26_stage2_run_creation.py `
  tests/test_phase26_stage2_contract.py

uv run pytest -q `
  domain_tests/test_phase26_stage1_full_demo.py `
  domain_tests/test_phase26_stage2_run_creation.py `
  tests/test_phase26_stage1_contract.py `
  tests/test_phase26_stage2_contract.py `
  tests/test_phase23_stage2_contracts.py

uv run python -m scripts.verify_phase26_stage2
```

Expected final line:

```text
Phase 26 Stage 2 acceptance: PASS
```
