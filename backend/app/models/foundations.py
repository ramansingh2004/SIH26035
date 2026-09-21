"""Phase 3 persistence. No sessions, observations or compliance results."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable
from app.models.master_data import Attributed


class RuleSetRecord(Identity, Mutable, Base):
    __tablename__ = "rule_sets"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("standard_code", "edition", "version", name="uq_ruleset_version"),
        CheckConstraint("ruleset_status IN ('DRAFT','ACTIVE','RETIRED')", name="ck_ruleset_status"),
        CheckConstraint("lock_version > 0", name="ck_ruleset_version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_ruleset_dates",
        ),
        Index(
            "uq_ruleset_active",
            "standard_code",
            "edition",
            unique=True,
            postgresql_where=text("ruleset_status = 'ACTIVE'"),
        ),
    )
    standard_code: Mapped[str] = mapped_column(String(50))
    standard_name: Mapped[str] = mapped_column(Text)
    standard_parts: Mapped[list] = mapped_column(JSONB)
    edition: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    ruleset_status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB)
    supported_test_codes: Mapped[list] = mapped_column(JSONB)
    source_reference: Mapped[str] = mapped_column(Text)
    validation_summary: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Provenance:
    validation_status: Mapped[str] = mapped_column(String(40), default="TODO_REGULATORY_VALIDATION")
    source_identity: Mapped[dict] = mapped_column(JSONB)
    source_digest: Mapped[str | None] = mapped_column(String(64))
    verified_by: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_evidence: Mapped[str | None] = mapped_column(Text)


class RuleDefinition(Identity, Provenance, Base):
    __tablename__ = "rule_definitions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "rule_key", name="uq_rule_key"),
        CheckConstraint(
            "validation_status IN ('TODO_REGULATORY_VALIDATION','VERIFIED')",
            name="ck_rule_validation",
        ),
        CheckConstraint(
            "section_no IS NULL OR section_no BETWEEN 1 AND 17", name="ck_rule_section"
        ),
    )
    rule_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), index=True
    )
    rule_key: Mapped[str] = mapped_column(String(100))
    section_no: Mapped[int | None]
    clause_reference: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(100))
    configuration: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text)


class TestDefinitionRecord(Identity, Provenance, Base):
    __tablename__ = "test_definitions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "code", name="uq_test_code"),
        UniqueConstraint("rule_set_id", "id", name="uq_test_parent_scope"),
        ForeignKeyConstraint(
            ["rule_set_id", "parent_definition_id"],
            ["test_definitions.rule_set_id", "test_definitions.id"],
            ondelete="RESTRICT",
            name="fk_test_parent_scope",
        ),
        CheckConstraint("section_number BETWEEN 1 AND 17", name="ck_test_section"),
        CheckConstraint(
            "parent_definition_id IS NULL OR parent_definition_id <> id", name="ck_test_parent"
        ),
        CheckConstraint(
            "validation_status IN ('TODO_REGULATORY_VALIDATION','VERIFIED')",
            name="ck_test_validation",
        ),
    )
    rule_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    section_number: Mapped[int]
    parent_definition_id: Mapped[UUID | None]
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    subtest_family: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int]
    supports_numeric_evaluation: Mapped[bool] = mapped_column(Boolean)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean)
    supported: Mapped[bool] = mapped_column(Boolean)
    implemented: Mapped[bool] = mapped_column(Boolean)
    applicability_metadata: Mapped[dict] = mapped_column(JSONB)
    default_observation_schema_version: Mapped[str | None] = mapped_column(String(40))
    default_procedure_schema_version: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)


class ChecklistRule(Identity, Provenance, Base):
    __tablename__ = "checklist_rules"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "requirement_key", name="uq_checklist_key"),
        CheckConstraint(
            "group_code IN ('GENERAL','DIRECT_SALES','ELECTRONIC','SOFTWARE_CONTROLLED')",
            name="ck_checklist_group",
        ),
        CheckConstraint(
            "validation_status IN ('TODO_REGULATORY_VALIDATION','VERIFIED')",
            name="ck_checklist_validation",
        ),
    )
    rule_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), index=True
    )
    group_code: Mapped[str] = mapped_column(String(40))
    requirement_key: Mapped[str] = mapped_column(String(100))
    clause_reference: Mapped[str | None] = mapped_column(Text)
    display_text: Mapped[str] = mapped_column(Text)
    applicability_expression: Mapped[dict] = mapped_column(JSONB)
    evidence_required: Mapped[bool | None] = mapped_column(Boolean)
    sort_order: Mapped[int]


class TestEquipment(Identity, Mutable, Attributed, Base):
    __tablename__ = "test_equipment"
    __table_args__ = (
        CheckConstraint("lock_version > 0", name="ck_equipment_version"),
        CheckConstraint("metadata_schema_version = 1", name="ck_equipment_schema"),
        CheckConstraint(
            "calibration_due_date IS NULL OR calibration_date IS NULL "
            "OR calibration_due_date >= calibration_date",
            name="ck_equipment_dates",
        ),
    )
    laboratory_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    category: Mapped[str] = mapped_column(String(200))
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    serial_number: Mapped[str | None] = mapped_column(String(200))
    reference_number: Mapped[str | None] = mapped_column(String(200))
    calibration_certificate_no: Mapped[str | None] = mapped_column(String(200))
    calibration_date: Mapped[date | None] = mapped_column(Date)
    calibration_due_date: Mapped[date | None] = mapped_column(Date)
    accuracy_or_class: Mapped[str | None] = mapped_column(String(200))
    metadata_schema_version: Mapped[int] = mapped_column(default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Attachment(Identity, Mutable, Base):
    __tablename__ = "attachments"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint(
            "storage_provider", "storage_key", "object_version", name="uq_attachment_object"
        ),
        UniqueConstraint("laboratory_id", "id", name="uq_attachment_lab"),
        CheckConstraint("file_size > 0 AND lock_version > 0", name="ck_attachment_size_version"),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_attachment_hash"),
        CheckConstraint("metadata_schema_version = 1", name="ck_attachment_schema"),
    )
    laboratory_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    attachment_type: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int]
    storage_provider: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(Text)
    object_version: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    metadata_schema_version: Mapped[int] = mapped_column(default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column(JSONB)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttachmentUpload(Identity, Mutable, Base):
    __tablename__ = "attachment_uploads"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint(
            "upload_status IN ('PENDING','COMPLETED','EXPIRED','FAILED')", name="ck_upload_status"
        ),
        CheckConstraint("expected_size > 0 AND lock_version > 0", name="ck_upload_size_version"),
        CheckConstraint("expected_sha256 ~ '^[a-f0-9]{64}$'", name="ck_upload_hash"),
        CheckConstraint(
            "(upload_status = 'COMPLETED') = (completed_attachment_id IS NOT NULL)",
            name="ck_upload_completion",
        ),
        ForeignKeyConstraint(
            ["laboratory_id", "completed_attachment_id"],
            ["attachments.laboratory_id", "attachments.id"],
            ondelete="RESTRICT",
            name="fk_upload_attachment_lab",
        ),
        Index("ix_upload_expiry", "upload_status", "expires_at"),
    )
    laboratory_id: Mapped[UUID] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), index=True
    )
    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[UUID]
    purpose: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    expected_file_name: Mapped[str] = mapped_column(String(200))
    expected_content_type: Mapped[str] = mapped_column(String(100))
    expected_size: Mapped[int]
    expected_sha256: Mapped[str] = mapped_column(String(64))
    upload_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", server_default="PENDING"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_attachment_id: Mapped[UUID | None]


class AttachmentLink(Identity, Mutable, Base):
    __tablename__ = "attachment_links"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint(
            "attachment_id", "entity_type", "entity_id", "purpose", name="uq_attachment_link"
        ),
        CheckConstraint(
            "lock_version > 0 AND length(purpose) > 0 AND purpose = lower(trim(purpose))",
            name="ck_link_purpose_version",
        ),
        Index("ix_attachment_target", "entity_type", "entity_id"),
    )
    attachment_id: Mapped[UUID] = mapped_column(
        ForeignKey("attachments.id", ondelete="RESTRICT"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID]
    purpose: Mapped[str] = mapped_column(String(100))
    linked_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
