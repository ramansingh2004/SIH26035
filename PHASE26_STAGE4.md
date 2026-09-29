# Phase 26 Stage 4 — Section 16 Construction Demo

Stage 4 completes the specialized **Section 16 Construction Examination** flow
for the V3 SIH software-demonstration artifact.

## What Stage 4 adds

- Uses the existing V3 synthetic ruleset; no V4 fork.
- Covers all 8 Section 16 construction categories.
- Adds a guarded one-click demo endpoint:
  `POST /api/v1/test-sessions/{id}/construction/demo-complete`
- Marks all 8 synthetic construction items `EXAMINED + PASS`.
- Creates one metadata-only synthetic evidence record per required item.
- Runs the normal Section 16 summarizer and aggregation path.
- Produces `COMPLETE + COMPLIANT` for Section 16.
- Adds a frontend button visible only for the V3 synthetic demo session.

## Safety boundary

The one-click action is accepted only when all of these are true:

1. the pinned ruleset is `SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3`;
2. the laboratory code is `SIH26035-DEMO`;
3. `evaluation_context == SYNTHETIC`;
4. the workflow is `EXAMINATION`.

Generated evidence is explicitly tagged `synthetic_demo=true` and
`metadata_only=true`. It is not an uploaded regulatory document, cannot make
the Stage 7 human signoff gate pass, and cannot enable official report issuance.

No database migration is added.
