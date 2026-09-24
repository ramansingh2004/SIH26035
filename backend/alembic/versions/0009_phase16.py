"""Phase 16 report persistence, lineage and immutable-generation contracts."""
# ruff: noqa: E501

from alembic import op

revision = "0009_phase16"
down_revision = "0008_phase15"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase16_report_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      source_session test_sessions%ROWTYPE;
      predecessor reports%ROWTYPE;
      predecessor_session test_sessions%ROWTYPE;
      selected_generation report_generations%ROWTYPE;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Report history is immutable'
          USING ERRCODE = '23514';
      END IF;

      SELECT * INTO source_session
      FROM test_sessions
      WHERE id = NEW.test_session_id;

      IF source_session.id IS NULL THEN
        RAISE EXCEPTION 'Report source session is missing'
          USING ERRCODE = '23514';
      END IF;

      IF TG_OP = 'INSERT' THEN
        IF source_session.workflow_status <> 'APPROVED' THEN
          RAISE EXCEPTION 'Official report requires an approved session'
            USING ERRCODE = '23514';
        END IF;

        IF NEW.revision_no = 1 THEN
          IF NEW.root_report_id <> NEW.id OR NEW.supersedes_report_id IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid root report lineage'
              USING ERRCODE = '23514';
          END IF;
        ELSE
          SELECT * INTO predecessor
          FROM reports
          WHERE id = NEW.supersedes_report_id;

          IF predecessor.id IS NULL
             OR predecessor.report_status <> 'ISSUED'
             OR predecessor.report_number <> NEW.report_number
             OR predecessor.revision_no + 1 <> NEW.revision_no
             OR predecessor.root_report_id <> NEW.root_report_id THEN
            RAISE EXCEPTION 'Invalid report predecessor'
              USING ERRCODE = '23514';
          END IF;

          SELECT * INTO predecessor_session
          FROM test_sessions
          WHERE id = predecessor.test_session_id;

          IF source_session.parent_session_id IS DISTINCT FROM predecessor_session.id
             OR source_session.root_session_id IS DISTINCT FROM predecessor_session.root_session_id
             OR source_session.laboratory_id IS DISTINCT FROM predecessor_session.laboratory_id
             OR source_session.instrument_id IS DISTINCT FROM predecessor_session.instrument_id THEN
            RAISE EXCEPTION 'Report revision must use the approved child session lineage'
              USING ERRCODE = '23514';
          END IF;
        END IF;

        RETURN NEW;
      END IF;

      IF (
        NEW.test_session_id,
        NEW.report_number,
        NEW.revision_no,
        NEW.root_report_id,
        NEW.supersedes_report_id,
        NEW.revision_reason,
        NEW.created_at,
        NEW.created_by
      ) IS DISTINCT FROM (
        OLD.test_session_id,
        OLD.report_number,
        OLD.revision_no,
        OLD.root_report_id,
        OLD.supersedes_report_id,
        OLD.revision_reason,
        OLD.created_at,
        OLD.created_by
      ) THEN
        RAISE EXCEPTION 'Report identity and lineage are immutable'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.lock_version <> OLD.lock_version + 1 THEN
        RAISE EXCEPTION 'Report mutation requires one lock-version increment'
          USING ERRCODE = '23514';
      END IF;

      IF OLD.report_status = 'UNISSUED' THEN
        IF NEW.report_status NOT IN ('UNISSUED','ISSUED') THEN
          RAISE EXCEPTION 'Invalid report status transition'
            USING ERRCODE = '23514';
        END IF;
      ELSIF OLD.report_status = 'ISSUED' THEN
        IF NEW.report_status NOT IN ('ISSUED','SUPERSEDED') THEN
          RAISE EXCEPTION 'Invalid issued-report transition'
            USING ERRCODE = '23514';
        END IF;
        IF (
          NEW.selected_generation_id,
          NEW.issued_at,
          NEW.issued_by,
          NEW.issuance_manifest,
          NEW.report_hash
        ) IS DISTINCT FROM (
          OLD.selected_generation_id,
          OLD.issued_at,
          OLD.issued_by,
          OLD.issuance_manifest,
          OLD.report_hash
        ) THEN
          RAISE EXCEPTION 'Issued report metadata is immutable'
            USING ERRCODE = '23514';
        END IF;
      ELSE
        RAISE EXCEPTION 'Superseded report is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.report_status = 'ISSUED' THEN
        SELECT * INTO selected_generation
        FROM report_generations
        WHERE id = NEW.selected_generation_id
          AND report_id = NEW.id;

        IF selected_generation.id IS NULL
           OR selected_generation.generation_status <> 'READY'
           OR selected_generation.report_hash IS DISTINCT FROM NEW.report_hash THEN
          RAISE EXCEPTION 'Issued report requires the selected READY generation'
            USING ERRCODE = '23514';
        END IF;
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute("""
    CREATE FUNCTION phase16_generation_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      source_session_id UUID;
      approved_revision INTEGER;
      pdf_count INTEGER;
      docx_count INTEGER;
    BEGIN
      IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Report generation history is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF TG_OP = 'INSERT' THEN
        SELECT r.test_session_id INTO source_session_id
        FROM reports r
        WHERE r.id = NEW.report_id;

        SELECT s.regulatory_revision INTO approved_revision
        FROM session_approval_snapshots s
        WHERE s.test_session_id = source_session_id;

        IF source_session_id IS NULL
           OR approved_revision IS NULL
           OR approved_revision <> NEW.source_regulatory_revision THEN
          RAISE EXCEPTION 'Report generation must reference the approved regulatory revision'
            USING ERRCODE = '23514';
        END IF;

        RETURN NEW;
      END IF;

      IF OLD.generation_status <> 'GENERATING' THEN
        RAISE EXCEPTION 'Completed report generation is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF (
        NEW.report_id,
        NEW.attempt_no,
        NEW.report_context_snapshot,
        NEW.context_schema_version,
        NEW.context_hash,
        NEW.source_regulatory_revision,
        NEW.intended_issuer_id,
        NEW.planned_issue_date,
        NEW.template_version,
        NEW.renderer_manifest,
        NEW.created_at
      ) IS DISTINCT FROM (
        OLD.report_id,
        OLD.attempt_no,
        OLD.report_context_snapshot,
        OLD.context_schema_version,
        OLD.context_hash,
        OLD.source_regulatory_revision,
        OLD.intended_issuer_id,
        OLD.planned_issue_date,
        OLD.template_version,
        OLD.renderer_manifest,
        OLD.created_at
      ) THEN
        RAISE EXCEPTION 'Report generation context is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.generation_status NOT IN ('READY','FAILED') THEN
        RAISE EXCEPTION 'Generation may only complete READY or FAILED'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.generation_status = 'READY' THEN
        SELECT
          count(*) FILTER (WHERE format = 'PDF'),
          count(*) FILTER (WHERE format = 'DOCX')
        INTO pdf_count, docx_count
        FROM report_files
        WHERE report_generation_id = NEW.id;

        IF pdf_count <> 1 OR docx_count <> 1 THEN
          RAISE EXCEPTION 'READY generation requires exactly one PDF and one DOCX'
            USING ERRCODE = '23514';
        END IF;
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute("""
    CREATE FUNCTION phase16_report_file_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      report_lab UUID;
      attachment_lab UUID;
      attachment_archived TIMESTAMP WITH TIME ZONE;
      generation_state VARCHAR(20);
    BEGIN
      IF TG_OP IN ('UPDATE','DELETE') THEN
        RAISE EXCEPTION 'Report files are immutable'
          USING ERRCODE = '23514';
      END IF;

      SELECT s.laboratory_id, g.generation_status
      INTO report_lab, generation_state
      FROM report_generations g
      JOIN reports r ON r.id = g.report_id
      JOIN test_sessions s ON s.id = r.test_session_id
      WHERE g.id = NEW.report_generation_id;

      SELECT a.laboratory_id, a.archived_at
      INTO attachment_lab, attachment_archived
      FROM attachments a
      WHERE a.id = NEW.attachment_id;

      IF report_lab IS NULL
         OR attachment_lab IS NULL
         OR attachment_lab IS DISTINCT FROM report_lab
         OR attachment_archived IS NOT NULL THEN
        RAISE EXCEPTION 'Report file attachment must be active and laboratory-scoped'
          USING ERRCODE = '23514';
      END IF;

      IF generation_state <> 'GENERATING' THEN
        RAISE EXCEPTION 'Files may only be attached while generation is in progress'
          USING ERRCODE = '23514';
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute("""
    CREATE FUNCTION phase16_preview_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        IF OLD.expires_at > now() THEN
          RAISE EXCEPTION 'Unexpired report preview cannot be deleted'
            USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
      END IF;

      IF TG_OP = 'INSERT' THEN
        RETURN NEW;
      END IF;

      IF OLD.preview_status <> 'GENERATING' THEN
        RAISE EXCEPTION 'Completed report preview is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF (
        NEW.test_session_id,
        NEW.source_regulatory_revision,
        NEW.preview_context_snapshot,
        NEW.requested_by,
        NEW.requested_at,
        NEW.expires_at,
        NEW.context_hash
      ) IS DISTINCT FROM (
        OLD.test_session_id,
        OLD.source_regulatory_revision,
        OLD.preview_context_snapshot,
        OLD.requested_by,
        OLD.requested_at,
        OLD.expires_at,
        OLD.context_hash
      ) THEN
        RAISE EXCEPTION 'Report preview context and provenance are immutable'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.preview_status NOT IN ('READY','FAILED') THEN
        RAISE EXCEPTION 'Preview may only complete READY or FAILED'
          USING ERRCODE = '23514';
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute(
        "CREATE TRIGGER phase16_reports_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON reports "
        "FOR EACH ROW EXECUTE FUNCTION phase16_report_guard()"
    )
    op.execute(
        "CREATE TRIGGER phase16_report_generations_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON report_generations "
        "FOR EACH ROW EXECUTE FUNCTION phase16_generation_guard()"
    )
    op.execute(
        "CREATE TRIGGER phase16_report_files_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON report_files "
        "FOR EACH ROW EXECUTE FUNCTION phase16_report_file_guard()"
    )
    op.execute(
        "CREATE TRIGGER phase16_report_previews_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON report_previews "
        "FOR EACH ROW EXECUTE FUNCTION phase16_preview_guard()"
    )


def upgrade():
    op.execute("""
CREATE TABLE report_number_counters (
    year INTEGER NOT NULL,
    next_sequence INTEGER DEFAULT 1 NOT NULL,
    lock_version INTEGER DEFAULT 1 NOT NULL,
    PRIMARY KEY (year),
    CONSTRAINT ck_report_counter_values CHECK (
      year BETWEEN 2000 AND 9999
      AND next_sequence > 0
      AND lock_version > 0
    )
)
    """)

    op.execute("""
CREATE TABLE reports (
    test_session_id UUID NOT NULL,
    report_number VARCHAR(80) NOT NULL,
    revision_no INTEGER NOT NULL,
    root_report_id UUID NOT NULL,
    supersedes_report_id UUID,
    revision_reason TEXT,
    report_status VARCHAR(20) DEFAULT 'UNISSUED' NOT NULL,
    selected_generation_id UUID,
    issued_at TIMESTAMP WITH TIME ZONE,
    issued_by UUID,
    issuance_manifest JSONB,
    report_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    created_by UUID NOT NULL,
    lock_version INTEGER DEFAULT 1 NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_report_session UNIQUE (test_session_id),
    CONSTRAINT uq_report_number_revision UNIQUE (report_number, revision_no),
    CONSTRAINT uq_report_number_scope UNIQUE (id, report_number),
    CONSTRAINT ck_report_number_format CHECK (
      report_number ~ '^R76-[0-9]{4}-[1-9][0-9]*$'
    ),
    CONSTRAINT ck_report_versions CHECK (
      revision_no > 0 AND lock_version > 0
    ),
    CONSTRAINT ck_report_status CHECK (
      report_status IN ('UNISSUED','ISSUED','SUPERSEDED')
    ),
    CONSTRAINT ck_report_lineage CHECK (
      (
        revision_no = 1
        AND root_report_id = id
        AND supersedes_report_id IS NULL
        AND revision_reason IS NULL
      ) OR (
        revision_no > 1
        AND root_report_id <> id
        AND supersedes_report_id IS NOT NULL
        AND revision_reason IS NOT NULL
        AND length(trim(revision_reason)) > 0
      )
    ),
    CONSTRAINT ck_report_issue_state CHECK (
      (
        report_status = 'UNISSUED'
        AND issued_at IS NULL
        AND issued_by IS NULL
        AND issuance_manifest IS NULL
      ) OR (
        report_status IN ('ISSUED','SUPERSEDED')
        AND selected_generation_id IS NOT NULL
        AND issued_at IS NOT NULL
        AND issued_by IS NOT NULL
        AND issuance_manifest IS NOT NULL
        AND jsonb_typeof(issuance_manifest) = 'object'
        AND report_hash IS NOT NULL
      )
    ),
    CONSTRAINT ck_report_hash CHECK (
      report_hash IS NULL OR report_hash ~ '^[a-f0-9]{64}$'
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(issued_by)
      REFERENCES users (id) ON DELETE RESTRICT,
    FOREIGN KEY(created_by)
      REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_report_root_number
      FOREIGN KEY(root_report_id, report_number)
      REFERENCES reports (id, report_number)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_report_predecessor_number
      FOREIGN KEY(supersedes_report_id, report_number)
      REFERENCES reports (id, report_number)
      ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
)
    """)
    op.execute("CREATE INDEX ix_reports_number_revision ON reports (report_number, revision_no)")
    op.execute(
        "CREATE UNIQUE INDEX uq_report_current_issued "
        "ON reports (report_number) WHERE report_status = 'ISSUED'"
    )

    op.execute("""
CREATE TABLE report_generations (
    report_id UUID NOT NULL,
    attempt_no INTEGER NOT NULL,
    generation_status VARCHAR(20) DEFAULT 'GENERATING' NOT NULL,
    report_context_snapshot JSONB NOT NULL,
    context_schema_version INTEGER DEFAULT 1 NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    source_regulatory_revision INTEGER NOT NULL,
    intended_issuer_id UUID NOT NULL,
    planned_issue_date DATE NOT NULL,
    template_version VARCHAR(100) NOT NULL,
    renderer_manifest JSONB NOT NULL,
    report_hash VARCHAR(64),
    error_code VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_report_generation_attempt UNIQUE (report_id, attempt_no),
    CONSTRAINT uq_report_generation_scope UNIQUE (report_id, id),
    CONSTRAINT ck_report_generation_versions CHECK (
      attempt_no > 0 AND source_regulatory_revision > 0
    ),
    CONSTRAINT ck_report_generation_status CHECK (
      generation_status IN ('GENERATING','READY','FAILED')
    ),
    CONSTRAINT ck_report_generation_context CHECK (
      context_schema_version = 1
      AND jsonb_typeof(report_context_snapshot) = 'object'
    ),
    CONSTRAINT ck_report_generation_context_hash CHECK (
      context_hash ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT ck_report_generation_renderer_manifest CHECK (
      jsonb_typeof(renderer_manifest) = 'object'
    ),
    CONSTRAINT ck_report_generation_report_hash CHECK (
      report_hash IS NULL OR report_hash ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT ck_report_generation_completion CHECK (
      (
        generation_status = 'GENERATING'
        AND completed_at IS NULL
        AND report_hash IS NULL
        AND error_code IS NULL
      ) OR (
        generation_status = 'READY'
        AND completed_at IS NOT NULL
        AND report_hash IS NOT NULL
        AND error_code IS NULL
      ) OR (
        generation_status = 'FAILED'
        AND completed_at IS NOT NULL
        AND report_hash IS NULL
        AND error_code IS NOT NULL
        AND length(trim(error_code)) > 0
      )
    ),
    FOREIGN KEY(report_id)
      REFERENCES reports (id) ON DELETE RESTRICT,
    FOREIGN KEY(intended_issuer_id)
      REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_report_generations_report_attempt "
        "ON report_generations (report_id, attempt_no)"
    )

    op.execute("""
ALTER TABLE reports
ADD CONSTRAINT fk_report_selected_generation
FOREIGN KEY(id, selected_generation_id)
REFERENCES report_generations (report_id, id)
ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
    """)

    op.execute("""
CREATE TABLE report_files (
    report_generation_id UUID NOT NULL,
    format VARCHAR(10) NOT NULL,
    attachment_id UUID NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_report_file_format
      UNIQUE (report_generation_id, format),
    CONSTRAINT ck_report_file_format CHECK (
      format IN ('PDF','DOCX')
    ),
    CONSTRAINT ck_report_file_hash CHECK (
      file_hash ~ '^[a-f0-9]{64}$'
    ),
    FOREIGN KEY(report_generation_id)
      REFERENCES report_generations (id) ON DELETE RESTRICT,
    FOREIGN KEY(attachment_id)
      REFERENCES attachments (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_report_files_generation ON report_files (report_generation_id, format)"
    )

    op.execute("""
CREATE TABLE report_previews (
    test_session_id UUID NOT NULL,
    source_regulatory_revision INTEGER NOT NULL,
    preview_context_snapshot JSONB NOT NULL,
    preview_status VARCHAR(20) DEFAULT 'GENERATING' NOT NULL,
    requested_by UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    file_attachment_ids JSONB DEFAULT '{}'::jsonb NOT NULL,
    error_code VARCHAR(100),
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_report_preview_revision CHECK (
      source_regulatory_revision > 0
    ),
    CONSTRAINT ck_report_preview_status CHECK (
      preview_status IN ('GENERATING','READY','FAILED')
    ),
    CONSTRAINT ck_report_preview_context CHECK (
      jsonb_typeof(preview_context_snapshot) = 'object'
    ),
    CONSTRAINT ck_report_preview_context_hash CHECK (
      context_hash ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT ck_report_preview_files CHECK (
      jsonb_typeof(file_attachment_ids) = 'object'
    ),
    CONSTRAINT ck_report_preview_expiry CHECK (
      expires_at > requested_at
    ),
    CONSTRAINT ck_report_preview_completion CHECK (
      (
        preview_status = 'GENERATING'
        AND file_attachment_ids = '{}'::jsonb
        AND error_code IS NULL
      ) OR (
        preview_status = 'READY'
        AND file_attachment_ids ? 'pdf'
        AND file_attachment_ids ? 'docx'
        AND jsonb_typeof(file_attachment_ids -> 'pdf') = 'string'
        AND jsonb_typeof(file_attachment_ids -> 'docx') = 'string'
        AND error_code IS NULL
      ) OR (
        preview_status = 'FAILED'
        AND error_code IS NOT NULL
        AND length(trim(error_code)) > 0
      )
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(requested_by)
      REFERENCES users (id) ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_report_previews_session_requested "
        "ON report_previews (test_session_id, requested_at)"
    )

    install_guards()


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS phase16_report_previews_guard ON report_previews")
    op.execute("DROP TRIGGER IF EXISTS phase16_report_files_guard ON report_files")
    op.execute("DROP TRIGGER IF EXISTS phase16_report_generations_guard ON report_generations")
    op.execute("DROP TRIGGER IF EXISTS phase16_reports_guard ON reports")

    op.execute("DROP FUNCTION IF EXISTS phase16_preview_guard()")
    op.execute("DROP FUNCTION IF EXISTS phase16_report_file_guard()")
    op.execute("DROP FUNCTION IF EXISTS phase16_generation_guard()")
    op.execute("DROP FUNCTION IF EXISTS phase16_report_guard()")

    op.execute("ALTER TABLE reports DROP CONSTRAINT IF EXISTS fk_report_selected_generation")
    op.drop_table("report_previews")
    op.drop_table("report_files")
    op.drop_table("report_generations")
    op.drop_table("reports")
    op.drop_table("report_number_counters")
