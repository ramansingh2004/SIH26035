"""Phase 13 Stage 2 service/domain helpers."""

from types import SimpleNamespace

from app.compliance.domain import Applicability
from app.schemas.checklist import ChecklistRowView, ChecklistSummary
from app.services.checklist import (
    assessment_for,
    checklist_rule_input,
    response_view,
)


def rule(**changes):
    data = dict(
        id="00000000-0000-0000-0000-000000000001",
        requirement_key="GENERAL_SYNTHETIC",
        group_code="GENERAL",
        clause_reference="SYNTHETIC",
        display_text="SYNTHETIC TEST FIXTURE ONLY",
        applicability_expression={
            "schema_version": "v1",
            "mode": "ALL",
            "conditions": [],
            "when_match": "REQUIRED",
            "when_not_match": "NOT_APPLICABLE",
            "match_reason": "Synthetic required",
            "no_match_reason": "Synthetic excluded",
        },
        evidence_required=False,
        validation_status="VERIFIED",
        sort_order=10,
    )
    data.update(changes)
    return SimpleNamespace(**data)


def response(**changes):
    data = dict(
        id="00000000-0000-0000-0000-000000000002",
        test_session_id="00000000-0000-0000-0000-000000000003",
        checklist_rule_id="00000000-0000-0000-0000-000000000001",
        applicability_status="REQUIRED",
        applicability_reason="Synthetic required",
        response_result="NOT_EXAMINED",
        remarks=None,
        examined_by=None,
        examined_at=None,
        lock_version=1,
        created_at="2026-09-23T00:00:00Z",
        updated_at="2026-09-23T00:00:00Z",
    )
    data.update(changes)
    return SimpleNamespace(**data)


def test_phase13_service_maps_persisted_rule_to_engine_contract():
    mapped = checklist_rule_input(rule())
    assert mapped.rule_key == "GENERAL_SYNTHETIC"
    assert mapped.group_code == "GENERAL"
    assert mapped.validation_status == "VERIFIED"


def test_phase13_service_uses_snapshotted_applicability():
    item = assessment_for(response(), rule(), evidence_count=0)
    assert item.decision.applicability == Applicability.REQUIRED
    assert item.response_result == "NOT_EXAMINED"


def test_phase13_service_maps_retained_na_response():
    item = assessment_for(
        response(
            applicability_status="NOT_APPLICABLE",
            applicability_reason="Synthetic excluded",
            response_result="NOT_APPLICABLE",
        ),
        rule(),
    )
    assert item.decision.applicability == Applicability.NOT_APPLICABLE


def test_phase13_row_view_contains_versioned_rule_wording():
    view = response_view(response(), rule())
    parsed = ChecklistRowView.model_validate(view)
    assert parsed.requirement_key == "GENERAL_SYNTHETIC"
    assert parsed.display_text == "SYNTHETIC TEST FIXTURE ONLY"
    assert parsed.validation_status == "VERIFIED"


def test_phase13_summary_exposes_parent_lock_version():
    parsed = ChecklistSummary(
        catalog_total=1,
        applicable=1,
        passed=0,
        failed=0,
        not_examined=1,
        not_applicable=0,
        review_required=0,
        evaluation_status="NOT_STARTED",
        compliance_outcome="UNDETERMINED",
        missing_rule_keys=["GENERAL_SYNTHETIC"],
        blockers=[],
        lock_version=4,
    )
    assert parsed.lock_version == 4
