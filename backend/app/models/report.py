"""Phase 16 report persistence and immutable generation contracts."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity

REPORT_STATUSES = ("UNISSUED", "ISSUED", "SUPERSEDED")
GENERATION_STATUSES = ("GENERATING", "READY", "FAILED")
REPORT_FORMATS = ("PDF", "DOCX")
PREVIEW_STATUSES = ("GENERATING", "READY", "FAILED")


class ReportNumberCounter(Base):
    __tablename__ = "report_number_counters"
    __table_args__ = (
        CheckConstraint(
            "year BETWEEN 2000 AND 9999 AND next_sequence > 0 AND lock_version > 0",
            name="ck_report_counter_values",
        ),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )
    lock_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )


class Report(Identity, Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "test_session_id",
            name="uq_report_session",
        ),
        UniqueConstraint(
            "report_number",
            "revision_no",
            name="uq_report_number_revision",
        ),
        UniqueConstraint(
            "id",
            "report_number",
            name="uq_report_number_scope",
        ),
        CheckConstraint(
            "report_number ~ '^R76-[0-9]{4}-[1-9][0-9]*$'",
            name="ck_report_number_format",
        ),
        CheckConstraint(
            "revision_no > 0 AND lock_version > 0",
            name="ck_report_versions",
        ),
        CheckConstraint(
            "report_status IN ('UNISSUED','ISSUED','SUPERSEDED')",
            name="ck_report_status",
        ),
        CheckConstraint(
            "("
            "revision_no = 1 "
            "AND root_report_id = id "
            "AND supersedes_report_id IS NULL "
            "AND revision_reason IS NULL"
            ") OR ("
            "revision_no > 1 "
            "AND root_report_id <> id "
            "AND supersedes_report_id IS NOT NULL "
            "AND revision_reason IS NOT NULL "
            "AND length(trim(revision_reason)) > 0"
            ")",
            name="ck_report_lineage",
        ),
        CheckConstraint(
            "("
            "report_status = 'UNISSUED' "
            "AND issued_at IS NULL "
            "AND issued_by IS NULL "
            "AND issuance_manifest IS NULL"
            ") OR ("
            "report_status IN ('ISSUED','SUPERSEDED') "
            "AND selected_generation_id IS NOT NULL "
            "AND issued_at IS NOT NULL "
            "AND issued_by IS NOT NULL "
            "AND issuance_manifest IS NOT NULL "
            "AND jsonb_typeof(issuance_manifest) = 'object' "
            "AND report_hash IS NOT NULL"
            ")",
            name="ck_report_issue_state",
        ),
        CheckConstraint(
            "report_hash IS NULL OR report_hash ~ '^[a-f0-9]{64}$'",
            name="ck_report_hash",
        ),
        ForeignKeyConstraint(
            ["root_report_id", "report_number"],
            ["reports.id", "reports.report_number"],
            name="fk_report_root_number",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["supersedes_report_id", "report_number"],
            ["reports.id", "reports.report_number"],
            name="fk_report_predecessor_number",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["id", "selected_generation_id"],
            ["report_generations.report_id", "report_generations.id"],
            name="fk_report_selected_generation",
            ondelete="RESTRICT",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        Index(
            "ix_reports_number_revision",
            "report_number",
            "revision_no",
        ),
        Index(
            "uq_report_current_issued",
            "report_number",
            unique=True,
            postgresql_where=text("report_status = 'ISSUED'"),
        ),
    )

    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT")
    )
    report_number: Mapped[str] = mapped_column(String(80))
    revision_no: Mapped[int] = mapped_column(Integer)
    root_report_id: Mapped[UUID]
    supersedes_report_id: Mapped[UUID | None]
    revision_reason: Mapped[str | None] = mapped_column(Text)
    report_status: Mapped[str] = mapped_column(
        String(20),
        default="UNISSUED",
        server_default="UNISSUED",
    )
    selected_generation_id: Mapped[UUID | None]
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issuance_manifest: Mapped[dict | None] = mapped_column(JSONB)
    report_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    lock_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )


class ReportGeneration(Identity, Base):
    __tablename__ = "report_generations"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "attempt_no",
            name="uq_report_generation_attempt",
        ),
        UniqueConstraint(
            "report_id",
            "id",
            name="uq_report_generation_scope",
        ),
        CheckConstraint(
            "attempt_no > 0 AND source_regulatory_revision > 0",
            name="ck_report_generation_versions",
        ),
        CheckConstraint(
            "generation_status IN ('GENERATING','READY','FAILED')",
            name="ck_report_generation_status",
        ),
        CheckConstraint(
            "context_schema_version = 1 AND jsonb_typeof(report_context_snapshot) = 'object'",
            name="ck_report_generation_context",
        ),
        CheckConstraint(
            "context_hash ~ '^[a-f0-9]{64}$'",
            name="ck_report_generation_context_hash",
        ),
        CheckConstraint(
            "jsonb_typeof(renderer_manifest) = 'object'",
            name="ck_report_generation_renderer_manifest",
        ),
        CheckConstraint(
            "report_hash IS NULL OR report_hash ~ '^[a-f0-9]{64}$'",
            name="ck_report_generation_report_hash",
        ),
        CheckConstraint(
            "("
            "generation_status = 'GENERATING' "
            "AND completed_at IS NULL "
            "AND report_hash IS NULL "
            "AND error_code IS NULL"
            ") OR ("
            "generation_status = 'READY' "
            "AND completed_at IS NOT NULL "
            "AND report_hash IS NOT NULL "
            "AND error_code IS NULL"
            ") OR ("
            "generation_status = 'FAILED' "
            "AND completed_at IS NOT NULL "
            "AND report_hash IS NULL "
            "AND error_code IS NOT NULL "
            "AND length(trim(error_code)) > 0"
            ")",
            name="ck_report_generation_completion",
        ),
        Index(
            "ix_report_generations_report_attempt",
            "report_id",
            "attempt_no",
        ),
    )

    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id", ondelete="RESTRICT"))
    attempt_no: Mapped[int] = mapped_column(Integer)
    generation_status: Mapped[str] = mapped_column(
        String(20),
        default="GENERATING",
        server_default="GENERATING",
    )
    report_context_snapshot: Mapped[dict] = mapped_column(JSONB)
    context_schema_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )
    context_hash: Mapped[str] = mapped_column(String(64))
    source_regulatory_revision: Mapped[int] = mapped_column(Integer)
    intended_issuer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    planned_issue_date: Mapped[date] = mapped_column(Date)
    template_version: Mapped[str] = mapped_column(String(100))
    renderer_manifest: Mapped[dict] = mapped_column(JSONB)
    report_hash: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportFile(Identity, Base):
    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint(
            "report_generation_id",
            "format",
            name="uq_report_file_format",
        ),
        CheckConstraint(
            "format IN ('PDF','DOCX')",
            name="ck_report_file_format",
        ),
        CheckConstraint(
            "file_hash ~ '^[a-f0-9]{64}$'",
            name="ck_report_file_hash",
        ),
        Index(
            "ix_report_files_generation",
            "report_generation_id",
            "format",
        ),
    )

    report_generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_generations.id", ondelete="RESTRICT")
    )
    format: Mapped[str] = mapped_column(String(10))
    attachment_id: Mapped[UUID] = mapped_column(ForeignKey("attachments.id", ondelete="RESTRICT"))
    file_hash: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ReportPreview(Identity, Base):
    __tablename__ = "report_previews"
    __table_args__ = (
        CheckConstraint(
            "source_regulatory_revision > 0",
            name="ck_report_preview_revision",
        ),
        CheckConstraint(
            "preview_status IN ('GENERATING','READY','FAILED')",
            name="ck_report_preview_status",
        ),
        CheckConstraint(
            "jsonb_typeof(preview_context_snapshot) = 'object'",
            name="ck_report_preview_context",
        ),
        CheckConstraint(
            "context_hash ~ '^[a-f0-9]{64}$'",
            name="ck_report_preview_context_hash",
        ),
        CheckConstraint(
            "jsonb_typeof(file_attachment_ids) = 'object'",
            name="ck_report_preview_files",
        ),
        CheckConstraint(
            "expires_at > requested_at",
            name="ck_report_preview_expiry",
        ),
        CheckConstraint(
            "("
            "preview_status = 'GENERATING' "
            "AND file_attachment_ids = '{}'::jsonb "
            "AND error_code IS NULL"
            ") OR ("
            "preview_status = 'READY' "
            "AND file_attachment_ids ? 'pdf' "
            "AND file_attachment_ids ? 'docx' "
            "AND jsonb_typeof(file_attachment_ids -> 'pdf') = 'string' "
            "AND jsonb_typeof(file_attachment_ids -> 'docx') = 'string' "
            "AND error_code IS NULL"
            ") OR ("
            "preview_status = 'FAILED' "
            "AND error_code IS NOT NULL "
            "AND length(trim(error_code)) > 0"
            ")",
            name="ck_report_preview_completion",
        ),
        Index(
            "ix_report_previews_session_requested",
            "test_session_id",
            "requested_at",
        ),
    )

    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT")
    )
    source_regulatory_revision: Mapped[int] = mapped_column(Integer)
    preview_context_snapshot: Mapped[dict] = mapped_column(JSONB)
    preview_status: Mapped[str] = mapped_column(
        String(20),
        default="GENERATING",
        server_default="GENERATING",
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context_hash: Mapped[str] = mapped_column(String(64))
    file_attachment_ids: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
