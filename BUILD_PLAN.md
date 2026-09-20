# SIH26035 — Build Plan

Specification Freeze v1 — 2026-09-20. This is the sole phase/dependency plan; alternative phase letters and earlier numerical migration lists are retired. No phase is implemented by this documentation freeze. Wait for explicit user instruction to start Phase 0.

## Global phase rules

Read PROJECT_CONTEXT.md, DECISIONS.md and the named phase specifications; inspect the repository before editing. Implement only the requested phase. Routes contain no OIML calculations or SQL; independent domain types use exact Decimal; async SQLAlchemy/Alembic/Pydantic v2 remain settled. No ML compliance or unverified fabricated thresholds.

Every phase that adds mutations implements its permissions, laboratory scope, optimistic versions, transactional audit and source/review invalidation hooks as applicable. Do not postpone foundational integrity until the final workflow phase. Backend lint/format and relevant unit/integration tests are required; reporting/security/migration gates apply when their features exist. No fabricated complete/N/A states for future modules.

## Phase 0 — Repository bootstrap

Read PROJECT_CONTEXT, DECISIONS and architecture. Create monorepo backend/, frontend/, docs/, README plus the frozen specification files. Backend bootstrap: FastAPI, Python 3.12+, uv/pyproject, Ruff, pytest, Pydantic settings, async SQLAlchemy/Alembic configuration; frontend: Next.js/TypeScript/ESLint. No domain models, feature migrations, auth, regulatory rules or application features yet. Done: backend starts; GET /health returns 200; frontend starts; lint/test commands work; README documents local startup. Preserve specification freeze files unchanged unless a separately authorized decision revises them.

## Phase 1 — PostgreSQL, auth, labs and cross-cutting foundations

Read 03/05/06/07/09. Implement users/roles/permissions/role_permissions/laboratories/user_role_assignments, auth_refresh_sessions, audit_events and idempotency_keys. Implement password hashing, login/rotation/replay revocation/logout/logout-all/session listing/revocation/password lifecycle, effective permissions, explicit scopes, current user activity, ETag conventions, transaction/audit ownership. Seed the complete permission matrix with no ADMIN approval wildcard. Secure bootstrap-admin provisioning is documented; no committed passwords.

Done: allowed users access only authorized scope; UUID scope constraints/global null handling work; refresh replay and revocation tests pass; auth/concurrency/idempotency primitives and audit tests exist. No session-specific tables yet; later phases plug into these foundations.

## Phase 2 — Manufacturers and instruments

Read 02 common candidates, 05/06/09. Implement lab-owned manufacturers, instruments/ranges/components and typed applicability metadata. Exact Decimal sanity and n arithmetic; master CRUD/archive/history placeholder; range/component permissions and audit. Regulatory classification verification waits for versioned verified rules; return explicit TODOs rather than claiming full validation from positive numeric fields.

Done: sane configuration/ranges/components persist; cross-lab manufacturer references fail; exact values survive serialization; unsupported precision rejected; invalid Max/Min/e/d tests pass. No full R76 evaluator yet.

## Phase 3 — Rules/catalog plus equipment and attachment foundations

Read 03/04 loader contract, 05/06/09. Implement versioned rule_sets/rule_definitions/test_definitions/checklist_rules, standard-part/source metadata, verification gate, supported-test declarations, immutable RuleSet loader/validation/hash/registry. Seed 17 sections and all subtest families as candidate definitions, not verified production rules.

Also implement test_equipment, attachment_uploads, attachments, attachment_links and ObjectStorage/MinioStorage/S3Storage private upload/download/finalization foundations. Test-run-equipment association is added in Phase 5 once runs exist. Implement size/MIME/ownership/hash checks, equipment calibration snapshot shape, same-lab evidence linking and lifecycle guards for existing targets. This moves infrastructure ahead of dependent test/dossier features; Phase 14 is hardening, not first availability.

Done: deterministic rule hashes, valid/invalid configuration, no activation of unverified supported dependencies, inspectable catalog, private verified upload round-trip and equipment CRUD all tested. A DRAFT rule can be inspected; candidate fixture data cannot issue an official report.

## Phase 4 — Independent R76 engine, context and applicability

