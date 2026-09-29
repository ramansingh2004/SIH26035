# Phase 26 Stage 1 — Full 17-Section Synthetic Applicability / RuleSet

Stage 1 adds one immutable synthetic ruleset that can drive the complete SIH
17-section walkthrough without claiming regulatory authority.

It adds trusted artifact `sih26035_full_flow_demo_v1`, keeps the artifact
synthetic/demo-only, forces the demo applicability plan to REQUIRED while
preserving the existing range/scenario/procedure identities, preserves the
Section 16 construction catalog and Section 17 checklist catalog, and adds
focused tests plus an acceptance verifier.

Stage 1 does not create runs, observations, results, approvals, reports, a
database migration, or frontend changes.

Validation:

```powershell
cd D:\SIH\sih26035\backend

uv run ruff check app/compliance/demo.py app/compliance/full_demo.py app/services/rulesets.py scripts/verify_phase26_stage1.py domain_tests/test_phase26_stage1_full_demo.py tests/test_phase26_stage1_contract.py

uv run pytest -q domain_tests/test_phase26_stage1_full_demo.py tests/test_phase26_stage1_contract.py

uv run python -m scripts.verify_phase26_stage1
```

Expected:

```text
Phase 26 Stage 1 acceptance: PASS
```

