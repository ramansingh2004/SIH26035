# SIH26035 — Standalone R76 Rule Engine

Specification Freeze v1 — 2026-09-20. Normative architectural decisions: [DECISIONS.md](../DECISIONS.md), F02 and F05–F11. Regulatory content: [02-r76-tests.md](02-r76-tests.md), subject to its TODO_REGULATORY_VALIDATION register.

## 1. Independence

The compliance package receives immutable typed domain values and returns immutable deterministic output. It must not import FastAPI, Starlette, SQLAlchemy, database sessions, HTTPException, request/response types or application services. It does not query files, storage, users or networks during evaluation. Adapters/loaders prepare data outside the evaluation core.

Routes invoke application services; services obtain snapshots, map validated persisted values to domain types and invoke the engine. Persistence, permission, audit and lifecycle effects remain outside the engine. Reports and frontend consume stored outputs and never perform authoritative recalculation.

## 2. Canonical call and domain types

The contract is R76Engine.evaluate(test_code, instrument_snapshot, procedure_context, observations, ruleset). Named arguments are mandatory in eventual implementation; this document specifies a contract, not application source code.

| Input/type | Required content |
|---|---|
| InstrumentSnapshot | Class, exact Max/Min/e/d/n, all ranges, indication mode, power/temperature/tare/zero/tilt geometry, electronic/software/direct-sales/DSD/interface flags and construction facts required for applicability |
| ProcedureContext | Discriminator test_code + procedure_variant, procedure_schema_version, evaluation_context, range_no/scenario, selected test protocol, timings/stages, environment/equipment snapshots and test-specific severity/fault-response data |
| Observation collection | Typed test-specific immutable rows; unique sequence_no; measurement timestamps and typed mode/stage/position/direction data where applicable |
| RuleSet | Immutable standard parts/editions, semantic version, hash, supported tests, verified rules, source evidence and configuration |

Each protocol variant has a registered typed context schema; it is not an untyped free-form dictionary. No universal optional-field bag may stand in for required per-test metadata. Unsupported/missing schema versions are explicit validation errors; schemas are pinned per run. A run may contain only one observation_schema_version; migration of observations/context is explicit, audited and invalidates results.

The initial InstrumentSnapshot includes ranges even for single-range instruments. Multi-range/multi-interval evaluation explicitly selects a range and verifies transition rules; never silently use the top-level e for every range. Unknown applicability features cannot be defaulted to false. Negative indications/errors can be valid; distinguish them from invalid negative applied mass rather than banning all negative numeric values.

## 3. Registry and evaluator protocol

The registry maps test codes to evaluator implementations, input/context schemas and supported versions. Duplicate registration or unknown test code is rejected. Each evaluator provides structured applicability, procedure validation and evaluation. The engine first resolves required verified rules, then applicability, validates inputs and executes the algorithm. Validation samples that merely check a nonempty list are illustrative only and are not an acceptable implementation.

Applicability returns REQUIRED, OPTIONAL, NOT_APPLICABLE or REQUIRES_REVIEW with reason, references and unresolved rule IDs. Unresolved rules yield REVIEW_REQUIRED/UNDETERMINED rather than a Boolean false. A known N/A case yields COMPLETE/NOT_APPLICABLE; the application API prevents starting/evaluating an explicitly N/A run with 409 TEST_NOT_APPLICABLE, while the standalone domain can represent N/A directly.

## 4. Regulatory gate

Normative rule configuration carries validation_status (TODO_REGULATORY_VALIDATION or VERIFIED), source part/edition/clause/digest, verifier, date and evidence. All inherited worksheet thresholds are candidate interpretations until validated. A RuleSet can be loaded in DRAFT for inspection; activation and authoritative evaluation require verified transitive dependencies for its declared supported tests. Unsupported catalog sections are visible and blocked, not excluded deceptively.

Absent/unverified exact rules produce a deterministic explanatory result: evaluation_status REVIEW_REQUIRED, compliance_outcome UNDETERMINED, issue_code TODO_REGULATORY_VALIDATION, unresolved_rule_ids and known references. Do not infer a threshold from a similar test or label unavailable code N/A. No client-controlled production bypass exists. Unit tests can use synthetic isolated fixtures explicitly marked non-regulatory; those fixtures are not available to official report generation.

## 5. Decimal, units and comparisons

Canonical mass unit is grams; voltage is volts, temperature Celsius, relative humidity percent, pressure hPa and elapsed time seconds. Compound physical units are named in schema fields. API/JSONB decimal values are strings. Normalize inputs exactly using known unit factors. Reject NaN, infinity and float-origin values.

All internal metrological arithmetic uses Decimal, with locally controlled precision and detection of inexact/rounded operations. Never quantize before a compliance comparison for display or to fit NUMERIC columns. Persist only exactly representable values; reject excess declared precision rather than silently truncate. An explicit VERIFIED rounding rule may specify an exception with mode/scale/stage.

