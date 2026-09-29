# Phase 26 Stage 7 — Complete Simulated PDF/DOCX Report

Stage 7 adds the final evidence-rich SIH demonstration report without changing
the official reporting lifecycle.

## Source gate

The full demo report is available only for the V3 synthetic artifact after
Stage 6 has produced:

- workflow `EXAMINATION`;
- evaluation `COMPLETE`;
- compliance `COMPLIANT`;
- 17/17 REQUIRED sections `COMPLETE + COMPLIANT`;
- 23 completed compliant runs;
- 92 observations;
- 23 environment readings;
- 24 equipment links;
- 23 persisted results;
- 8 PASS construction items;
- 27 REQUIRED/PASS checklist responses;
- 60 unique synthetic evidence attachments;
- 85 immutable evidence links after the normal evaluator copies 25 source
  evidence references onto immutable result records.

## Output

The new endpoint is:

`POST /api/v1/test-sessions/{id}/full-demo-report-previews`

It creates the same immutable/expiring preview pair used by the controlled
preview subsystem:

- PDF
- DOCX

The full report contains:

- document control and demonstration declaration;
- laboratory, manufacturer and instrument identity;
- pinned synthetic ruleset declaration;
- all 17 section outcomes;
- equipment and environmental traceability;
- all 23 persisted test runs with observations and stored results;
- Section 16 construction examination;
- Section 17 checklist;
- evidence register;
- review/approval history;
- reproducibility manifest.

Every full-demo report is prominently labeled:

`SIMULATED / DEMONSTRATION REPORT - NOT AN OFFICIAL OIML CERTIFICATE`

## Isolation

Stage 7 does not:
- create a production `Report` record;
- create an official `ReportGeneration`;
- move the session to `UNDER_REVIEW` or `APPROVED`;
- satisfy the independent-human production gate;
- issue an official report.

The older compact Phase 25 simulated-approved report remains available and
unchanged for its original use case.

No database migration is added.
