"""Phase 13 Stage 1 persistence/contract tests."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.checklist import (
    CHECKLIST_APPLICABILITIES,
    CHECKLIST_RESULTS,
    ChecklistResponse,
)
from app.schemas.checklist import ChecklistResponsePatch


def constraint_names(table, kind):
    return {constraint.name for constraint in table.constraints if isinstance(constraint, kind)}


def test_phase13_model_registers_canonical_table():
    assert ChecklistResponse.__tablename__ == "checklist_responses"


def test_phase13_response_unique_per_session_rule():
    assert "uq_checklist_response_rule" in constraint_names(
        ChecklistResponse.__table__,
        UniqueConstraint,
    )


def test_phase13_applicability_contract_is_strict():
    assert CHECKLIST_APPLICABILITIES == (
        "REQUIRED",
        "NOT_APPLICABLE",
        "REQUIRES_REVIEW",
    )
    assert "ck_checklist_response_applicability" in constraint_names(
        ChecklistResponse.__table__,
        CheckConstraint,
    )


def test_phase13_response_values_match_frozen_contract():
    assert CHECKLIST_RESULTS == (
        "PASS",
        "FAIL",
        "NOT_APPLICABLE",
        "NOT_EXAMINED",
    )


def test_phase13_patch_requires_a_field():
    try:
        ChecklistResponsePatch()
    except ValueError:
        pass
    else:
        raise AssertionError("Empty checklist patch must be rejected")