For repeating division, keep exact operands and compare algebraically using Decimal products/cross multiplication when equivalent; a rounded diagnostic quotient is display-only and labeled approximate. Do not claim a fixed Decimal precision makes every quotient exact. If no exact safe comparison is supported, return EVALUATION_NOT_POSSIBLE. Canonical hash normalization never rounds.

calculate_mpe selects the verified class/load/range/context band; calculate_prerounding_indication, calculate_error and calculate_corrected_error apply the verified mode-specific formulas. The general digital worksheet candidate is P=I+0.5e−ΔL, E=P−L, Ec=E−E0. e-versus-d and analog exceptions remain REG-03. calculate_n uses exact Max/e validation without an invented approximate tolerance.

Limit comparison accepts an explicit rule-defined operator and signed/absolute semantics. A conventional absolute <= helper is not universal: candidate temperature drift uses strict <; REG-05 must confirm it. Equality expectations must be verified per rule. Preserve exact intermediate operands and the comparison actually used.

## 6. Canonical input and hashes

Persist evaluation_input_snapshot with these top-level fields:

| Field | Meaning |
|---|---|
| hash_schema_version | v1 |
| instrument_snapshot | Full relevant instrument and range values |
| test_code | Exact registered code |
| procedure_context | Typed context including its schema version and all decision-relevant environment/equipment/protocol values |
| observations | Normalized typed rows in stable sequence |
| ruleset_configuration_hash | Content identity of pinned rules |
| observation_schema_version | Pinned schema identity |
| engine_version | Algorithm/build identity |

Canonicalization: unit normalization; finite decimal strings in plain notation without redundant zeros (−0 → 0); NFC text; UTC timestamps with six fractional digits and Z; schema-defined explicit nulls; sorted object keys; compact UTF-8 JSON; no duplicate keys, unknown fields or nonfinite numbers. Observations sort by unique sequence_no, ranges by range_no; unordered sets have stable schema-defined keys. Preserve meaningful time/phase order. Storage UUIDs and evaluation wall-clock metadata are excluded unless they are semantic protocol values; measurement times remain included where relevant.

input_hash = SHA-256(canonical evaluation_input_snapshot). No alternative partial hash definition exists. A result hash uses canonical deterministic output only, excluding generated result UUID and evaluated_at. Hash fixtures prove equivalent Decimal spellings produce the same identity and changes to context, range, schema, rules or engine change identity.

Ruleset hashes cover all normalized normative configuration/source identities, supported test declarations and verification evidence; administrative lifecycle timestamps/status toggles are excluded. Content changes require a new version. Do not hash raw YAML whitespace. A version ID is not a substitute for a configuration hash.

## 7. Canonical result

| Field | Contract |
|---|---|
| test_code | Registered test identifier |
| applicability_status, applicability_reason | Four-state applicability and explanation |
| evaluation_status | NOT_STARTED, IN_PROGRESS, INCOMPLETE, STALE, REVIEW_REQUIRED, COMPLETE as applicable; engine emits INCOMPLETE/REVIEW_REQUIRED/COMPLETE, application derives lifecycle progress/staleness |
| compliance_outcome | UNDETERMINED, COMPLIANT, NONCOMPLIANT, NOT_APPLICABLE |
| calculations | Ordered named calculation rows, exact operands, units and formula identifiers |
| acceptance_limits | Verified rule IDs, values, comparison operator and sign/absolute semantics |
| failed_conditions | Structured rule/observation/condition failures; never overwrite history with just a Boolean |
| rule_references | Standard part/edition/clause references |
| reason, issue_code, unresolved_rule_ids | Human explanation and machine-readable blockers |
| ruleset_version, engine_version | Distinct pinned versions |

Canonical weighing row keys are sequence_no, range_no, direction, load_g, indication_g, additional_load_g, prerounding_indication_g, raw_error_g, zero_error_g, corrected_error_g, mpe_g and compliance_outcome. P/E/Ec are report column labels, not competing API keys. Outcome NONCOMPLIANT maps to FAIL in UI; no overloaded status field or duplicate authoritative passed Boolean.

Correct arithmetic fixture: I=10020, e=10, ΔL=5, L=10000, E0=0 gives P=10020, E=20, Ec=20 g. Candidate MPE=10 g gives NONCOMPLIANT only in an isolated candidate fixture until verified.

## 8. Procedure validation

Three layers remain separate: API field/schema validation; domain procedure completeness/compatibility; metrological acceptance evaluation. Validate required loading/unloading, sample counts, coverage around transitions, stage order, stabilization/timing, ranges, geometry, power/severity, functional response and evidence prerequisites according to verified rules.

