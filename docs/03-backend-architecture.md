# SIH26035 — Backend Architecture

Specification Freeze v1 — 2026-09-20. See [DECISIONS.md](../DECISIONS.md) and [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md). This replaces the earlier duplicated schema and illustrative source snippets with a single architectural contract.

## 1. Layers and dependency direction

| Layer | Owns | Must not own |
|---|---|---|
| FastAPI /api/v1 routes | HTTP parsing, auth/permission dependencies, response/error translation | OIML formulas, direct SQL, workflow shortcuts |
| Application services | Scope, state, correction permissions, orchestration, transactions, snapshots, hash invocation, persistence, audit | Duplicated thresholds or hidden recalculation during reporting |
| Repositories | Async SQLAlchemy persistence and scoped queries | Regulatory decisions |
| Compliance domain | Typed immutable inputs, applicability, procedure validation, calculations, outcomes, aggregation | HTTP, ORM models, user lookup, filesystem/storage/network calls |
| Reporting | Immutable context assembly by service; rendering by isolated renderers | Live queries in templates or new compliance evaluation |
| Storage adapters | Private upload/download/finalization, object hash/version checks | Unchecked cross-lab linking |

Dependencies point inward from API to services to domain. Repositories and storage are injected service dependencies. An evaluator can run in unit tests or a CLI without FastAPI/PostgreSQL/Redis/S3. Application startup builds immutable rule and evaluator registries; it does not reload YAML per evaluation.

## 2. Package responsibilities

The planned backend has api/v1, core, db, models, schemas, repositories, services, compliance/domain, compliance/calculations, compliance/evaluators, compliance/loaders, compliance/rules, reports/context, reports/renderers and workers. Domain models are independent from API/SQLAlchemy models. This is a directory responsibility specification, not generated source code.

Primary services: AuthService, AuthorizationService, LaboratoryService, ManufacturerService, InstrumentService, RuleSetService, ApplicabilityService, TestSessionService, TestWorkflowService, EquipmentService, AttachmentService, ConstructionService, ChecklistService, ApprovalService, ReportService and AuditService. AuditService participates in the caller's transaction; it is not a separate asynchronous substitute for regulatory audit persistence.

## 3. Relational and JSONB strategy

[05-database-schema.md](05-database-schema.md) is the canonical schema. Core entities and relationships are relational. Flexible observations/context/results are validated JSONB with explicit schema versions; no unvalidated universal JSON editor.

Instrument/session snapshots include ranges and all relevant feature flags. Laboratory-owned manufacturers, instruments/equipment/files and derived child records are scoped consistently. Child foreign keys alone do not prove common parent/lab ownership; enforce composite constraints where described and transactional scope checks for polymorphic attachment links.

Section 12 uses generic test_runs with procedure_context and test-specific observations; there is no dedicated disturbance table. Sections 16/17 have construction/checklist tables because they have different workflows.

## 4. Authentication and access

JWT access tokens expire after 15 minutes by default. Refresh tokens are high-entropy opaque secrets stored only as digests in auth_refresh_sessions; default sliding token lifetime is 7 days within a 30-day absolute family lifetime. Rotation, replay-family revocation, logout, logout-all, inactivity and password-reset revocation are transactionally enforced. Cookie/CSRF and client handling follow 06-api-spec.md.

user_role_assignments supports UUID identities and GLOBAL or LABORATORY scope. Backend authorization loads current activity/permissions; token claims are not the source of truth for mutable grants. GLOBAL ADMIN is limited to global administrative operations; regulatory permissions are laboratory-scoped. ADMIN has no final-approval or issue wildcard. See 07-rbac-workflow.md for the complete seeded permission mapping.

## 5. Session creation and applicability

POST /test-sessions creates a DRAFT with all 17 sections, immutable initial instrument/range and ruleset snapshots, and revision counters in one transaction. It does not silently bypass configuration states. Configuration edits before testing create an audited replacement snapshot, increment regulatory_revision and invalidate applicability/current dependent results.

Configuration validation and applicability calculation precede explicit confirmation. Once applicable requirements are resolved, create stable session_test_requirements slots with concrete test/range/scenario identities and initial runs. Unresolved applicability rules produce REVIEW_REQUIRED/UNDETERMINED and block confirmation. Known applicability may be confirmed while a later test evaluator or its acceptance rules remain unimplemented/unverified; that test stays REVIEW_REQUIRED/UNDETERMINED and blocks session completeness, not execution of already supported verified tests. Non-applicable sections remain visible with reasons. Optional election is explicit and audited.

Construction/checklist initialization is idempotent for existing preapproval sessions as their modules become available in Phases 12/13. Before that, their section records remain NOT_STARTED/UNDETERMINED and cannot pass completeness. No required run or checklist response is fabricated to make an early-phase demo appear complete.

## 6. Observation/evaluation flow

1. Authorize scope/permission and check target ETag and session workflow under the parent-session lock.
2. Validate the declared observation schema against the run's pinned schema; reject unknown fields and nonfinite/float-origin metrology inputs.
3. Save observations or typed procedure_context; increment input_revision and session regulatory_revision; append stale/invalidation/audit events atomically.
4. Evaluation captures instrument/ranges, context, observations, pinned rules and versions into evaluation_input_snapshot.
5. The standalone engine checks verified rule availability, applicability, procedural completeness, exact arithmetic and acceptance criteria.
6. Recheck input_revision/workflow before persistence. Concurrently changed source returns SOURCE_CHANGED_DURING_EVALUATION.
7. Persist a new append-only result version or reuse the identical current result; update current result pointer, aggregate states/outcomes and invalidate any dependent reviewed revision.

