# SIH26035 — Canonical PostgreSQL Schema

Specification Freeze v1 — 2026-09-20. This is a declarative schema contract, not a migration or backend implementation. It incorporates [DECISIONS.md](../DECISIONS.md), particularly F03 and F08–F15.

## 1. Conventions

UUID primary keys except explicitly named join keys. Time instants use TIMESTAMPTZ; calendar dates use DATE; email uses CITEXT. Enable pgcrypto/citext; pg_trgm is optional for later fuzzy search. Metrology uses exact NUMERIC, never FLOAT/DOUBLE PRECISION. API/JSONB Decimal values are normalized decimal strings. NUMERIC(20,6) mass, NUMERIC(12,4) voltage and NUMERIC(8,3) temperature are initial storage envelopes; reject nonrepresentable values before insert, never silently round. Wider verified needs require an explicit schema migration. Intermediate exact results live in validated JSONB strings.

Unless stated otherwise, mutable entities have created_at, updated_at, lock_version (positive integer starting at 1), and created_by where attribution applies. Versions increment atomically on mutation. Immutable events/snapshots have creation metadata and cannot be updated/deleted by application roles. Soft archive master records instead of destroying regulatory history. Referential deletion defaults to RESTRICT for regulatory data.

Fields listed without optional markers are required unless described as phase-dependent. Nullable relationship decisions are stated explicitly. All JSONB has a registered schema/version: observations, contexts, snapshots, configuration, addresses, component metadata and audit structures. Unknown legal-data fields are rejected, not silently dropped.

## 2. Identity and laboratory scope

| Table | Fields and constraints |
|---|---|
| users | id; unique email; password_hash; full_name; is_active; last_login_at nullable; mutable metadata. Never store raw passwords. |
| roles | id; unique code; name; description nullable. Six frozen codes from PROJECT_CONTEXT. |
| permissions | id; unique code; description. Canonical catalog in 07-rbac-workflow. |
| role_permissions | role_id, permission_id; composite PK. Seed assignments have no ADMIN wildcard. Changes are audited. |
| laboratories | id; name; unique code; address_line1/2, city/state/postal_code/country; phone/email; accreditation_no; logo_attachment_id nullable; timezone (default UTC); is_active; mutable metadata. |
| user_role_assignments | id UUID PK; user_id; role_id; scope_type GLOBAL or LABORATORY; laboratory_id nullable; assigned_by; assigned_at; revoked_by/revoked_at/revocation_reason nullable; lock_version. |

Assignment constraints: GLOBAL iff laboratory_id IS NULL; LABORATORY iff laboratory_id IS NOT NULL. Unique active GLOBAL (user_id, role_id), and unique active LABORATORY (user_id, role_id, laboratory_id), implemented with partial unique indexes where revoked_at IS NULL. A new assignment after revocation receives a new UUID; preserve history. No nullable composite primary key.

Global permissions only apply to global administrative operations. Regulatory data always needs lab-scoped authorization. Inactive users and revoked assignments cannot authorize new requests. Role and laboratory changes require explicit actor scope; assigning oneself regulatory authority is auditable and does not bypass separation of duties.

## 3. Auth sessions and idempotency

| Table | Fields and constraints |
|---|---|
| auth_refresh_sessions | id; user_id; family_id; unique token_digest; parent_session_id/replaced_by_session_id nullable self-FKs; created_at; expires_at; family_expires_at; consumed_at/revoked_at/revocation_reason nullable; client_ip/user_agent nullable. Unique non-null parent_session_id prevents multiple successors. |
| idempotency_keys | id; actor_id; scope_key (GLOBAL or lab UUID text); operation; key; request_hash; operation_status IN_PROGRESS/SUCCEEDED/FAILED; response_status/body nullable; resource_ids JSONB; created_at/expires_at. UNIQUE(actor_id, scope_key, operation, key). |

