# Phase 25 Stage 3C3A — resolved v2 execution contracts

Stage 3C2 created deterministic primitives for semantic Stage 3 targets.
Stage 3C3A composes those primitives into immutable resolved execution
contracts for Sections 6–10.

This stage covers:

- zero return;
- creep with multiple independent routes;
- stability-of-equilibrium function and accuracy rules;
- tilting with per-load MPE limits;
- tare with per-scenario/per-net-load limits;
- warm-up with a resolved loaded-error limit.

The resolver accepts only:

1. frozen instrument facts;
2. explicit `Stage3ResolutionFacts`; and
3. an explicit compatible-MPE callback when the policy limit is MPE-based.

No OIML constant is supplied by the resolver itself.

`CLOSE_TO_MAX`, MPE-transition loads, tilt limits and similar semantics remain
blocked unless the caller supplies the corresponding explicit fact.

Stage 3C3A still does not modify evaluator dispatch or runtime Sections 6–10.
That wiring is deferred until these resolved contracts are accepted.
Candidate regulatory data remains unverified and non-activatable.
