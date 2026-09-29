# Phase 26 Stage 3 — Complete Synthetic Evaluator Data Matrix

Stage 3 creates a **V3 software-exercise artifact** and a static dataset for all
23 executable evaluator leaves in Sections 1–15.

This is intentionally different from a real regulatory test program. Some R76
branches are mutually exclusive for a real instrument. V3 therefore exists only
to exercise the software end-to-end and must never be represented as an OIML
conclusion.

## Artifact

- `sih26035_full_flow_demo_v3`
- `SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3`
- evaluation context: `SYNTHETIC`
- 28 applicability slots
- 23 typed evaluator datasets
- 23 deterministic COMPLETE + COMPLIANT synthetic evaluations

The static runtime files are generated from the repository's already-tested
synthetic domain fixtures. Runtime loading itself does **not** import
`domain_tests`.

## Stage boundary

Stage 3 does not:
- populate database runs yet,
- create Section 16 construction responses,
- create Section 17 checklist responses,
- perform technical review or final approval,
- generate an official report,
- modify production regulatory rules,
- add a migration,
- change frontend code.

## Validation

From `D:\SIH\sih26035\backend`:

```powershell
uv run ruff check `
  app/compliance/demo.py `
  app/compliance/full_demo_execution.py `
  app/services/rulesets.py `
  app/services/testing.py `
  scripts/build_phase26_stage3_execution.py `
  scripts/verify_phase26_stage3.py `
  domain_tests/test_phase26_stage3_execution.py `
  tests/test_phase26_stage3_contract.py

uv run pytest -q `
  domain_tests/test_phase26_stage1_full_demo.py `
  domain_tests/test_phase26_stage2_run_creation.py `
  domain_tests/test_phase26_stage3_execution.py `
  tests/test_phase26_stage1_contract.py `
  tests/test_phase26_stage2_contract.py `
  tests/test_phase26_stage3_contract.py `
  tests/test_phase23_stage2_contracts.py

uv run python -m scripts.verify_phase26_stage3
```

Expected:

```text
Phase 26 Stage 3 acceptance: PASS
```