Invalid field shape is an API 422. An incomplete procedure gives 422 MISSING_REQUIRED_OBSERVATIONS/EVALUATION_NOT_POSSIBLE with structured issues and updates readiness to INCOMPLETE without creating a current compliance result. Missing regulatory knowledge is REVIEW_REQUIRED/UNDETERMINED and may be stored as an explanatory assessment. Genuine observed failure under a complete valid procedure is COMPLETE/NONCOMPLIANT, not a validation error.

## 9. Sections and specialized workflows

Sections 1–15 have specialized evaluators; Section 4 includes sensitivity for applicable non-self-indicating instruments, Section 6 has ZERO_RETURN/CREEP, and Section 12 has seven families with vehicle subvariants represented in typed context/requirement keys. Reuse calculation helpers and a disturbance base without one giant if/else evaluator. A fault-detected Boolean alone cannot prove an acceptable significant-fault response; use verified behavior requirements.

Section 16 is managed by ConstructionExaminationService with versioned required items and explicit examiner conformance. Section 17 is managed by ChecklistEngine with versioned wording/applicability and PASS/FAIL/N/A/NOT_EXAMINED responses. Failed examined rows count toward completeness while yielding NONCOMPLIANT; unanswered rows do not. Retain excluded/non-applicable rule decisions so summary totals and report traceability remain explainable.

## 10. Aggregation

SectionResultAggregator and SessionComplianceAggregator apply DECISIONS F05. They consume selected current runs and required/elected requirements, construction conformance and checklist completeness. STALE precedes REVIEW_REQUIRED, then INCOMPLETE, IN_PROGRESS, NOT_STARTED, COMPLETE; mixed complete/unstarted required work is IN_PROGRESS. A current known failed required result yields NONCOMPLIANT even while other work is incomplete. Without such a failure, unfinished/unknown required work yields UNDETERMINED. All complete conforming required work yields COMPLIANT; entirely N/A sections yield COMPLETE/NOT_APPLICABLE.

Workflow approval is not calculated by this engine. The application may approve a COMPLETE/NONCOMPLIANT evaluation after review. Optional unelected results are disclosed without silently influencing the required aggregate.

## 11. Result versions, retests and source change

Immutable result rows have evaluation_version, source input_revision, input snapshot/hash, deterministic output/hash and predecessor ID. Freshness events CURRENT/STALE/SUPERSEDED are append-only and separate from immutable outputs. Source/context changes clear run.current_result_id and make dependent aggregates stale. Same current canonical input returns the existing result; changed input or engine/schema/rule version creates a new version after authorized revision control.

Retests create new run attempts within one logical requirement slot, preserve failed attempts and require explicit selection/reason. Report context includes all relevant attempts. Selection and new current result change the session regulatory_revision and invalidate affected review approvals. Immutable approved sessions cannot be reevaluated in place; create a session revision.

## 12. Testing and build gate

Test the engine without HTTP/database/storage. Cover exact Decimal behavior, all verified boundaries, golden calculations, applicability, missing-rule gates, procedure validation, canonical hashes, status precedence and immutability. Synthetic fixtures must never masquerade as verified regulations. Phase 4 completes the engine skeleton, loaders, context and applicability before Phase 5 creates test sessions; Phase 5 then adds Section 1 evaluator and vertical integration after its pure unit tests pass.


## 13. Versioned configuration artifacts

The initial source folder remains app/compliance/rules/oiml_r76_2006/. Its versioned artifact set includes metadata.yaml, classes.yaml, mpe.yaml, applicability.yaml, voltage.yaml, disturbances.yaml, endurance.yaml, checklist.yaml and report_sections.yaml; typed procedure requirements may live in procedures.yaml with the same version/hash/provenance gate. These are planned configuration artifacts, not generated by this freeze. Standard-part metadata distinguishes R76-1 requirements edition from R76-2 report edition. Different content versions are separately retained via immutable release artifacts/Git revisions and registry identities; a shared directory name is not permission to overwrite active content.

The canonical evaluator registry includes WEIGHING_PERFORMANCE, TEMPERATURE_ZERO, ECCENTRICITY, DISCRIMINATION, SENSITIVITY, REPEATABILITY, ZERO_RETURN, CREEP, STABILITY_EQUILIBRIUM, TILTING, TARE, WARM_UP, VOLTAGE_VARIATION, DISTURBANCE_VOLTAGE_DIP, DISTURBANCE_BURST, DISTURBANCE_SURGE, DISTURBANCE_ESD, DISTURBANCE_RADIATED_RF, DISTURBANCE_CONDUCTED_RF, DISTURBANCE_VEHICLE_SUPPLY, DAMP_HEAT, SPAN_STABILITY and ENDURANCE. Group catalog codes DISCRIMINATION_SENSITIVITY, TIME_DEPENDENCE and ELECTRICAL_DISTURBANCES aggregate subtests; CONSTRUCTION_EXAMINATION and CHECKLIST use their dedicated non-numeric services/engine.
