"""Phase 13 checklist response foundation. Static PostgreSQL DDL snapshot."""
# ruff: noqa: E501

from alembic import op

revision = "0006_phase13"
down_revision = "0005_phase12"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase13_checklist_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      session_rule_set UUID;
      catalog_rule_set UUID;
    BEGIN
      SELECT s.rule_set_id INTO session_rule_set
        FROM test_sessions s
        WHERE s.id = NEW.test_session_id;

      SELECT c.rule_set_id INTO catalog_rule_set
        FROM checklist_rules c
        WHERE c.id = NEW.checklist_rule_id;

      IF session_rule_set IS NULL OR catalog_rule_set IS NULL
         OR session_rule_set IS DISTINCT FROM catalog_rule_set THEN
        RAISE EXCEPTION 'Checklist rule/session ruleset mismatch'
          USING ERRCODE = '23514';
      END IF;

      IF TG_OP = 'UPDATE' AND (
        NEW.test_session_id,
        NEW.checklist_rule_id
      ) IS DISTINCT FROM (
        OLD.test_session_id,
        OLD.checklist_rule_id
      ) THEN
        RAISE EXCEPTION 'Checklist response identity is immutable'
          USING ERRCODE = '23514';
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute(
        "CREATE TRIGGER phase13_checklist_guard "
        "BEFORE INSERT OR UPDATE ON checklist_responses "
        "FOR EACH ROW EXECUTE FUNCTION phase13_checklist_guard()"
    )


def upgrade():
    op.execute("""
CREATE TABLE checklist_responses (
    test_session_id UUID NOT NULL,
    checklist_rule_id UUID NOT NULL,
    applicability_status VARCHAR(30) NOT NULL,
    applicability_reason TEXT NOT NULL,
    response_result VARCHAR(30) DEFAULT 'NOT_EXAMINED' NOT NULL,
    remarks TEXT,
    examined_by UUID,
    examined_at TIMESTAMP WITH TIME ZONE,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    lock_version INTEGER DEFAULT '1' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_checklist_response_rule UNIQUE (
      test_session_id, checklist_rule_id
    ),
    CONSTRAINT ck_checklist_response_applicability CHECK (
      applicability_status IN (
        'REQUIRED','NOT_APPLICABLE','REQUIRES_REVIEW'
      )
    ),
    CONSTRAINT ck_checklist_response_result CHECK (
      response_result IN (
        'PASS','FAIL','NOT_APPLICABLE','NOT_EXAMINED'
      )
    ),
    CONSTRAINT ck_checklist_response_examiner CHECK (
      (
        response_result = 'NOT_EXAMINED'
        AND examined_by IS NULL AND examined_at IS NULL
      ) OR (
        applicability_status = 'NOT_APPLICABLE'
        AND response_result = 'NOT_APPLICABLE'
        AND examined_by IS NULL AND examined_at IS NULL
      ) OR (
        response_result IN ('PASS','FAIL','NOT_APPLICABLE')
        AND examined_by IS NOT NULL AND examined_at IS NOT NULL
      )
    ),
    CONSTRAINT ck_checklist_response_excluded_result CHECK (
      applicability_status <> 'NOT_APPLICABLE'
      OR response_result = 'NOT_APPLICABLE'
    ),
    CONSTRAINT ck_checklist_response_version CHECK (
      lock_version > 0
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(checklist_rule_id)
      REFERENCES checklist_rules (id) ON DELETE RESTRICT,
    FOREIGN KEY(examined_by)
      REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_checklist_responses_session ON checklist_responses (test_session_id, id)"
    )
    op.execute(
        "CREATE INDEX ix_checklist_responses_test_session_id "
        "ON checklist_responses (test_session_id)"
    )
    op.execute(
        "CREATE INDEX ix_checklist_responses_checklist_rule_id "
        "ON checklist_responses (checklist_rule_id)"
    )
    install_guards()


def downgrade():
    op.drop_table("checklist_responses")
    op.execute("DROP FUNCTION phase13_checklist_guard()")
