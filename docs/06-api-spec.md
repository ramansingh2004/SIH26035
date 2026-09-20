# SIH26035 — API Contract

Specification Freeze v1 — 2026-09-20. Base path /api/v1; the process health endpoint is absolute /health outside that prefix; [07-rbac-workflow.md](07-rbac-workflow.md) owns effective permissions and state rules, [04-r76-rule-engine.md](04-r76-rule-engine.md) owns domain payloads, [05-database-schema.md](05-database-schema.md) owns persistence.

## 1. Shared conventions

JSON requests/responses use UUID strings and finite metrological Decimal strings. Reject unknown payload fields, incompatible schema versions, duplicate keys and nonfinite/float-origin metrology. Timestamps are timezone-aware and normalized to UTC. List envelope: items, page, page_size, total; defaults page=1/page_size=20, maximum 100. Sorting accepts explicit allowlisted fields only. Single resources return their fields directly.

Regulatory resources expose workflow_status where relevant plus evaluation_status and compliance_outcome; never a generic overloaded status. They expose lock_version/ETag, regulatory_revision for sessions and input_revision for runs. Canonical result keys are defined in 04, including corrected_error_g rather than competing Ec_g names. Checklist answer request field is response_result; PASS/FAIL remain valid checklist answers only.

Error envelope has error.code, message, details and request_id. HTTP: 401 invalid/missing auth; 403 missing permission/scope (404 may conceal a cross-lab object consistently); 404 absent authorized resource; 409 workflow/idempotency/source conflict; 412 stale If-Match; 422 malformed/incomplete input; 428 missing If-Match. All GET endpoints require authentication except health; permission and lab checks apply even when omitted from a path description.

## 2. Concurrency and retry contract

Require If-Match on PATCH/DELETE and mutating actions for existing resources; child POST uses the parent ETag. Independent root creation needs no ETag. Require Idempotency-Key for session creation, evaluate, final approval, retest/revision creation, report generation and issue. Successful replay by the same authorized actor/scope returns the stored response; same key/different normalized request returns 409 IDEMPOTENCY_CONFLICT. IN_PROGRESS returns 409 OPERATION_IN_PROGRESS. A valid replay is resolved before stale ETag checks; authorization is still checked.

Services lock parent session then affected runs, check state/correction scope and revisions, and commit mutations plus audit atomically. Evaluation captures immutable inputs, calculates outside locks, then returns 409 SOURCE_CHANGED_DURING_EVALUATION if input_revision changed or session became locked. A 412/409 never silently overwrites evidence. Upload/render calls are outside DB locks with persistent pending/failed states.

## 3. Authentication and account lifecycle

| Method/path | Access | Contract |
|---|---|---|
| GET /health | Public | Phase 0 process health only; 200 when process is serving |
| POST /auth/login | Public, rate-limited | Email/password; access_token, token_type=bearer, expires_in; sets HttpOnly refresh cookie; no refresh secret in response body |
| POST /auth/refresh | Refresh cookie + CSRF/Origin validation | Atomically rotate persistent session; new access JWT and cookie; replay revokes family |
| POST /auth/logout | Refresh cookie + CSRF/Origin validation | Revoke corresponding family if present, clear cookie; idempotent 204 even if already revoked |
| POST /auth/logout-all | Active user + CSRF/Origin validation | Revoke all user's refresh families, clear cookie; 204 |
| GET /auth/me | Active user | Identity and laboratory-scoped roles/effective permissions; global grants separately identified |
| GET /auth/sessions | Active user | Own refresh families/client metadata; never token digest/secret |
| DELETE /auth/sessions/{family_id} | Owner + session ETag | Revoke owned family and audit; 204 |
| POST /auth/password | Active user, current password + CSRF | Set replacement password hash, revoke refresh sessions; no password in logs |

Default JWT lifetime 15 minutes; refresh 7 days with 30-day absolute family cap. Cookie Secure/HttpOnly/SameSite plus Origin/CSRF checks; local insecure HTTP is explicitly development-only. Frontend keeps access token in memory. Account activation and permissions are checked authoritatively on requests. The refresh-family list exposes an aggregate ETag derived from its current session state for revocation.

## 4. Administration and master data

