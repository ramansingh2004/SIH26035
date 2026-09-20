# SIH26035 — RBAC and Regulatory Workflow

Specification Freeze v1 — 2026-09-20. [DECISIONS.md](../DECISIONS.md) F03–F06 and F11–F16 are the frozen policy. Enforcement is in backend services as well as route dependencies; hiding a button is not authorization.

## 1. Scope and identity

Use UUID user_role_assignments with scope_type GLOBAL/LABORATORY. GLOBAL requires a null laboratory_id; LABORATORY requires a non-null laboratory_id. Partial unique active-assignment constraints replace the invalid nullable composite primary key. A user may hold multiple roles and different roles in different labs.

Effective permissions are the union of active assignments within the target laboratory, not a union across labs. GLOBAL assignments authorize only explicitly global administrative operations; they do not expand regulatory access to all labs. Users must be active and grants current on every request. Manufacturers are lab-owned. Rules/catalog are global reference data, read by authorized laboratory users and managed through global administrative grants.

## 2. Permission catalog and complete seeded mappings

The sets below are normative expansions used for seeds, not a partial example matrix. No wildcard is permitted. Permissions not listed for a role are denied. A lab-scoped ADMIN can manage its lab's users/master data; only a global ADMIN can create laboratories or manage global rulesets. User/assignment management cannot target labs outside the actor's administrative scope.

| Set | Exact permissions |
|---|---|
| READ | laboratory:read, manufacturer:read, instrument:read, ruleset:read, session:read, test:read, observation:read, construction:read, checklist:read, equipment:read, attachment:read, approval:read, report:read, dashboard:read |
| MASTER | manufacturer:create, manufacturer:update, manufacturer:archive, instrument:create, instrument:update, instrument:archive, instrument:manage_components, instrument:manage_ranges, equipment:create, equipment:update, equipment:archive |
| ENTRY | session:create, session:update, session:cancel, observation:create, observation:update, observation:delete, test:execute, construction:update, checklist:update, attachment:create, attachment:delete |
| ENGINEER | test:evaluate, test:complete, test:retest, test:select_run, construction:complete, checklist:complete, review:submit, session:reopen, session:create_revision, report:preview, report:generate, report:create_revision |
| REVIEW | review:perform, review:return_correction, session:reopen, session:create_revision, report:preview, report:generate, report:create_revision, audit:read |
| APPROVE | approval:finalize, report:issue, session:create_revision, report:preview, report:generate, report:create_revision, audit:read |
| LAB_ADMIN | user:read, user:create, user:update, user:deactivate, user:manage_roles, role:read, laboratory:update, audit:read |
| GLOBAL_ADMIN | user:read, user:create, user:update, user:deactivate, user:manage_roles, role:read, laboratory:read, laboratory:create, laboratory:update, ruleset:read, ruleset:create, ruleset:validate, ruleset:activate, ruleset:retire, audit:read |

| Role and assignment | Seeded grants |
|---|---|
| ADMIN, GLOBAL | GLOBAL_ADMIN; no laboratory regulatory record permission |
| ADMIN, LABORATORY | READ + MASTER + LAB_ADMIN; no review/final approval/issue automatically |
| LAB_TECHNICIAN, LABORATORY | READ + MASTER + ENTRY |
| LAB_ENGINEER, LABORATORY | READ + MASTER + ENTRY + ENGINEER |
| REVIEWER, LABORATORY | READ + REVIEW |
| APPROVING_OFFICER, LABORATORY | READ + APPROVE |
| VIEWER, LABORATORY | READ |

Only GLOBAL ADMIN assignments are supported globally in v1. Other roles require LABORATORY scope. A global administrator needs an additional lab assignment to read observations/reports. An ADMIN who also has explicit APPROVING_OFFICER assignment may approve through that permission, subject to separation of duties. The role/permission tables, not hardcoded route role-name checks, determine authority.

## 3. Separation of duties