Refresh tokens are stored only as digests. Atomic rotation consumes one session and links exactly one replacement. Reuse revokes the family; logout revokes a family; logout-all and user disable revoke all active sessions. Expiry bounds are enforced under transaction. Active refresh sessions need not share database identity with access JWTs.

Idempotency survives worker/process restarts; IN_PROGRESS is not guessed successful. An expired reservation tied to a regulatory artifact must be reconciled against that artifact before reuse/cleanup; an issued operation is never blindly repeated.

## 4. Manufacturers and instruments

| Table | Fields |
|---|---|
| manufacturers | id; laboratory_id; name; registration_no nullable; address JSONB; contact_person/email/phone/country nullable; is_active; mutable metadata. No cross-lab shared manufacturer in v1. |
| instruments | id; manufacturer_id; laboratory_id; model_name; type_designation/serial_number nullable; accuracy_class I/II/III/IIII; max_capacity_g; min_capacity_g nullable until valid configuration; scale_interval_d_g; verification_interval_e_g; verification_intervals_n; range_type; indication_type; is_self_indicating; is_electronic; is_software_controlled; is_portable; is_mobile; load_receptor_type; support_point_count; tare_type/maximum_tare_g; zero_setting_type/zero_tracking_available; level_indicator_available/automatic_tilt_sensor; power_supply_type; nominal_voltage/min_voltage/max_voltage; declared_temp_min_c/declared_temp_max_c; software_identifier; instrument_status ACTIVE/ARCHIVED; metadata_schema_version/metadata_json; mutable metadata. |
| instrument_ranges | id; instrument_id; range_no; min_capacity_g nullable; max_capacity_g; scale_interval_d_g; verification_interval_e_g; mutable metadata. UNIQUE(instrument_id, range_no). |
| instrument_components | id; instrument_id; component_type; manufacturer_name/model/serial_or_type/certificate_reference nullable; technical_specifications JSONB with schema version; notes nullable; mutable metadata. |

Applicability feature metadata explicitly includes is_direct_sales, is_price_computing, is_labeling, data_storage_device_present, peripheral/interface/port configuration, power charging/vehicle details and declared operating/installation facts. Unknown applicability facts remain null/unknown until confirmed; no silent false defaults where a rule depends on them. Model/API snapshots preserve these fields.

Constraints: Max/e/d > 0; Min >= 0 when present; range_no > 0; valid class code; manufacturer/instrument laboratory match. Exact Min < Max, n = Max/e, class/range/temperature compatibility require domain verification as specified in REG-02. Instrument snapshot includes all ranges/components and facts used by rules; master changes do not rewrite it.

## 5. Rules and catalog

| Table | Fields and constraints |
|---|---|
| rule_sets | id; standard_code/name; standard_parts JSONB (part, edition, amendment/source identity); edition (display label); version; ruleset_status DRAFT/ACTIVE/RETIRED; effective_from/to nullable; configuration_hash; configuration_snapshot JSONB; supported_test_codes; source_reference; validation_summary; created_at/by; activated_at/by nullable. UNIQUE(standard_code, edition, version). |
| rule_definitions | id; rule_set_id; rule_key; section_no/clause_reference; rule_type; configuration JSONB; description; validation_status TODO_REGULATORY_VALIDATION or VERIFIED; source_identity/digest; verified_by/at/evidence nullable until verified. UNIQUE(rule_set_id, rule_key). |
| test_definitions | id; rule_set_id; code; section_number; parent_definition_id nullable self-FK; name; category; sort_order; supports_numeric_evaluation; requires_manual_review; default_observation_schema_version/default_procedure_schema_version; description. UNIQUE(rule_set_id, code); parent belongs to same ruleset. |
| checklist_rules | id; rule_set_id; group_code GENERAL/DIRECT_SALES/ELECTRONIC/SOFTWARE_CONTROLLED; requirement_key; clause_reference; display_text; applicability_expression JSONB; evidence_required; sort_order; validation_status and verification provenance. UNIQUE(rule_set_id, requirement_key). |