| Methods/paths | Permission | Contract |
|---|---|---|
| GET /laboratories and /laboratories/{id} | laboratory:read | Authorized labs; global administrative listing allowed |
| POST /laboratories | laboratory:create | Global admin scope; create metadata |
| PATCH /laboratories/{id} | laboratory:update | Scope and ETag |
| GET /users | user:read | Filters lab, role, active, search; administrative scope |
| POST /users | user:create | Create account; secure initial credential setup, no logging |
| PATCH /users/{id} | user:update | Profile/active changes; deactivation additionally requires user:deactivate and revokes sessions |
| POST /users/{id}/reset-password | user:update | Administrative reset; invalidate refresh sessions; secret supplied/handled privately |
| GET /roles | role:read | Role/permission mapping |
| GET /users/{id}/role-assignments | user:read | UUID assignments with explicit scopes |
| POST /users/{id}/role-assignments | user:manage_roles | scope_type and laboratory_id matching invariant; no grant outside actor scope |
| DELETE /users/{id}/role-assignments/{assignment_id} | user:manage_roles | Revoke assignment, retain historical row |
| GET /manufacturers and /manufacturers/{id} | manufacturer:read | Lab-scoped search/registration/country filters |
| POST /manufacturers | manufacturer:create | laboratory_id required; name/address/contact data |
| PATCH /manufacturers/{id} | manufacturer:update | Does not alter historical snapshots |
| POST /manufacturers/{id}/archive | manufacturer:archive | No destructive deletion |
| GET /instruments and /instruments/{id} | instrument:read | Lab/manufacturer/class/status/search filters |
| POST /instruments | instrument:create | Exact numeric fields, typed applicability metadata; n calculated exactly |
| PATCH /instruments/{id} | instrument:update | Master edit only; old sessions unchanged |
| POST /instruments/{id}/archive | instrument:archive | Preserve linked evaluations |
| POST /instruments/validate-configuration | instrument:create | Candidate schema/config validation; return errors/warnings and regulatory TODOs, never claim regulatory validity from shape alone |
| GET /instruments/{id}/ranges and /components | instrument:read | Current master children |
| POST/PATCH/DELETE /instruments/{id}/ranges[/{range_id}] | instrument:manage_ranges | Child create/update/archive semantics; prohibit dangling/range-invalid active configuration |
| POST/PATCH/DELETE /instruments/{id}/components[/{component_id}] | instrument:manage_components | Master children; historical snapshot unaffected |
| GET /instruments/{id}/history | instrument:read | Sessions/revisions/reports with outcome/workflow/history |

Square-bracket notation denotes collection POST versus item PATCH/DELETE routes, not literal URL characters. No mass/interval field uses a JSON floating number. Applicability feature fields include direct sales, DSD, interface/port, power, tilt and range facts; preserve unknown values until confirmed.

## 5. Rulesets and catalog

| Method/path | Permission | Contract |
|---|---|---|
| GET /rulesets, /rulesets/{id}, /rulesets/{id}/tests, /rulesets/{id}/checklist | ruleset:read | Version/hash/parts, verification state, supported tests, catalog/wording |
| POST /rulesets | ruleset:create | Register draft from versioned source artifact; no arbitrary active JSON edits |
| POST /rulesets/{id}/validate | ruleset:validate | Schema/hash/provenance validation; cannot fabricate competent verification |
| POST /rulesets/{id}/activate | ruleset:activate | All transitive normative rules for declared supported tests VERIFIED; serialized default-version change |
| POST /rulesets/{id}/retire | ruleset:retire | No new selection; historical pinned sessions retain reproducibility |

Creation/validation/activation/retirement require GLOBAL administrative grants. Invalid/missing verification returns 409 RULESET_NOT_VERIFIED with TODO_REGULATORY_VALIDATION details. Changing active content registers a new version; no active-rule PATCH exists.

## 6. Session lifecycle

