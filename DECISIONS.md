# SIH26035 — DECISIONS

Specification Freeze v1 — 2026-09-20

Status: architectural contracts frozen; application implementation has not started.
Authority: the user's Specification Freeze v1 instruction. This file and PROJECT_CONTEXT.md agree; future changes require a new recorded decision and coordinated specification updates. The nine domain specifications supply details; BUILD_PLAN.md owns phase sequencing. Earlier illustrative snippets are not implementation authority.

## F01 — Product and implementation boundary

Build a desktop-oriented web laboratory platform for NAWI type evaluation, recording all 17 R76-2 report sections, deterministic assessment, independent review, approval of the evaluation record, and PDF/DOCX reporting. Preserve the Next.js/TypeScript frontend, FastAPI/Pydantic v2 backend, async SQLAlchemy/asyncpg/Alembic/PostgreSQL, independent Python compliance domain, and private MinIO/S3 storage. No AI compliance decisions. This freeze changes documentation only. Phase 0 requires a separate explicit user instruction.

## F02 — Decimal and the corrected example

Metrological inputs use finite Decimal values constructed from decimal strings, never binary floats. Preserve exact supplied values and exact finite arithmetic. Reject values outside declared bounds/scale instead of silently rounding them for persistence. Do not quantize for display before comparison. Presentation formatting never changes stored values or decisions.

Use a locally controlled Decimal context (not ambient process defaults). A provisional precision such as 50 significant digits is not a license to round authoritative comparisons: detect inexact operations; use algebraically equivalent exact comparisons (for example cross multiplication for normalized drift) when possible. Repeating quotients may be rendered as labeled display approximations while retaining exact operands. If an exact comparison cannot be established, return EVALUATION_NOT_POSSIBLE; any regulatory rounding exception requires a VERIFIED rule declaring its mode, scale, and stage. There is no invented tolerance, epsilon, or approximate n validation.

For I=10020 g, e=10 g, ΔL=5 g, L=10000 g and E0=0 g: P=10020 g, E=20 g, Ec=20 g. The candidate Class III MPE fixture at this point is 10 g, so its fixture outcome is NONCOMPLIANT. Arithmetic correctness does not establish regulatory verification of the rule.

## F03 — Explicit role-assignment scopes

Replace user_roles with user_role_assignments: UUID primary key; user_id, role_id, scope_type, optional laboratory_id; assignment/revocation metadata. GLOBAL requires laboratory_id IS NULL; LABORATORY requires laboratory_id IS NOT NULL. Use separate partial unique indexes for active GLOBAL (user_id, role_id) and active LABORATORY (user_id, role_id, laboratory_id) assignments.

GLOBAL applies only to explicitly global administrative permissions. It does not grant regulatory data access or final approval in every laboratory. Laboratory resources always require a corresponding active LABORATORY assignment and a permission granted in that laboratory. A GLOBAL ADMIN may manage system/laboratory/user/ruleset configuration, but needs lab-scoped permissions for regulatory data. Manufacturer records are laboratory-owned in v1; sharing a manufacturer between labs is outside v1. Rulesets/catalog are global versioned reference data.

## F04 — Final authority and separation of duties

ADMIN has no wildcard permission, approval:finalize, or report:issue by default. Only the APPROVING_OFFICER role receives approval:finalize and report:issue in the seeded permission matrix; users with ADMIN plus a separate lab-scoped APPROVING_OFFICER assignment may act through that assignment. Authorization uses effective permissions and laboratory scope, never role-name shortcuts.

Final approver must differ from the session initiator and every raw-observation author for that session/revision. Technical reviewer must also be independent of raw-observation authors. Combining reviewer and final approver is allowed in v1 if these author exclusions hold. Assignments and changes are audited; user inactivity/revocation takes effect on subsequent requests without waiting for JWT expiry. Final approval attests to the reviewed evaluation record, not automatic certification of the instrument.

## F05 — Three independent status axes

| Axis | Canonical values | Meaning |
|---|---|---|
| workflow_status (session) | DRAFT, INSTRUMENT_CONFIGURATION, APPLICABILITY_CONFIRMED, TESTING, EXAMINATION, UNDER_REVIEW, APPROVED, REPORT_ISSUED, REJECTED, CANCELLED | Lifecycle and permitted actions |
| evaluation_status (run/section/session) | NOT_STARTED, IN_PROGRESS, INCOMPLETE, STALE, REVIEW_REQUIRED, COMPLETE | Readiness, procedure completeness and validity of evidence/results |
| compliance_outcome (run/section/session) | UNDETERMINED, COMPLIANT, NONCOMPLIANT, NOT_APPLICABLE | Assessment of applicable requirements |

