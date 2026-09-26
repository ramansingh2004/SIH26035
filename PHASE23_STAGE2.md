# Phase 23 Stage 2 — deterministic positive/negative SIH demo scenarios

Stage 2 adds a deliberately synthetic demonstration ruleset and two complete
demo scenarios without weakening the normal regulatory path.

## Safety boundaries

The demo artifact is:

- server allowlisted as `sih26035_demo_v1`;
- visibly identified as `SYNTHETIC_TEST_SIH26035_DEMO_V1`;
- restricted to laboratory code `SIH26035-DEMO`;
- kept in `DRAFT`;
- forbidden from activation;
- evaluated with a synthetic-marked evaluator registry;
- allowed to persist synthetic outcomes only inside the exact demo path;
- blocked from regulatory review/final approval;
- blocked from official report generation/issue;
- allowed to generate `UNOFFICIAL_PREVIEW`.

No candidate OIML rule is changed or marked verified.

## Demo scenarios

### SIH26035-DEMO-POSITIVE

- all 17 sections visible;
- Section 1 is the only REQUIRED synthetic demonstration assessment;
- Sections 2–17 are explicitly NOT_APPLICABLE for this synthetic scenario;
- deterministic result: `COMPLETE / COMPLIANT`;
- `synthetic_fixture=true`.

### SIH26035-DEMO-NEGATIVE

- same explicit applicability plan;
- one Section 1 demonstration observation exceeds the synthetic demo limit;
- deterministic result: `COMPLETE / NONCOMPLIANT`;
- failed-condition/calculation trace persisted;
- `synthetic_fixture=true`.

Neither outcome is an OIML regulatory conclusion.

## Validation before deployment

```powershell
cd D:\SIH\sih26035\backend

uv run ruff check .
uv run pytest tests/test_phase23_stage2_contracts.py -q
```

After the focused checks, run the complete backend suite against the isolated real
PostgreSQL `_test` database before deploying.

## Important

Do **not** run the live Stage 2 scenario seeder against the current Stage 1
production backend. The new Stage 2 backend behavior must first be committed,
pushed and deployed after explicit user instruction.

No migration is introduced by Stage 2.
