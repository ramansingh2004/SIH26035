# Phase 25 Stage 7 — Verified registration / activation acceptance

## Engineering status

**STAGE 7 ACTIVATION-ACCEPTANCE INFRASTRUCTURE = COMPLETE**

The repository now has a dedicated trusted intake path for a future
`oiml_r76_2006/verified-v1` artifact.

This is deliberately different from claiming that the regulatory artifact is
already verified or activated.

## What Stage 7 implements

Before a production verified artifact can even be registered, the Stage 7
gate requires:

- immutable binding to the current `candidate-v1` configuration hash;
- immutable binding to the final verified configuration hash;
- controlled official-source SHA-256 records;
- exact REG-01 through REG-17 sign-off coverage;
- item-level sign-off for every rule, test definition and checklist item;
- verifier identity, role, organization, timestamp and evidence reference;
- explicit declaration that verification is independent of implementation;
- exact source clause and digest agreement between sign-off and encoded item;
- no unresolved parameters or rule blockers;
- complete 17-section catalog;
- complete verified Section 16 construction catalog;
- complete verified Section 17 checklist/applicability/evidence policy;
- supported test set exactly matching deterministic evaluator coverage;
- explicit per-test runtime procedure/observation schema selection;
- no synthetic/demo artifact;
- the existing `RuleSet.activation_blockers()` must also be empty.

## Registration lifecycle

`RuleRegistration` recognizes `oiml_r76_2006/verified-v1`, but the server loads
it only from the fixed trusted repository directory. No client path or
arbitrary file path is accepted.

If the external package is absent, incomplete, mismatched, synthetic, or
unsigned, registration fails closed with `RULESET_NOT_VERIFIED`.

If a verified artifact is eventually registered, the external verification
manifest hash is frozen into the ruleset validation summary. Subsequent
validate/activate actions must reload the same trusted artifact and the same
manifest hash.

A Stage 7 verified artifact must also pass the explicit validate action before
activation.

## Runtime schema activation

Existing candidate/demo behavior remains v1.

The external manifest records the intended procedure/observation schema for
every supported test, and the selected versions are persisted into the immutable
test-definition catalog.

For the current authoritative HTTP/domain workflow, Stage 7 accepts only v1
runtime selection. Candidate v2 schema registration remains non-authoritative
and is explicitly blocked by `V2_NOT_AUTHORITY_ENABLED`.

## Current regulatory state

The repository does **not** contain a completed
`stage7_verification_manifest.json` or a verified ruleset.

Therefore:

- independent regulatory sign-off: `PENDING`;
- verified artifact registration: `BLOCKED`;
- production activation: `BLOCKED`;
- Stage 8 authoritative walkthrough: `BLOCKED`.

This is the required safe state until an independent human/domain-expert
verification package is supplied.

## Completion boundary

`STAGE 7 ENGINEERING = COMPLETE`

does **not** mean:

`REG-01..REG-17 = VERIFIED`

and does **not** mean:

`verified-v1 = ACTIVE`.