These are separate fields, never one overloaded status. PASS/FAIL are presentation labels for COMPLIANT/NONCOMPLIANT; checklist row answers remain PASS, FAIL, NOT_APPLICABLE, NOT_EXAMINED. Resource lifecycle enums such as ruleset status and report status are separately named.

Applicability uses REQUIRED, OPTIONAL, NOT_APPLICABLE, REQUIRES_REVIEW. It is distinct from result status. OPTIONAL tests become required-for-completion once explicitly elected in the session; unelected optional tests remain visible and are excluded from the required aggregate, not relabeled N/A. Unresolved applicability blocks confirmation/approval.

Aggregation: evaluate required/elected children. Readiness precedence is STALE, REVIEW_REQUIRED, INCOMPLETE, IN_PROGRESS, NOT_STARTED, COMPLETE; no children started yields NOT_STARTED, started-but-not-complete children yield IN_PROGRESS, failed validation/missing mandatory stages yield INCOMPLETE. Mixed COMPLETE/NOT_STARTED children yield IN_PROGRESS. A current, valid negative result yields NONCOMPLIANT even when other children are unfinished; otherwise any unfinished/unknown required assessment gives UNDETERMINED. All resolved required assessments conforming gives COMPLIANT. Entirely non-applicable sections give COMPLETE/NOT_APPLICABLE; a session cannot issue with an entirely non-applicable or empty assessment. Construction completion alone is not numerical compliance: applicable conformance checks and examiner determinations must also be resolved. A completed negative finding is COMPLETE/NONCOMPLIANT.

## F06 — Approval is independent of compliance outcome

Final approval requires COMPLETE evaluation, a determined COMPLIANT or NONCOMPLIANT session outcome, resolved applicability, current results, completed required examination/checklist items, evidence/equipment checks, and valid technical review of the current regulatory revision. A known, fully documented failed requirement is not an unresolved review condition. COMPLETE/NONCOMPLIANT may be approved and issued accurately as such. Approval never rewrites failure to success. Missing/unknown rules, incomplete tests, stale results, and unresolved manual decisions block official issue.

## F07 — Pure engine with typed procedure context

The canonical domain call is R76Engine.evaluate(test_code, instrument_snapshot, procedure_context, observations, ruleset). Every argument is immutable typed domain data; snapshots include all ranges and applicable feature flags. procedure_context is a versioned discriminated domain structure for the test and procedure variant, including evaluation_context, range/scenario identity, stages, required timing, environment links/values, equipment/calibration inputs where decision-relevant, and severity/fault-response metadata where applicable. Exact fields and requirements are test-specific and gated by verified rules.

Routes handle HTTP; services handle scope, permissions, state, transactions, mapping and persistence; repositories handle SQL; the engine handles applicability, procedure validation and deterministic evaluation. The engine imports neither FastAPI nor SQLAlchemy. Section 16 uses a construction service and Section 17 a checklist engine. Applicability returns all four applicability values with reasons/references; a Boolean shortcut must not turn REQUIRES_REVIEW into NOT_APPLICABLE.

## F08 — One canonical evaluation identity

The canonical evaluation_input_snapshot contains exactly these top-level semantic inputs: hash_schema_version (v1), instrument_snapshot (including ranges), test_code, procedure_context (including its schema version), observations, ruleset_configuration_hash, observation_schema_version, engine_version. No user identity, wall-clock evaluation timestamp, live master-data lookup, or mutable database object is an implicit engine input. Measurement timestamps are retained where procedure-relevant. Every decision-relevant environment/equipment value must be represented in these inputs.

Normalize units to named canonical units before hashing. Normalize finite decimals to plain decimal strings: no exponent, no redundant leading/trailing zeros, negative zero becomes "0". Use explicit nulls as required by the schema; forbid unknown fields, nonfinite values and duplicate object keys. Sort JSON object keys, emit UTF-8 without insignificant whitespace, normalize text to NFC and times to UTC ISO-8601 with fixed six fractional digits and Z. Observation order is by unique sequence_no; range order by range_no; other unordered collections have a schema-defined stable key; meaningful time/sequence arrays keep semantic order. Hash with SHA-256. IDs used solely for persistence are excluded; stable observation sequence and measurement data are retained.