| Method/path | Permission | Contract |
|---|---|---|
| GET /test-sessions and /test-sessions/{id} | session:read | Filter lab/instrument/workflow/outcome/date/application/report; show three axes |
| POST /test-sessions | session:create | instrument_id, rule_set_id, application_number, evaluation_context; creates DRAFT snapshots and all 17 sections; no silent applicability confirmation |
| PATCH /test-sessions/{id} | session:update | Preapproval editable metadata; regulatory changes increment revision; state/correction scope enforced |
| POST /test-sessions/{id}/configure | session:update | DRAFT/configuration only; typed snapshot setup; enters INSTRUMENT_CONFIGURATION |
| POST /test-sessions/{id}/applicability | test:execute | Recompute structured decisions from pinned snapshots/rules; required TODOs remain unresolved |
| POST /test-sessions/{id}/confirm-applicability | test:execute | Explicit optional elections; requires verified resolved applicability and active pinned rules; creates slots/initial runs, enters APPLICABILITY_CONFIRMED |
| POST /test-sessions/{id}/start-testing | test:execute | APPLICABILITY_CONFIRMED → TESTING |
| POST /test-sessions/{id}/start-examination | construction:update | TESTING → EXAMINATION; does not mark testing complete |
| POST /test-sessions/{id}/submit-for-review | review:submit | Completeness/current-results/evidence gate, accepts known NONCOMPLIANT; enters UNDER_REVIEW |
| POST /test-sessions/{id}/return-for-correction | review:return_correction | Reason, entity/field scope, target TESTING/EXAMINATION; append correction/review actions |
| POST /test-sessions/{id}/reopen | session:reopen | Activate existing open correction request only; cannot reopen approved/issued sessions |
| POST /test-sessions/{id}/cancel | session:cancel | Enumerated pre-review editable states only; reason required |
| POST /test-sessions/{id}/revisions | session:create_revision | Reason; create child session snapshot/provenance with fresh configuration/evaluation/review; original unchanged |
| GET /test-sessions/{id}/revisions | session:read | Ordered root/parent revision chain |
| GET /test-sessions/{id}/dashboard | session:read | All 17 sections with applicability, evaluation_status, compliance_outcome and progress |
| GET /test-sessions/{id}/sections[/{section_number}] | session:read | Section/slots/runs/summaries; always 17 in collection |
| GET /test-sessions/{id}/corrections | session:read | Scoped correction requests/status |
| POST /test-sessions/{id}/corrections/{request_id}/resolve | session:update | Engineer/entry mutation allowed only within scope; record evidence of correction before resubmission |

No override can turn TODO_REGULATORY_VALIDATION into N/A or waive a required test. Manual applicability confirmation requires a verified rule with explicit examiner evidence. A DRAFT ruleset can be pinned for setup/preview only; confirmation requires ACTIVE rules satisfying required applicability/dependency gates. Existing confirmed sessions pinned to a later RETIRED version may continue under their original version.

## 7. Runs, context, retests and results

| Method/path | Permission | Contract |
|---|---|---|
| GET /test-runs/{id} | test:read | Context, schema/input versions, result/currentness and selected-attempt state |
| POST /test-runs/{id}/start | test:execute | Permitted editable session; NOT_STARTED → IN_PROGRESS |
| PATCH /test-runs/{id}/procedure-context | test:execute | Typed test-specific context/schema; source mutation invalidates results/review |
| POST /test-runs/{id}/evaluate | test:evaluate | No body; canonical captured inputs; reuse current same hash or append version; missing rules return stored REVIEW_REQUIRED/UNDETERMINED assessment |
| POST /test-runs/{id}/complete | test:complete | Verified valid current complete procedure/evidence; accepts NONCOMPLIANT |
| GET /test-runs/{id}/results | test:read | All evaluation versions, hashes, freshness events; no overwritten prior results |
| GET /test-runs/{id}/results/{result_id} | test:read | Immutable exact inputs, context, calculation trace and output |
| POST /test-runs/{id}/retests | test:retest | Mandatory reason; new run_no in same requirement slot, retest_of_run_id; does not auto-select |
| POST /test-requirements/{id}/select-run | test:select_run | run_id and reason; same slot; verified permitted retest policy; invalidates dependent review and records previous selection |

Known N/A run invocation returns 409 TEST_NOT_APPLICABLE. Locked source returns 409 TEST_ALREADY_LOCKED. Missing procedure observations returns 422 MISSING_REQUIRED_OBSERVATIONS and INCOMPLETE readiness. Unknown/unverified rule is not an observed failure: successful explanatory assessment response is 200 with REVIEW_REQUIRED/UNDETERMINED and issue_code TODO_REGULATORY_VALIDATION.

