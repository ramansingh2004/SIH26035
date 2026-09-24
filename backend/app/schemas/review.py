"""Strict Phase 15 review/correction HTTP and persistence contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from app.schemas.identity import Schema

Reason = Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
Comment = Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
EntityType = Annotated[
    str,
    Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"),
]
FieldPath = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$"),
]


class CorrectionTarget(Schema):
    entity_type: EntityType
    entity_id: UUID
    field_paths: tuple[FieldPath, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_fields(self):
        if len(self.field_paths) != len(set(self.field_paths)):
            raise ValueError("Duplicate correction field path")
        return self


class CorrectionScope(Schema):
    targets: tuple[CorrectionTarget, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_targets(self):
        identities = [(target.entity_type, target.entity_id) for target in self.targets]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate correction target")
        return self


class TechnicalReviewRequest(Schema):
    decision: Literal["APPROVED", "REJECTED"]
    comment: Comment | None = None
    reviewed_regulatory_revision: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def rejection_has_reason(self):
        if self.decision == "REJECTED" and self.comment is None:
            raise ValueError("Rejected technical review requires a comment")
        return self


class ReturnForCorrectionRequest(Schema):
    target_workflow_status: Literal["TESTING", "EXAMINATION"]
    requested_scope: CorrectionScope
    reason: Reason


class CorrectionResolveRequest(Schema):
    resolution_note: Reason


class FinalRejectRequest(Schema):
    reason: Reason


class ApprovalActionView(Schema):
    id: UUID
    test_session_id: UUID
    stage: Literal["TECHNICAL_REVIEW", "FINAL_APPROVAL"]
    decision: Literal[
        "SUBMITTED",
        "APPROVED",
        "REJECTED",
        "RETURNED_FOR_CORRECTION",
        "INVALIDATED",
    ]
    actor_id: UUID
    regulatory_revision: int
    scope_json: dict[str, JsonValue]
    referenced_action_id: UUID | None
    comment: str | None
    reason: str | None
    created_at: datetime


class CorrectionRequestView(Schema):
    id: UUID
    test_session_id: UUID
    approval_action_id: UUID
    target_workflow_status: Literal["TESTING", "EXAMINATION"]
    requested_scope_json: dict[str, JsonValue]
    reason: str
    requested_by: UUID
    requested_at: datetime
    correction_status: Literal["OPEN", "RESOLVED", "CANCELLED"]
    resolved_at: datetime | None
    lock_version: int
    created_at: datetime
    updated_at: datetime


class SessionApprovalSnapshotView(Schema):
    id: UUID
    test_session_id: UUID
    approval_action_id: UUID
    regulatory_revision: int
    snapshot_schema_version: Literal[1]
    snapshot_json: dict[str, JsonValue]
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime
    captured_by: UUID
