# Phase 26 Stage 5 — Section 17 Checklist Demo

Stage 5 completes the specialized **Section 17 Conformity Checklist** flow for
the V3 SIH software-demonstration artifact.

## What Stage 5 adds

- Reuses the existing V3 synthetic ruleset.
- Covers all 27 pinned Section 17 checklist rows.
- All 27 V3 rows are VERIFIED, REQUIRED and evidence-required.
- Adds a guarded one-click demo endpoint:
  `POST /api/v1/test-sessions/{id}/checklist/demo-complete`
- Requires Section 16 to already be `COMPLETE + COMPLIANT`.
- Sets all 27 synthetic checklist responses to `PASS`.
- Creates one metadata-only synthetic evidence record per checklist row.
- Runs the existing ChecklistEngine completion and aggregation path.
- Produces `COMPLETE + COMPLIANT` for Section 17.
- Adds a frontend button visible only for the V3 synthetic demo session.

## Safety boundary

The one-click action is accepted only when all of these are true:

1. pinned ruleset is `SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3`;
2. laboratory code is `SIH26035-DEMO`;
3. `evaluation_context == SYNTHETIC`;
4. workflow is `EXAMINATION`;
5. Section 16 is already `COMPLETE + COMPLIANT`.

Generated evidence is tagged `synthetic_demo=true` and `metadata_only=true`.
It is not regulatory evidence, cannot satisfy the independent-human Stage 7
gate, and cannot enable official report issuance.

No database migration is added.
