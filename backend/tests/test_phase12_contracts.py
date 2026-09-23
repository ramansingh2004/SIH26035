"""Phase 12 Stage 1 persistence and contract tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.construction import (
    CONSTRUCTION_CATEGORIES,
    ConstructionExamination,
    ConstructionItem,
)
from app.schemas.construction import (
    ConstructionAssessment,
    ConstructionItemPatch,
)


def constraint_names(table, kind):
    return {constraint.name for constraint in table.constraints if isinstance(constraint, kind)}


def test_phase12_models_register_canonical_tables():
    assert ConstructionExamination.__tablename__ == "construction_examinations"
    assert ConstructionItem.__tablename__ == "construction_items"


def test_phase12_examination_is_unique_per_session():
    assert "uq_construction_session" in constraint_names(
        ConstructionExamination.__table__,
        UniqueConstraint,
    )


def test_phase12_item_identity_is_unique_per_dossier():
    assert "uq_construction_item_key" in constraint_names(
        ConstructionItem.__table__,
        UniqueConstraint,
    )


def test_phase12_structural_categories_are_frozen():
    assert CONSTRUCTION_CATEGORIES == (
        "GENERAL",
        "RECEPTOR_LOAD_CELLS",
        "INDICATOR_DISPLAY",
        "PRINTER_PERIPHERALS",
        "POWER_INTERFACES",
        "TILT_ZERO_TARE",
        "SEALS_SECURITY_SOFTWARE",
        "DOCUMENTS_PHOTOS",
    )
    assert "ck_construction_item_category" in constraint_names(
        ConstructionItem.__table__,
        CheckConstraint,
    )


@pytest.mark.parametrize(
    ("state", "result"),
    [
        ("NOT_EXAMINED", "UNDETERMINED"),
        ("REVIEW_REQUIRED", "UNDETERMINED"),
        ("EXAMINED", "PASS"),
        ("EXAMINED", "FAIL"),
        ("EXAMINED", "NOT_APPLICABLE"),
    ],
)
def test_phase12_valid_item_state_pairs(state, result):
    assessment = ConstructionAssessment(
        examination_state=state,
        conformance_result=result,
    )
    assert assessment.examination_state == state
    assert assessment.conformance_result == result


@pytest.mark.parametrize(
    ("state", "result"),
    [
        ("NOT_EXAMINED", "PASS"),
        ("NOT_EXAMINED", "FAIL"),
        ("REVIEW_REQUIRED", "PASS"),
        ("EXAMINED", "UNDETERMINED"),
    ],
)
def test_phase12_invalid_item_state_pairs_are_rejected(state, result):
    with pytest.raises(ValidationError):
        ConstructionAssessment(
            examination_state=state,
            conformance_result=result,
        )


def test_phase12_patch_requires_a_changed_field():
    with pytest.raises(ValidationError):
        ConstructionItemPatch()


def test_phase12_patch_accepts_typed_json_value():
    patch = ConstructionItemPatch(
        value_json={
            "component_reference": str(uuid4()),
            "observed": True,
        }
    )
    assert patch.value_schema_version is None
    assert patch.value_json["observed"] is True
