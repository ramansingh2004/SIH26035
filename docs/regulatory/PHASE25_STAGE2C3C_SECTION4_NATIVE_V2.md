# Phase 25 Stage 2C3C — native Section 4 multi-load and MPE execution

Stage 2C3B wired Sections 1–5 to dual v1/v2 policy dispatch. The compatibility
adapter deliberately refused Section 4 policies that could not be represented
losslessly by the legacy single-load v1 shape.

Stage 2C3C adds a native parameterized execution path for those Section 4 cases.

## Added

- multi-load discrimination policies;
- multi-load sensitivity policies;
- per-test-load extra-load resolution;
- per-test-load response thresholds;
- MPE-based Section 4 mass expressions resolved against the selected load via
  the verified v1/v2 MPE dispatch from Stage 2C3A;
- explicit coverage validation requiring every v2 test load to be observed.

Existing v1 discrimination and sensitivity behavior is preserved.

## Eccentricity geometry remains fail-closed

The current parameterized eccentricity schema names strategies such as
`UP_TO_FOUR_SUPPORTS`, `MORE_THAN_FOUR_SUPPORTS`, `SPECIAL_RECEPTOR`, and
`ROLLING_LOAD`, but it does not yet encode independently verified rules for
deriving the exact required positions from geometry.

Stage 2C3C therefore does **not** invent those positions. Non-explicit
eccentricity strategies remain blocked by `PolicyResolutionError`.

This is intentional: implementing a guessed support/position formula would
silently turn an unverified interpretation into regulatory behavior.

## Regulatory safety state

Unchanged:

- candidate-v1 remains unverified;
- official `supported_test_codes` remains empty;
- no candidate rule becomes VERIFIED;
- no verifier identity, source digest, or evidence is fabricated;
- activation, approval and official-report gates remain unchanged.
