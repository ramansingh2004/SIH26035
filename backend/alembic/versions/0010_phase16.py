"""Phase 16 generated-document attachment integrity and preview publication guards."""
# ruff: noqa: E501

from alembic import op

revision = "0010_phase16"
down_revision = "0009_phase16"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION phase16_generated_attachment_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM report_files f
        WHERE f.attachment_id = OLD.id
      ) THEN
        RAISE EXCEPTION 'Canonical report attachment is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF EXISTS (
        SELECT 1
        FROM report_previews p
        WHERE p.preview_status = 'READY'
          AND p.expires_at > now()
          AND (
            p.file_attachment_ids ->> 'pdf' = OLD.id::text
            OR p.file_attachment_ids ->> 'docx' = OLD.id::text
          )
      ) THEN
        RAISE EXCEPTION 'Active report preview attachment is protected'
          USING ERRCODE = '23514';
      END IF;

      IF TG_OP = 'DELETE' THEN
        RETURN OLD;
      END IF;
      RETURN NEW;
    END $$
    """)

    op.execute("""
    CREATE FUNCTION phase16_preview_ready_files_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      session_lab UUID;
      pdf_id UUID;
      docx_id UUID;
    BEGIN
      IF TG_OP = 'UPDATE'
         AND OLD.preview_status = 'GENERATING'
         AND NEW.preview_status = 'READY' THEN

        SELECT laboratory_id INTO session_lab
        FROM test_sessions
        WHERE id = NEW.test_session_id;

        BEGIN
          pdf_id := (NEW.file_attachment_ids ->> 'pdf')::uuid;
          docx_id := (NEW.file_attachment_ids ->> 'docx')::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
          RAISE EXCEPTION 'Preview attachment identity is invalid'
            USING ERRCODE = '23514';
        END;

        IF NOT EXISTS (
          SELECT 1
          FROM attachments a
          WHERE a.id = pdf_id
            AND a.laboratory_id = session_lab
            AND a.archived_at IS NULL
            AND a.attachment_type = 'REPORT_PREVIEW'
            AND a.content_type = 'application/pdf'
        ) THEN
          RAISE EXCEPTION 'READY preview requires same-lab PDF attachment'
            USING ERRCODE = '23514';
        END IF;

        IF NOT EXISTS (
          SELECT 1
          FROM attachments a
          WHERE a.id = docx_id
            AND a.laboratory_id = session_lab
            AND a.archived_at IS NULL
            AND a.attachment_type = 'REPORT_PREVIEW'
            AND a.content_type =
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ) THEN
          RAISE EXCEPTION 'READY preview requires same-lab DOCX attachment'
            USING ERRCODE = '23514';
        END IF;
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute("""
    CREATE FUNCTION phase16_report_file_integrity_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      attachment_type_value VARCHAR(50);
      attachment_mime VARCHAR(100);
      attachment_hash VARCHAR(64);
    BEGIN
      SELECT a.attachment_type, a.content_type, a.sha256
      INTO attachment_type_value, attachment_mime, attachment_hash
      FROM attachments a
      WHERE a.id = NEW.attachment_id
        AND a.archived_at IS NULL;

      IF attachment_type_value IS DISTINCT FROM 'REPORT'
         OR attachment_hash IS DISTINCT FROM NEW.file_hash THEN
        RAISE EXCEPTION 'Report file attachment identity/hash mismatch'
          USING ERRCODE = '23514';
      END IF;

      IF (
        NEW.format = 'PDF'
        AND attachment_mime <> 'application/pdf'
      ) OR (
        NEW.format = 'DOCX'
        AND attachment_mime <>
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ) THEN
        RAISE EXCEPTION 'Report file format/media type mismatch'
          USING ERRCODE = '23514';
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute(
        "CREATE TRIGGER phase16_generated_attachment_guard "
        "BEFORE UPDATE OR DELETE ON attachments "
        "FOR EACH ROW EXECUTE FUNCTION phase16_generated_attachment_guard()"
    )
    op.execute(
        "CREATE TRIGGER phase16_preview_ready_files_guard "
        "BEFORE UPDATE ON report_previews "
        "FOR EACH ROW EXECUTE FUNCTION phase16_preview_ready_files_guard()"
    )
    op.execute(
        "CREATE TRIGGER phase16_report_file_integrity_guard "
        "BEFORE INSERT ON report_files "
        "FOR EACH ROW EXECUTE FUNCTION phase16_report_file_integrity_guard()"
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS phase16_report_file_integrity_guard ON report_files")
    op.execute("DROP TRIGGER IF EXISTS phase16_preview_ready_files_guard ON report_previews")
    op.execute("DROP TRIGGER IF EXISTS phase16_generated_attachment_guard ON attachments")
    op.execute("DROP FUNCTION IF EXISTS phase16_report_file_integrity_guard()")
    op.execute("DROP FUNCTION IF EXISTS phase16_preview_ready_files_guard()")
    op.execute("DROP FUNCTION IF EXISTS phase16_generated_attachment_guard()")
