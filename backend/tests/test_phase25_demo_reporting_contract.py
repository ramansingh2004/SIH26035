from app.reporting.context import (
    official_context,
    preview_context,
    simulated_approved_context,
)
from app.reporting.renderers import build_plan


def _record():
    return {
        "session": {
            "id": "11111111-2222-3333-4444-555555555555",
            "workflow_status": "TESTING",
            "evaluation_status": "IN_PROGRESS",
            "compliance_outcome": "UNDETERMINED",
        },
        "laboratory": {},
        "manufacturer": {},
        "instrument_master_at_approval": {},
        "instrument_ranges_at_approval": [],
        "ruleset_record": {},
        "sections": [],
        "equipment": [],
        "environment": [],
        "test_runs": [],
        "construction": {"examination": {}, "items": []},
        "checklist": [],
        "evidence": [],
        "approval_actions": [],
        "ruleset_snapshot": {},
    }


def test_simulated_approved_context_is_permanently_demo_only():
    context = simulated_approved_context(
        _record(),
        requested_by="demo-user",
        source_regulatory_revision=7,
    )

    assert context["document_kind"] == "SIMULATED_APPROVED_REPORT"
    assert context["document_control"]["report_status"] == "SIMULATED_APPROVED"
    assert context["simulation"]["demo_only"] is True
    assert context["simulation"]["not_for_regulatory_use"] is True
    assert context["simulation"]["actual_workflow_status"] == "TESTING"
    assert context["simulation"]["target_workflow_status"] == "APPROVED"
    assert context["simulation"]["target_evaluation_status"] == "COMPLETE"
    assert context["simulation"]["target_compliance_outcome"] == "COMPLIANT"

    plan = build_plan(context)
    assert plan.status == "SIMULATED APPROVED — DEMONSTRATION ONLY"
    assert plan.watermark == "SIMULATED / DEMONSTRATION ONLY"
    assert any(section.title == "Simulation Declaration" for section in plan.sections)


def test_existing_preview_and_official_contexts_keep_their_identity():
    record = _record()
    preview = preview_context(
        record,
        requested_by="demo-user",
        source_regulatory_revision=7,
    )
    official = official_context(
        record,
        report_number="R76-TEST-001",
        revision_no=1,
        intended_issuer_id="issuer",
        planned_issue_date="2026-09-28",
        source_regulatory_revision=7,
    )

    preview_plan = build_plan(preview)
    official_plan = build_plan(official)

    assert preview["document_kind"] == "UNOFFICIAL_PREVIEW"
    assert preview_plan.watermark == "UNOFFICIAL PREVIEW"
    assert official["document_kind"] == "OFFICIAL_REPORT"
    assert official_plan.watermark is None
