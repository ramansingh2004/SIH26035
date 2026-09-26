# Phase 25 — OIML R 76 Regulatory Verification

Phase 25 converts the existing candidate regulatory configuration into a
source-controlled, independently verified ruleset without weakening any of the
existing regulatory gates.

The authoritative target edition for this workstream is pinned as:

- OIML R 76-1:2006 (E) — metrological and technical requirements/tests;
- OIML R 76-2:2007 (E) — type evaluation report format.

The edition pin is deliberate. OIML currently has an active revision project
for R 76. Draft revision material is tracked as change intelligence only and
must never be mixed into the 2006/2007 ruleset.

## Non-negotiable verification rule

No source identified, clause mapped, parameter transcribed, or test vector
prepared by a developer, script, or AI is sufficient to change a rule to
VERIFIED.

A regulatory rule can become VERIFIED only after:

1. controlled acquisition of the official source;
2. source identity and cryptographic digest capture;
3. clause-level extraction of the requirement;
4. independent human verification of the encoded meaning;
5. recorded verifier identity, timestamp and evidence;
6. deterministic test-vector cross-checks;
7. activation-gate acceptance.

Until then the existing behavior remains:

- `TODO_REGULATORY_VALIDATION`;
- `REVIEW_REQUIRED` where required knowledge is unresolved;
- `UNDETERMINED` compliance outcome;
- candidate ruleset remains `DRAFT`;
- no official report issue from unverified regulatory data.

## Stage plan

### Stage 1 — Official-source inventory + clause-to-engine matrix

Status: IMPLEMENTED LOCALLY, VALIDATION PENDING.

Stage 1 establishes evidence and mapping only. It does **not** change regulatory
rules, evaluator mechanics, database schema, APIs, activation state, or report
gates.

Deliverables:

- `docs/regulatory/PHASE25_STAGE1_SOURCE_INVENTORY.md`;
- `docs/regulatory/phase25_clause_engine_matrix.csv`;
- `docs/regulatory/phase25_verification_register.csv`;
- Stage 1 contract tests.

### Stage 2 — Common rules + Sections 1–5

Target register coverage: REG-01 through REG-08.

### Stage 3 — Sections 6–10

Target register coverage: REG-09 through REG-12 as applicable.

### Stage 4 — Sections 11–15

Target register coverage: remaining REG-12, REG-13 and REG-14.

### Stage 5 — Sections 16–17

Target register coverage: REG-15.

### Stage 6 — Equipment/evidence/report semantics + independent test vectors

Target register coverage: REG-16 and REG-17, plus cross-section regression
vectors.

### Stage 7 — Verified artifact registration and activation acceptance

No activation occurs unless every required dependency passes the existing
activation blockers.

### Stage 8 — End-to-end authoritative evaluation walkthrough

Run a complete evaluation using only the activated verified artifact. Historical
candidate/demo sessions remain pinned to their original snapshots.

## Stage 1 acceptance

Stage 1 is accepted only when:

- all 17 top-level R 76 report sections are represented exactly once;
- all currently implemented evaluator codes are mapped to an official R 76
  report/test area;
- R 76-1 and R 76-2 official source identities are recorded;
- the current OIML revision project is explicitly isolated from the pinned
  edition;
- Indian legal-metrology sources are catalogued as national-context sources,
  not silently substituted for OIML clauses;
- REG-01 through REG-17 remain open and unverified;
- `candidate-v1` remains unchanged and non-activatable from Stage 1 output.
