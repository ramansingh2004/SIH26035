"""Phase 17 read-only repository/search projections."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.compliance.domain import (
    ComplianceOutcome,
    EvaluationStatus,
    WorkflowStatus,
)
from app.schemas.identity import Schema


class ReportRepositoryItem(Schema):
    id: UUID
    test_session_id: UUID
    laboratory_id: UUID
    instrument_id: UUID
    manufacturer_id: UUID
    manufacturer_name: str
    instrument_model_name: str
    instrument_serial_number: str | None
    application_number: str | None

    workflow_status: WorkflowStatus
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome

    report_number: str
    revision_no: int
    root_report_id: UUID
    supersedes_report_id: UUID | None
    revision_reason: str | None
    report_status: Literal["UNISSUED", "ISSUED", "SUPERSEDED"]
    issued_at: datetime | None
    report_hash: str | None
    created_at: datetime

    is_current_issued: bool
    is_superseded: bool


class InstrumentHistoryItem(Schema):
    session_id: UUID
    root_session_id: UUID
    parent_session_id: UUID | None
    session_revision_no: int
    revision_reason: str | None
    application_number: str | None

    workflow_status: WorkflowStatus
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    regulatory_revision: int
    session_created_at: datetime

    run_count: int
    retest_count: int

    report_id: UUID | None
    report_number: str | None
    report_revision_no: int | None
    report_status: Literal["UNISSUED", "ISSUED", "SUPERSEDED"] | None
    supersedes_report_id: UUID | None
    report_issued_at: datetime | None
