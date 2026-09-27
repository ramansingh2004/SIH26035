# Phase 25 Stage 7 — Verification and activation acceptance

Stage 7 is the handoff point between completed engineering groundwork and
external regulatory verification.

## Required external verification package

A production `verified-v1` artifact must contain the full immutable ruleset
files plus `stage7_verification_manifest.json`.

The manifest must bind:

1. the source `candidate-v1` configuration hash;
2. the final verified ruleset configuration hash;
3. the external evidence-package SHA-256;
4. controlled source acquisition records and SHA-256 values;
5. REG-01 through REG-17 independent sign-offs;
6. every rule/test/checklist item to its exact clause, digest, verifier and
   evidence reference;
7. the verified runtime schema version for every supported deterministic test.

## Independent-verifier rule

The manifest requires `independent_of_implementation = true` for source,
register and item sign-off records.

The system cannot prove organizational independence by itself. That
declaration must be backed by the external evidence package and governance
process. Developer notes, AI output, extraction scripts, screenshots and
synthetic test fixtures are not sufficient regulatory sign-off.

## Production acceptance gates

Production intake rejects:

- candidate-hash mismatch;
- verified-hash mismatch;
- source digest mismatch;
- missing source acquisition evidence;
- missing REG-01..REG-17 sign-off;
- missing item-level sign-off;
- unresolved rules/parameters/checklist applicability/evidence requirements;
- incomplete Section 16 or Section 17 catalogs;
- incorrect supported deterministic-test set;
- runtime schema versions not registered by the evaluator;
- synthetic/demo identity;
- any remaining normal activation blocker.

## Current outcome

The Stage 7 machinery is implemented and regression-testable.

The actual regulatory package remains absent, so registration/activation are
correctly blocked pending independent sign-off.