input_hash covers this complete canonical snapshot. result_hash covers canonical deterministic output (test_code, evaluation_status, compliance_outcome, applicability, calculations, limits, failures, reasons, references, versions); exclude evaluation wall-clock time and generated record IDs. Canonicalization has its own version and golden fixtures. Same semantic inputs and engine version produce the same hashes/results.

## F09 — Validation and regulatory verification gates

All evaluator snippets with minimal/nonempty-list validation are illustrative only and are removed as executable-looking specifications. Production evaluators enforce the complete applicable verified procedure: counts, load coverage/order, ranges, stages, timing, geometry, environmental conditions, severity and fault response, evidence, and equipment prerequisites as relevant. A valid API shape does not establish a valid test procedure.

Each normative rule/worksheet/checklist item has validation_status TODO_REGULATORY_VALIDATION or VERIFIED, plus source document part/edition/clause, source digest/version, verifier, verification date and evidence. All regulatory interpretations inherited from the supplied draft are TODO_REGULATORY_VALIDATION until verified; none is certified by this freeze. Activation is scoped to explicitly declared supported tests and requires all transitive rules for those tests VERIFIED. Unsupported catalog sections remain visible with REVIEW_REQUIRED/UNDETERMINED, never silently N/A. Final 17-section readiness requires all applicable supported rules verified. No production endpoint may disable this gate. Synthetic candidates may be tested only as explicitly labeled isolated fixtures and cannot produce official results.

If a needed rule is absent/unverified, persist or return an explanatory assessment with evaluation_status REVIEW_REQUIRED, compliance_outcome UNDETERMINED, and issue_code TODO_REGULATORY_VALIDATION. Never invent a threshold, sign convention, applicability decision, or authority policy. Later verification is a new immutable ruleset version when an active version is affected.

## F10 — Generic runs and versioned results

Section 12 uses generic test_runs and validated test_observations JSONB with typed procedure context; the dedicated electrical_disturbance_runs suggestion is retired.

session_test_requirements identifies each logical required/elected test slot (section, test definition, range/scenario/variant key, applicability). Each slot can have multiple numbered test_runs (attempts) and one explicitly selected authoritative run. A retest creates a new run linked by retest_of_run_id and a mandatory reason. It never deletes a failed attempt. Selecting a replacement run records supersession of the previously selected run, reevaluates aggregates and invalidates dependent review. All attempts and selection reasons remain visible in history/report context; a later passing attempt does not erase prior failures.

test_run_results is append-only, keyed by UUID and UNIQUE(test_run_id, evaluation_version), not UNIQUE(test_run_id). Each result includes immutable evaluation_input_snapshot, hashes, outputs, schema/engine/ruleset versions, source input_revision and predecessor reference. Separate append-only evaluation_result_events record CURRENT, STALE and SUPERSEDED transitions. A current_result_id pointer on a run identifies its valid selected result; stale records cannot remain current.

On input mutation, increment input_revision, append STALE events for affected results, clear current pointers, invalidate affected aggregates and review, and require reevaluation. Broader snapshot/ruleset/procedure changes invalidate all dependent runs; conservatively invalidate all when dependencies are uncertain. Re-evaluating identical current input returns the existing result; changed input creates a new version. Previous versions remain stale until a replacement exists, then may be marked superseded by an appended event. Outputs and historical input snapshots never change.

## F11 — Review and correction revisions

Sessions have regulatory_revision and lock_version. Every regulatory input change, evidence/equipment change, authoritative run/result selection, or applicability change increments regulatory_revision atomically and invalidates dependent technical-review approval. approval_actions are append-only and record stage, decision, reviewed revision, actor, reason, affected scope and referenced prior action. INVALIDATED is an action event, not deletion of approval history.

Under review, source data cannot be edited. A reviewer returns a bounded correction_request with affected entities/fields and reason; session returns to TESTING or EXAMINATION. Reopen only activates that approved scope. Any relevant correction requires fresh submission/review before approval. No unbounded reopening of approved/issued sessions.

