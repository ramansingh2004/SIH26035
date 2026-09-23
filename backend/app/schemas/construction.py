"""Strict Phase 12 construction-examination HTTP/domain contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from app.compliance.domain import ComplianceOutcome, EvaluationStatus
from app.schemas.identity import Schema

ConstructionCategory = Literal[
    "GENERAL",
    "RECEPTOR_LOAD_CELLS",
    "INDICATOR_DISPLAY",
    "PRINTER_PERIPHERALS",
    "POWER_INTERFACES",
    "TILT_ZERO_TARE",
    "SEALS_SECURITY_SOFTWARE",
    "DOCUMENTS_PHOTOS",
]
ExaminationState = Literal[
    "NOT_EXAMINED",
    "EXAMINED",
    "REVIEW_REQUIRED",
]
ConformanceResult = Literal[
    "PASS",
    "FAIL",
    "NOT_APPLICABLE",
    "UNDETERMINED",
]


class ConstructionAssessment(Schema):
    """Complete merged item state used before persistence."""

    value_schema_version: Literal[1] = 1
    value_json: dict[str, JsonValue] = Field(default_factory=dict)
    examination_state: ExaminationState
    conformance_result: ConformanceResult
    remarks: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def state_matches_conformance(self):
        if self.examination_state in {
            "NOT_EXAMINED",
            "REVIEW_REQUIRED",
        }:
            if self.conformance_result != "UNDETERMINED":
                raise ValueError(
                    "Unexamined/review-required construction items must remain UNDETERMINED"
                )
        elif self.conformance_result == "UNDETERMINED":
            raise ValueError(
                "An EXAMINED construction item requires an explicit "
                "PASS, FAIL or NOT_APPLICABLE determination"
            )
        return self


class ConstructionExaminationPatch(Schema):
    overall_notes: str | None = Field(None, max_length=10000)


class ConstructionItemPatch(Schema):
    value_schema_version: Literal[1] | None = None
    value_json: dict[str, JsonValue] | None = None
    examination_state: ExaminationState | None = None
    conformance_result: ConformanceResult | None = None
    remarks: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def changed_field_supplied(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one changed construction-item field")
        return self


class ConstructionExaminationView(Schema):
    id: UUID
    test_session_id: UUID
    evaluation_status: EvaluationStatus
    compliance_outcome: ComplianceOutcome
    overall_notes: str | None
    examined_by: UUID | None
    examined_at: datetime | None
    summary_json: dict[str, JsonValue]
    lock_version: int
    created_at: datetime
    updated_at: datetime


class ConstructionItemView(Schema):
    id: UUID
    construction_examination_id: UUID
    requirement_rule_id: UUID
    category: ConstructionCategory
    item_key: str
    description_snapshot: str
    value_schema_version: Literal[1]
    value_json: dict[str, JsonValue]
    examination_state: ExaminationState
    conformance_result: ConformanceResult
    remarks: str | None
    sort_order: int
    lock_version: int
    created_at: datetime
    updated_at: datetime


class ConstructionRulePolicy(Schema):
    """Strict policy embedded in a versioned construction_item_v1 rule."""

    schema_version: Literal["v1"]
    category: ConstructionCategory
    item_key: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z0-9][A-Z0-9_.-]*$",
    )
    sort_order: int = Field(ge=0, strict=True)
    required: bool
    evidence_required: bool
    allow_not_applicable: bool
    required_value_keys: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_required_keys(self):
        if len(set(self.required_value_keys)) != len(self.required_value_keys):
            raise ValueError("Duplicate required construction value key")
        if any(not key.strip() for key in self.required_value_keys):
            raise ValueError("Construction value keys cannot be blank")
        return self
