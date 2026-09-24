"""Phase 15 Stage 1 persistence and strict contract tests."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.review import (
    APPROVAL_DECISIONS,
    APPROVAL_STAGES,
    CORRECTION_STATUSES,
    CORRECTION_TARGET_STATES,
    ApprovalAction,
    CorrectionRequest,
    SessionApprovalSnapshot,
)
from app.schemas.review import (
    CorrectionScope,
    ReturnForCorrectionRequest,
    TechnicalReviewRequest,
)

MIGRATION = Path("alembic/versions/0007_phase15.py").read_text()


def constraint_names(table, kind):
    return {constraint.name for constraint in table.constraints if isinstance(constraint, kind)}


def target(*, entity_type="test_observations", identifier=None, fields=("payload",)):
    return {
        "entity_type": entity_type,
        "entity_id": str(identifier or uuid4()),
        "field_paths": list(fields),
    }


def test_phase15_models_register_frozen_tables():
    assert ApprovalAction.__tablename__ == "approval_actions"
    assert CorrectionRequest.__tablename__ == "correction_requests"
    assert SessionApprovalSnapshot.__tablename__ == "session_approval_snapshots"


def test_phase15_enums_match_frozen_contract():
    assert APPROVAL_STAGES == ("TECHNICAL_REVIEW", "FINAL_APPROVAL")
    assert APPROVAL_DECISIONS == (
        "SUBMITTED",
        "APPROVED",
        "REJECTED",
        "RETURNED_FOR_CORRECTION",
        "INVALIDATED",
    )
    assert CORRECTION_TARGET_STATES == ("TESTING", "EXAMINATION")
    assert CORRECTION_STATUSES == ("OPEN", "RESOLVED", "CANCELLED")


def test_phase15_snapshot_is_unique_per_session_revision():
    assert "uq_session_approval_snapshot" in constraint_names(
        SessionApprovalSnapshot.__table__,
        UniqueConstraint,
    )


def test_phase15_correction_requires_bounded_nonempty_scope():
    with pytest.raises(ValidationError):
        CorrectionScope(targets=[])

    scope = CorrectionScope(targets=[target()])
    assert len(scope.targets) == 1
    assert scope.targets[0].field_paths == ("payload",)


def test_phase15_duplicate_target_and_field_paths_rejected():
    identifier = uuid4()
    with pytest.raises(ValidationError):
        CorrectionScope(
            targets=[
                target(identifier=identifier, fields=("payload",)),
                target(identifier=identifier, fields=("notes",)),
            ]
        )

    with pytest.raises(ValidationError):
        CorrectionScope(
            targets=[
                target(fields=("payload", "payload")),
            ]
        )


def test_phase15_return_request_only_targets_editable_workflow_states():
    request = ReturnForCorrectionRequest(
        target_workflow_status="TESTING",
        requested_scope={"targets": [target()]},
        reason="Correct the captured observation.",
    )
    assert request.target_workflow_status == "TESTING"

    with pytest.raises(ValidationError):
        ReturnForCorrectionRequest(
            target_workflow_status="APPROVED",
            requested_scope={"targets": [target()]},
            reason="Not allowed.",
        )


def test_phase15_rejected_technical_review_requires_comment():
    with pytest.raises(ValidationError):
        TechnicalReviewRequest(
            decision="REJECTED",
            reviewed_regulatory_revision=3,
        )

    accepted = TechnicalReviewRequest(
        decision="APPROVED",
        reviewed_regulatory_revision=3,
    )
    assert accepted.comment is None


def test_phase15_migration_is_based_on_phase13_head():
    assert 'revision = "0007_phase15"' in MIGRATION
    assert 'down_revision = "0006_phase13"' in MIGRATION


def test_phase15_migration_protects_append_only_review_history():
    assert 'for table in ("approval_actions", "session_approval_snapshots")' in MIGRATION
    assert 'f"CREATE TRIGGER phase15_{table}_immutable "' in MIGRATION
    assert "BEFORE UPDATE OR DELETE OR TRUNCATE" in MIGRATION
    assert "Phase 15 review history is append-only" in MIGRATION


def test_phase15_migration_protects_correction_scope_and_provenance():
    assert "Correction request scope and provenance are immutable" in MIGRATION
    assert "Resolved correction request is immutable" in MIGRATION
    assert "Correction request may only leave OPEN once" in MIGRATION


def test_phase15_final_snapshot_requires_matching_approved_action():
    assert "Approval snapshot requires matching final approval action and revision" in MIGRATION


def test_phase15_model_constraint_names_are_present():
    assert "ck_approval_action_stage_decision" in constraint_names(
        ApprovalAction.__table__,
        CheckConstraint,
    )
    assert "ck_correction_resolution" in constraint_names(
        CorrectionRequest.__table__,
        CheckConstraint,
    )
    assert "ck_session_approval_hash" in constraint_names(
        SessionApprovalSnapshot.__table__,
        CheckConstraint,
    )
