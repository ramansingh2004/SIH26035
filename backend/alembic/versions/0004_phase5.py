"""Phase 5 session/run/result foundation. Static PostgreSQL DDL snapshot."""
# ruff: noqa: E501

from alembic import op

revision = "0004_phase5"
down_revision = "0003_phase3"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase5_immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'Evaluation and selection history is append-only'
        USING ERRCODE = '23514';
    END $$
    """)
    for table in ("test_run_results", "evaluation_result_events", "test_run_selection_events"):
        op.execute(
            f"CREATE TRIGGER phase5_history_guard BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION phase5_immutable_history()"
        )
    op.execute("""
    CREATE FUNCTION phase5_ownership_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      parent_session test_sessions%ROWTYPE;
      parent_run test_runs%ROWTYPE;
      definition test_definitions%ROWTYPE;
    BEGIN
      IF TG_TABLE_NAME = 'test_sessions' THEN
        IF NOT EXISTS (SELECT 1 FROM instruments i WHERE i.id = NEW.instrument_id
          AND i.laboratory_id = NEW.laboratory_id) THEN
          RAISE EXCEPTION 'Instrument laboratory mismatch' USING ERRCODE = '23514';
        END IF;
        IF NEW.parent_session_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM test_sessions s WHERE s.id = NEW.parent_session_id
            AND s.root_session_id = NEW.root_session_id
            AND s.session_revision_no < NEW.session_revision_no) THEN
          RAISE EXCEPTION 'Invalid session lineage' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'UPDATE' AND (
          (NEW.ruleset_snapshot, NEW.rule_set_id, NEW.instrument_id, NEW.laboratory_id,
           NEW.root_session_id, NEW.parent_session_id, NEW.session_revision_no)
          IS DISTINCT FROM
          (OLD.ruleset_snapshot, OLD.rule_set_id, OLD.instrument_id, OLD.laboratory_id,
           OLD.root_session_id, OLD.parent_session_id, OLD.session_revision_no)
          OR (OLD.workflow_status NOT IN ('DRAFT','INSTRUMENT_CONFIGURATION')
              AND NEW.instrument_snapshot IS DISTINCT FROM OLD.instrument_snapshot)
        ) THEN
          RAISE EXCEPTION 'Pinned session identity/snapshot is immutable'
            USING ERRCODE = '23514';
        END IF;
      ELSIF TG_TABLE_NAME IN ('session_test_requirements','test_runs') THEN
        SELECT * INTO parent_session FROM test_sessions WHERE id = NEW.test_session_id;
        SELECT * INTO definition FROM test_definitions WHERE id = NEW.test_definition_id;
        IF definition.rule_set_id IS DISTINCT FROM parent_session.rule_set_id OR
          NOT EXISTS (SELECT 1 FROM test_session_sections s
            WHERE s.id = NEW.session_section_id AND s.section_number = definition.section_number
              AND s.test_session_id = parent_session.id) THEN
          RAISE EXCEPTION 'Catalog/session/section mismatch' USING ERRCODE = '23514';
        END IF;
        IF TG_TABLE_NAME = 'test_runs' THEN
          IF NOT EXISTS (
            SELECT 1 FROM session_test_requirements q WHERE q.id = NEW.requirement_id
              AND q.test_definition_id = NEW.test_definition_id
          ) THEN
            RAISE EXCEPTION 'Run definition differs from requirement' USING ERRCODE = '23514';
          END IF;
        END IF;
      ELSIF TG_TABLE_NAME IN ('test_run_results','test_run_equipment') THEN
        SELECT * INTO parent_run FROM test_runs WHERE id = NEW.test_run_id;
        SELECT * INTO parent_session FROM test_sessions WHERE id = parent_run.test_session_id;
        IF TG_TABLE_NAME = 'test_run_results' THEN
          IF NEW.rule_set_id IS DISTINCT FROM parent_session.rule_set_id OR
             NEW.source_input_revision <> parent_run.input_revision THEN
            RAISE EXCEPTION 'Result source mismatch' USING ERRCODE = '23514';
          END IF;
        ELSE
          IF NOT EXISTS (SELECT 1 FROM test_equipment e WHERE e.id = NEW.equipment_id
            AND e.laboratory_id = parent_session.laboratory_id) OR
            (NEW.calibration_attachment_id IS NOT NULL AND NOT EXISTS (
              SELECT 1 FROM attachments a WHERE a.id = NEW.calibration_attachment_id
                AND a.laboratory_id = parent_session.laboratory_id)) THEN
            RAISE EXCEPTION 'Equipment/certificate laboratory mismatch' USING ERRCODE = '23514';
          END IF;
          IF TG_OP = 'UPDATE' AND NEW.equipment_snapshot IS DISTINCT FROM OLD.equipment_snapshot THEN
            RAISE EXCEPTION 'Captured calibration snapshot is immutable' USING ERRCODE = '23514';
          END IF;
        END IF;
      ELSIF TG_TABLE_NAME = 'evaluation_result_events' THEN
        IF NEW.replacement_result_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM test_run_results a JOIN test_run_results b
            ON a.test_run_id = b.test_run_id
          WHERE a.id = NEW.result_id AND b.id = NEW.replacement_result_id
        ) THEN
          RAISE EXCEPTION 'Replacement result belongs to another run' USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in (
        "test_sessions",
        "session_test_requirements",
        "test_runs",
        "test_run_results",
        "test_run_equipment",
        "evaluation_result_events",
    ):
        op.execute(
            f"CREATE TRIGGER phase5_ownership BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION phase5_ownership_guard()"
        )


