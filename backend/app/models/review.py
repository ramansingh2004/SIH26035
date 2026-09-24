"""Phase 15 append-only review, scoped-correction and approval-snapshot models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable

APPROVAL_STAGES = ("TECHNICAL_REVIEW", "FINAL_APPROVAL")
APPROVAL_DECISIONS = (
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "RETURNED_FOR_CORRECTION",
    "INVALIDATED",
)
CORRECTION_TARGET_STATES = ("TESTING", "EXAMINATION")
CORRECTION_STATUSES = ("OPEN", "RESOLVED", "CANCELLED")


class ApprovalAction(Identity, Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        UniqueConstraint(
            "test_session_id",
            "id",
            name="uq_approval_action_session_scope",
        ),
        CheckConstraint(
            "stage IN ('TECHNICAL_REVIEW','FINAL_APPROVAL')",
            name="ck_approval_action_stage",
        ),
        CheckConstraint(
            "decision IN ("
            "'SUBMITTED','APPROVED','REJECTED',"
            "'RETURNED_FOR_CORRECTION','INVALIDATED'"
            ")",
            name="ck_approval_action_decision",
        ),
        CheckConstraint(
            "("
            "stage = 'TECHNICAL_REVIEW' "
            "AND decision IN ("
            "'SUBMITTED','APPROVED','REJECTED',"
            "'RETURNED_FOR_CORRECTION','INVALIDATED'"
            ")"
            ") OR ("
            "stage = 'FINAL_APPROVAL' "
            "AND decision IN ('APPROVED','REJECTED')"
            ")",
            name="ck_approval_action_stage_decision",
        ),
        CheckConstraint(
            "regulatory_revision > 0",
            name="ck_approval_action_revision",
        ),
        CheckConstraint(
            "jsonb_typeof(scope_json) = 'object'",
            name="ck_approval_action_scope",
        ),
        CheckConstraint(
            "decision <> 'INVALIDATED' OR referenced_action_id IS NOT NULL",
            name="ck_approval_action_reference",
        ),
        CheckConstraint(
            "decision NOT IN ('REJECTED','RETURNED_FOR_CORRECTION','INVALIDATED') "
            "OR (reason IS NOT NULL AND length(trim(reason)) > 0)",
            name="ck_approval_action_reason",
        ),
        ForeignKeyConstraint(
            ["test_session_id", "referenced_action_id"],
            ["approval_actions.test_session_id", "approval_actions.id"],
            name="fk_approval_action_reference_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_approval_actions_session",
            "test_session_id",
            "created_at",
            "id",
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"),
    )
    stage: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    regulatory_revision: Mapped[int]
    scope_json: Mapped[dict] = mapped_column(JSONB)
    referenced_action_id: Mapped[UUID | None]
    comment: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class CorrectionRequest(Identity, Mutable, Base):
    __tablename__ = "correction_requests"
    __table_args__ = (
        UniqueConstraint(
            "approval_action_id",
            name="uq_correction_action",
        ),
        CheckConstraint(
            "target_workflow_status IN ('TESTING','EXAMINATION')",
            name="ck_correction_target",
        ),
        CheckConstraint(
            "correction_status IN ('OPEN','RESOLVED','CANCELLED')",
            name="ck_correction_status",
        ),
        CheckConstraint(
            "jsonb_typeof(requested_scope_json) = 'object' "
            "AND requested_scope_json ? 'targets' "
            "AND jsonb_typeof(requested_scope_json -> 'targets') = 'array' "
            "AND jsonb_array_length(requested_scope_json -> 'targets') > 0",
            name="ck_correction_scope",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="ck_correction_reason",
        ),
        CheckConstraint(
            "("
            "correction_status = 'OPEN' AND resolved_at IS NULL"
            ") OR ("
            "correction_status IN ('RESOLVED','CANCELLED') "
            "AND resolved_at IS NOT NULL"
            ")",
            name="ck_correction_resolution",
        ),
        CheckConstraint(
            "lock_version > 0",
            name="ck_correction_version",
        ),
        ForeignKeyConstraint(
            ["test_session_id", "approval_action_id"],
            ["approval_actions.test_session_id", "approval_actions.id"],
            name="fk_correction_action_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_correction_requests_session",
            "test_session_id",
            "correction_status",
            "requested_at",
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"),
    )
    approval_action_id: Mapped[UUID]
    target_workflow_status: Mapped[str] = mapped_column(String(30))
    requested_scope_json: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    correction_status: Mapped[str] = mapped_column(
        String(20),
        default="OPEN",
        server_default="OPEN",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionApprovalSnapshot(Identity, Base):
    __tablename__ = "session_approval_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "test_session_id",
            name="uq_session_approval_snapshot",
        ),
        UniqueConstraint(
            "approval_action_id",
            name="uq_session_approval_action",
        ),
        CheckConstraint(
            "regulatory_revision > 0",
            name="ck_session_approval_revision",
        ),
        CheckConstraint(
            "snapshot_schema_version = 1",
            name="ck_session_approval_schema",
        ),
        CheckConstraint(
            "jsonb_typeof(snapshot_json) = 'object'",
            name="ck_session_approval_payload",
        ),
        CheckConstraint(
            "snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_session_approval_hash",
        ),
        ForeignKeyConstraint(
            ["test_session_id", "approval_action_id"],
            ["approval_actions.test_session_id", "approval_actions.id"],
            name="fk_session_approval_action_scope",
            ondelete="RESTRICT",
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"),
    )
    approval_action_id: Mapped[UUID]
    regulatory_revision: Mapped[int]
    snapshot_schema_version: Mapped[int] = mapped_column(
        default=1,
        server_default="1",
    )
    snapshot_json: Mapped[dict] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    captured_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
