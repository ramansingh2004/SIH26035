# Phase 24 — Final SIH polish acceptance

This is the final judge-facing acceptance checklist for SIH26035 after the deterministic
backend, review/report governance, production deployment, Phase 23 demo dataset, and
Phase 24 presentation polish are in place.

## Acceptance objectives

The final presentation must make five things obvious without weakening regulatory
boundaries:

1. **Where the user is in the workflow**
   - Dashboard onboarding explains the path from evaluation to review to reporting.
   - Workflow status, evaluation readiness and compliance outcome remain separate axes.

2. **How much evaluation work is covered**
   - The 17-section overview shows COMPLETE and explicit NOT_APPLICABLE coverage.
   - This percentage is presentation progress only; it is not a compliance score.

3. **Why a deterministic result looks the way it does**
   - Result panels show persisted calculation entries, acceptance criteria, failed checks,
     unresolved rule IDs, hashes and rule references.
   - The frontend does not calculate MPE or determine compliance.

4. **What is unofficial versus official**
   - Preview files are clearly identified as unofficial working artifacts.
   - PDF and DOCX preview downloads show source revision and expiry context.
   - Official generation remains separately gated by APPROVED + COMPLETE + determined
     outcome, and generation remains separate from issue.

5. **How the record remains traceable**
   - Evaluation history presents session revisions, review actions and correction requests
     as append-only history.
   - Issued report PDF/DOCX files are presented as artifacts of one immutable selected
     generation.

## Final judge walkthrough

Use the deployed application:

`https://sih26035.vercel.app`

Use the already-seeded Phase 23 demo laboratory:

`SIH26035-DEMO`

### A. Dashboard — explain the architecture in under one minute

Show the **Guided onboarding** block.

Explain:

> The system intentionally separates lifecycle, evaluation completeness and compliance
> outcome. A COMPLIANT deterministic result does not mean the record is approved or
> officially issued.

Point to the operational summary and recent activity.

### B. Candidate regulatory-safe path

Open either:

- `SIH26035-DEMO-NOMINAL`
- `SIH26035-DEMO-ADVERSE`

Show that the candidate rules remain blocked/undetermined.

Explain:

> Missing or unverified regulatory material is not filled by AI or guessed thresholds.
> The system keeps the record UNDETERMINED and exposes the blocker.

### C. Positive synthetic demonstration

Open:

`SIH26035-DEMO-POSITIVE`

Show:

- three status axes;
- 17-section readiness overview;
- Section 1 deterministic result;
- calculation entries;
- persisted acceptance criteria;
- hashes;
- traceability/history;
- unofficial preview workflow.

Say:

> This is a synthetic software demonstration fixture. The result demonstrates the
> deterministic engine path; it is not an OIML regulatory conclusion.

### D. Negative synthetic demonstration

Open:

`SIH26035-DEMO-NEGATIVE`

Show the same result explanation, this time including the persisted failed-condition
trace.

Explain:

> The opposite result is produced from different captured observations through the same
> deterministic path. No LLM participates in the compliance decision.

### E. Report preview

Create an unofficial preview.

Show:

- `UNOFFICIAL` / preview status;
- source regulatory revision;
- expiry;
- PDF download;
- DOCX download;
- official generation gate reason.

Explain:

> Preview is available for working review. Official report generation and report issue are
> separate governance actions.

### F. Traceability

Scroll to **Evaluation lifecycle history**.

Point to:

- session revision count;
- review event count;
- correction request count;
- append-only history statement.

Explain:

> Corrections and retests do not overwrite earlier evidence or decisions. The chain remains
> inspectable.

## Full local acceptance

From `frontend/`:

```powershell
npm run lint
npm run typecheck
node --test tests/phase24-stage1.test.mjs tests/phase24-stage2.test.mjs tests/phase24-stage3.test.mjs
npm run test
```

`npm run test` performs a production Next.js build followed by the complete frontend test
suite.

From the repository root:

```powershell
git diff --check
git status --short
```

The Phase 24 implementation is frontend/documentation-only. There should be no backend
migration or regulatory-engine change in the Phase 24 diff.

## Production acceptance after deployment

After the final Phase 24 commit is deployed to Vercel:

1. Login successfully.
2. Select `SIH26035-DEMO`.
3. Confirm Guided onboarding is visible on Dashboard.
4. Open `SIH26035-DEMO-POSITIVE`.
5. Confirm 17-section progress is visible.
6. Open Section 1 / selected run and confirm deterministic explanation is visible.
7. Create and download an unofficial PDF preview.
8. Confirm the official gate remains blocked for the synthetic scenario.
9. Open lifecycle history and confirm append-only traceability summary is visible.
10. Repeat the result view for `SIH26035-DEMO-NEGATIVE` and show failed checks.

Phase 23 already proved the backend production guards for synthetic official workflow.
Phase 24 acceptance therefore validates judge-facing presentation without introducing any
new regulatory bypass.

## Phase 24 completion criteria

Phase 24 is complete when:

- Stage 1/2/3 source-contract tests pass;
- full frontend lint/typecheck/build/test passes;
- working tree contains only the intended Phase 24 files before commit;
- final Phase 24 commit is pushed/deployed;
- the production judge walkthrough above passes.