## 8. Observations, environment, equipment and evidence

| Methods/paths | Permission | Contract |
|---|---|---|
| GET /test-runs/{id}/observations | observation:read | Ordered typed observations |
| POST /test-runs/{id}/observations | observation:create | sequence_no, observation_type, payload_schema_version, payload; schema must match run |
| PATCH /test-runs/{id}/observations/{observation_id} | observation:update | ETag/source revision/correction checks; mark dependent results stale |
| DELETE /test-runs/{id}/observations/{observation_id} | observation:delete | Editable source only; preserve historical evaluation snapshots and audit |
| GET /test-runs/{id}/environment | observation:read | Phase/time-series values |
| POST/PATCH/DELETE /test-runs/{id}/environment[/{reading_id}] | observation:create for POST; observation:update for PATCH; observation:delete for DELETE | Source invalidation applies |
| GET /test-equipment and /test-equipment/{id} | equipment:read | Lab-scoped registry/calibration data |
| POST /test-equipment | equipment:create | Create master equipment |
| PATCH /test-equipment/{id} | equipment:update | No historical snapshot change |
| POST /test-equipment/{id}/archive | equipment:archive | Preserve linked history |
| POST/DELETE /test-runs/{id}/equipment/{equipment_id} | test:execute | Capture/remove editable link/snapshot; calibration gate; invalidate dependent results/review |
| POST /attachments/presign | attachment:create | lab + authorized target + name/type/size; return upload_id and short-lived URL, not unrestricted ownership |
| POST /attachments/complete | attachment:create | upload_id; verify remote object/hash/type/size, parent ETag and ownership; return immutable attachment metadata |
| POST /attachments/{id}/link | attachment:create | entity_type/id/purpose; same lab, supported target, parent ETag/state |
| DELETE /attachments/{id}/links/{link_id} | attachment:delete | Editable evidence only; regulatory revision invalidation |
| DELETE /attachments/{id} | attachment:delete | Archive only if no approved/issued dependency; reject protected deletion |
| GET /attachments/{id}/download | attachment:read | Authorized short-lived private URL |

Presign establishes no evidence acceptance until finalization. Upload links/download URLs and tokens are not logged. Approved objects cannot be overwritten under the same key.

## 9. Construction and checklist

| Method/path | Permission | Contract |
|---|---|---|
| GET /test-sessions/{id}/construction and /construction/items | construction:read | Versioned requirements, values, conformance and completeness |
| PATCH /test-sessions/{id}/construction | construction:update | Dossier notes/metadata within scope |
| PATCH /test-sessions/{id}/construction/items/{item_id} | construction:update | examination_state, conformance_result, typed value, remarks/evidence; no fabricated MPE |
| POST /test-sessions/{id}/construction/complete | construction:complete | Required verified items examined and conformance resolved; FAIL is complete negative |
| GET /test-sessions/{id}/checklist | checklist:read | group/response filters; versioned clause/wording/applicability |
| PATCH /test-sessions/{id}/checklist/{rule_id} | checklist:update | response_result PASS/FAIL/NOT_APPLICABLE/NOT_EXAMINED; evidence/remarks; N/A requires verified justification |
| POST /test-sessions/{id}/checklist/complete | checklist:complete | All applicable rows examined/evidence present; failure does not mean unanswered |
| GET /test-sessions/{id}/checklist/summary | checklist:read | catalog_total, applicable, passed, failed, not_examined, not_applicable, evaluation_status, compliance_outcome |

Applicable response rows and retained N/A applicability-decision rows support consistent totals. No examiner/time is fabricated for unexamined rows. Source changes invalidate dependent review.

## 10. Review and final approval

| Method/path | Permission | Contract |
|---|---|---|
| GET /test-sessions/{id}/reviews | approval:read | Append-only actions/revisions/invalidation history |
| POST /test-sessions/{id}/reviews | review:perform | decision APPROVED or REJECTED; comment; reviewed_regulatory_revision; independence checks. Corrections use dedicated return endpoint. |
| POST /test-sessions/{id}/approve | approval:finalize | Current independent technical approval + complete current data; outcome COMPLIANT or NONCOMPLIANT; capture immutable session_approval_snapshot and lock dataset |
| POST /test-sessions/{id}/reject | approval:finalize | Officer rejection while UNDER_REVIEW; reason mandatory |

