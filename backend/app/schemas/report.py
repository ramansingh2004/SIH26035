"""Strict Phase 16 report, generation, issue and preview contracts."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from app.schemas.identity import Schema

Reason = Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
TemplateVersion = Annotated[
    str,
    Field(min_length=1, max_length=100, pattern=r"^\S(?:.*\S)?$"),
]
Hash64 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ReportGenerateRequest(Schema):
    intended_issuer_id: UUID
    planned_issue_date: date


class ReportRegenerateRequest(ReportGenerateRequest):
    pass


class ReportIssueRequest(Schema):
    generation_id: UUID
    expected_predecessor_id: UUID | None = None


class ReportRevisionRequest(ReportGenerateRequest):
    test_session_id: UUID
    revision_reason: Reason


class ReportView(Schema):
    id: UUID
    test_session_id: UUID
    report_number: str = Field(
        pattern=r"^R76-[0-9]{4}-[1-9][0-9]*$",
    )
    revision_no: int = Field(gt=0)
    root_report_id: UUID
    supersedes_report_id: UUID | None
    revision_reason: str | None
    report_status: Literal["UNISSUED", "ISSUED", "SUPERSEDED"]
    selected_generation_id: UUID | None
    issued_at: datetime | None
    issued_by: UUID | None
    issuance_manifest: dict[str, JsonValue] | None
    report_hash: Hash64 | None
    created_at: datetime
    created_by: UUID
    lock_version: int = Field(gt=0)

    @model_validator(mode="after")
    def issue_state(self):
        issued = self.report_status in {"ISSUED", "SUPERSEDED"}
        required = (
            self.selected_generation_id,
            self.issued_at,
            self.issued_by,
            self.issuance_manifest,
            self.report_hash,
        )
        if issued != all(value is not None for value in required):
            raise ValueError("Issued/superseded report requires complete issuance metadata")
        return self


class ReportGenerationView(Schema):
    id: UUID
    report_id: UUID
    attempt_no: int = Field(gt=0)
    generation_status: Literal["GENERATING", "READY", "FAILED"]
    report_context_snapshot: dict[str, JsonValue]
    context_schema_version: Literal[1]
    context_hash: Hash64
    source_regulatory_revision: int = Field(gt=0)
    intended_issuer_id: UUID
    planned_issue_date: date
    template_version: TemplateVersion
    renderer_manifest: dict[str, JsonValue]
    report_hash: Hash64 | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class ReportFileView(Schema):
    id: UUID
    report_generation_id: UUID
    format: Literal["PDF", "DOCX"]
    attachment_id: UUID
    file_hash: Hash64
    generated_at: datetime


class ReportPreviewView(Schema):
    id: UUID
    test_session_id: UUID
    source_regulatory_revision: int = Field(gt=0)
    preview_context_snapshot: dict[str, JsonValue]
    preview_status: Literal["GENERATING", "READY", "FAILED"]
    requested_by: UUID
    requested_at: datetime
    expires_at: datetime
    context_hash: Hash64
    file_attachment_ids: dict[str, JsonValue]
    error_code: str | None


class ReportGenerationResponse(Schema):
    report: ReportView
    generation: ReportGenerationView
    files: list[ReportFileView]
