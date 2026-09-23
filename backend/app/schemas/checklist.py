"""Strict Phase 13 checklist contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.schemas.identity import Schema

ChecklistGroup = Literal[
    "GENERAL",
    "DIRECT_SALES",
    "ELECTRONIC",
    "SOFTWARE_CONTROLLED",
]
ChecklistApplicability = Literal[
    "REQUIRED",
    "NOT_APPLICABLE",
    "REQUIRES_REVIEW",
]
ChecklistResult = Literal[
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "NOT_EXAMINED",
]


class ChecklistResponsePatch(Schema):
    response_result: ChecklistResult | None = None
    remarks: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def changed_field_supplied(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one changed checklist field")
        return self


class ChecklistResponseView(Schema):
    id: UUID
    test_session_id: UUID
    checklist_rule_id: UUID
    applicability_status: ChecklistApplicability
    applicability_reason: str
    response_result: ChecklistResult
    remarks: str | None
    examined_by: UUID | None
    examined_at: datetime | None
    lock_version: int
    created_at: datetime
    updated_at: datetime


class ChecklistRowView(ChecklistResponseView):
    group_code: ChecklistGroup
    requirement_key: str
    clause_reference: str | None
    display_text: str
    evidence_required: bool | None
    validation_status: Literal[
        "TODO_REGULATORY_VALIDATION",
        "VERIFIED",
    ]
    sort_order: int = Field(ge=0)


class ChecklistSummary(Schema):
    schema_version: Literal[1] = 1
    lock_version: int = Field(gt=0)
    catalog_total: int = Field(ge=0)
    applicable: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    not_examined: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    review_required: int = Field(ge=0)
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    missing_rule_keys: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