Read 02/04/09. Implement immutable domain types, three status axes, typed versioned procedure_context, observation schema registry, canonical evaluation-input normalization/hash, calculation primitives, operator-aware comparisons, evaluator registry and engine. Implement applicability (not merely a skeleton), feature/range validation and required/elected slot planning needed before Phase 5. Implement aggregation primitives and missing-rule gates.

Done: all implemented verified/synthetic-fixture calculation boundaries and exact arithmetic/hash fixtures pass without HTTP/DB. Unknown/absent regulatory rules yield REVIEW_REQUIRED/UNDETERMINED. Applicability is available before session creation; the initial instrument matrix has explicit verified decisions or documented blockers. Hard gate: do not wire calculations into FastAPI before pure domain tests pass. Regulatory TODOs remain blockers for authoritative features, not permission to guess.

## Phase 5 — Sessions, versioned results and Section 1 slice

Read 03–07/09. Implement test_sessions, 17 sections, session_test_requirements, test_runs, environment_readings, observations, test_run_results, evaluation_result_events, selection events and test_run_equipment. Implement explicit draft/configure/applicability-confirm/start states, snapshots/revisions, ETags/parent locks, typed context, source invalidation and append-only result versions. Retest/history/selection foundations belong here. Approval states are protected even though full review UI/service comes later.

Implement Section 1 evaluator with complete verified procedure validation; first pass pure evaluator tests, then API integration. DRAFT setup is allowed with candidate rules; authoritative confirmation/evaluation requires the regulatory gates. Isolated synthetic integration tests are clearly labeled and cannot feed official issue.

Done: instrument → DRAFT session with 17 visible sections → confirmed verified applicability → Section 1 observations/context → independent engine → versioned result → API. Future construction/checklist modules remain explicitly NOT_STARTED/UNDETERMINED; no full approval/report claim. Source edits/retests preserve history and reject stale commits.

## Phase 6 — Core reusable tests

Implement Sections 3 eccentricity, 5 repeatability and 9 tare. Each has observation/context schemas, applicability, verified procedure rules, evaluator, specialized API data and unit/integration tests. Geometry/scenarios/counts/equipment/environment inputs are explicit. Reuse MPE/error primitives without copying thresholds.

## Phase 7 — Functional and time tests

Implement Sections 4 discrimination/sensitivity, 6 ZERO_RETURN/CREEP and 7 stability of equilibrium. Cover mode differences, short/extended timing, printing/storage and zero/tare subparts, and section aggregation. Missing exact sensitivity/zero-return procedures remain TODO_REGULATORY_VALIDATION rather than placeholder success.

## Phase 8 — Influence tests

Implement Sections 2 temperature zero drift, 8 tilting, 10 warm-up and 11 voltage variations. Add typed environment/power/protection metadata, strict versus inclusive verified boundary tests, timing and scenario completeness. Use infrastructure already available from Phases 3/5.

## Phase 9 — Climatic and long-duration tests

Implement Sections 13 damp heat and 14 span stability: phase/time-series validation, measurement count/order/intervals, environmental/equipment snapshots and verified trend/extension rules. Frontend graph work may wait, but stored trace/context must support it.

## Phase 10 — Electrical disturbances

Implement seven Section 12 subtest families using generic runs, typed procedure_context and validated JSONB observations. Reuse a disturbance base with verified severity/procedure/fault-response logic; do not create a dedicated disturbance table. Cover missing severity, within-limit, excessive unhandled fault and valid handled-fault cases. Physical waveforms/equipment are recorded, not simulated as evidence.

## Phase 11 — Endurance

Implement Section 15 applicability, cycles, pre/post pairing and durability criteria. Verify full prerequisite/count/timing rules and preserve equipment evidence. Incomplete cycling cannot become a completed compliance outcome.

## Phase 12 — Construction examination

Implement construction_examinations/items and versioned required categories: general, receptor/load cells, indicator/display, printer/peripherals, power/interfaces, tilt/zero/tare, seals/security/software and documents/photos. Use Phase 3 evidence infrastructure; no attachment dependency gap. Initialize missing dossiers idempotently for existing preapproval sessions. Complete data entry plus explicit required conformance yields COMPLETE; failed examined requirements yield NONCOMPLIANT. No fabricated numeric evaluator.

## Phase 13 — Checklist engine