Catalog names, hierarchy, checklist wording and construction requirements are versioned with rules, not mutable global live labels. The 17 top-level codes are WEIGHING_PERFORMANCE, TEMPERATURE_ZERO, ECCENTRICITY, DISCRIMINATION_SENSITIVITY, REPEATABILITY, TIME_DEPENDENCE, STABILITY_EQUILIBRIUM, TILTING, TARE, WARM_UP, VOLTAGE_VARIATION, ELECTRICAL_DISTURBANCES, DAMP_HEAT, SPAN_STABILITY, ENDURANCE, CONSTRUCTION_EXAMINATION and CHECKLIST. Subtests include DISCRIMINATION/SENSITIVITY, ZERO_RETURN/CREEP and the seven DISTURBANCE_* codes in 04-r76-rule-engine.md; vehicle/rolling/geometry variants use typed context and requirement keys. Construction requirements are rule_definitions of type CONSTRUCTION_REQUIREMENT; no unversioned frontend-only checklist.

At most one default ACTIVE version per standard_code/edition; activation/retirement is a serialized service transaction. Historical pinned versions remain readable/evaluable for existing authorized sessions. A later active version never auto-migrates a session. VERIFIED provenance is mandatory for supported transitive rules; an unsupported test is represented visibly as blocked. Active normative content is immutable; status/activation events are administrative and audited separately.

## 6. Sessions and revisions

| Table | Fields and constraints |
|---|---|
| test_sessions | id; laboratory_id; instrument_id; rule_set_id; application_number nullable; workflow_status; evaluation_status; compliance_outcome; evaluation_context; started_by/started_at; submitted_at/approved_at/completed_at nullable; instrument_snapshot; ruleset_snapshot; snapshot_schema_version; regulatory_revision >= 1; lock_version; root_session_id; parent_session_id nullable; session_revision_no >= 1; revision_reason nullable only for initial revision; notes; created_at/updated_at. UNIQUE(root_session_id, session_revision_no). |
| test_session_sections | id; test_session_id; section_number 1..17; section_code/name snapshot; applicability_status/reason/references; evaluation_status/compliance_outcome; started_at/completed_at nullable; summary_schema_version/summary_json; lock_version. UNIQUE(test_session_id, section_number). |
| session_test_requirements | id; test_session_id; session_section_id; test_definition_id; requirement_key (stable range/scenario/variant slot); applicability_status/reason/references; is_elected for OPTIONAL; selected_run_id nullable; lock_version. UNIQUE(session_section_id, requirement_key). |
| test_runs | id; test_session_id; session_section_id; requirement_id; test_definition_id; run_no > 0; retest_of_run_id/retest_reason nullable for first attempt; evaluation_status/compliance_outcome; observation_schema_version; procedure_schema_version; procedure_context JSONB; input_revision >= 1; current_result_id nullable; started_by/at/completed_at nullable; lock_version. UNIQUE(requirement_id, run_no). |

Session root points to self on initial creation; parent/root must belong to same instrument/lab. A revision requires reason and explicit permissions. All original approved session data remains immutable. Multiple drafts may exist, but report issue enforces a single current revision chain and compares its expected predecessor.

Enforce matching parent session/section/requirement/test definition and pinned ruleset by composite FK/unique pairs where possible plus transactional checks. selected_run_id belongs to its requirement; current_result_id belongs to its run and current input revision. Circular pointers are initially null and set after target insert in the same transaction. Do not use on-delete cascades to destroy approved data.

The exact three-axis enums are defined in PROJECT_CONTEXT. These fields replace ambiguous generic status columns on regulatory sessions/sections/runs/results. Non-regulatory lifecycle columns have resource-specific names.

## 7. Source observations, context and environments

| Table | Fields |
|---|---|
| test_observations | id; test_run_id; sequence_no > 0; observation_type; recorded_at/by; payload_schema_version; payload_json; is_locked; created_at/updated_at/lock_version. UNIQUE(test_run_id, sequence_no). |
| environment_readings | id; test_session_id; test_run_id; measured_at; temperature_c/relative_humidity_percent/barometric_pressure_hpa as applicable; phase; notes; recorded_by; mutable metadata. |