ADMIN has no approval:finalize by default. Final approving officer cannot modify source observations. Corrections after approval create child session revisions, not same-row edits.

## 11. Preview, official reporting and repository

| Method/path | Permission | Contract |
|---|---|---|
| POST /test-sessions/{id}/report-previews | report:preview | Capture working snapshot; formats PDF/DOCX; watermarked; returns preview/job ID, no official number |
| GET /report-previews/{id} | report:read | Authorized preview state/metadata |
| GET /report-previews/{id}/download?format=pdf\|docx | report:read | Private watermarked file |
| POST /test-sessions/{id}/reports | report:generate | APPROVED only; both mandatory formats; intended_issuer_id, planned_issue_date; reserve number/revision, freeze context and generation attempt |
| POST /reports/{id}/regenerate | report:generate | UNISSUED only; new attempt/context when metadata changes or rendering retries; never overwrite issued generation |
| GET /reports and /reports/{id} | report:read | Lab/manufacturer/instrument/number/outcome/report_status/date/search filters |
| GET /reports/{id}/generations | report:read | Attempt states/hashes/failures; private authorized content |
| GET /reports/{id}/files | report:read | Selected generation's formats/hashes |
| GET /reports/{id}/download?format=pdf\|docx | report:read | Authorized selected file; UNISSUED metadata clear; no implicit issue |
| POST /reports/{id}/issue | report:issue | generation_id + expected predecessor; officer, planned date, current approved snapshot, both files READY; atomic issue/supersession |
| POST /reports/{id}/revisions | report:create_revision | Approved child test_session_id, revision_reason, planned issue metadata; reserve same-number next revision and generate immutable attempt |
| GET /reports/{id}/revisions | report:read | Full report chain, current/superseded metadata |
| GET /dashboard/summary | dashboard:read | Scoped progress/review/issued counts and recent activity; paginated drill-down |
| GET /audit-events | audit:read | Scope/entity/date filters; immutable audit data |

Generation endpoints return 202 with persistent generation IDs when asynchronous (201 if fully completed synchronously); status endpoints expose GENERATING/READY/FAILED without implying issue. previews never use reports rows. Failure reports are valid official outputs after approval. A report revision must reference an approved child session of the source lineage; original issued files/context remain unchanged. POST /reports is not a free-form content endpoint.

## 12. Required error codes and phase gates

Codes include AUTHENTICATION_REQUIRED, INVALID_CREDENTIALS, PERMISSION_DENIED, RESOURCE_NOT_FOUND, INVALID_INSTRUMENT_CONFIGURATION, RULESET_NOT_FOUND, RULESET_NOT_ACTIVE, RULESET_NOT_VERIFIED, TODO_REGULATORY_VALIDATION, TEST_NOT_APPLICABLE, TEST_ALREADY_LOCKED, INVALID_OBSERVATION_SCHEMA, MISSING_REQUIRED_OBSERVATIONS, EVALUATION_NOT_POSSIBLE, SESSION_INVALID_STATE, SESSION_NOT_READY_FOR_REVIEW, SESSION_NOT_READY_FOR_APPROVAL, CORRECTION_SCOPE_VIOLATION, SOURCE_CHANGED_DURING_EVALUATION, PRECONDITION_REQUIRED, VERSION_CONFLICT, IDEMPOTENCY_CONFLICT, OPERATION_IN_PROGRESS, REPORT_ALREADY_ISSUED, REPORT_GENERATION_FAILED, REPORT_CHAIN_CONFLICT, ISSUE_METADATA_MISMATCH, FILE_INVALID and FILE_TOO_LARGE.

Endpoints arrive in their BUILD_PLAN phase, not all at bootstrap. Unimplemented sections stay visibly unfinished. OpenAPI must reflect the frozen contract; generated documentation does not override the specification. No endpoint may suppress regulatory TODOs to produce an official report.