For post-approval corrections, create a new session revision linked to its parent/root; preserve the approved original. Copy regulatory inputs with provenance, reset workflow to INSTRUMENT_CONFIGURATION, and do not treat copied results/reviews as current approvals. Revalidate applicability, reevaluate required runs, complete review and final approval. Editorial report corrections also use this controlled revision in v1; no bypass category is introduced.

## F12 — Previews, official generation, issue and supersession

Unofficial previews may be generated from a consistent captured working snapshot by report:preview. They are watermarked UNOFFICIAL PREVIEW and show workflow/evaluation/outcome, unfinished/stale data and regulatory TODOs. They have preview IDs and private retention, no official report number or issue transition. Preview renderers do not recalculate rules.

Official generation requires APPROVED and the F06 gate. Final approval first captures an immutable session_approval_snapshot of the complete reviewed regulatory record and historical master/actor/evidence facts; generation reads that snapshot rather than live master data. Freeze report_context_snapshot before rendering. It includes historical lab/manufacturer/instrument/ranges/components, equipment/calibration, environments, selected results plus retest history, complete checklist wording/responses, construction/evidence hashes, approvals/actor names, source revisions, rule/engine/schema/template/renderer identities, intended issue metadata and all 17 sections. Both renderers consume the exact same persisted immutable context. Never join live mutable names/addresses/calibration records into an issued report.

Official reports use UNIQUE(report_number, revision_no), with revision_no >= 1. Report numbering is globally unique per report series: R76-<year>-<atomic sequence>; the same number is reused only within its revision chain. reports includes supersedes_report_id, revision_reason and root_report_id; UNIQUE(test_session_id) binds one official report record to each approved session revision. Reverse supersession is derived from the successor link. At most one issued current revision per report series. A revision does not supersede the old issued report until the new revision is successfully issued. Old bytes/context remain accessible as SUPERSEDED.

Generation status is GENERATING, READY or FAILED; report_status is UNISSUED, ISSUED or SUPERSEDED. Issue is a separate officer-authorized atomic action after both formats are READY and hashes verified. report:generate alone never issues. Final approval remains required for a NONCOMPLIANT report.

The generation request reserves report number/revision and captures intended_issuer_id and planned_issue_date (UTC calendar date) in the immutable context. The printed approval block uses the stored final approval timestamp; the printed issue field is the planned date. At issue, issuer identity and the current UTC date must match these reserved values; otherwise generate a new immutable attempt/context before issuing. The actual issue instant is recorded separately in reports.issued_at, the issue action and the immutable issuance manifest; it is not retroactively inserted into rendered bytes. A failed/unissued context is retained; no issued content is rewritten. An issue idempotency record returns the first successful issue response on retries.

context_hash hashes the canonical report context without its own hash field. Each output file has a separate SHA-256. report_hash hashes a canonical manifest containing context_hash plus format/file hashes; it is not embedded recursively in its own file. Hashes identify content, not legal signatures. Store immutable generation attempts separately so retry never overwrites an issued artifact.

## F13 — Refresh-session persistence

Persist auth_refresh_sessions: UUID, user, family ID, unique token digest, parent/replaced-by references, created/expires/consumed/revoked times, revocation reason, client metadata. Store no raw refresh token. Hash high-entropy opaque refresh tokens with SHA-256; access tokens are short-lived signed JWTs (default 15 minutes), refresh tokens default 7 days and family absolute lifetime 30 days, configurable independently of regulatory rules.

Rotation atomically consumes the old token and creates its replacement under a row lock. Reuse of a consumed token revokes the family. Logout revokes the active family; logout-all revokes all user families. User disable/password reset revokes sessions. Permissions and user activity are checked from authoritative state on each protected request; do not trust stale token role claims. Browser refresh tokens use Secure HttpOnly SameSite cookies with Origin/CSRF protection; access JWTs are held in memory. Local HTTP development may relax Secure only via explicit development configuration. Never log token material.

## F14 — Optimistic and transactional concurrency

Mutable resources expose monotonically increasing lock_version via ETag. PATCH/DELETE and mutating lifecycle actions require If-Match on the target resource; return 428 when missing, 412 on mismatch, 409 for a valid-version request forbidden by state. New independent resource creation needs no If-Match; creation under a mutable parent uses the parent's ETag. Replayed idempotent responses are returned before reapplying If-Match/state checks after matching actor, scope and request digest.

