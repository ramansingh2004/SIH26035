# Phase 25 Stage 3C1 — v2 policy-kind registration

Stage 3B introduced parameterized v2 policy contracts for Sections 6–10.
Stage 3C1 makes those policy kinds visible to the dependency gate and evaluator
schema registries while deliberately preserving the current v1 execution path.

Registered v2 kinds:

- `zero_return_procedure_v2`
- `creep_procedure_v2`
- `stability_equilibrium_procedure_v2`
- `tilting_procedure_v2`
- `tare_procedure_v2`
- `warm_up_procedure_v2`

MPE-dependent Sections 6.2, 8, 9 and 10 also advertise
`mpe_profile_set_v2` for the future compatible-MPE runtime path.

Stage 3C1 does not wire evaluators to v2, resolve semantic load targets, promote
candidate rules, activate test codes, or alter approval/report gates.
Independent sign-off remains mandatory.
