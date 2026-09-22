"""Strict Phase 5 HTTP contracts. Metrological values are decimal strings."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue, StrictBool

from app.compliance.domain import (
    Applicability,
    ComplianceOutcome,
    EvaluationStatus,
    InstrumentSnapshot,
    Number,
    WorkflowStatus,
)
from app.compliance.planning import RequirementPlan
from app.compliance.weighing import MeasurementTime, WeighingContext, WeighingObservation
from app.schemas.identity import Schema

Reason = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]


class SessionCreate(Schema):
    instrument_id: UUID
    rule_set_id: UUID
    evaluation_context: Annotated[str, Field(min_length=1, max_length=100)]
    application_number: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=4000)


class SessionPatch(Schema):
    application_number: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=4000)


class Configure(Schema):
    instrument_snapshot: InstrumentSnapshot


class Confirmation(Schema):
    # An explicit true/false entry for EVERY optional semantic slot.
    elections: dict[str, StrictBool]


class ReasonRequest(Schema):
    reason: Reason


class SelectRun(ReasonRequest):
    run_id: UUID


class ObservationData(Schema):
    sequence_no: int = Field(gt=0, strict=True)
    observation_type: Literal["WEIGHING_PERFORMANCE"]
    payload_schema_version: Literal["v1"]
    payload: WeighingObservation


class EnvironmentData(Schema):
    measured_at: MeasurementTime
    temperature_c: Number | None = None
    relative_humidity_percent: Number | None = Field(None, ge=0, le=100)
    barometric_pressure_hpa: Number | None = Field(None, gt=0)
    phase: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class EquipmentLink(Schema):
    equipment_id: UUID
    calibration_attachment_id: UUID | None = None


class Version(Schema):
    id: UUID
    lock_version: int
    created_at: datetime
    updated_at: datetime


class SessionView(Version):
    laboratory_id: UUID
    instrument_id: UUID
    rule_set_id: UUID
    application_number: str | None
    evaluation_context: str
    notes: str | None
    workflow_status: WorkflowStatus
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    instrument_snapshot: InstrumentSnapshot
    ruleset_snapshot: dict[str, JsonValue]
    snapshot_schema_version: Literal[1]
    regulatory_revision: int
    root_session_id: UUID
    parent_session_id: UUID | None
    session_revision_no: int
    revision_reason: str | None
    started_by: UUID
    started_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None


class SectionView(Version):
    test_session_id: UUID
    section_number: int
    code: str
    name: str
    applicability_status: Applicability
    applicability_reason: str
    rule_references: list[dict[str, JsonValue]]
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    summary_schema_version: int
    summary_json: dict[str, JsonValue]
    started_at: datetime | None
    completed_at: datetime | None


class RequirementView(Version):
    test_session_id: UUID
    session_section_id: UUID
    test_definition_id: UUID
    requirement_key: str
    applicability_status: Applicability
    applicability_reason: str
    rule_references: list[dict[str, JsonValue]]
    slot_snapshot: dict[str, JsonValue]
    is_elected: bool
    selected_run_id: UUID | None


class RunView(Version):
    test_session_id: UUID
    session_section_id: UUID
    requirement_id: UUID
    test_definition_id: UUID
    run_no: int
    retest_of_run_id: UUID | None
    retest_reason: str | None
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    observation_schema_version: str
    procedure_schema_version: str
    procedure_context: dict[str, JsonValue]
    input_revision: int
    current_result_id: UUID | None
    started_by: UUID | None
    started_at: datetime | None
    completed_at: datetime | None


class ObservationView(Version, ObservationData):
    test_run_id: UUID
    recorded_by: UUID
    recorded_at: datetime
    is_locked: bool


class EnvironmentView(Version, EnvironmentData):
    test_session_id: UUID
    test_run_id: UUID
    recorded_by: UUID


class EquipmentLinkView(Version):
    test_run_id: UUID
    equipment_id: UUID
    equipment_snapshot: dict[str, JsonValue]
    calibration_attachment_id: UUID | None
    linked_by: UUID
    linked_at: datetime


class ResultView(Schema):
    id: UUID
    test_run_id: UUID
    rule_set_id: UUID
    evaluation_version: int
    source_input_revision: int
    supersedes_result_id: UUID | None
    evaluation_input_snapshot: dict[str, JsonValue]
    deterministic_result: dict[str, JsonValue]
    applicability_status: Applicability
    applicability_reason: str
    calculations_json: list[dict[str, JsonValue]]
    acceptance_limits_json: list[dict[str, JsonValue]]
    failed_conditions_json: list[dict[str, JsonValue]]
    rule_references_json: list[dict[str, JsonValue]]
    reason: str
    issue_code: str | None
    unresolved_rule_ids: list[str]
    hash_schema_version: Literal["v1"]
    observation_schema_version: str
    procedure_schema_version: str
    engine_version: str
    ruleset_version: str
    ruleset_configuration_hash: str
    input_hash: str
    result_hash: str
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    evaluated_at: datetime
    initiated_by: UUID


class Dashboard(Schema):
    session: SessionView
    sections: list[SectionView]
    requirements: list[RequirementView]


class ApplicabilityView(Schema):
    session_id: UUID
    regulatory_revision: int
    plan: RequirementPlan
    confirmable: bool


class ProcedureUpdate(Schema):
    procedure_context: WeighingContext


class ResultEventView(Schema):
    id: UUID
    result_id: UUID
    event_type: Literal["CURRENT", "STALE", "SUPERSEDED"]
    replacement_result_id: UUID | None
    regulatory_revision: int
    actor_id: UUID
    reason: str
    created_at: datetime


class SelectionEventView(Schema):
    id: UUID
    requirement_id: UUID
    previous_run_id: UUID | None
    selected_run_id: UUID
    reason: str
    regulatory_revision: int
    actor_id: UUID
    created_at: datetime


class RunHistory(Schema):
    results: list[ResultView]
    events: list[ResultEventView]
    selections: list[SelectionEventView]


class EquipmentCertificate(Schema):
    calibration_attachment_id: UUID | None = None
