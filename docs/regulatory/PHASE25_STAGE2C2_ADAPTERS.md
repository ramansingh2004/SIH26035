# Phase 25 Stage 2C2 — deterministic v2 compatibility adapters

Stage 2C1 registered the new v2 policy kinds. Stage 2C2 adds a deterministic
compatibility layer that resolves parameterized v2 policies against an
immutable instrument snapshot and produces the existing v1 policy objects
where doing so is lossless.

## What is executable now

The adapter layer can deterministically resolve:

- Section 1 instrument-relative weighing loads;
- Section 2 declared/absolute temperature points;
- Section 3 explicitly mapped eccentricity positions and formula-driven load;
- Section 4 single-load discrimination;
- Section 4 single-load sensitivity, including an explicitly supplied MPE;
- Section 5 Max-relative repeatability series;
- class/evaluation-context MPE profile selection.

## Deliberate fail-closed boundaries

The adapter refuses to downgrade a v2 policy when existing v1 mechanics cannot
represent it without loss:

- geometry-derived eccentricity position strategies;
- multi-load discrimination;
- multi-load sensitivity;
- an MPE-based mass expression when the MPE value has not been supplied.

Those cases require native v2 evaluator handling in Stage 2C3. No guessed
position identifiers, loads or acceptance values are introduced.

## Schema corrections made in Stage 2C2

The Stage 2B v2 contracts are extended with data required for deterministic
execution:

- eccentricity gains minimum observation count, allowed receptor types and
  typed explicit positions;
- discrimination and sensitivity gain the common stabilization/evidence/
  equipment/timestamp requirements that their v1 mechanics already enforce.

## Regulatory safety state

Unchanged:

- candidate-v1 remains DRAFT;
- supported test codes remain empty;
- official rule YAML is not promoted;
- no rule becomes VERIFIED;
- no independent verifier identity/evidence is fabricated;
- official report and activation gates remain blocked.
