# Phase 25 Stage 3C — completion checkpoint

Stage 3C is complete as the safe dual-policy dispatch boundary for Sections
6–10.

Completed in Stage 3C:

- 3C1 — v2 policy-kind registration;
- 3C2 — deterministic semantic-target resolution;
- 3C3A — immutable resolved v2 contracts;
- final Stage 3C runtime boundary:
  - legacy v1 execution is preserved;
  - v2 policy kinds are recognized;
  - v2 is never silently coerced into v1;
  - until native v2 procedure/observation schemas exist, v2 runtime execution
    raises `RegulatoryBlocked`;
  - Stage-3 MPE consumers use compatible v1/v2 MPE resolution where applicable.

The v2 runtime gate is intentional because the current v1 observation models
cannot faithfully capture all source-mapped requirements, including
multiple-range zero-return behavior, creep temperature conditions, stability
numeric observations, tilting zero-tracking details, separate tare-setting
accuracy, and warm-up pre-ready behavior.

No candidate rule is VERIFIED or activatable merely because Stage 3C is
complete.
