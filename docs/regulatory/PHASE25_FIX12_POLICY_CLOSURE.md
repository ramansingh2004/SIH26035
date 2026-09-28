# Phase 25 Fix 12 — Policy Expressiveness and Runtime Closure

Fix 12 addresses the seven policy/runtime limitations identified after Fix 11:

- SECTION1_PROCEDURE
- SECTION2_TEMPERATURE_ZERO_PROCEDURE
- SECTION3_PROCEDURE
- SECTION4_DISCRIMINATION_PROCEDURE
- SECTION4_SENSITIVITY_PROCEDURE
- SECTION5_PROCEDURE
- SECTION8_TILTING_PROCEDURE

The change is engineering capability, not regulatory signoff.

A generic numeric selector now supports exact comparison operators over selected
Max, Min/e, support count, and declared temperature bounds. This permits
source-defined conditional branches without epsilon tricks or instrument-specific
constants.

Eccentricity can resolve declared runtime positions for ordinary, >4-support,
special-receptor and rolling-load strategies. Rolling directions remain explicit
verified policy data; positions remain runtime geometry facts.

The existing native Section-4 resolver can already execute multi-load analog and
digital discrimination. Fix 12 makes the remaining capacity branches selectable.

Tilting no longer routes verified v2 policy to the deliberate Stage-3 block.
Relative loads are resolved from explicit instrument/test-plan facts or the
verified MPE profile. Missing facts fail closed.

Fix 12 does not:
- mark review rows VERIFIED;
- decide reviewer identity/independence;
- resolve RETEST_SELECTION;
- supply missing IEC/ISO evidence;
- activate candidate-v1;
- alter the seven Section-12 external-standard blockers.

Because parameterized.py belongs to the conservative runtime-binding core, all
23 rows of 06_runtime_schema_review.csv must be regenerated/re-reviewed after
Fix 12. 07_executable_rule_review.csv must also be re-exported against the new
schemas.

No database migration is required.