Implement checklist_responses and ChecklistEngine using Phase 3 versioned rules. Groups GENERAL/DIRECT_SALES/ELECTRONIC/SOFTWARE_CONTROLLED. Initialize applicable response rows and retain excluded applicability decisions for consistent totals. Examine/evidence all required verified rows; FAIL is answered, NOT_EXAMINED is not. Initialize existing preapproval sessions idempotently; never change approved snapshots in place.

## Phase 14 — Equipment/evidence hardening

Harden the infrastructure already present: calibration-at-measurement rules after verification, mandatory-evidence mapping, multi-day environment traceability, private object retention/version protection, file/link lock enforcement, expired/staged-upload cleanup and recovery. Exercise cross-lab, protected-delete and source-invalidation paths. No first-time creation of a dependency that earlier features already require.

## Phase 15 — Review, final approval and revision governance

Implement approval_actions/correction_requests/session_approval_snapshots, full state machine, completeness validators, independent-actor checks, bounded correction/reopen, review invalidation and session revisions. Integrate versioning/audit/concurrency foundations from Phases 1/5; do not replace them. Prove COMPLETE/NONCOMPLIANT can be technically reviewed/finally approved, while STALE/UNDETERMINED/unverified required work cannot. Approved/issued sources remain immutable; corrections clone a controlled revision.

## Phase 16 — Report engine, previews and official issue

Read 08/05/06/09. Implement number counters, reports, immutable report_generations/report_context_snapshot, report_files and report_previews. Both renderers use one context; preserve master/equipment/actor/checklist history; no recalculation. Implement unofficial preview, generation/recovery, separate officer issue, immutable file/context hashes, numbering, revisions and atomic supersession. Test both compliant and noncompliant approved reports, failure recovery, issue metadata and concurrent successors.

## Phase 17 — Repository, search and dashboard

Implement report/session search, paginated instrument/revision/retest history and scoped dashboard summaries. Expose workflow/readiness/outcome separately. Include current/superseded report metadata and traceability. Avoid unbounded analytics/N+1 queries.

## Phase 18 — Frontend foundation

Implement auth/refresh cookie integration, app shell, navigation, TanStack Query, typed API client, CSRF/ETag/idempotency handling, permission-aware UI and form infrastructure. Bootstrap shell from Phase 0 is not feature implementation.

## Phase 19 — Frontend master data

Build manufacturer/instrument/range/component/equipment screens, lab context and evidence upload UX. Preserve Decimal strings and explicit unknown applicability facts; show regulatory-validation blockers rather than optimistic success.

## Phase 20 — Frontend evaluation workspace

Build all 17 specialized section views/forms, typed procedure metadata, retest/result history, stale/review indicators, traces and diagrams/charts. No universal JSON editor or frontend compliance calculations. Source conflicts are surfaced; do not overwrite on 412.

## Phase 21 — Frontend review and report repository

Build technical review, scoped corrections, final approval, unofficial preview, generation/issue, revisions and repository/history. Clearly distinguish approved record from COMPLIANT outcome and UNISSUED generation from official issue.

## Phase 22 — Deployment

Docker Compose development: PostgreSQL/MinIO/backend/frontend; production target: HTTPS/Nginx/FastAPI/PostgreSQL or RDS/private S3/Next.js. Add secrets, logging/health checks, backups/restores for database/object versions/rule/render artifacts, worker recovery and least-privilege DB/object access. Do not silently change frozen architecture.

## Phase 23 — SIH demo data

Seed a lab, manufacturer, Class III scale, equipment and complete sample scenarios including positive/negative outcomes. Synthetic/unverified rule data must be visibly unofficial and cannot issue official reports; show previews if regulatory verification is incomplete. If demonstrating official issue, use only verified complete approved data. No production bypass or hidden shortcuts.

## Phase 24 — SIH polish

Guided onboarding, clean progress, calculation explanations, report download and traceability. Optional QR verification/AI explanation after the deterministic core and gates; AI never supplies thresholds or changes outcomes.

## Phase completion report

Every implementation phase reports changed files, migrations, endpoints, tests, commands/results, known limitations/regulatory blockers and next phase. Regulatory release gate: verified applicable rules plus passed calculation/workflow/migration/auth/context tests. Bootstrap gate: Phase 0 starts and toolchain works. These are intentionally different readiness levels.