def upgrade():
    op.execute("""
CREATE TABLE test_sessions (
	laboratory_id UUID NOT NULL, 
	instrument_id UUID NOT NULL, 
	rule_set_id UUID NOT NULL, 
	application_number VARCHAR(200), 
	workflow_status VARCHAR(40) DEFAULT 'DRAFT' NOT NULL, 
	evaluation_context VARCHAR(100) NOT NULL, 
	instrument_snapshot JSONB NOT NULL, 
	ruleset_snapshot JSONB NOT NULL, 
	snapshot_schema_version INTEGER DEFAULT '1' NOT NULL, 
	regulatory_revision INTEGER DEFAULT '1' NOT NULL, 
	root_session_id UUID NOT NULL, 
	parent_session_id UUID, 
	session_revision_no INTEGER DEFAULT '1' NOT NULL, 
	revision_reason TEXT, 
	started_by UUID NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	submitted_at TIMESTAMP WITH TIME ZONE, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	notes TEXT, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	evaluation_status VARCHAR(30) DEFAULT 'NOT_STARTED' NOT NULL, 
	compliance_outcome VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_session_evaluation CHECK (evaluation_status IN ('NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE')), 
	CONSTRAINT ck_session_outcome CHECK (compliance_outcome IN ('UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE')), 
	CONSTRAINT uq_session_revision UNIQUE (root_session_id, session_revision_no), 
	CONSTRAINT uq_session_lineage_scope UNIQUE (id, laboratory_id, instrument_id), 
	CONSTRAINT fk_session_root_scope FOREIGN KEY(root_session_id, laboratory_id, instrument_id) REFERENCES test_sessions (id, laboratory_id, instrument_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_session_parent_scope FOREIGN KEY(parent_session_id, laboratory_id, instrument_id) REFERENCES test_sessions (id, laboratory_id, instrument_id) ON DELETE RESTRICT, 
	CONSTRAINT ck_session_versions CHECK (regulatory_revision > 0 AND lock_version > 0 AND session_revision_no > 0), 
	CONSTRAINT ck_session_snapshot_schema CHECK (snapshot_schema_version = 1), 
	CONSTRAINT ck_session_lineage CHECK ((parent_session_id IS NULL AND root_session_id = id AND session_revision_no = 1) OR (parent_session_id IS NOT NULL AND parent_session_id <> id AND revision_reason IS NOT NULL AND length(trim(revision_reason)) > 0 AND session_revision_no > 1)), 
	CONSTRAINT ck_session_workflow CHECK (workflow_status IN ('DRAFT','INSTRUMENT_CONFIGURATION','APPLICABILITY_CONFIRMED','TESTING','EXAMINATION','UNDER_REVIEW','APPROVED','REPORT_ISSUED','REJECTED','CANCELLED')), 
	FOREIGN KEY(laboratory_id) REFERENCES laboratories (id) ON DELETE RESTRICT, 
	FOREIGN KEY(instrument_id) REFERENCES instruments (id) ON DELETE RESTRICT, 
	FOREIGN KEY(rule_set_id) REFERENCES rule_sets (id) ON DELETE RESTRICT, 
	FOREIGN KEY(started_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_session_lab_workflow ON test_sessions (laboratory_id, workflow_status, created_at)"
    )
    op.execute("CREATE INDEX ix_test_sessions_instrument_id ON test_sessions (instrument_id)")
    op.execute("""
CREATE TABLE test_session_sections (
	test_session_id UUID NOT NULL, 
	section_number INTEGER NOT NULL, 
	section_code VARCHAR(100) NOT NULL, 
	section_name TEXT NOT NULL, 
	applicability_status VARCHAR(30) NOT NULL, 
	applicability_reason TEXT NOT NULL, 
	rule_references JSONB NOT NULL, 
	summary_schema_version INTEGER DEFAULT '1' NOT NULL, 
	summary_json JSONB NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	evaluation_status VARCHAR(30) DEFAULT 'NOT_STARTED' NOT NULL, 
	compliance_outcome VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_section_evaluation CHECK (evaluation_status IN ('NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE')), 
	CONSTRAINT ck_section_outcome CHECK (compliance_outcome IN ('UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE')), 
	CONSTRAINT uq_session_section UNIQUE (test_session_id, section_number), 
	CONSTRAINT uq_section_scope UNIQUE (test_session_id, id), 
	CONSTRAINT ck_section_number_version CHECK (section_number BETWEEN 1 AND 17 AND lock_version > 0), 
	CONSTRAINT ck_section_applicability CHECK (applicability_status IN ('REQUIRED','OPTIONAL','NOT_APPLICABLE','REQUIRES_REVIEW')), 
	FOREIGN KEY(test_session_id) REFERENCES test_sessions (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_test_session_sections_test_session_id ON test_session_sections (test_session_id)"
    )
    op.execute("""
CREATE TABLE session_test_requirements (
	test_session_id UUID NOT NULL, 
	session_section_id UUID NOT NULL, 
	test_definition_id UUID NOT NULL, 
	requirement_key TEXT NOT NULL, 
	applicability_status VARCHAR(30) NOT NULL, 
	applicability_reason TEXT NOT NULL, 
	rule_references JSONB NOT NULL, 
	slot_snapshot JSONB NOT NULL, 
	is_elected BOOLEAN NOT NULL, 
	selected_run_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_requirement_key UNIQUE (session_section_id, requirement_key), 
	CONSTRAINT uq_requirement_scope UNIQUE (test_session_id, session_section_id, id), 
	CONSTRAINT fk_requirement_section FOREIGN KEY(test_session_id, session_section_id) REFERENCES test_session_sections (test_session_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_requirement_applicability CHECK (applicability_status IN ('REQUIRED','OPTIONAL','NOT_APPLICABLE','REQUIRES_REVIEW') AND lock_version > 0), 
	CONSTRAINT ck_requirement_election CHECK (NOT is_elected OR applicability_status = 'OPTIONAL'), 
	FOREIGN KEY(test_session_id) REFERENCES test_sessions (id) ON DELETE RESTRICT, 
	FOREIGN KEY(test_definition_id) REFERENCES test_definitions (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_session_test_requirements_test_session_id ON session_test_requirements (test_session_id)"
    )
    op.execute("""
CREATE TABLE test_runs (
	test_session_id UUID NOT NULL, 
	session_section_id UUID NOT NULL, 
	requirement_id UUID NOT NULL, 
	test_definition_id UUID NOT NULL, 
	run_no INTEGER NOT NULL, 
	retest_of_run_id UUID, 
	retest_reason TEXT, 
	observation_schema_version VARCHAR(40) NOT NULL, 
	procedure_schema_version VARCHAR(40) NOT NULL, 
	procedure_context JSONB NOT NULL, 
	input_revision INTEGER DEFAULT '1' NOT NULL, 
	current_result_id UUID, 
	started_by UUID, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	evaluation_status VARCHAR(30) DEFAULT 'NOT_STARTED' NOT NULL, 
	compliance_outcome VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_run_evaluation CHECK (evaluation_status IN ('NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE')), 
	CONSTRAINT ck_run_outcome CHECK (compliance_outcome IN ('UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE')), 
	CONSTRAINT uq_run_number UNIQUE (requirement_id, run_no), 
	CONSTRAINT uq_run_requirement UNIQUE (requirement_id, id), 
	CONSTRAINT uq_run_session UNIQUE (test_session_id, id), 
	CONSTRAINT fk_run_requirement_scope FOREIGN KEY(test_session_id, session_section_id, requirement_id) REFERENCES session_test_requirements (test_session_id, session_section_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_run_retest_scope FOREIGN KEY(requirement_id, retest_of_run_id) REFERENCES test_runs (requirement_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_run_versions CHECK (run_no > 0 AND input_revision > 0 AND lock_version > 0), 
	CONSTRAINT ck_run_retest CHECK ((run_no = 1 AND retest_of_run_id IS NULL) OR (run_no > 1 AND retest_of_run_id IS NOT NULL AND retest_of_run_id <> id AND retest_reason IS NOT NULL AND length(trim(retest_reason)) > 0)), 
	FOREIGN KEY(test_session_id) REFERENCES test_sessions (id) ON DELETE RESTRICT, 
	FOREIGN KEY(test_definition_id) REFERENCES test_definitions (id) ON DELETE RESTRICT, 
	FOREIGN KEY(started_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_runs_test_session_id ON test_runs (test_session_id)")
    op.execute("""
CREATE TABLE test_observations (
	test_run_id UUID NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	observation_type VARCHAR(100) NOT NULL, 
	payload_schema_version VARCHAR(40) NOT NULL, 
	payload_json JSONB NOT NULL, 
	recorded_by UUID NOT NULL, 
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	is_locked BOOLEAN DEFAULT 'false' NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_observation_sequence UNIQUE (test_run_id, sequence_no), 
	CONSTRAINT ck_observation_version CHECK (sequence_no > 0 AND lock_version > 0), 
	FOREIGN KEY(test_run_id) REFERENCES test_runs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_observations_test_run_id ON test_observations (test_run_id)")
    op.execute("""
CREATE TABLE environment_readings (
	test_session_id UUID NOT NULL, 
	test_run_id UUID NOT NULL, 
	measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	temperature_c NUMERIC, 
	relative_humidity_percent NUMERIC, 
	barometric_pressure_hpa NUMERIC, 
	phase VARCHAR(100), 
	notes TEXT, 
	recorded_by UUID NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_environment_run_scope FOREIGN KEY(test_session_id, test_run_id) REFERENCES test_runs (test_session_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_environment_values CHECK (lock_version > 0 AND (relative_humidity_percent IS NULL OR relative_humidity_percent BETWEEN 0 AND 100) AND (barometric_pressure_hpa IS NULL OR barometric_pressure_hpa > 0)), 
	FOREIGN KEY(test_session_id) REFERENCES test_sessions (id) ON DELETE RESTRICT, 
	FOREIGN KEY(test_run_id) REFERENCES test_runs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_environment_readings_test_run_id ON environment_readings (test_run_id)"
    )
    op.execute(
        "CREATE INDEX ix_environment_readings_test_session_id ON environment_readings (test_session_id)"
    )
    op.execute("""
CREATE TABLE test_run_equipment (
	test_run_id UUID NOT NULL, 
	equipment_id UUID NOT NULL, 
	equipment_snapshot JSONB NOT NULL, 
	calibration_attachment_id UUID, 
	linked_by UUID NOT NULL, 
	linked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_run_equipment UNIQUE (test_run_id, equipment_id), 
	CONSTRAINT ck_run_equipment_version CHECK (lock_version > 0), 
	FOREIGN KEY(test_run_id) REFERENCES test_runs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(equipment_id) REFERENCES test_equipment (id) ON DELETE RESTRICT, 
	FOREIGN KEY(calibration_attachment_id) REFERENCES attachments (id) ON DELETE RESTRICT, 
	FOREIGN KEY(linked_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_run_equipment_test_run_id ON test_run_equipment (test_run_id)")
    op.execute("""
CREATE TABLE test_run_results (
	test_run_id UUID NOT NULL, 
	rule_set_id UUID NOT NULL, 
	evaluation_version INTEGER NOT NULL, 
	source_input_revision INTEGER NOT NULL, 
	supersedes_result_id UUID, 
	evaluation_input_snapshot JSONB NOT NULL, 
	deterministic_result JSONB NOT NULL, 
	applicability_status VARCHAR(30) NOT NULL, 
	applicability_reason TEXT NOT NULL, 
	calculations_json JSONB NOT NULL, 
	acceptance_limits_json JSONB NOT NULL, 
	failed_conditions_json JSONB NOT NULL, 
	rule_references_json JSONB NOT NULL, 
	reason TEXT NOT NULL, 
	issue_code VARCHAR(100), 
	unresolved_rule_ids JSONB NOT NULL, 
	hash_schema_version VARCHAR(20) NOT NULL, 
	observation_schema_version VARCHAR(40) NOT NULL, 
	procedure_schema_version VARCHAR(40) NOT NULL, 
	engine_version TEXT NOT NULL, 
	ruleset_version VARCHAR(100) NOT NULL, 
	ruleset_configuration_hash VARCHAR(64) NOT NULL, 
	input_hash VARCHAR(64) NOT NULL, 
	result_hash VARCHAR(64) NOT NULL, 
	evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	initiated_by UUID NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	evaluation_status VARCHAR(30) DEFAULT 'NOT_STARTED' NOT NULL, 
	compliance_outcome VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_result_evaluation CHECK (evaluation_status IN ('NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE')), 
	CONSTRAINT ck_result_outcome CHECK (compliance_outcome IN ('UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE')), 
	CONSTRAINT uq_result_version UNIQUE (test_run_id, evaluation_version), 
	CONSTRAINT uq_result_current_scope UNIQUE (test_run_id, id, source_input_revision), 
	CONSTRAINT uq_result_run UNIQUE (test_run_id, id), 
	CONSTRAINT fk_result_supersedes_scope FOREIGN KEY(test_run_id, supersedes_result_id) REFERENCES test_run_results (test_run_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_result_versions CHECK (evaluation_version > 0 AND source_input_revision > 0 AND hash_schema_version = 'v1'), 
	CONSTRAINT ck_result_hashes CHECK (input_hash ~ '^[a-f0-9]{64}$' AND result_hash ~ '^[a-f0-9]{64}$'), 
	FOREIGN KEY(test_run_id) REFERENCES test_runs (id) ON DELETE RESTRICT, 
	FOREIGN KEY(rule_set_id) REFERENCES rule_sets (id) ON DELETE RESTRICT, 
	FOREIGN KEY(initiated_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_run_results_test_run_id ON test_run_results (test_run_id)")
    op.execute("""
CREATE TABLE evaluation_result_events (
	result_id UUID NOT NULL, 
	event_type VARCHAR(20) NOT NULL, 
	replacement_result_id UUID, 
	regulatory_revision INTEGER NOT NULL, 
	actor_id UUID NOT NULL, 
	reason TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_result_event CHECK (event_type IN ('CURRENT','STALE','SUPERSEDED') AND regulatory_revision > 0), 
	FOREIGN KEY(result_id) REFERENCES test_run_results (id) ON DELETE RESTRICT, 
	FOREIGN KEY(replacement_result_id) REFERENCES test_run_results (id) ON DELETE RESTRICT, 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_evaluation_result_events_result_id ON evaluation_result_events (result_id)"
    )
    op.execute("""
CREATE TABLE test_run_selection_events (
	requirement_id UUID NOT NULL, 
	previous_run_id UUID, 
	selected_run_id UUID NOT NULL, 
	reason TEXT NOT NULL, 
	regulatory_revision INTEGER NOT NULL, 
	actor_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_selection_run FOREIGN KEY(requirement_id, selected_run_id) REFERENCES test_runs (requirement_id, id) ON DELETE RESTRICT, 
	CONSTRAINT fk_selection_previous FOREIGN KEY(requirement_id, previous_run_id) REFERENCES test_runs (requirement_id, id) ON DELETE RESTRICT, 
	CONSTRAINT ck_selection_reason CHECK (regulatory_revision > 0 AND length(trim(reason)) > 0), 
	FOREIGN KEY(requirement_id) REFERENCES session_test_requirements (id) ON DELETE RESTRICT, 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_test_run_selection_events_requirement_id ON test_run_selection_events (requirement_id)"
    )
    op.execute(
        "ALTER TABLE session_test_requirements ADD CONSTRAINT fk_requirement_selection FOREIGN KEY(id, selected_run_id) REFERENCES test_runs (requirement_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        "ALTER TABLE test_runs ADD CONSTRAINT fk_run_current_result FOREIGN KEY(id, current_result_id, input_revision) REFERENCES test_run_results (test_run_id, id, source_input_revision) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    install_guards()


def downgrade():
    op.drop_constraint("fk_requirement_selection", "session_test_requirements", type_="foreignkey")
    op.drop_constraint("fk_run_current_result", "test_runs", type_="foreignkey")
    op.drop_table("test_run_selection_events")
    op.drop_table("evaluation_result_events")
    op.drop_table("test_run_results")
    op.drop_table("test_run_equipment")
    op.drop_table("environment_readings")
    op.drop_table("test_observations")
    op.drop_table("test_runs")
    op.drop_table("session_test_requirements")
    op.drop_table("test_session_sections")
    op.drop_table("test_sessions")
    op.execute("DROP FUNCTION phase5_immutable_history()")
    op.execute("DROP FUNCTION phase5_ownership_guard()")
