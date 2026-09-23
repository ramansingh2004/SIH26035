"""Closed version-one equipment and attachment contracts."""

import unicodedata
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.identity import Schema
from app.schemas.master_data import Description, Mass, Text, Versioned, partial


class EquipmentMetadata(Schema):
    notes: Description | None = None
    nominal_mass_g: Mass | None = Field(None, gt=0)
    certificate_reference: Text | None = None


class EquipmentData(Schema):
    category: Text
    manufacturer: Text | None = None
    model: Text | None = None
    serial_number: Text | None = None
    reference_number: Text | None = None
    calibration_certificate_no: Text | None = None
    calibration_date: date | None = None
    calibration_due_date: date | None = None
    accuracy_or_class: Text | None = None
    metadata_schema_version: Literal[1] = 1
    metadata_json: EquipmentMetadata = Field(default_factory=EquipmentMetadata)

    @model_validator(mode="after")
    def dates_ordered(self):
        if (
            self.calibration_date
            and self.calibration_due_date
            and self.calibration_due_date < self.calibration_date
        ):
            raise ValueError("Calibration due date precedes calibration date")
        return self


class EquipmentCreate(EquipmentData):
    laboratory_id: UUID


class EquipmentView(EquipmentCreate, Versioned):
    is_active: bool


EquipmentPatch = partial("EquipmentPatch", EquipmentData)


class CalibrationSnapshot(Schema):
    """Immutable serialized master facts; no calibration-acceptance conclusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    equipment_id: UUID
    laboratory_id: UUID
    equipment_version: int
    captured_at: datetime
    category: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    reference_number: str | None
    calibration_certificate_no: str | None
    calibration_date: date | None
    calibration_due_date: date | None
    accuracy_or_class: str | None
    calibration_attachment_id: UUID | None = None
    calibration_attachment_sha256: str | None = Field(
        None,
        pattern=r"^[a-f0-9]{64}$",
    )
    calibration_attachment_object_version: str | None = None
    nominal_mass_g: Mass | None
    certificate_reference: str | None
    notes: str | None
    is_active: bool
    regulatory_validation_status: Literal["TODO_REGULATORY_VALIDATION"] = (
        "TODO_REGULATORY_VALIDATION"
    )


TargetType = Literal[
    "laboratories",
    "manufacturers",
    "instruments",
    "instrument_ranges",
    "instrument_components",
    "test_equipment",
    "test_sessions",
    "test_runs",
    "test_observations",
    "test_run_equipment",
    "test_run_results",
    "construction_items",
    "checklist_responses",
]
MimeType = Literal["application/pdf", "image/png", "image/jpeg"]


class EvidenceTarget(Schema):
    entity_type: TargetType
    entity_id: UUID
    purpose: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_.-]*$")


class UploadRequest(EvidenceTarget):
    laboratory_id: UUID
    file_name: Text
    content_type: MimeType
    file_size: int = Field(gt=0, le=25 * 1024 * 1024, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("file_name")
    @classmethod
    def safe_name(cls, value):
        value = unicodedata.normalize("NFC", value)
        if (
            value in (".", "..")
            or any(c in value for c in "/\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("Unsafe file name")
        return value


class CompleteRequest(Schema):
    upload_id: UUID


class RuleRegistration(Schema):
    artifact: Literal["oiml_r76_2006/candidate-v1"]
