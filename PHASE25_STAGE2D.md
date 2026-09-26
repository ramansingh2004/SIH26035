# Phase 25 Stage 2D — Controlled Candidate Encoding

Status after apply: candidate artifacts present; independent verification still
pending.

Stage 2D does not promote regulatory data. It serializes the Stage 2A
source-mapped requirements into a typed candidate bundle and an explicit
projection-gap ledger.

Acceptance requires:

- focused candidate-artifact tests pass;
- full backend regression remains green;
- runtime `candidate-v1` metadata remains unchanged;
- `supported_test_codes` remains empty;
- all Stage 2D candidate facts keep
  `SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF`;
- all candidate vectors remain non-authoritative;
- no controlled source digest is invented.

Stage 2D is not equivalent to regulatory verification.
