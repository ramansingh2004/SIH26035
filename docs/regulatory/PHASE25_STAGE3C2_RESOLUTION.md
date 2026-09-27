# Phase 25 Stage 3C2 — deterministic Stage 3 resolution layer

Stage 3B introduced typed policy targets such as `CLOSE_TO_MAX`,
`MPE_TRANSITION`, `LEVEL_INDICATOR_LIMIT`, and MPE-based limits. Stage 3C2 adds
a deterministic resolution boundary for those targets.

The core rule is simple: **a semantic target is not guessed**.

`Stage3ResolutionFacts` carries explicit inputs that later verified rules or a
frozen test plan may provide, including:

- resolved close-to-Max load;
- resolved function-operating-range load;
- explicit MPE-transition loads;
- level-indicator limiting tilt;
- automatic-sensor limiting tilt.

Without the necessary fact, resolution raises `PolicyResolutionError`.

MPE-based limits likewise require an explicit MPE from the existing compatible
MPE resolver; the Stage 3 resolution layer does not calculate or invent one.

Relative tare values are resolved only from the instrument's declared maximum
tare. Explicit loads, Min/Max, and fractions of Max are deterministic from the
frozen instrument snapshot.

Stage 3C2 still does not wire Sections 6–10 evaluators to v2 policies. It does
not change candidate OIML files, verification status, test activation, approval
or report issue.
