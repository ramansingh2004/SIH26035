# Phase 25 Stage 4 — Sections 11–15 — COMPLETE

Stage 4 covers the implementation groundwork for:

- Section 11 — voltage variation;
- Section 12 — electrical disturbances:
  - voltage dips / short interruptions;
  - burst;
  - surge;
  - electrostatic discharge;
  - radiated RF;
  - conducted RF;
  - road-vehicle supply disturbances;
- Section 13 — damp heat, steady state;
- Section 14 — span stability;
- Section 15 — endurance.

## Completion state

Stage 4 implementation groundwork is complete in three steps.

### Stage 4A — source mapping and engine-gap analysis

Completed:

- source-mapped Sections 11–15 against pinned OIML R 76 editions;
- recorded REG-12, REG-13 and REG-14 coverage;
- compared source-native requirements with the existing v1 engine;
- identified only the missing v2 semantics rather than replacing mature v1
  evaluators.

Stage 4A does not change evaluator runtime behavior.

### Stage 4B — v2 contracts, native mechanics and controlled candidate facts

Completed:

- parameterized v2 policy contracts;
- native v2 context/observation schemas;
- safe v1/v2 registration vocabulary;
- deterministic native mechanics using explicit caller-supplied limits;
- controlled non-authoritative candidate facts;
- ten synthetic mechanics vectors, one passing and one failing vector for each
  top-level Stage 4 family;
- fail-closed native-v2 dispatch boundary.

### Stage 4C — final acceptance

Completed:

- machine-checkable Stage 4 verification;
- explicit implementation-vs-regulatory-verification boundary;
- external verification/sign-off checklist;
- final regression acceptance entry point.

## Important distinction

`STAGE 4 IMPLEMENTATION WORK = COMPLETE`

does **not** mean:

`REGULATORY VERIFICATION = COMPLETE`

The following remain intentionally pending:

- controlled acquisition and approved digests of the pinned official sources;
- independent human/domain-expert verification of REG-12, REG-13 and REG-14;
- independent review of the Stage 4 mechanics vectors;
- verification of referenced IEC/ISO source identity/version details needed by
  Section 12 disturbance procedures;
- promotion of any candidate fact to `VERIFIED`;
- authoritative activation of Sections 11–15;
- official report authority.

Until those gates are satisfied, native-v2 Stage 4 execution remains
non-authoritative and fail closed.

The pinned runtime ruleset remains `candidate-v1`, and
`supported_test_codes` remains empty.
