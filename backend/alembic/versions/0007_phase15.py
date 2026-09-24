"""Phase 15 review, correction and final-approval snapshot foundation."""
# ruff: noqa: E501

from alembic import op

revision = "0007_phase15"
down_revision = "0006_phase13"
branch_labels = None
depends_on = None


def install_guards():
    op.execute("""
    CREATE FUNCTION phase15_validate_review_insert()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
      referenced_stage VARCHAR(30);
      approval_stage VARCHAR(30);
      approval_decision VARCHAR(40);
      approval_revision INTEGER;
    BEGIN
      IF TG_TABLE_NAME = 'approval_actions' THEN
        IF NEW.referenced_action_id IS NOT NULL THEN
          SELECT stage INTO referenced_stage
            FROM approval_actions
            WHERE id = NEW.referenced_action_id
              AND test_session_id = NEW.test_session_id;
          IF referenced_stage IS NULL OR referenced_stage IS DISTINCT FROM NEW.stage THEN
            RAISE EXCEPTION 'Referenced approval action must belong to the same session and stage'
              USING ERRCODE = '23514';
          END IF;
        END IF;
        RETURN NEW;
      END IF;

      IF TG_TABLE_NAME = 'correction_requests' THEN
        SELECT stage, decision INTO approval_stage, approval_decision
          FROM approval_actions
          WHERE id = NEW.approval_action_id
            AND test_session_id = NEW.test_session_id;
        IF approval_stage IS DISTINCT FROM 'TECHNICAL_REVIEW'
           OR approval_decision IS DISTINCT FROM 'RETURNED_FOR_CORRECTION' THEN
          RAISE EXCEPTION 'Correction request requires matching technical return action'
            USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
      END IF;

      IF TG_TABLE_NAME = 'session_approval_snapshots' THEN
        SELECT stage, decision, regulatory_revision
          INTO approval_stage, approval_decision, approval_revision
          FROM approval_actions
          WHERE id = NEW.approval_action_id
            AND test_session_id = NEW.test_session_id;
        IF approval_stage IS DISTINCT FROM 'FINAL_APPROVAL'
           OR approval_decision IS DISTINCT FROM 'APPROVED'
           OR approval_revision IS DISTINCT FROM NEW.regulatory_revision THEN
          RAISE EXCEPTION 'Approval snapshot requires matching final approval action and revision'
            USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
      END IF;

      RETURN NEW;
    END $$
    """)

    for table in (
        "approval_actions",
        "correction_requests",
        "session_approval_snapshots",
    ):
        op.execute(
            f"CREATE TRIGGER phase15_validate_{table} "
            f"BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION phase15_validate_review_insert()"
        )

    op.execute("""
    CREATE FUNCTION phase15_deny_review_history_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'Phase 15 review history is append-only'
        USING ERRCODE = '42501';
    END $$
    """)

    for table in ("approval_actions", "session_approval_snapshots"):
        op.execute(
            f"CREATE TRIGGER phase15_{table}_immutable "
            f"BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION phase15_deny_review_history_mutation()"
        )

    op.execute("""
    CREATE FUNCTION phase15_correction_update_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (
        NEW.test_session_id,
        NEW.approval_action_id,
        NEW.target_workflow_status,
        NEW.requested_scope_json,
        NEW.reason,
        NEW.requested_by,
        NEW.requested_at
      ) IS DISTINCT FROM (
        OLD.test_session_id,
        OLD.approval_action_id,
        OLD.target_workflow_status,
        OLD.requested_scope_json,
        OLD.reason,
        OLD.requested_by,
        OLD.requested_at
      ) THEN
        RAISE EXCEPTION 'Correction request scope and provenance are immutable'
          USING ERRCODE = '23514';
      END IF;

      IF OLD.correction_status <> 'OPEN' THEN
        RAISE EXCEPTION 'Resolved correction request is immutable'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.correction_status NOT IN ('RESOLVED','CANCELLED') THEN
        RAISE EXCEPTION 'Correction request may only leave OPEN once'
          USING ERRCODE = '23514';
      END IF;

      IF NEW.lock_version <> OLD.lock_version + 1 THEN
        RAISE EXCEPTION 'Correction request lock version must increment by one'
          USING ERRCODE = '23514';
      END IF;

      RETURN NEW;
    END $$
    """)

    op.execute(
        "CREATE TRIGGER phase15_correction_request_update_guard "
        "BEFORE UPDATE ON correction_requests "
        "FOR EACH ROW EXECUTE FUNCTION phase15_correction_update_guard()"
    )


