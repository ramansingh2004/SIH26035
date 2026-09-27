# Phase 25 Stage 3E — native v2 mechanics and independent-vector preparation

Stage 3D supplied lossless native v2 procedure/observation schemas for
Sections 6–10. Stage 3E adds the pure deterministic calculation layer that can
operate on those observations without embedding regulatory source constants.

## Mechanics implemented

### Zero return
- post-unload zero minus pre-load zero;
- optional post-switch zero measurement;
- comparison only when an explicit limit object is supplied.

### Creep
- arbitrary explicit checkpoint-to-checkpoint indication differences;
- total observed temperature variation;
- all limits are caller-supplied.

### Stability of equilibrium
- print/storage event-output minus final-weight-value;
- adjacent-value count as an explicit observed quantity;
- zero/tare accuracy error comparisons.

### Tilting
- pre-rounding indication;
- corrected error for loaded observations;
- tilted-reference difference;
- unloaded and per-load limits are supplied explicitly.

### Tare
- pre-rounding indication and corrected net-load error;
- gross minus (tare + net) identity delta;
- independent tare-setting error mechanics.

### Warm-up
- contemporaneous zero correction;
- loaded corrected error;
- pre-ready result indication/transmission represented as a deterministic
  0/1 mechanics value.

## Independent-vector preparation

`backend/tests/fixtures/phase25_stage3e_independent_vectors.json` contains
12 synthetic mechanics vectors:

- one passing vector and one failing vector for each of the six Stage 3
  families.

The vector file is explicitly marked:

- `NON_AUTHORITATIVE_MECHANICS_ONLY`;
- `PENDING_INDEPENDENT_REVIEW`;
- `regulatory_signoff = false`.

The threshold values in those vectors are test inputs only. They must not be
read as independently verified OIML values.

## Runtime boundary

Stage 3E does not import its mechanics module into `phase7.py`, `phase8.py`,
`tare.py`, or `stage3_dispatch.py`. The Stage 3C v2 block remains intact.
Authoritative v2 runtime wiring is deferred until verified rules, verified
semantic-resolution facts, and independent vectors are available.