All regulatory mutations also lock the parent session row inside the transaction, then affected run rows in stable UUID order. Check workflow, correction scope, regulatory_revision/input_revision and versions under lock. Approval, report snapshot capture, retest selection and source mutation serialize through this parent lock. Evaluation may run outside a transaction on captured immutable inputs; committing it must recheck input_revision and session state, otherwise reject as 409 SOURCE_CHANGED_DURING_EVALUATION without selecting that result. Do not hold DB locks during file rendering/network transfer.

Use persistent idempotency_keys (actor, scope, operation, key, request hash, status, response, resource IDs, expiry) for session creation, evaluation, approval, report generation/issue and revision/retest creation. Reserve atomically. Same key/different payload returns 409; an in-progress duplicate returns 409 with retry guidance. Upload/report publication uses staged private objects and explicit finalize checks; PostgreSQL transactions cannot roll back object storage. Failed generation attempts do not issue/supersede reports; incomplete objects are retained for retry or cleaned by a documented worker.

## F15 — Audit ownership and immutable evidence

The application service owns audit events and writes them in the same transaction as each regulatory mutation. Authentication service owns login/refresh/revocation events; the report service/worker owns generation/issue events. Routes, evaluators and renderers do not independently emit duplicate domain audit records. Worker outcomes use an attributable system actor and originating request/job ID. Failed logins use a separate auditable transaction without recording credentials.

Audit events are append-only and contain actor, lab, action, entity, source/target revision, before/after or hashes, reason, request/correlation ID and timestamp. Every phase that introduces mutable behavior adds its audit tests. Approved/issued records, attachment content hashes/object versions and links used by them are protected from update/delete; files are private and accessed through scoped short-lived links. Ordinary master updates never mutate a session/report snapshot. Current mutable master data is not retroactively frozen globally.

## F16 — Lifecycle API completeness

06-api-spec.md owns the complete endpoint/permission/state matrix: explicit draft creation, configuration, applicability confirmation, testing/examination transitions, scoped correction/reopen, rejection/cancellation, retest creation/selection, input/result history, refresh-session listing/revocation, unofficial previews, official generation/issue and session/report revisions. Do not hide state changes inside unrelated CRUD endpoints. Construction/checklists are initialized idempotently when modules become available; required unavailable modules block completeness until their phase is implemented.

## F17 — Dependency-correct build sequence

Keep phases 0–24 and their main goals. Phase 1 includes audit/concurrency/idempotency/refresh foundations. Phase 3 includes the equipment and attachment infrastructure formerly deferred to Phase 14. Phase 4 includes applicability and typed procedure context before Phase 5 session creation. Phase 5 includes source/result versioning, requirement slots, locking guards and lifecycle foundations. Phases 12/13 add construction/checklist modules and initialize them for existing preapproval sessions. Phase 14 hardens existing evidence/equipment infrastructure. Phase 15 completes review/approval/revision governance. Phase 16 implements reporting, previews and issue. No Phase 5 claim of full 17-section readiness is allowed before later modules and regulatory gates are complete.

## F18 — Unresolved regulatory register

Every item below is TODO_REGULATORY_VALIDATION. Architecture is frozen; these items do not prevent Phase 0 tooling/bootstrap. They block authoritative evaluation/activation for affected tests and official issue until verified.

