# Phase 26 Stage 6 — Full 17-Section Demo Session Closure

Stage 6 turns the V3 static execution matrix into one persisted end-to-end
software demonstration.

## One-click flow

`POST /api/v1/test-sessions/{id}/demo-complete-evaluation`

Starting from a fresh V3 session in `TESTING`, the guarded action:

1. materializes all 23 persisted Sections 1–15 run inputs;
2. creates 92 typed observation rows;
3. creates 23 synthetic environment readings;
4. creates 24 synthetic equipment/run links;
5. creates 23 metadata-only run-evidence records;
6. creates 2 metadata-only calibration-evidence records;
7. invokes the existing evaluator capture/evaluate path for all 23 runs;
8. completes each run through the existing completion path;
9. enters `EXAMINATION` through the existing construction service;
10. completes Section 16 through Stage 4;
11. completes Section 17 through Stage 5;
12. verifies all 17 persisted sections and the session aggregate to
    `COMPLETE + COMPLIANT`.

## Safety/governance boundary

The action is restricted to:
- V3 synthetic artifact;
- `SIH26035-DEMO` laboratory;
- `evaluation_context=SYNTHETIC`;
- a fresh `TESTING` session;
- an actor holding all normal testing/construction/checklist permissions.

It deliberately stops in `EXAMINATION`. It does **not** submit technical review,
perform approval, satisfy the independent-human production gate, or create an
official report.

All Stage 6 evidence is `synthetic_demo=true` and `metadata_only=true`.

No database migration is added.
