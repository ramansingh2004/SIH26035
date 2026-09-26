# Phase 25 Stage 2D — controlled candidate artifacts for common rules + Sections 1–5

Stage 2D converts the Stage 2A clause transcript into machine-readable,
source-linked **candidate facts**.

This is deliberately not an authoritative ruleset.

## Files introduced

- `backend/app/compliance/candidate_stage2d.py`
- `backend/app/compliance/rules/oiml_r76_2006/phase25_stage2d_candidate.json`
- `docs/regulatory/phase25_stage2d_candidate_ledger.csv`
- `docs/regulatory/phase25_stage2d_vectors.csv`
- `backend/tests/test_phase25_stage2d_candidate_artifacts.py`

The runtime loader in `ruleset.py` is unchanged and does not read the Stage 2D
candidate JSON.

## Source scope encoded

The candidate bundle records source-mapped facts for:

- pinned R 76-1:2006 / R 76-2:2007 edition scope;
- Table 3 classification;
- Table 6 MPE plus the in-service multiplier;
- Section 1 weighing procedure;
- Section 2 temperature/no-load indication;
- Section 3 eccentricity;
- Section 4 discrimination;
- Section 4 sensitivity;
- Section 5 repeatability.

Every candidate fact carries:

- source ID;
- clause/page references;
- REG register ownership;
- explicit non-authoritative verification status;
- `activation_allowed=false`;
- runtime projection status and blockers.

## Important Stage 2D finding

The Stage 2B/2C parameterized engine is sufficient to represent some source
facts, but not the full source semantics for every Section 1–5 family.

The candidate ledger therefore keeps the following gaps explicit instead of
inventing regulatory behavior:

- classification still has no parameterized runtime policy;
- weighing needs conditional Min inclusion and MPE-transition generation;
- temperature needs declared/default range branching and conditional 5 °C
  sequence generation;
- eccentricity needs support-count-dependent load formulas, rolling-load facts,
  and verified geometry derivation;
- discrimination needs richer non-self-indicating/analog response semantics;
- sensitivity needs Max-dependent selection and `max(MPE, 1 mg)`;
- repeatability needs Max-dependent repetition selection, approximate-load
  semantics, and zero-setting/tracking state.

MPE Table 6 is structurally representable by `mpe_profile_set_v2`, but it still
remains candidate-only until evaluation-context mapping, source acquisition,
independent sign-off, and test-vector cross-check are complete.

## Candidate vectors

`phase25_stage2d_vectors.csv` contains developer-transcribed boundary and
derivation examples. They are useful regression inputs but are **not**
independent verification evidence.

A vector may only become regulatory acceptance evidence after a second person
independently checks:

1. source edition and clause;
2. numeric value;
3. boundary operator;
4. applicability/context;
5. expected result.

## Safety state after Stage 2D

Unchanged:

- `candidate-v1` stays unverified;
- `supported_test_codes` stays empty;
- runtime OIML YAML is untouched;
- no `Verification.status` becomes `VERIFIED`;
- controlled PDF SHA-256 values remain pending rather than fabricated;
- no candidate artifact is loaded by `load_ruleset()`;
- no activation, approval, official report-generation, or report-issue gate is
  changed.

## Next acceptance question

Stage 2D makes remaining schema gaps auditable. Those gaps must be closed or
explicitly resolved by independently verified policy design before Stage 2 can
produce an activatable Sections 1–5 ruleset.
