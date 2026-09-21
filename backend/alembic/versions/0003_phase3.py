"""Phase 3 rules/catalog, equipment and private attachments. Static DDL snapshot."""

from alembic import op

revision = "0003_phase3"
down_revision = "0002_phase2"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase3_ruleset_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Ruleset history cannot be deleted' USING ERRCODE = '23514';
      END IF;
      IF TG_OP = 'UPDATE' AND
        (to_jsonb(NEW) - ARRAY['lock_version','updated_at','validation_summary',
          'ruleset_status','activated_at','activated_by','effective_from','effective_to'])
        IS DISTINCT FROM
        (to_jsonb(OLD) - ARRAY['lock_version','updated_at','validation_summary',
          'ruleset_status','activated_at','activated_by','effective_from','effective_to']) THEN
        RAISE EXCEPTION 'Registered artifact content is immutable; register a new version'
          USING ERRCODE = '23514';
      END IF;
      IF NEW.ruleset_status = 'ACTIVE' AND (
        jsonb_array_length(NEW.supported_test_codes) = 0 OR
        NEW.validation_summary->>'authoritative' IS DISTINCT FROM 'true'
      ) THEN
        RAISE EXCEPTION 'Unverified/unsupported ruleset cannot activate' USING ERRCODE = '23514';
      END IF;
      IF TG_OP = 'UPDATE' AND (
        (OLD.ruleset_status = 'RETIRED' AND NEW.ruleset_status <> 'RETIRED') OR
        (OLD.ruleset_status = 'ACTIVE' AND NEW.ruleset_status = 'DRAFT')
      ) THEN
        RAISE EXCEPTION 'Invalid ruleset lifecycle transition' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER ruleset_guard BEFORE INSERT OR UPDATE OR DELETE ON rule_sets
    FOR EACH ROW EXECUTE FUNCTION phase3_ruleset_guard()
    """)
    op.execute("""
    CREATE FUNCTION phase3_catalog_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Registered catalog rows are immutable' USING ERRCODE = '23514';
      END IF;
      PERFORM 1 FROM rule_sets WHERE id = NEW.rule_set_id
        AND ruleset_status = 'DRAFT' FOR UPDATE;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Only draft catalogs accept definitions' USING ERRCODE = '23514';
      END IF;
      IF NEW.validation_status = 'VERIFIED' AND (
        NEW.source_digest IS NULL OR NEW.verified_by IS NULL OR NEW.verified_at IS NULL OR
        NEW.verification_evidence IS NULL OR NEW.source_identity->>'clause' IS NULL
      ) THEN
        RAISE EXCEPTION 'Verification provenance required' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$
    """)
    for table in ("rule_definitions", "test_definitions", "checklist_rules"):
        op.execute(f"""
        CREATE TRIGGER catalog_guard BEFORE INSERT OR UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION phase3_catalog_guard()
        """)
    op.execute("""
    CREATE FUNCTION phase3_attachment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Attachment identity cannot be deleted' USING ERRCODE = '23514';
      END IF;
      IF (to_jsonb(NEW) - ARRAY['lock_version','updated_at','archived_at']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['lock_version','updated_at','archived_at']) THEN
        RAISE EXCEPTION 'Published attachment content is immutable' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER attachment_identity_guard BEFORE UPDATE OR DELETE ON attachments
    FOR EACH ROW EXECUTE FUNCTION phase3_attachment_guard()
    """)


def upgrade():
    op.execute("""
