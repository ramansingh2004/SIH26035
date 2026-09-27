# Phase 25 Stage 8 â€” Authoritative E2E Runbook

This runbook may be executed only after `scripts.verify_phase25_stage7` reports
that the verified artifact is ready.

## Preconditions

Before any authoritative run:

- use an isolated acceptance database;
- use the real private/versioned object-storage path intended for acceptance;
- preserve exact source/manifest hashes from Stage 7;
- use a non-demo laboratory;
- use real acceptance master data approved for the walkthrough;
- ensure LAB_TECHNICIAN/LAB_ENGINEER/REVIEWER/APPROVING_OFFICER permissions
  are assigned explicitly;
- do not use ADMIN as a substitute for final-approval authority;
- keep idempotency keys and ETags from the actual run;
- retain every generated evidence identifier/hash in the final evidence pack.

## Sequence

### A. Verified ruleset lifecycle

Register `oiml_r76_2006/verified-v1`, validate it, verify the validation summary
is authoritative and blocker-free, then activate it.

Record:

- ruleset ID;
- configuration hash;
- Stage 7 manifest hash;
- activation actor/time.

### B. Evaluation session

Create a new session against the ACTIVE verified ruleset and freeze the real
instrument configuration.

Run applicability preview and confirmation. Record the resulting requirement
set and confirm no required/elected slot remains `REQUIRES_REVIEW`.

### C. Sections 1â€“15

For every required/elected leaf requirement:

- start the run;
- capture the verified procedure context;
- capture typed observations;
- capture required environmental readings;
- link required calibrated equipment/certificate evidence;
- link required supporting evidence;
- evaluate;
- verify current deterministic result;
- complete the run.

When the verified rules require a retest:

- create a new retest run with reason;
- repeat required capture/evaluation;
- explicitly select the authoritative run;
- preserve selection/result-event history.

Do not invent a retest only to exercise the API if the verified rules do not
permit/require one. If no real retest is justified, document the N/A evidence
in the final acceptance pack.

### D. Sections 16â€“17

Start examination.

For Section 16, complete every verified construction item with its required
evidence and complete the construction examination.

For Section 17, answer every verified checklist row according to its resolved
applicability/evidence policy and complete the checklist.

### E. Review and approval

Verify the session is COMPLETE with a determined compliance outcome.

Submit for review.

A REVIEWER performs technical review.

An independently authorized APPROVING_OFFICER performs final approval. ADMIN
alone must not be used as a final-approval shortcut.

ADMIN alone must not be used as a substitute for final-approval authority.

Capture the immutable approval snapshot hash.

### F. Official reporting

Generate the official report from the approved snapshot.

Verify both canonical formats exist:

- PDF;
- DOCX.

The authenticated issuing actor must match the intended issuer frozen into the
generation context.

Issue through the REG-17 gate.

Record:

- report ID/number/revision;
- generation ID;
- report hash;
- PDF attachment/hash/object version;
- DOCX attachment/hash/object version;
- issue actor/time.

### G. Reproducibility checks

Verify:

- report files match stored SHA-256 values;
- approval snapshot remains immutable;
- registered ruleset remains immutable;
- session/result/run-selection history is preserved;
- report history/revision lineage is queryable;
- rerunning reads never recomputes authoritative compliance from mutable master
  data.

## Completion rule

Stage 8 may be marked authoritative COMPLETE only when the real run evidence
validates against `Stage8AuthoritativeRunRecord`.

A template containing `PENDING_STAGE7_EXTERNAL_SIGNOFF` is not evidence of an
authoritative run.
