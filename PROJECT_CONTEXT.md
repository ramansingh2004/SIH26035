# SIH26035 — Project Context

Specification Freeze v1 — 2026-09-20. Architecture frozen; no application implementation authorized by this document.

## 1. Authority and document map

Read [DECISIONS.md](DECISIONS.md) with this file before implementation. They form the frozen architectural baseline. [BUILD_PLAN.md](BUILD_PLAN.md) owns phase order; the nine documents in docs/ define domain detail. A future conflict requires an explicit decision and coordinated documentation correction, not a silent implementation guess.

| File | Ownership |
|---|---|
| [01-problem-requirements.md](docs/01-problem-requirements.md) | Product scope and functional requirements |
| [02-r76-tests.md](docs/02-r76-tests.md) | Seventeen section worksheets and regulatory-validation register links |
| [03-backend-architecture.md](docs/03-backend-architecture.md) | Layer boundaries, application orchestration and infrastructure |
| [04-r76-rule-engine.md](docs/04-r76-rule-engine.md) | Typed inputs, Decimal behavior, hashes, evaluation and aggregation |
| [05-database-schema.md](docs/05-database-schema.md) | Canonical PostgreSQL model and constraints |
| [06-api-spec.md](docs/06-api-spec.md) | Endpoint, permission, concurrency and lifecycle contracts |
| [07-rbac-workflow.md](docs/07-rbac-workflow.md) | Effective permissions, scope, states, approval and corrections |
| [08-report-spec.md](docs/08-report-spec.md) | Preview, immutable context, rendering, issue and revisions |
| [09-test-plan.md](docs/09-test-plan.md) | Verification and phase/release gates |

## 2. Purpose

A web-based legal-metrology laboratory platform for recording NAWI type evaluation, performing deterministic assessment under verified OIML R76 rules, completing examinations/checklists, reviewing and approving the evaluation record, generating standardized PDF and editable DOCX reports, and retaining searchable instrument/report history.

Users register manufacturer and instrument data, confirm a snapshot and applicability, record real laboratory observations/evidence, evaluate, examine, review, approve and issue. Laboratory equipment performs the physical tests. Software neither simulates those tests as evidence nor uses AI to determine compliance. Final evaluation approval can accompany NONCOMPLIANT; the report faithfully records failure.

## 3. Settled stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, React, TanStack Query, React Hook Form, Zod; accessible form-oriented UI |
| API/application | FastAPI, Python 3.12+, Pydantic v2 |
| Persistence | PostgreSQL, async SQLAlchemy 2.x, asyncpg, Alembic |
| Compliance | Independent pure Python domain package, immutable typed inputs, Decimal, versioned verified configuration |
| Files | Private MinIO in development; S3 or equivalent in production |
| Reporting | Shared immutable ReportContext, DOCX/PDF renderers |
| Optional infrastructure | Redis, background workers, Docker, Nginx; Redis is not an engine dependency |

## 4. Hard boundaries

1. Routes perform HTTP/auth dependencies/parsing/serialization; no OIML calculations or SQL queries.
2. Application services enforce permissions, lab scope, states, locks, revisions, transactions and audit; repositories own SQLAlchemy access.
3. The R76 engine has no FastAPI, Starlette, SQLAlchemy, request, session, storage or user dependencies.
4. Engine inputs are instrument/range snapshot, test code, typed procedure_context, normalized typed observations and immutable RuleSet.
5. Frontend and reports only display authoritative stored results. They do not recalculate compliance.
6. Metrological arithmetic uses finite Decimal; no floating point or display quantization before comparison. Exact-comparison and rounding gates are defined in DECISIONS F02 and 04-r76-rule-engine.md.
7. Active rulesets, historical evaluation outputs, approved regulatory source datasets and issued report contexts/files cannot be overwritten.
8. Incomplete/unverified rules become TODO_REGULATORY_VALIDATION with REVIEW_REQUIRED/UNDETERMINED; no invented PASS, FAIL or N/A.

## 5. All 17 report sections

| No. | Section | Execution model |
|---:|---|---|
| 1 | Weighing performance | Numerical evaluator |
| 2 | Temperature effect on no-load indication | Temperature-series evaluator |
| 3 | Eccentricity | Position/rolling-load evaluator |
| 4 | Discrimination and sensitivity | Mode-specific subtests |
| 5 | Repeatability | Repetition-series evaluator |
| 6 | Time dependence | ZERO_RETURN and CREEP subtests |
| 7 | Stability of equilibrium | Functional/numerical subparts |
| 8 | Tilting | Direction/tilt and protective-function evaluator |
| 9 | Tare | Tare-scenario evaluator |
| 10 | Warm-up time | Time-checkpoint evaluator |
| 11 | Voltage variations | Power-profile evaluator |
| 12 | Electrical disturbances | Seven subtest families using generic runs and typed JSONB |
| 13 | Damp heat, steady state | Three-stage evaluator |
| 14 | Span stability | Long-duration evaluator |
| 15 | Endurance | Cycle/pre-post evaluator |
| 16 | Construction examination | Structured examination and conformance workflow |
| 17 | Checklist | Separate versioned ChecklistEngine |

Every session and report summary shows 17 sections. Applicability is REQUIRED, OPTIONAL, NOT_APPLICABLE or REQUIRES_REVIEW. An optional test becomes required for completion when elected. Unknown applicability is not N/A. Numerical result fields use COMPLIANT/NONCOMPLIANT; UI PASS/FAIL labels are mappings, not alternate wire enums. Checklist answers retain PASS/FAIL/NOT_APPLICABLE/NOT_EXAMINED.