Environment readings affecting a run are captured in typed procedure_context before evaluation; changing or linking them invalidates dependent results. Observation payload_schema_version must equal its run observation_schema_version. Exact chronology/count/stage rules remain test-specific regulatory gates. Before approval, source edits are allowed only in permitted workflow/correction scope and are audited. Historical evaluations preserve complete immutable source snapshots independently of edits/deletion of draft source rows.

## 8. Versioned results and attempt selection

| Table | Fields and constraints |
|---|---|
| test_run_results | id; test_run_id; evaluation_version > 0; supersedes_result_id nullable; rule_set_id; source_input_revision; evaluation_input_snapshot; hash_schema_version; observation_schema_version; procedure_schema_version; engine_version; ruleset_version/hash; applicability_status/reason; evaluation_status/compliance_outcome; calculations_json; acceptance_limits_json; failed_conditions_json; rule_references_json; reason/issue_code/unresolved_rule_ids; input_hash/result_hash; evaluated_at; initiated_by. UNIQUE(test_run_id, evaluation_version). Immutable. |
| evaluation_result_events | id; result_id; event_type CURRENT/STALE/SUPERSEDED; replacement_result_id nullable; regulatory_revision; actor_id; reason; created_at. Append-only. |
| test_run_selection_events | id; requirement_id; previous_run_id nullable; selected_run_id; reason; actor_id; regulatory_revision; created_at. Append-only. |

There is deliberately no UNIQUE(test_run_id) on results. Same unchanged current input reuses its result. Changed observations/context/ranges/engine/rules require a new authorized version; prior outputs are never updated. input_revision guards concurrent evaluation. Freshness is derived from events and pointer consistency; STALE events clear current_result_id in the same transaction. A new attempt does not automatically replace the selected run; explicit selection preserves the previous attempt and reason.

## 9. Construction and checklist

| Table | Fields |
|---|---|
| construction_examinations | id; unique test_session_id; evaluation_status/compliance_outcome; overall_notes; examined_by/at nullable; summary_json; lock_version. |
| construction_items | id; construction_examination_id; requirement_rule_id; category; item_key; description snapshot; value_schema_version/value_json; examination_state NOT_EXAMINED/EXAMINED/REVIEW_REQUIRED; conformance_result PASS/FAIL/NOT_APPLICABLE/UNDETERMINED; remarks; sort_order; evidence refs via attachment_links; mutable metadata. UNIQUE(construction_examination_id, item_key). |
| checklist_responses | id; test_session_id; checklist_rule_id; applicability_status/reason snapshot; response_result PASS/FAIL/NOT_APPLICABLE/NOT_EXAMINED; remarks; examined_by/at nullable until answered; mutable metadata. UNIQUE(test_session_id, checklist_rule_id). |

Only applicable rows need editable answers; retain N/A applicability-decision rows so totals include excluded catalog requirements. A NOT_EXAMINED response has no invented examiner/time. A failed but examined row is complete and contributes NONCOMPLIANT. Unverified wording/applicability or unresolved conformance is REVIEW_REQUIRED/UNDETERMINED. All rule references match the session ruleset. Construction/checklist mutation obeys source revision, review invalidation and approval locking.

## 10. Equipment and files

| Table | Fields |
|---|---|
| test_equipment | id; laboratory_id; category; manufacturer/model/serial_number/reference_number; calibration_certificate_no/date/due_date; accuracy_or_class; metadata_schema_version/metadata_json; is_active; mutable metadata. |
| test_run_equipment | id; test_run_id; equipment_id; equipment_snapshot JSONB; calibration_attachment_id nullable; linked_by/at; lock_version. UNIQUE(test_run_id, equipment_id). |
| attachment_uploads | id; laboratory_id; requested_by; target_type/target_id; storage_key; expected_file_name/type/size; upload_status PENDING/COMPLETED/EXPIRED/FAILED; expires_at; created_at; completed_attachment_id nullable. |
| attachments | id; laboratory_id; attachment_type; file_name; content_type; file_size; storage_provider/key/object_version; sha256; uploaded_by/at; metadata_schema_version/metadata_json; archived_at nullable. Content identity immutable after finalization. |
| attachment_links | id; attachment_id; entity_type; entity_id; purpose; linked_by; created_at. UNIQUE(attachment_id, entity_type, entity_id, purpose) with normalized non-null purpose. |

