# Phase 25 Stage 3B — parameterized policy contracts for Sections 6–10

Stage 3A identified where the existing v1 evaluator policies cannot faithfully
represent the source-mapped R 76 branches. Stage 3B introduces typed policy
contracts for those branches without wiring them into runtime execution.

## Added representation

`parameterized_stage3.py` adds:

- `Stage3Selector` for class/context/range/power/mobile/tilt facts;
- `LoadTarget`:
  - explicit mass;
  - Min/Max;
  - fraction of Max;
  - close-to-Max semantic target;
  - MPE-transition target;
  - function-operating-range target;
- `LimitTarget`:
  - absolute mass;
  - selected-range e;
  - explicitly selected range e;
  - MPE.

Policy families are provided for:

- zero return;
- creep with multiple alternative routes and route-specific criteria;
- stability of equilibrium including numeric output/accuracy requirements;
- tilting including MPE-transition loads and protection behavior;
- tare including relative tare scenarios and separate tare-setting accuracy;
- warm-up including pre-ready indication/transmission behavior.

## Fail-closed semantic targets

Stage 3B deliberately does **not** guess how to resolve source phrases whose
exact runtime derivation still needs verified policy or test-plan information.

`resolve_load_target()` therefore refuses:

- `CLOSE_TO_MAX`;
- `MPE_TRANSITION`;
- `FUNCTION_OPERATING_RANGE`.

Those targets can be encoded in a candidate policy without silently turning an
engineering interpretation into regulatory behavior.

Likewise, an MPE-based `LimitTarget` cannot resolve without an explicit MPE
value supplied by the regulatory MPE resolver.

## No runtime wiring yet

Stage 3B does not:

- register new policy kinds in evaluator dispatch;
- alter `regulatory.py`;
- alter Sections 6–10 evaluators;
- alter the candidate OIML YAML;
- mark any regulatory source VERIFIED;
- enable any official test code.

Runtime integration belongs to the next Stage 3 sub-stage after these schemas
are accepted.