## 6. Three independent statuses

| Field | Values |
|---|---|
| workflow_status | DRAFT, INSTRUMENT_CONFIGURATION, APPLICABILITY_CONFIRMED, TESTING, EXAMINATION, UNDER_REVIEW, APPROVED, REPORT_ISSUED, REJECTED, CANCELLED |
| evaluation_status | NOT_STARTED, IN_PROGRESS, INCOMPLETE, STALE, REVIEW_REQUIRED, COMPLETE |
| compliance_outcome | UNDETERMINED, COMPLIANT, NONCOMPLIANT, NOT_APPLICABLE |

Canonical lifecycle: DRAFT → INSTRUMENT_CONFIGURATION → APPLICABILITY_CONFIRMED → TESTING → EXAMINATION → UNDER_REVIEW → APPROVED → REPORT_ISSUED. Submission from TESTING is also allowed if examination/checklist completion is already established. Correction returns to TESTING/EXAMINATION; rejection/cancellation do not erase data. Aggregate readiness/outcome precedence is defined once in DECISIONS F05 and implemented by domain aggregators.

Approval requires COMPLETE and a determined COMPLIANT or NONCOMPLIANT outcome, current valid results, resolved requirements/evidence and independent technical approval of the current regulatory revision. Missing rules, stale results and incomplete work block official reporting; genuine completed failures do not.

## 7. Persistence and identity

Relational entities cover users, user_role_assignments, laboratories, manufacturers, instruments/ranges/components, rulesets/catalog, sessions/sections/requirements/runs, results, examinations, evidence, approvals and reports. Test observations use per-test/per-version Pydantic-validated JSONB. Decimal API/JSONB fields are strings; typed SQL metrological fields use exact NUMERIC with rejection on unrepresentable scale.

Role assignments have UUID identities and explicit GLOBAL/LABORATORY scope constraints. GLOBAL administration is not laboratory regulatory access. Manufacturers belong to a lab. All child relationships are checked for matching lab/session ownership; global rules/catalog are versioned reference data.

Auth refresh sessions, idempotency keys and audit events are PostgreSQL-backed. Regulatory mutations use ETags plus parent-session transactional locks. Session regulatory_revision and per-run input_revision drive review/result invalidation.

## 8. Engine identity and result history

One input hash includes hash-schema version, instrument/ranges, test code, typed procedure_context, normalized observations, ruleset hash, observation-schema version and engine version. See DECISIONS F08 for canonical JSON rules.

Each evaluation version stores its immutable input snapshot, calculation trace, limits, failures, references and result hash. Input changes append stale events, clear current pointers, invalidate dependent reviews and require reevaluation. Retests create new numbered attempts in explicit requirement slots; selecting a new attempt records supersession, preserving failed history.

## 9. Ruleset policy

Git-versioned configuration is the authoritative definition; PostgreSQL holds immutable metadata/configuration mirrors. Rulesets have DRAFT/ACTIVE/RETIRED lifecycle and declared supported tests. Activation requires schema/hash validity and verified transitive regulatory rules for supported tests. Old versions remain accessible to pinned sessions. A change to active content creates a new version.

All inherited normative draft rules currently carry TODO_REGULATORY_VALIDATION. DECISIONS F18 lists REG-01 through REG-17. Verification evidence and competent sign-off are required before affected authoritative evaluations, irrespective of implementation phase. Synthetic fixture demonstrations remain explicitly unofficial.

## 10. Access, corrections and audit

Roles: ADMIN, LAB_TECHNICIAN, LAB_ENGINEER, REVIEWER, APPROVING_OFFICER, VIEWER. Effective permission checks are lab-specific. ADMIN never automatically receives approval:finalize/report:issue. Final approval requires explicit lab-scoped approving-officer permissions and author-independence checks.

Under-review regulatory data is read-only. Approved correction requests unlock only named preapproval scope. Changes invalidate dependent review approvals through append-only actions. Approved/issued corrections create a new session revision and fresh review/approval; historical datasets remain intact.

Services own transactional audit. Authentication and report workers audit their own outcomes. All phases implementing mutations also implement related audit and concurrency checks.

## 11. Reporting

Unofficial previews show unfinished/current/stale/TODO information with an UNOFFICIAL PREVIEW watermark, no official number and no issue action. Final approval captures an immutable session_approval_snapshot of the approved content and historical master/evidence facts. Official generation reads that snapshot, freezes report_context_snapshot with report metadata, and generates both formats privately. Issue is a distinct report:issue action.

Reports use UNIQUE(report_number, revision_no), a revision reason and supersession link. Only successful issue of a replacement supersedes the previous current report. Report context snapshots include historical lab/manufacturer/equipment/people, full evidence/result/checklist content and rendering/version metadata. Renderers query no live domain data and perform no OIML calculations.

## 12. Implementation and readiness

Implement one requested phase at a time. Phase 0 is only monorepo/bootstrap/tooling; it is not authorized by Specification Freeze v1. Applicability must precede session creation; storage/equipment foundations precede dependent test/dossier features. See BUILD_PLAN for exact ownership.

The first end-to-end slice remains Phase 5: instrument → session with 17 visible sections → Section 1 observations → independent engine → versioned stored result → API. Sections not yet implemented/verified are visibly incomplete or REVIEW_REQUIRED, never fabricated complete/N/A. Full official issue waits for all applicable modules, verified rules and workflow/report gates.

The architecture is ready for Phase 0; regulatory completion is not claimed.