The final approver must differ from session.started_by and every author who created/changed raw observations for the session revision, including provenance retained through copied observations. The technical reviewer must differ from all raw-observation authors. Technician/engineer permissions alone cannot approve. Reviewer and approver may be the same independent person in v1. Preserve actor identities after account rename/deactivation in report snapshots. Approval cannot be obtained by selecting a different display name or using a stale role claim.

## 4. Separate status axes

workflow_status tracks DRAFT, INSTRUMENT_CONFIGURATION, APPLICABILITY_CONFIRMED, TESTING, EXAMINATION, UNDER_REVIEW, APPROVED, REPORT_ISSUED, REJECTED or CANCELLED. evaluation_status tracks NOT_STARTED, IN_PROGRESS, INCOMPLETE, STALE, REVIEW_REQUIRED or COMPLETE. compliance_outcome tracks UNDETERMINED, COMPLIANT, NONCOMPLIANT or NOT_APPLICABLE.

No workflow transition changes a negative outcome into a positive one. PASS/FAIL labels map only to compliance outcomes. Technical approval and final approval attest to the completeness/correctness of the evaluation record. A fully examined failure is complete; an unanswered/missing/unverified requirement is not.

## 5. Workflow transitions

All mutations require scope, target ETag and parent-session transactional checks. Conditions below include verified rules where required.

| From → To | Permission/action | Conditions |
|---|---|---|
| none → DRAFT | session:create | Instrument/lab access valid; initial snapshots and 17 section records captured; candidate DRAFT rules allowed for setup only |
| DRAFT → INSTRUMENT_CONFIGURATION | session:update, configure | Metadata/snapshot schema valid |
| INSTRUMENT_CONFIGURATION → APPLICABILITY_CONFIRMED | test:execute, confirm-applicability | Active pinned ruleset; every applicable decision resolved; required/elected slots/runs generated; no unverified applicability dependency; unverified evaluation rules remain visibly blocked per affected test |
| APPLICABILITY_CONFIRMED → TESTING | test:execute, start-testing | Confirmed applicability and concrete run slots |
| TESTING → EXAMINATION | construction:update, start-examination | Configuration/applicability valid; examination may proceed while other testing remains unfinished |
| TESTING or EXAMINATION → UNDER_REVIEW | review:submit | COMPLETE evaluation; current selected results; required construction/checklist/equipment/evidence complete; determined COMPLIANT or NONCOMPLIANT |
| UNDER_REVIEW → UNDER_REVIEW | review:perform, reviews(APPROVED) | Independent technical approval references current regulatory_revision |
| UNDER_REVIEW → TESTING or EXAMINATION | review:return_correction | Bounded correction scope/reason; append action/request; prior review becomes invalid for affected changes |
| UNDER_REVIEW → REJECTED | review:perform, reviews(REJECTED) | Independent reviewer; reason required; records retained |
| UNDER_REVIEW → APPROVED | approval:finalize, approve | Valid current technical approval, completeness rechecked, independent officer; COMPLIANT or NONCOMPLIANT allowed |
| UNDER_REVIEW → REJECTED | approval:finalize, reject | Officer rejection with reason; no data modification |
| APPROVED → REPORT_ISSUED | report:issue | Selected official generation READY in both formats; issuer/date match context; scope/chain/idempotency checks pass |
| DRAFT/INSTRUMENT_CONFIGURATION/APPLICABILITY_CONFIRMED/TESTING/EXAMINATION → CANCELLED | session:cancel | Reason required; no approval/issued dataset destruction |

REJECTED/CANCELLED are terminal in v1; create a new linked revision to continue. Final officers do not return raw data directly in v1; an authorized reviewer handles corrections while under review. There is no same-session reopening from APPROVED/REPORT_ISSUED.

## 6. Data locking and correction scope

Before review, only permitted fields in permitted states are editable. Once testing begins, changing instrument/ruleset snapshots requires a controlled session revision; do not silently recalculate applicability on live master edits. Draft/configuration snapshot updates invalidate all dependent setup results.

