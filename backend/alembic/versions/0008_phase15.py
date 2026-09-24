"""Phase 15 terminal-session source immutability hardening."""
# ruff: noqa: E501

from alembic import op

revision = "0008_phase15"
down_revision = "0007_phase15"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION phase15_terminal_source_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      target_session_id UUID;
      target_status VARCHAR(40);
      target_entity_type VARCHAR(80);
      target_entity_id UUID;
      target_run_id UUID;
      target_examination_id UUID;
    BEGIN
      IF TG_TABLE_NAME = 'test_sessions' THEN
        IF TG_OP = 'DELETE' THEN
          IF OLD.workflow_status IN ('APPROVED','REPORT_ISSUED','REJECTED','CANCELLED') THEN
            RAISE EXCEPTION 'Terminal session source is immutable'
              USING ERRCODE = '23514';
          END IF;
          RETURN OLD;
        END IF;

        IF TG_OP = 'UPDATE'
           AND OLD.workflow_status IN ('APPROVED','REPORT_ISSUED','REJECTED','CANCELLED') THEN
          IF OLD.workflow_status = 'APPROVED'
             AND NEW.workflow_status = 'REPORT_ISSUED'
             AND NEW.lock_version = OLD.lock_version + 1
             AND (
               to_jsonb(NEW)
               - 'workflow_status'
               - 'lock_version'
               - 'updated_at'
             ) = (
               to_jsonb(OLD)
               - 'workflow_status'
               - 'lock_version'
               - 'updated_at'
             ) THEN
            RETURN NEW;
          END IF;

          RAISE EXCEPTION 'Terminal session source is immutable'
            USING ERRCODE = '23514';
        END IF;

        RETURN NEW;
      END IF;

      IF TG_TABLE_NAME IN (
        'test_session_sections',
        'session_test_requirements',
        'test_runs',
        'environment_readings',
        'construction_examinations',
        'checklist_responses'
      ) THEN
        IF TG_OP = 'DELETE' THEN
          target_session_id := OLD.test_session_id;
        ELSE
          target_session_id := NEW.test_session_id;
        END IF;

      ELSIF TG_TABLE_NAME IN ('test_observations','test_run_equipment') THEN
        IF TG_OP = 'DELETE' THEN
          target_run_id := OLD.test_run_id;
        ELSE
          target_run_id := NEW.test_run_id;
        END IF;

        SELECT test_session_id INTO target_session_id
        FROM test_runs
        WHERE id = target_run_id;

      ELSIF TG_TABLE_NAME = 'construction_items' THEN
        IF TG_OP = 'DELETE' THEN
          target_examination_id := OLD.construction_examination_id;
        ELSE
          target_examination_id := NEW.construction_examination_id;
        END IF;

        SELECT test_session_id INTO target_session_id
        FROM construction_examinations
        WHERE id = target_examination_id;

      ELSIF TG_TABLE_NAME = 'attachment_links' THEN
        IF TG_OP = 'DELETE' THEN
          target_entity_type := OLD.entity_type;
          target_entity_id := OLD.entity_id;
        ELSE
          target_entity_type := NEW.entity_type;
          target_entity_id := NEW.entity_id;
        END IF;

        IF target_entity_type = 'test_sessions' THEN
          target_session_id := target_entity_id;

        ELSIF target_entity_type = 'test_runs' THEN
          SELECT test_session_id INTO target_session_id
          FROM test_runs
          WHERE id = target_entity_id;

        ELSIF target_entity_type = 'test_observations' THEN
          SELECT r.test_session_id INTO target_session_id
          FROM test_observations o
          JOIN test_runs r ON r.id = o.test_run_id
          WHERE o.id = target_entity_id;

        ELSIF target_entity_type = 'test_run_equipment' THEN
          SELECT r.test_session_id INTO target_session_id
          FROM test_run_equipment e
          JOIN test_runs r ON r.id = e.test_run_id
          WHERE e.id = target_entity_id;

        ELSIF target_entity_type = 'test_run_results' THEN
          SELECT r.test_session_id INTO target_session_id
          FROM test_run_results x
          JOIN test_runs r ON r.id = x.test_run_id
          WHERE x.id = target_entity_id;

        ELSIF target_entity_type = 'construction_items' THEN
          SELECT e.test_session_id INTO target_session_id
          FROM construction_items i
          JOIN construction_examinations e
            ON e.id = i.construction_examination_id
          WHERE i.id = target_entity_id;

        ELSIF target_entity_type = 'checklist_responses' THEN
          SELECT test_session_id INTO target_session_id
          FROM checklist_responses
          WHERE id = target_entity_id;
        END IF;
      END IF;

      IF target_session_id IS NOT NULL THEN
        SELECT workflow_status INTO target_status
        FROM test_sessions
        WHERE id = target_session_id;

        IF target_status IN ('APPROVED','REPORT_ISSUED','REJECTED','CANCELLED') THEN
          RAISE EXCEPTION 'Terminal session source is immutable'
            USING ERRCODE = '23514';
        END IF;
      END IF;

      IF TG_OP = 'DELETE' THEN
        RETURN OLD;
      END IF;
      RETURN NEW;
    END $$
    """)

    for table in (
        "test_sessions",
        "test_session_sections",
        "session_test_requirements",
        "test_runs",
        "test_observations",
        "environment_readings",
        "test_run_equipment",
        "construction_examinations",
        "construction_items",
        "checklist_responses",
        "attachment_links",
    ):
        op.execute(
            f"CREATE TRIGGER phase15_terminal_source_{table} "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION phase15_terminal_source_guard()"
        )


def downgrade():
    for table in (
        "attachment_links",
        "checklist_responses",
        "construction_items",
        "construction_examinations",
        "test_run_equipment",
        "environment_readings",
        "test_observations",
        "test_runs",
        "session_test_requirements",
        "test_session_sections",
        "test_sessions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS phase15_terminal_source_{table} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS phase15_terminal_source_guard()")
