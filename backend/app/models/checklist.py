"""Phase 13 checklist response persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable

CHECKLIST_APPLICABILITIES = (
    "REQUIRED",
    "NOT_APPLICABLE",
    "REQUIRES_REVIEW",
)
CHECKLIST_RESULTS = (
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "NOT_EXAMINED",
)


class ChecklistResponse(Identity, Mutable, Base):
    __tablename__ = "checklist_responses"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint(
            "test_session_id",
            "checklist_rule_id",
            name="uq_checklist_response_rule",
        ),
        CheckConstraint(
            "applicability_status IN ('REQUIRED','NOT_APPLICABLE','REQUIRES_REVIEW')",
            name="ck_checklist_response_applicability",
        ),
        CheckConstraint(
            "response_result IN ('PASS','FAIL','NOT_APPLICABLE','NOT_EXAMINED')",
            name="ck_checklist_response_result",
        ),
        CheckConstraint(
            "("
            "response_result = 'NOT_EXAMINED' "
            "AND examined_by IS NULL AND examined_at IS NULL"
            ") OR ("
            "applicability_status = 'NOT_APPLICABLE' "
            "AND response_result = 'NOT_APPLICABLE' "
            "AND examined_by IS NULL AND examined_at IS NULL"
            ") OR ("
            "response_result IN ('PASS','FAIL','NOT_APPLICABLE') "
            "AND examined_by IS NOT NULL AND examined_at IS NOT NULL"
            ")",
            name="ck_checklist_response_examiner",
        ),
        CheckConstraint(
            "applicability_status <> 'NOT_APPLICABLE' OR response_result = 'NOT_APPLICABLE'",
            name="ck_checklist_response_excluded_result",
        ),
        CheckConstraint(
            "lock_version > 0",
            name="ck_checklist_response_version",
        ),
        Index(
            "ix_checklist_responses_session",
            "test_session_id",
            "id",
        ),
    )

    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"),
        index=True,
    )
    checklist_rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("checklist_rules.id", ondelete="RESTRICT"),
        index=True,
    )
    applicability_status: Mapped[str] = mapped_column(String(30))
    applicability_reason: Mapped[str] = mapped_column(Text)
    response_result: Mapped[str] = mapped_column(
        String(30),
        default="NOT_EXAMINED",
        server_default="NOT_EXAMINED",
    )
    remarks: Mapped[str | None] = mapped_column(Text)
    examined_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    examined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