Presign binds an upload to an authorized lab/target; finalize verifies bytes, MIME, size, ownership and digest, not client claims alone. Polymorphic links require an explicit supported entity-type registry and same-lab lookup; finalization/linking obeys session state and ETag. Evidence referenced by approved/issued data is undeletable and immutable. Private storage object versioning/retention prevents overwriting the same key from changing historical bytes. Equipment snapshots retain calibration facts used at measurement; future master updates do not rewrite past snapshots.

## 11. Review and correction

| Table | Fields |
|---|---|
| approval_actions | id; test_session_id; stage TECHNICAL_REVIEW/FINAL_APPROVAL; decision SUBMITTED/APPROVED/REJECTED/RETURNED_FOR_CORRECTION/INVALIDATED; actor_id; regulatory_revision; scope_json; referenced_action_id nullable; comment/reason; created_at. Append-only. |
| session_approval_snapshots | id; unique test_session_id; approval_action_id; regulatory_revision; snapshot_schema_version; snapshot_json (complete approved regulatory record plus historical lab/manufacturer/equipment/actor/evidence facts); snapshot_hash; captured_at/by. Immutable; one final approval snapshot per immutable session revision. |
| correction_requests | id; test_session_id; approval_action_id; target_workflow_status TESTING/EXAMINATION; requested_scope_json (entity IDs and permitted field paths); reason; requested_by/at; correction_status OPEN/RESOLVED/CANCELLED; resolved_at nullable; lock_version. |

Review approval is valid only for the current regulatory_revision and scope with no subsequent invalidation. On change, append INVALIDATED against affected approval actions (conservative full invalidation if dependency unknown). Do not edit old approval rows. Under-review mutation requires return-for-correction; final approval requires independent reviewer/approver permissions and COMPLETE with COMPLIANT or NONCOMPLIANT. Approved history is protected; revisions reset review authority.

## 12. Reports, immutable contexts and revisions

| Table | Fields and constraints |
|---|---|
| report_number_counters | year PK; next_sequence; lock_version. Atomic global numbering R76-<year>-<sequence>. |
| reports | id; test_session_id; report_number; revision_no > 0; root_report_id; supersedes_report_id nullable; revision_reason nullable only at revision 1; report_status UNISSUED/ISSUED/SUPERSEDED; selected_generation_id nullable; issued_at/by nullable; issuance_manifest JSONB nullable until issue; report_hash nullable until chosen generation; created_at/by; lock_version. UNIQUE(report_number, revision_no); UNIQUE(test_session_id), so one approved session revision cannot spawn competing official report series. |
| report_generations | id; report_id; attempt_no > 0; generation_status GENERATING/READY/FAILED; report_context_snapshot immutable; context_schema_version; context_hash; source_regulatory_revision; intended_issuer_id; planned_issue_date; template_version; renderer_manifest; report_hash nullable until READY; error_code nullable; created_at/completed_at. UNIQUE(report_id, attempt_no). |
| report_files | id; report_generation_id; format PDF/DOCX; attachment_id; file_hash; generated_at. UNIQUE(report_generation_id, format). Immutable. |
| report_previews | id; test_session_id; source_regulatory_revision; preview_context_snapshot immutable; preview_status GENERATING/READY/FAILED; requested_by/at; expires_at; context_hash; file_attachment_ids; error_code nullable. No report_number or official issue authority. |