Under review: observations, procedure/context, environments, equipment links, evidence links, results/selection, construction and checklist are read-only. A reviewer creates correction_requests identifying affected sections/entities/field paths and target editable state. Return transitions the session; reopen acknowledges/activates only that existing request and cannot broaden it. Mutations outside correction scope are rejected, even if the user normally has update permission. Submission requires resolving requested corrections.

Every regulatory change increments session.regulatory_revision. Relevant input changes increment run.input_revision, append STALE events and clear current result pointers. Affected technical approvals receive appended INVALIDATED actions; their original approval rows remain intact. If dependencies cannot be isolated, invalidate the full reviewed revision. A new current result or selected retest also changes the reviewed regulatory content and requires fresh review.

Approval atomically captures session_approval_snapshot with the complete approved record and historical lab/manufacturer/equipment/actor/evidence facts. It permanently protects the session snapshot, sources, current/historical results, construction/checklist, evidence links and approval history. Master equipment/manufacturer/user records can still change independently; their historical report facts are frozen.

## 7. Completeness and outcomes

Submission/approval check all required and explicitly elected optional test slots, current valid results, full verified procedures, resolved applicability, complete construction conformance, answered applicable checklist rows, and mandatory equipment/evidence. Missing/unverified rule IDs or modules block completeness. N/A requires a verified rule/reason.

Known complete failed tests/checklist items yield NONCOMPLIANT and can be reviewed/approved/reported. NONCOMPLIANT does not mean missing review. UNDETERMINED cannot be officially issued. The engine aggregate precedence in DECISIONS F05 is shared by services/API/reports; no frontend-only interpretation.

## 8. Retests and revisions

A retest creates a new numbered attempt in a stable requirement slot with reason and retest_of_run_id. Previous attempts/results remain visible. Engineers select the authoritative run explicitly; the previous selection is superseded through an append-only event. If permitted retest policy is unverified, mark REG-16 and block authoritative substitution pending validation.

A post-approval/report correction creates a new session revision, links root/parent and copies inputs with provenance. Reset to INSTRUMENT_CONFIGURATION and require renewed applicability, evaluations, construction/checklist confirmation, review and approval. Do not carry an old technical approval as current. After approval, an official report revision reuses report_number with incremented revision_no and supersedes_report_id/reason. The original remains ISSUED until the new revision successfully issues, then becomes SUPERSEDED without file/context mutation.

## 9. Preview, generation and issue permissions

report:preview allows unofficial watermarked output at any readable stage, including unresolved work. It never reserves an official report number or changes workflow. report:generate operates only on APPROVED complete sessions and persists immutable official generation contexts. report:issue is separate and only seeded for explicit approving officers. Generation by an engineer/reviewer does not authorize issue.

Official issue accepts both COMPLIANT and NONCOMPLIANT. Printed issue date/intended issuer must match the generation snapshot; otherwise regenerate an unissued attempt. Actual issue timestamp and the issued manifest are recorded atomically. Report revision permissions cannot bypass session approval or edit an existing issued file.

## 10. Audit and concurrency ownership

Services own same-transaction audit for role changes, instrument/configuration changes, source mutations, evaluation/selection, corrections, review invalidation, approval, rule activation, report generation/issue/revision and evidence links. AuthService owns login/refresh/logout/replay events. Report workers preserve actor/job provenance. Evaluators/renderers do not generate their own competing audit events.

ETag is optimistic client concurrency; parent-session row locks prevent approval/edit races even when clients use different child ETags. Freshness and reviewed regulatory_revision are checked inside the transaction. Persistent idempotency protects retries; issued artifacts are never recreated based solely on a client timeout.

## 11. Acceptance

Tests must prove scoped multi-role permissions, no ADMIN approval wildcard, author independence, inactive/revoked grants, cross-lab isolation, COMPLETE/NONCOMPLIANT approval, unverified-rule blocking, correction-scope enforcement, stale-result/review invalidation, immutable originals and single-current report supersession. Specifications are frozen policy; no permissions or accounts are created by this documentation task.
