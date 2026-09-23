"""Phase 12 construction examination foundation. Static PostgreSQL DDL snapshot."""
# ruff: noqa: E501

from alembic import op

revision = "0005_phase12"
down_revision = "0004_phase5"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase12_construction_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      session_rule_set UUID;
      rule_row rule_definitions%ROWTYPE;
      examination_session UUID;
    BEGIN
      IF TG_TABLE_NAME = 'construction_examinations' THEN
        IF TG_OP = 'UPDATE' AND NEW.test_session_id IS DISTINCT FROM OLD.test_session_id THEN
          RAISE EXCEPTION 'Construction examination session is immutable'
            USING ERRCODE = '23514';
        END IF;
      ELSIF TG_TABLE_NAME = 'construction_items' THEN
        SELECT e.test_session_id INTO examination_session
          FROM construction_examinations e
          WHERE e.id = NEW.construction_examination_id;
        IF examination_session IS NULL THEN
          RAISE EXCEPTION 'Construction examination is missing'
            USING ERRCODE = '23514';
        END IF;

        SELECT s.rule_set_id INTO session_rule_set
          FROM test_sessions s
          WHERE s.id = examination_session;

        SELECT * INTO rule_row
          FROM rule_definitions r
          WHERE r.id = NEW.requirement_rule_id;

        IF rule_row.id IS NULL
          OR rule_row.rule_set_id IS DISTINCT FROM session_rule_set
          OR rule_row.section_no IS DISTINCT FROM 16 THEN
          RAISE EXCEPTION 'Construction item rule/session/section mismatch'
            USING ERRCODE = '23514';
        END IF;

        IF TG_OP = 'UPDATE' AND (
          NEW.construction_examination_id,
          NEW.requirement_rule_id,
          NEW.category,
          NEW.item_key,
          NEW.description_snapshot,
          NEW.sort_order
        ) IS DISTINCT FROM (
          OLD.construction_examination_id,
          OLD.requirement_rule_id,
          OLD.category,
          OLD.item_key,
          OLD.description_snapshot,
          OLD.sort_order
        ) THEN
          RAISE EXCEPTION 'Construction item requirement snapshot is immutable'
            USING ERRCODE = '23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$
    """)

    for table in ("construction_examinations", "construction_items"):
        op.execute(
            f"CREATE TRIGGER phase12_construction_guard "
            f"BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION phase12_construction_guard()"
        )


def upgrade():
    op.execute("""
CREATE TABLE construction_examinations (
    test_session_id UUID NOT NULL,
    overall_notes TEXT,
    examined_by UUID,
    examined_at TIMESTAMP WITH TIME ZONE,
    summary_json JSONB DEFAULT '{}'::jsonb NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    lock_version INTEGER DEFAULT '1' NOT NULL,
    evaluation_status VARCHAR(30) DEFAULT 'NOT_STARTED' NOT NULL,
    compliance_outcome VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_construction_session UNIQUE (test_session_id),
    CONSTRAINT ck_construction_examination_evaluation CHECK (
      evaluation_status IN ('NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE')
    ),
    CONSTRAINT ck_construction_examination_outcome CHECK (
      compliance_outcome IN ('UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE')
    ),
    CONSTRAINT ck_construction_exam_version CHECK (lock_version > 0),
    CONSTRAINT ck_construction_examiner_pair CHECK (
      (examined_by IS NULL AND examined_at IS NULL) OR
      (examined_by IS NOT NULL AND examined_at IS NOT NULL)
    ),
    FOREIGN KEY(test_session_id) REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(examined_by) REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_construction_examinations_test_session_id "
        "ON construction_examinations (test_session_id)"
    )

    op.execute("""
CREATE TABLE construction_items (
    construction_examination_id UUID NOT NULL,
    requirement_rule_id UUID NOT NULL,
    category VARCHAR(60) NOT NULL,
    item_key VARCHAR(100) NOT NULL,
    description_snapshot TEXT NOT NULL,
    value_schema_version INTEGER DEFAULT '1' NOT NULL,
    value_json JSONB DEFAULT '{}'::jsonb NOT NULL,
    examination_state VARCHAR(30) DEFAULT 'NOT_EXAMINED' NOT NULL,
    conformance_result VARCHAR(30) DEFAULT 'UNDETERMINED' NOT NULL,
    remarks TEXT,
    sort_order INTEGER NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    lock_version INTEGER DEFAULT '1' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_construction_item_key UNIQUE (
      construction_examination_id, item_key
    ),
    CONSTRAINT ck_construction_item_category CHECK (
      category IN (
        'GENERAL','RECEPTOR_LOAD_CELLS','INDICATOR_DISPLAY',
        'PRINTER_PERIPHERALS','POWER_INTERFACES','TILT_ZERO_TARE',
        'SEALS_SECURITY_SOFTWARE','DOCUMENTS_PHOTOS'
      )
    ),
    CONSTRAINT ck_construction_item_state CHECK (
      examination_state IN ('NOT_EXAMINED','EXAMINED','REVIEW_REQUIRED')
    ),
    CONSTRAINT ck_construction_item_conformance CHECK (
      conformance_result IN ('PASS','FAIL','NOT_APPLICABLE','UNDETERMINED')
    ),
    CONSTRAINT ck_construction_item_state_result CHECK (
      (examination_state = 'NOT_EXAMINED' AND conformance_result = 'UNDETERMINED') OR
      (examination_state = 'REVIEW_REQUIRED' AND conformance_result = 'UNDETERMINED') OR
      (examination_state = 'EXAMINED' AND conformance_result IN ('PASS','FAIL','NOT_APPLICABLE'))
    ),
    CONSTRAINT ck_construction_item_metadata CHECK (
      value_schema_version = 1 AND lock_version > 0 AND sort_order >= 0
      AND length(trim(item_key)) > 0
    ),
    FOREIGN KEY(construction_examination_id)
      REFERENCES construction_examinations (id) ON DELETE RESTRICT,
    FOREIGN KEY(requirement_rule_id)
      REFERENCES rule_definitions (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_construction_items_examination "
        "ON construction_items (construction_examination_id, sort_order, id)"
    )
    op.execute(
        "CREATE INDEX ix_construction_items_requirement_rule_id "
        "ON construction_items (requirement_rule_id)"
    )
    install_guards()


def downgrade():
    op.drop_table("construction_items")
    op.drop_table("construction_examinations")
    op.execute("DROP FUNCTION phase12_construction_guard()")