report_context_snapshot lives on immutable generation records, not live joins; reports.selected_generation_id identifies the final exact context and file pair. Generation state fields may transition but captured context never mutates. A retry needing changed issue metadata uses a new attempt/context. Both formats must be READY before issue. Unique current issued report per report_number is enforced with a partial unique index on report_status=ISSUED. Only one successfully issued successor may supersede a predecessor; concurrent competing drafts must fail/rebase before issue.

Revision/root/predecessor links must refer to the same report number, instrument and lab and must form an acyclic increasing revision chain. A successor report uses an approved child session revision, never mutates the original. Creating/generating a draft successor does not change the old report status. Atomic successful issue changes old ISSUED to SUPERSEDED, new UNISSUED to ISSUED, session to REPORT_ISSUED, and appends audit/issue metadata.

The snapshot includes frozen lab/manufacturer/instrument/ranges/components, equipment/calibration, environment, checklist wording/responses, construction, all 17 sections, current and relevant historical results/attempts, evidence identities/hashes, approvals/actor names, rule/schema/engine/template/renderer versions and planned issue metadata. Actual issue instant is immutable in issuance_manifest plus issued_at; printed planned date and intended issuer must match issue authorization/date. See 08-report-spec.md for nonrecursive hash definitions.

## 13. Audit

audit_events: id; actor_id nullable only for identified system/anonymous auth events; actor_type; laboratory_id nullable for global/auth events; action; entity_type/id; source_revision/target_revision nullable; request_id/correlation_id; reason; before_json/after_json or content hashes; ip_address/user_agent nullable; created_at. Append-only. Regulatory mutations and their events commit together. No mutable result history is reconstructed solely from audit.

Auth owns auth audit; application services own domain audit; report jobs own attributed generation outcomes. Prevent application-role UPDATE/DELETE on immutable histories; use constrained administrative migration/retention processes with documented authorization, never routine API deletion.

## 14. Concurrency and referential integrity

Expose lock_version as an ETag. Require If-Match for updates/deletes/lifecycle actions and child creation against mutable parents. Serialize regulatory writes on the parent session row and then stable-order affected runs. Check state/scope/version inside the transaction. Snapshot capture/approval/issue checks serialize with source mutation. Evaluation commit verifies captured input_revision and current workflow. No database lock is held during object transfer or PDF/DOCX rendering.

Add composite FK/unique pairs for session/section/requirement/run/result ownership; validate lab consistency on instruments/manufacturers, equipment links, report predecessors and attachments. Database/service constraints enforce enum values, positive revisions, section 1..17 and uniqueness. A service creates exactly 17 section rows atomically; a count is not implied by UNIQUE alone.

## 15. Indexes and migration ownership

Index lab ownership and common filters: manufacturers(laboratory_id,name), instruments(laboratory_id,manufacturer_id), sessions(laboratory_id,workflow_status,created_at), sessions(instrument_id), child parent IDs, observations(test_run_id,sequence_no), results(test_run_id,evaluation_version), report_number/revisions, audit(entity_type,entity_id,created_at), refresh family/user/digest and idempotency scope/key. Add GIN only for established JSONB query patterns.

Migrations are owned by BUILD_PLAN phases: Phase 1 identity/refresh/audit/idempotency; Phase 2 master data; Phase 3 rules/catalog/equipment/files; Phase 5 sessions/requirements/runs/source/results/events; Phase 12 construction; Phase 13 checklist responses; Phase 15 approvals/corrections/session approval snapshots; Phase 16 reports/previews/generations. Checklist definitions may be seeded with Phase 3 rules; responses wait for Phase 13. No alternative numerical migration ordering overrides these dependencies. Use staged nullable/deferred FKs for circular current/root pointers, then enforce invariants transactionally.

Seed roles/complete permission mappings and bootstrap administrator securely; seed all section/subtest catalog definitions. Unverified rules/checklists are DRAFT/TODO_REGULATORY_VALIDATION, never seeded as verified production rules. No issued demo artifact bypasses the regulatory gate.
