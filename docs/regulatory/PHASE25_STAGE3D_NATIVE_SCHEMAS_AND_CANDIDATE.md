# Phase 25 Stage 3D — native v2 schemas and controlled candidate encoding

Stage 3D closes the Sections 6–10 data-capture gap without changing the
Stage 3C fail-closed runtime boundary.

The new native v2 context/observation contracts cover zero return, creep,
stability of equilibrium, tilting, tare and warm-up. They retain information
that the legacy v1 schemas cannot faithfully represent, including post-switch
zero-return checks, creep temperatures, quantitative stability observations,
tilt zero-tracking state, separate tare-setting observations and warm-up
readiness/result-transmission state.

`phase25_stage3d_candidate.json` separately encodes the source-mapped REG-09
through REG-12 candidate facts. Every fact remains
`SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF`, has `activation_allowed=false`,
and uses source digests that remain pending controlled acquisition.

The Stage 3D candidate file is not loaded by the runtime RuleSet. Stage 3C also
continues to block v2 evaluator execution. Native evaluator mechanics and
independent test vectors are the next Stage 3 work.
