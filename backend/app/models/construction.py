"""Phase 12 construction-examination persistence.

Section 16 is a non-numeric technical examination. Regulatory requirement
content remains versioned RuleDefinition data; these tables only persist the
session dossier and its snapshotted item state.
"""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable
from app.models.testing import Status, status_checks

CONSTRUCTION_CATEGORIES = (
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
)


class ConstructionExamination(Identity, Mutable, Status, Base):
    __tablename__ = "construction_examinations"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        *status_checks("construction_examination"),
        UniqueConstraint("test_session_id", name="uq_construction_session"),
        CheckConstraint("lock_version > 0", name="ck_construction_exam_version"),
        CheckConstraint(
            "(examined_by IS NULL AND examined_at IS NULL) OR "
            "(examined_by IS NOT NULL AND examined_at IS NOT NULL)",
            name="ck_construction_examiner_pair",
        ),
    )

    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"),
        index=True,
    )
    overall_notes: Mapped[str | None] = mapped_column(Text)
    examined_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    examined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class ConstructionItem(Identity, Mutable, Base):
    __tablename__ = "construction_items"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint(
            "construction_examination_id",
            "item_key",
            name="uq_construction_item_key",
        ),
        CheckConstraint(
            "category IN ("
            "'GENERAL','RECEPTOR_LOAD_CELLS','INDICATOR_DISPLAY',"
            "'PRINTER_PERIPHERALS','POWER_INTERFACES','TILT_ZERO_TARE',"
            "'SEALS_SECURITY_SOFTWARE','DOCUMENTS_PHOTOS')",
            name="ck_construction_item_category",
        ),
        CheckConstraint(
            "examination_state IN ('NOT_EXAMINED','EXAMINED','REVIEW_REQUIRED')",
            name="ck_construction_item_state",
        ),
        CheckConstraint(
            "conformance_result IN ('PASS','FAIL','NOT_APPLICABLE','UNDETERMINED')",
            name="ck_construction_item_conformance",
        ),
        CheckConstraint(
            "(examination_state = 'NOT_EXAMINED' "
            "AND conformance_result = 'UNDETERMINED') OR "
            "(examination_state = 'REVIEW_REQUIRED' "
            "AND conformance_result = 'UNDETERMINED') OR "
            "(examination_state = 'EXAMINED' "
            "AND conformance_result IN ('PASS','FAIL','NOT_APPLICABLE'))",
            name="ck_construction_item_state_result",
        ),
        CheckConstraint(
            "value_schema_version = 1 AND lock_version > 0 "
            "AND sort_order >= 0 AND length(trim(item_key)) > 0",
            name="ck_construction_item_metadata",
        ),
        Index(
            "ix_construction_items_examination",
            "construction_examination_id",
            "sort_order",
            "id",
        ),
    )

    construction_examination_id: Mapped[UUID] = mapped_column(
        ForeignKey("construction_examinations.id", ondelete="RESTRICT")
    )
    requirement_rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("rule_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(60))
    item_key: Mapped[str] = mapped_column(String(100))
    description_snapshot: Mapped[str] = mapped_column(Text)
    value_schema_version: Mapped[int] = mapped_column(
        default=1,
        server_default="1",
    )
    value_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    examination_state: Mapped[str] = mapped_column(
        String(30),
        default="NOT_EXAMINED",
        server_default="NOT_EXAMINED",
    )
    conformance_result: Mapped[str] = mapped_column(
        String(30),
        default="UNDETERMINED",
        server_default="UNDETERMINED",
    )
    remarks: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int]
