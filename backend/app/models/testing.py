"""Phase 5 persistence; domain evaluation remains in app.compliance."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import Identity, Mutable

EVALUATIONS = "'NOT_STARTED','IN_PROGRESS','INCOMPLETE','STALE','REVIEW_REQUIRED','COMPLETE'"
OUTCOMES = "'UNDETERMINED','COMPLIANT','NONCOMPLIANT','NOT_APPLICABLE'"
APPLICABILITIES = "'REQUIRED','OPTIONAL','NOT_APPLICABLE','REQUIRES_REVIEW'"


def status_checks(prefix):
    return (
        CheckConstraint(f"evaluation_status IN ({EVALUATIONS})", name=f"ck_{prefix}_evaluation"),
        CheckConstraint(f"compliance_outcome IN ({OUTCOMES})", name=f"ck_{prefix}_outcome"),
    )


class Status:
    evaluation_status: Mapped[str] = mapped_column(
        String(30), default="NOT_STARTED", server_default="NOT_STARTED"
    )
    compliance_outcome: Mapped[str] = mapped_column(
        String(30), default="UNDETERMINED", server_default="UNDETERMINED"
    )


class TestSession(Identity, Mutable, Status, Base):
    __tablename__ = "test_sessions"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        *status_checks("session"),
        UniqueConstraint("root_session_id", "session_revision_no", name="uq_session_revision"),
        UniqueConstraint("id", "laboratory_id", "instrument_id", name="uq_session_lineage_scope"),
        ForeignKeyConstraint(
            ["root_session_id", "laboratory_id", "instrument_id"],
            ["test_sessions.id", "test_sessions.laboratory_id", "test_sessions.instrument_id"],
            name="fk_session_root_scope",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["parent_session_id", "laboratory_id", "instrument_id"],
            ["test_sessions.id", "test_sessions.laboratory_id", "test_sessions.instrument_id"],
            name="fk_session_parent_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "regulatory_revision > 0 AND lock_version > 0 AND session_revision_no > 0",
            name="ck_session_versions",
        ),
        CheckConstraint("snapshot_schema_version = 1", name="ck_session_snapshot_schema"),
        CheckConstraint(
            "(parent_session_id IS NULL AND root_session_id = id AND session_revision_no = 1) OR "
            "(parent_session_id IS NOT NULL AND parent_session_id <> id "
            "AND revision_reason IS NOT NULL AND length(trim(revision_reason)) > 0 "
            "AND session_revision_no > 1)",
            name="ck_session_lineage",
        ),
        CheckConstraint(
            "workflow_status IN ('DRAFT','INSTRUMENT_CONFIGURATION','APPLICABILITY_CONFIRMED',"
            "'TESTING','EXAMINATION','UNDER_REVIEW','APPROVED','REPORT_ISSUED','REJECTED','CANCELLED')",
            name="ck_session_workflow",
        ),
        Index("ix_session_lab_workflow", "laboratory_id", "workflow_status", "created_at"),
    )
    laboratory_id: Mapped[UUID] = mapped_column(ForeignKey("laboratories.id", ondelete="RESTRICT"))
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    rule_set_id: Mapped[UUID] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"))
    application_number: Mapped[str | None] = mapped_column(String(200))
    workflow_status: Mapped[str] = mapped_column(
        String(40), default="DRAFT", server_default="DRAFT"
    )
    evaluation_context: Mapped[str] = mapped_column(String(100))
    instrument_snapshot: Mapped[dict] = mapped_column(JSONB)
    ruleset_snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_schema_version: Mapped[int] = mapped_column(default=1, server_default="1")
    regulatory_revision: Mapped[int] = mapped_column(default=1, server_default="1")
    root_session_id: Mapped[UUID]
    parent_session_id: Mapped[UUID | None]
    session_revision_no: Mapped[int] = mapped_column(default=1, server_default="1")
    revision_reason: Mapped[str | None] = mapped_column(Text)
    started_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class TestSessionSection(Identity, Mutable, Status, Base):
    __tablename__ = "test_session_sections"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        *status_checks("section"),
        UniqueConstraint("test_session_id", "section_number", name="uq_session_section"),
        UniqueConstraint("test_session_id", "id", name="uq_section_scope"),
        CheckConstraint(
            "section_number BETWEEN 1 AND 17 AND lock_version > 0", name="ck_section_number_version"
        ),
        CheckConstraint(
            f"applicability_status IN ({APPLICABILITIES})", name="ck_section_applicability"
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"), index=True
    )
    section_number: Mapped[int]
    code: Mapped[str] = mapped_column("section_code", String(100))
    name: Mapped[str] = mapped_column("section_name", Text)
    applicability_status: Mapped[str] = mapped_column(String(30), default="REQUIRES_REVIEW")
    applicability_reason: Mapped[str] = mapped_column(Text)
    rule_references: Mapped[list] = mapped_column(JSONB, default=list)
    summary_schema_version: Mapped[int] = mapped_column(default=1, server_default="1")
    summary_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionTestRequirement(Identity, Mutable, Base):
    __tablename__ = "session_test_requirements"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("session_section_id", "requirement_key", name="uq_requirement_key"),
        UniqueConstraint(
            "test_session_id", "session_section_id", "id", name="uq_requirement_scope"
        ),
        ForeignKeyConstraint(
            ["test_session_id", "session_section_id"],
            ["test_session_sections.test_session_id", "test_session_sections.id"],
            name="fk_requirement_section",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["id", "selected_run_id"],
            ["test_runs.requirement_id", "test_runs.id"],
            name="fk_requirement_selection",
            ondelete="RESTRICT",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            f"applicability_status IN ({APPLICABILITIES}) AND lock_version > 0",
            name="ck_requirement_applicability",
        ),
        CheckConstraint(
            "NOT is_elected OR applicability_status = 'OPTIONAL'", name="ck_requirement_election"
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"), index=True
    )
    session_section_id: Mapped[UUID]
    test_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_definitions.id", ondelete="RESTRICT")
    )
    requirement_key: Mapped[str] = mapped_column(Text)
    applicability_status: Mapped[str] = mapped_column(String(30))
    applicability_reason: Mapped[str] = mapped_column(Text)
    rule_references: Mapped[list] = mapped_column(JSONB)
    slot_snapshot: Mapped[dict] = mapped_column(JSONB)
    is_elected: Mapped[bool] = mapped_column(default=False)
    selected_run_id: Mapped[UUID | None]


class TestRun(Identity, Mutable, Status, Base):
    __tablename__ = "test_runs"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        *status_checks("run"),
        UniqueConstraint("requirement_id", "run_no", name="uq_run_number"),
        UniqueConstraint("requirement_id", "id", name="uq_run_requirement"),
        UniqueConstraint("test_session_id", "id", name="uq_run_session"),
        ForeignKeyConstraint(
            ["test_session_id", "session_section_id", "requirement_id"],
            [
                "session_test_requirements.test_session_id",
                "session_test_requirements.session_section_id",
                "session_test_requirements.id",
            ],
            name="fk_run_requirement_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "retest_of_run_id"],
            ["test_runs.requirement_id", "test_runs.id"],
            name="fk_run_retest_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["id", "current_result_id", "input_revision"],
            [
                "test_run_results.test_run_id",
                "test_run_results.id",
                "test_run_results.source_input_revision",
            ],
            name="fk_run_current_result",
            ondelete="RESTRICT",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "run_no > 0 AND input_revision > 0 AND lock_version > 0", name="ck_run_versions"
        ),
        CheckConstraint(
            "(run_no = 1 AND retest_of_run_id IS NULL) OR (run_no > 1 "
            "AND retest_of_run_id IS NOT NULL AND retest_of_run_id <> id "
            "AND retest_reason IS NOT NULL AND length(trim(retest_reason)) > 0)",
            name="ck_run_retest",
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"), index=True
    )
    session_section_id: Mapped[UUID]
    requirement_id: Mapped[UUID]
    test_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_definitions.id", ondelete="RESTRICT")
    )
    run_no: Mapped[int]
    retest_of_run_id: Mapped[UUID | None]
    retest_reason: Mapped[str | None] = mapped_column(Text)
    observation_schema_version: Mapped[str] = mapped_column(String(40))
    procedure_schema_version: Mapped[str] = mapped_column(String(40))
    procedure_context: Mapped[dict] = mapped_column(JSONB)
    input_revision: Mapped[int] = mapped_column(default=1, server_default="1")
    current_result_id: Mapped[UUID | None]
    started_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestObservation(Identity, Mutable, Base):
    __tablename__ = "test_observations"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("test_run_id", "sequence_no", name="uq_observation_sequence"),
        CheckConstraint("sequence_no > 0 AND lock_version > 0", name="ck_observation_version"),
    )
    test_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="RESTRICT"), index=True
    )
    sequence_no: Mapped[int]
    observation_type: Mapped[str] = mapped_column(String(100))
    payload_schema_version: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column("payload_json", JSONB)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_locked: Mapped[bool] = mapped_column(default=False, server_default="false")


class EnvironmentReading(Identity, Mutable, Base):
    __tablename__ = "environment_readings"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        ForeignKeyConstraint(
            ["test_session_id", "test_run_id"],
            ["test_runs.test_session_id", "test_runs.id"],
            name="fk_environment_run_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "lock_version > 0 AND (relative_humidity_percent IS NULL "
            "OR relative_humidity_percent BETWEEN 0 AND 100) "
            "AND (barometric_pressure_hpa IS NULL OR barometric_pressure_hpa > 0)",
            name="ck_environment_values",
        ),
    )
    test_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="RESTRICT"), index=True
    )
    test_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="RESTRICT"), index=True
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric())
    relative_humidity_percent: Mapped[Decimal | None] = mapped_column(Numeric())
    barometric_pressure_hpa: Mapped[Decimal | None] = mapped_column(Numeric())
    phase: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class TestRunEquipment(Identity, Mutable, Base):
    __tablename__ = "test_run_equipment"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        UniqueConstraint("test_run_id", "equipment_id", name="uq_run_equipment"),
        CheckConstraint("lock_version > 0", name="ck_run_equipment_version"),
    )
    test_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="RESTRICT"), index=True
    )
    equipment_id: Mapped[UUID] = mapped_column(ForeignKey("test_equipment.id", ondelete="RESTRICT"))
    equipment_snapshot: Mapped[dict] = mapped_column(JSONB)
    calibration_attachment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("attachments.id", ondelete="RESTRICT")
    )
    linked_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestRunResult(Identity, Status, Base):
    __tablename__ = "test_run_results"
    __mapper_args__ = {"eager_defaults": True}
    __table_args__ = (
        *status_checks("result"),
        UniqueConstraint("test_run_id", "evaluation_version", name="uq_result_version"),
        UniqueConstraint(
            "test_run_id", "id", "source_input_revision", name="uq_result_current_scope"
        ),
        UniqueConstraint("test_run_id", "id", name="uq_result_run"),
        ForeignKeyConstraint(
            ["test_run_id", "supersedes_result_id"],
            ["test_run_results.test_run_id", "test_run_results.id"],
            name="fk_result_supersedes_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "evaluation_version > 0 AND source_input_revision > 0 AND hash_schema_version = 'v1'",
            name="ck_result_versions",
        ),
        CheckConstraint(
            "input_hash ~ '^[a-f0-9]{64}$' AND result_hash ~ '^[a-f0-9]{64}$'",
            name="ck_result_hashes",
        ),
    )
    test_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_runs.id", ondelete="RESTRICT"), index=True
    )
    rule_set_id: Mapped[UUID] = mapped_column(ForeignKey("rule_sets.id", ondelete="RESTRICT"))
    evaluation_version: Mapped[int]
    source_input_revision: Mapped[int]
    supersedes_result_id: Mapped[UUID | None]
    evaluation_input_snapshot: Mapped[dict] = mapped_column(JSONB)
    deterministic_result: Mapped[dict] = mapped_column(JSONB)
    applicability_status: Mapped[str] = mapped_column(String(30))
    applicability_reason: Mapped[str] = mapped_column(Text)
    calculations_json: Mapped[list] = mapped_column(JSONB)
    acceptance_limits_json: Mapped[list] = mapped_column(JSONB)
    failed_conditions_json: Mapped[list] = mapped_column(JSONB)
    rule_references_json: Mapped[list] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    issue_code: Mapped[str | None] = mapped_column(String(100))
    unresolved_rule_ids: Mapped[list] = mapped_column(JSONB)
    hash_schema_version: Mapped[str] = mapped_column(String(20))
    observation_schema_version: Mapped[str] = mapped_column(String(40))
    procedure_schema_version: Mapped[str] = mapped_column(String(40))
    engine_version: Mapped[str] = mapped_column(Text)
    ruleset_version: Mapped[str] = mapped_column(String(100))
    ruleset_configuration_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    result_hash: Mapped[str] = mapped_column(String(64))
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    initiated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class EvaluationResultEvent(Identity, Base):
    __tablename__ = "evaluation_result_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CURRENT','STALE','SUPERSEDED') AND regulatory_revision > 0",
            name="ck_result_event",
        ),
    )
    result_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_run_results.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(20))
    replacement_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("test_run_results.id", ondelete="RESTRICT")
    )
    regulatory_revision: Mapped[int]
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TestRunSelectionEvent(Identity, Base):
    __tablename__ = "test_run_selection_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id", "selected_run_id"],
            ["test_runs.requirement_id", "test_runs.id"],
            name="fk_selection_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "previous_run_id"],
            ["test_runs.requirement_id", "test_runs.id"],
            name="fk_selection_previous",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "regulatory_revision > 0 AND length(trim(reason)) > 0", name="ck_selection_reason"
        ),
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_test_requirements.id", ondelete="RESTRICT"), index=True
    )
    previous_run_id: Mapped[UUID | None]
    selected_run_id: Mapped[UUID]
    reason: Mapped[str] = mapped_column(Text)
    regulatory_revision: Mapped[int]
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