CREATE TABLE rule_sets (
	standard_code VARCHAR(50) NOT NULL, 
	standard_name TEXT NOT NULL, 
	standard_parts JSONB NOT NULL, 
	edition VARCHAR(100) NOT NULL, 
	version VARCHAR(100) NOT NULL, 
	ruleset_status VARCHAR(20) DEFAULT 'DRAFT' NOT NULL, 
	effective_from DATE, 
	effective_to DATE, 
	configuration_hash VARCHAR(64) NOT NULL, 
	configuration_snapshot JSONB NOT NULL, 
	supported_test_codes JSONB NOT NULL, 
	source_reference TEXT NOT NULL, 
	validation_summary JSONB NOT NULL, 
	created_by UUID, 
	activated_at TIMESTAMP WITH TIME ZONE, 
	activated_by UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_ruleset_version UNIQUE (standard_code, edition, version), 
	CONSTRAINT ck_ruleset_status CHECK (ruleset_status IN ('DRAFT','ACTIVE','RETIRED')), 
	CONSTRAINT ck_ruleset_version CHECK (lock_version > 0), 
    CONSTRAINT ck_ruleset_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR
        effective_to >= effective_from),
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
	FOREIGN KEY(activated_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_ruleset_active ON rule_sets (standard_code, edition) "
        "WHERE ruleset_status = 'ACTIVE'"
    )
    op.execute("""
CREATE TABLE rule_definitions (
	rule_set_id UUID NOT NULL, 
	rule_key VARCHAR(100) NOT NULL, 
	section_no INTEGER, 
	clause_reference TEXT, 
	rule_type VARCHAR(100) NOT NULL, 
	configuration JSONB NOT NULL, 
	description TEXT NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	validation_status VARCHAR(40) NOT NULL, 
	source_identity JSONB NOT NULL, 
	source_digest VARCHAR(64), 
	verified_by TEXT, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verification_evidence TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_rule_key UNIQUE (rule_set_id, rule_key), 
    CONSTRAINT ck_rule_validation CHECK (validation_status IN
        ('TODO_REGULATORY_VALIDATION','VERIFIED')),
	CONSTRAINT ck_rule_section CHECK (section_no IS NULL OR section_no BETWEEN 1 AND 17), 
	FOREIGN KEY(rule_set_id) REFERENCES rule_sets (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_rule_definitions_rule_set_id ON rule_definitions (rule_set_id)")
    op.execute("""
CREATE TABLE test_definitions (
	rule_set_id UUID NOT NULL, 
	code VARCHAR(100) NOT NULL, 
	section_number INTEGER NOT NULL, 
	parent_definition_id UUID, 
	name TEXT NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	subtest_family VARCHAR(100), 
	sort_order INTEGER NOT NULL, 
	supports_numeric_evaluation BOOLEAN NOT NULL, 
	requires_manual_review BOOLEAN NOT NULL, 
	supported BOOLEAN NOT NULL, 
	implemented BOOLEAN NOT NULL, 
	applicability_metadata JSONB NOT NULL, 
	default_observation_schema_version VARCHAR(40), 
	default_procedure_schema_version VARCHAR(40), 
	description TEXT NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	validation_status VARCHAR(40) NOT NULL, 
	source_identity JSONB NOT NULL, 
	source_digest VARCHAR(64), 
	verified_by TEXT, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verification_evidence TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_test_code UNIQUE (rule_set_id, code), 
	CONSTRAINT uq_test_parent_scope UNIQUE (rule_set_id, id), 
    CONSTRAINT fk_test_parent_scope FOREIGN KEY(rule_set_id, parent_definition_id)
        REFERENCES test_definitions (rule_set_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_test_section CHECK (section_number BETWEEN 1 AND 17), 
	CONSTRAINT ck_test_parent CHECK (parent_definition_id IS NULL OR parent_definition_id <> id), 
    CONSTRAINT ck_test_validation CHECK (validation_status IN
        ('TODO_REGULATORY_VALIDATION','VERIFIED')),
	FOREIGN KEY(rule_set_id) REFERENCES rule_sets (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_definitions_rule_set_id ON test_definitions (rule_set_id)")
    op.execute("""
CREATE TABLE checklist_rules (
	rule_set_id UUID NOT NULL, 
	group_code VARCHAR(40) NOT NULL, 
	requirement_key VARCHAR(100) NOT NULL, 
	clause_reference TEXT, 
	display_text TEXT NOT NULL, 
	applicability_expression JSONB NOT NULL, 
	evidence_required BOOLEAN, 
	sort_order INTEGER NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	validation_status VARCHAR(40) NOT NULL, 
	source_identity JSONB NOT NULL, 
	source_digest VARCHAR(64), 
	verified_by TEXT, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	verification_evidence TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_checklist_key UNIQUE (rule_set_id, requirement_key), 
    CONSTRAINT ck_checklist_group CHECK (group_code IN
        ('GENERAL','DIRECT_SALES','ELECTRONIC','SOFTWARE_CONTROLLED')),
    CONSTRAINT ck_checklist_validation CHECK (validation_status IN
        ('TODO_REGULATORY_VALIDATION','VERIFIED')),
	FOREIGN KEY(rule_set_id) REFERENCES rule_sets (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_checklist_rules_rule_set_id ON checklist_rules (rule_set_id)")
    op.execute("""
CREATE TABLE test_equipment (
	laboratory_id UUID NOT NULL, 
	category VARCHAR(200) NOT NULL, 
	manufacturer VARCHAR(200), 
	model VARCHAR(200), 
	serial_number VARCHAR(200), 
	reference_number VARCHAR(200), 
	calibration_certificate_no VARCHAR(200), 
	calibration_date DATE, 
	calibration_due_date DATE, 
	accuracy_or_class VARCHAR(200), 
	metadata_schema_version INTEGER DEFAULT '1' NOT NULL, 
	metadata_json JSONB NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	created_by UUID NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_equipment_version CHECK (lock_version > 0), 
	CONSTRAINT ck_equipment_schema CHECK (metadata_schema_version = 1), 
    CONSTRAINT ck_equipment_dates CHECK (calibration_due_date IS NULL OR calibration_date
        IS NULL OR calibration_due_date >= calibration_date),
	FOREIGN KEY(laboratory_id) REFERENCES laboratories (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_test_equipment_laboratory_id ON test_equipment (laboratory_id)")
    op.execute("""
CREATE TABLE attachments (
	laboratory_id UUID NOT NULL, 
	attachment_type VARCHAR(50) NOT NULL, 
	file_name VARCHAR(200) NOT NULL, 
	content_type VARCHAR(100) NOT NULL, 
	file_size INTEGER NOT NULL, 
	storage_provider VARCHAR(20) NOT NULL, 
	storage_key TEXT NOT NULL, 
	object_version TEXT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	uploaded_by UUID NOT NULL, 
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	metadata_schema_version INTEGER DEFAULT '1' NOT NULL, 
	metadata_json JSONB NOT NULL, 
	archived_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_attachment_object UNIQUE (storage_provider, storage_key, object_version), 
	CONSTRAINT uq_attachment_lab UNIQUE (laboratory_id, id), 
	CONSTRAINT ck_attachment_size_version CHECK (file_size > 0 AND lock_version > 0), 
	CONSTRAINT ck_attachment_hash CHECK (sha256 ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_attachment_schema CHECK (metadata_schema_version = 1), 
	FOREIGN KEY(laboratory_id) REFERENCES laboratories (id) ON DELETE RESTRICT, 
	FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_attachments_laboratory_id ON attachments (laboratory_id)")
    op.execute("""
CREATE TABLE attachment_uploads (
	laboratory_id UUID NOT NULL, 
	requested_by UUID NOT NULL, 
	target_type VARCHAR(80) NOT NULL, 
	target_id UUID NOT NULL, 
	purpose VARCHAR(100) NOT NULL, 
	storage_key TEXT NOT NULL, 
	expected_file_name VARCHAR(200) NOT NULL, 
	expected_content_type VARCHAR(100) NOT NULL, 
	expected_size INTEGER NOT NULL, 
	expected_sha256 VARCHAR(64) NOT NULL, 
	upload_status VARCHAR(20) DEFAULT 'PENDING' NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	completed_attachment_id UUID, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
    CONSTRAINT ck_upload_status CHECK (upload_status IN
        ('PENDING','COMPLETED','EXPIRED','FAILED')),
	CONSTRAINT ck_upload_size_version CHECK (expected_size > 0 AND lock_version > 0), 
	CONSTRAINT ck_upload_hash CHECK (expected_sha256 ~ '^[a-f0-9]{64}$'), 
    CONSTRAINT ck_upload_completion CHECK ((upload_status = 'COMPLETED') =
        (completed_attachment_id IS NOT NULL)),
    CONSTRAINT fk_upload_attachment_lab FOREIGN KEY(laboratory_id,
        completed_attachment_id) REFERENCES attachments (laboratory_id, id) ON DELETE
        RESTRICT,
	FOREIGN KEY(laboratory_id) REFERENCES laboratories (id) ON DELETE RESTRICT, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE RESTRICT, 
	UNIQUE (storage_key)
)
    """)
    op.execute(
        "CREATE INDEX ix_attachment_uploads_laboratory_id ON attachment_uploads (laboratory_id)"
    )
    op.execute(
        "CREATE INDEX ix_attachment_uploads_requested_by ON attachment_uploads (requested_by)"
    )
    op.execute("CREATE INDEX ix_upload_expiry ON attachment_uploads (upload_status, expires_at)")
    op.execute("""
CREATE TABLE attachment_links (
	attachment_id UUID NOT NULL, 
	entity_type VARCHAR(80) NOT NULL, 
	entity_id UUID NOT NULL, 
	purpose VARCHAR(100) NOT NULL, 
	linked_by UUID NOT NULL, 
	unlinked_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	lock_version INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_attachment_link UNIQUE (attachment_id, entity_type, entity_id, purpose), 
    CONSTRAINT ck_link_purpose_version CHECK (lock_version > 0 AND length(purpose) > 0 AND
        purpose = lower(trim(purpose))),
	FOREIGN KEY(attachment_id) REFERENCES attachments (id) ON DELETE RESTRICT, 
	FOREIGN KEY(linked_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute("CREATE INDEX ix_attachment_links_attachment_id ON attachment_links (attachment_id)")
    op.execute("CREATE INDEX ix_attachment_target ON attachment_links (entity_type, entity_id)")
    install_guards()


def downgrade():
    op.drop_table("attachment_links")
    op.drop_table("attachment_uploads")
    op.drop_table("attachments")
    op.drop_table("test_equipment")
    op.drop_table("checklist_rules")
    op.drop_table("test_definitions")
    op.drop_table("rule_definitions")
    op.drop_table("rule_sets")
    op.execute("DROP FUNCTION phase3_ruleset_guard()")
    op.execute("DROP FUNCTION phase3_catalog_guard()")
    op.execute("DROP FUNCTION phase3_attachment_guard()")