| ID | Required verification |
|---|---|
| REG-01 | Applicable R76-1/R76-2 editions/amendments, Indian supplemental requirements, accepted authority interpretation and official report wording |
| REG-02 | All four accuracy-class limits; Min/Max/e/d/n, auxiliary indication, multi-range/multi-interval transitions and evaluation-context mapping |
| REG-03 | MPE tables/boundaries, digital changeover using e versus d, analog modes, zero-error sign/absolute-value semantics and regulatory rounding exceptions |
| REG-04 | Section 1 exact load counts/coverage, loading/unloading, preloading and temperature variants |
| REG-05 | Section 2 applicability, temperature sequence/stabilization, normalization and strict boundary operator |
| REG-06 | Section 3 eccentricity test loads/positions, support/receptor exceptions and rolling-load cases |
| REG-07 | Section 4 digital/analog discrimination preparation and full construction-dependent sensitivity thresholds |
| REG-08 | Section 5 repetition counts, load series, individual error and repeatability-range limits |
| REG-09 | Section 6 zero-return limits/range rules and complete short/extended creep/time/temperature criteria |
| REG-10 | Section 7 printing/storage behavior, adjacent values, timing, trial counts and zero/tare error semantics |
| REG-11 | Section 8 tilt applicability, Class II/direct-sales exceptions, reference quantities, sensor/mobile behavior |
| REG-12 | Sections 9–11 tare modes/net-load limits, warm-up prerequisites/checkpoints and supply profiles/switch-off behavior |
| REG-13 | Section 12 all severity profiles, repetitions/ports/polarities, relevant IEC/ISO editions and acceptable significant-fault responses |
| REG-14 | Sections 13–15 damp-heat applicability/exposure, span corrections/trend/extension rules and endurance cycles/durability limits |
| REG-15 | Complete Section 16 examination/conformance items and Section 17 clause-level checklist with applicability/evidence requirements |
| REG-16 | Equipment calibration acceptance at measurement time, environmental tolerances, permitted deviations/retests and retained evidence requirements |
| REG-17 | Authority acceptance of report numbering, signatures, failure-report wording, issue timestamp, revision/supersession and retention policies |

Verification must record exact source evidence and domain-expert sign-off; a documentation label alone cannot mark a rule VERIFIED. No external regulatory verification was performed during this freeze.

## F19 — Freeze acceptance

All 11 source specifications are revised to these contracts. Obsolete table/status/hash examples are replaced, not left as competing normative alternatives. DECISIONS.md is the change record; the documents describe future implementation, not completed features. Consistency checks cover table/API/permission names, status axes, phase dependencies, regulatory gates, links and absence of application code. The specification is ready for Phase 0 after this freeze; implementation of later regulatory features remains subject to F18.


## Change traceability

| Original inconsistency/gap | Frozen resolution | Updated owners |
|---|---|---|
| 15 g worked error | F02: 20 g for E0=0 | 02, 03, 04, 09 |
| Nullable composite user role key / tenant ambiguity | F03 UUID scope assignments; lab-owned manufacturers | 03, 05, 06, 07 |
| Unique report number prevented revisions | F12 composite uniqueness and explicit supersession | 05, 06, 07, 08 |
| Failure blocked approval / mixed statuses | F05/F06 three axes and approved NONCOMPLIANT | PROJECT_CONTEXT, 01, 03–09 |
| ADMIN implied approving authority | F04 explicit permission and complete scoped mapping | 05, 06, 07 |
| Multiple hash definitions / missing procedure input | F07/F08 one typed context and canonical snapshot hash | 03, 04, 05, 06, 09 |
| Simplistic nonempty observation validation | F09 complete verified procedure gate | 02, 04, 09 |
| Dedicated Section 12 table | F10 generic runs/JSONB | 02, 03, 05, BUILD_PLAN |
| One overwritten result / undefined retests | F10 immutable versions, events and selected attempt slots | 03–09 |
| Correction reused obsolete review | F11 regulatory revisions, scoped correction and invalidation actions | 03–09 |
| Approved-only reports conflicted with previews | F12 separate preview/generation/issue | 06, 07, 08 |
| Mutable master data affected reports | F12 approval and report-context snapshots | PROJECT_CONTEXT, 03, 05–09 |
| Unspecified rounding / strict boundary risk | F02 exact comparison and explicit verified exceptions | 02, 04, 05, 09 |
| Guessed/missing regulatory rules | F09/F18 TODO register and verification gates | All product/domain/plan documents |
| Applicability/evidence dependency order | F17 reordered foundation ownership | BUILD_PLAN, 03, 05 |
| Missing refresh persistence/endpoints | F13 auth sessions, cookie/rotation/revocation contract | 03, 05, 06, 09, BUILD_PLAN |
| Missing lifecycle/concurrency/audit ownership | F14–F16 ETags/locks/idempotency, complete endpoints, service audit | 03, 05, 06, 07, 09, BUILD_PLAN |
| Permission/result-key/catalog naming drift | Canonical permission sets, corrected_error_g and versioned catalog | 03–09 |
| Competing aggregator priorities | F05 one readiness precedence and independent outcome | PROJECT_CONTEXT, 04, 07, 09 |

Source filenames ending in (1).md are updated as the same original documents; canonical repository filenames in this pack omit the upload suffix. No original application source was created or changed.