No evaluator sees live master records. The canonical identity and normalization are defined in 04-r76-rule-engine.md. Significant wall-clock evaluation metadata is stored for audit but excluded from deterministic result hash.

## 7. Correct worked weighing example

Given I=10020 g, e=10 g, ΔL=5 g, L=10000 g and E0=0 g:

| Quantity | Calculation | Value |
|---|---|---:|
| P | 10020 + 0.5 × 10 − 5 | 10020 g |
| E | 10020 − 10000 | 20 g |
| Ec | 20 − 0 | 20 g |

With the candidate fixture limit of 10 g the fixture is NONCOMPLIANT (display FAIL). The regulatory MPE/class/procedure assertions remain TODO_REGULATORY_VALIDATION until signed verification. There is no alternative 15 g result for these inputs.

## 8. Results, attempts and aggregation

One logical requirement slot can have many test attempts and one selected authoritative attempt. New retests preserve the earlier failed run and its outputs. Changing selection requires a documented reason and fresh dependent review. Result versions are append-only; freshness/supersession is tracked by append-only result events and current pointers. Source revisions and review revisions are never represented merely by an audit log.

Every session has workflow_status, evaluation_status and compliance_outcome as separate axes. Completed failures are COMPLETE/NONCOMPLIANT. Failed procedural validation is INCOMPLETE/UNDETERMINED. Unverified rules give REVIEW_REQUIRED/UNDETERMINED. Stale results cannot contribute a current known outcome. Aggregators use DECISIONS F05; reporting cannot override them.

## 9. Review and official issue

Technical review refers to a concrete regulatory_revision. Corrections append invalidation actions and clear its authority. Under-review records cannot be edited until a scoped reviewer correction permits them. Approved/issued records require a new session revision and fresh assessment/review/approval.

Final approval checks completeness, determined outcome, current evidence/results and independent actor authority. COMPLIANT and NONCOMPLIANT can both be approved. Approval records attest to the evaluation, not a certificate grant. Final approval atomically captures session_approval_snapshot with complete reviewed regulatory content and historical master/actor/evidence facts; report generation reads that immutable approval snapshot.

Preview generation is unofficial and may include incomplete data. Official generation captures a persisted immutable report context from approved data. Report issue is separate, officer-authorized and atomic after both outputs are ready. See 08-report-spec.md for numbering, immutable generation attempts, issue metadata and supersession.

## 10. Concurrency, idempotency and transactions

Require If-Match/ETag for mutable updates and lifecycle actions (428 absent, 412 stale). Independently enforce state/scope (409/403). All regulatory writes lock parent session then affected runs in stable order. Approval and report capture use the same session lock. Evaluation can calculate outside locks but must compare captured input revisions on commit. Database constraints prevent multiple selected/current successors.

Persistent idempotency_keys cover sensitive action retries; operation and request digest are bound to actor and lab/global scope. Do not retry a timed-out operation by creating a second report/run. Network/rendering work uses explicit generation jobs and private staged objects outside database locks; finalization checks manifest/hashes before transactional publication. Failed attempts never supersede an issued report.

## 11. Storage and evidence

ObjectStorage adapters implement private presign upload/download and finalization. attachment_uploads records pending ownership, target, expected size/type and expiry; finalization verifies stored bytes/hash before attachment creation. Links must belong to the same lab and respect session locks. A user-provided storage_key is not authority to claim another object's content. Approved linked evidence cannot be replaced/deleted; new evidence creates a new object/version and controlled revision.

Equipment records and calibration documents are available from Phase 3. Evaluation/report snapshots capture applicable calibration facts as of measurement, while master equipment can later change. Exact calibration acceptance rules remain REG-16 pending verification. Environmental readings are per run/phase/time, not one mutable value per multi-day session.

## 12. Audit and operational infrastructure

Services write audit rows in the mutation transaction; auth failure/replay events use durable separate transactions as appropriate. Events identify actor, scope, revisions, cause, before/after or hashes and correlation IDs. Workers preserve initiating actor/job provenance. Credentials/tokens and signed URLs are never audit payloads.

Use async persistence, pagination and targeted indexes; avoid N+1 reads. Cache only immutable versioned rule objects initially. Regulatory evaluation remains synchronous unless demonstrated workload requires scheduling. Rendering/scan/cleanup may use workers with persistent jobs and retry boundaries. Deployment/backup/restore must retain database, private object versions, rule artifacts and report rendering manifests together.

## 13. Build and acceptance

BUILD_PLAN.md owns sequence; earlier alternative milestone/migration orders are retired. Audit/auth/concurrency foundations arrive in Phase 1; equipment/files in Phase 3; applicability in Phase 4; session/result versioning in Phase 5. Full approval/reporting waits for Phases 15/16 and verified applicable rules.

Acceptance requires independent engine tests, PostgreSQL integrity/scope/concurrency tests, stale-result/review tests and equivalent report-context outputs. Bootstrap readiness is distinct from regulatory readiness.