def upgrade():
    op.execute("""
CREATE TABLE approval_actions (
    test_session_id UUID NOT NULL,
    stage VARCHAR(30) NOT NULL,
    decision VARCHAR(40) NOT NULL,
    actor_id UUID NOT NULL,
    regulatory_revision INTEGER NOT NULL,
    scope_json JSONB NOT NULL,
    referenced_action_id UUID,
    comment TEXT,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_approval_action_session_scope UNIQUE (test_session_id, id),
    CONSTRAINT ck_approval_action_stage CHECK (
      stage IN ('TECHNICAL_REVIEW','FINAL_APPROVAL')
    ),
    CONSTRAINT ck_approval_action_decision CHECK (
      decision IN (
        'SUBMITTED','APPROVED','REJECTED',
        'RETURNED_FOR_CORRECTION','INVALIDATED'
      )
    ),
    CONSTRAINT ck_approval_action_stage_decision CHECK (
      (
        stage = 'TECHNICAL_REVIEW'
        AND decision IN (
          'SUBMITTED','APPROVED','REJECTED',
          'RETURNED_FOR_CORRECTION','INVALIDATED'
        )
      ) OR (
        stage = 'FINAL_APPROVAL'
        AND decision IN ('APPROVED','REJECTED')
      )
    ),
    CONSTRAINT ck_approval_action_revision CHECK (
      regulatory_revision > 0
    ),
    CONSTRAINT ck_approval_action_scope CHECK (
      jsonb_typeof(scope_json) = 'object'
    ),
    CONSTRAINT ck_approval_action_reference CHECK (
      decision <> 'INVALIDATED' OR referenced_action_id IS NOT NULL
    ),
    CONSTRAINT ck_approval_action_reason CHECK (
      decision NOT IN ('REJECTED','RETURNED_FOR_CORRECTION','INVALIDATED')
      OR (reason IS NOT NULL AND length(trim(reason)) > 0)
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(actor_id)
      REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_approval_action_reference_scope
      FOREIGN KEY(test_session_id, referenced_action_id)
      REFERENCES approval_actions (test_session_id, id)
      ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_approval_actions_session "
        "ON approval_actions (test_session_id, created_at, id)"
    )

    op.execute("""
CREATE TABLE correction_requests (
    test_session_id UUID NOT NULL,
    approval_action_id UUID NOT NULL,
    target_workflow_status VARCHAR(30) NOT NULL,
    requested_scope_json JSONB NOT NULL,
    reason TEXT NOT NULL,
    requested_by UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    correction_status VARCHAR(20) DEFAULT 'OPEN' NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    lock_version INTEGER DEFAULT '1' NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_correction_action UNIQUE (approval_action_id),
    CONSTRAINT ck_correction_target CHECK (
      target_workflow_status IN ('TESTING','EXAMINATION')
    ),
    CONSTRAINT ck_correction_status CHECK (
      correction_status IN ('OPEN','RESOLVED','CANCELLED')
    ),
    CONSTRAINT ck_correction_scope CHECK (
      jsonb_typeof(requested_scope_json) = 'object'
      AND requested_scope_json ? 'targets'
      AND jsonb_typeof(requested_scope_json -> 'targets') = 'array'
      AND jsonb_array_length(requested_scope_json -> 'targets') > 0
    ),
    CONSTRAINT ck_correction_reason CHECK (
      length(trim(reason)) > 0
    ),
    CONSTRAINT ck_correction_resolution CHECK (
      (
        correction_status = 'OPEN'
        AND resolved_at IS NULL
      ) OR (
        correction_status IN ('RESOLVED','CANCELLED')
        AND resolved_at IS NOT NULL
      )
    ),
    CONSTRAINT ck_correction_version CHECK (
      lock_version > 0
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(requested_by)
      REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_correction_action_scope
      FOREIGN KEY(test_session_id, approval_action_id)
      REFERENCES approval_actions (test_session_id, id)
      ON DELETE RESTRICT
)
    """)
    op.execute(
        "CREATE INDEX ix_correction_requests_session "
        "ON correction_requests (test_session_id, correction_status, requested_at)"
    )

    op.execute("""
CREATE TABLE session_approval_snapshots (
    test_session_id UUID NOT NULL,
    approval_action_id UUID NOT NULL,
    regulatory_revision INTEGER NOT NULL,
    snapshot_schema_version INTEGER DEFAULT '1' NOT NULL,
    snapshot_json JSONB NOT NULL,
    snapshot_hash VARCHAR(64) NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    captured_by UUID NOT NULL,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_session_approval_snapshot UNIQUE (test_session_id),
    CONSTRAINT uq_session_approval_action UNIQUE (approval_action_id),
    CONSTRAINT ck_session_approval_revision CHECK (
      regulatory_revision > 0
    ),
    CONSTRAINT ck_session_approval_schema CHECK (
      snapshot_schema_version = 1
    ),
    CONSTRAINT ck_session_approval_payload CHECK (
      jsonb_typeof(snapshot_json) = 'object'
    ),
    CONSTRAINT ck_session_approval_hash CHECK (
      snapshot_hash ~ '^[a-f0-9]{64}$'
    ),
    FOREIGN KEY(test_session_id)
      REFERENCES test_sessions (id) ON DELETE RESTRICT,
    FOREIGN KEY(captured_by)
      REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_session_approval_action_scope
      FOREIGN KEY(test_session_id, approval_action_id)
      REFERENCES approval_actions (test_session_id, id)
      ON DELETE RESTRICT
)
    """)

    install_guards()


def downgrade():
    op.execute(
        "DROP TRIGGER IF EXISTS phase15_correction_request_update_guard ON correction_requests"
    )
    op.execute("DROP FUNCTION IF EXISTS phase15_correction_update_guard()")

    for table in ("session_approval_snapshots", "approval_actions"):
        op.execute(f"DROP TRIGGER IF EXISTS phase15_{table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS phase15_deny_review_history_mutation()")

    for table in (
        "session_approval_snapshots",
        "correction_requests",
        "approval_actions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS phase15_validate_{table} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS phase15_validate_review_insert()")

    op.drop_table("session_approval_snapshots")
    op.drop_table("correction_requests")
    op.drop_table("approval_actions")
