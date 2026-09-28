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


def test_simulated_report_plan_is_compact_and_hides_internal_payloads():
    record = _record()
    record["session"]["application_number"] = "DEMO-APPLICATION-001"
    record["laboratory"] = {
        "id": "hidden-lab-id",
        "name": "Demo Laboratory",
        "code": "DEMO-LAB",
        "city": "Ghaziabad",
        "state": "Uttar Pradesh",
        "country": "India",
        "accreditation_no": "DEMO-ONLY",
    }
    record["manufacturer"] = {
        "id": "hidden-manufacturer-id",
        "name": "Demo Manufacturer",
    }
    record["instrument_master_at_approval"] = {
        "id": "hidden-instrument-id",
        "created_by": "hidden-user-id",
        "type_designation": "DEMO-III-20K",
        "model_name": "Demo Scale",
        "serial_number": "DEMO-001",
        "accuracy_class": "III",
        "max_capacity_g": "20000",
        "min_capacity_g": "0",
        "scale_interval_d_g": "10",
        "verification_interval_e_g": "10",
        "verification_intervals_n": "2000",
        "is_electronic": True,
    }
    record["ruleset_record"] = {
        "standard_code": "OIML_R76",
        "edition": "R76-1:2006 / R76-2:2007",
        "version": "candidate-v1",
        "configuration_hash": "a" * 64,
        "source_reference": "Candidate only; independent review pending",
    }
    record["ruleset_snapshot"] = {"secret_internal_payload": "THIS MUST NOT APPEAR IN THE PLAN"}
    record["sections"] = [
        {
            "section_number": index,
            "section_name": name,
            "evaluation_status": "NOT_STARTED",
            "compliance_outcome": "UNDETERMINED",
        }
        for index, name in enumerate(
            (
                "WEIGHING PERFORMANCE",
                "TEMPERATURE ZERO",
                "ECCENTRICITY",
                "DISCRIMINATION / SENSITIVITY",
                "REPEATABILITY",
                "TIME DEPENDENCE",
                "STABILITY EQUILIBRIUM",
                "TILTING",
                "TARE",
                "WARM UP",
                "VOLTAGE VARIATION",
                "ELECTRICAL DISTURBANCES",
                "DAMP HEAT",
                "SPAN STABILITY",
                "ENDURANCE",
                "CONSTRUCTION EXAMINATION",
                "CHECKLIST",
            ),
            start=1,
        )
    ]

    context = simulated_approved_context(
        record,
        requested_by="demo-user",
        source_regulatory_revision=7,
    )
    plan = build_plan(context)

    assert len(plan.sections) == 7
    assert [section.title for section in plan.sections] == [
        "Document Control",
        "Simulation Declaration",
        "Instrument & Laboratory Details",
        "Evaluation Summary",
        "Sample Demonstration Results",
        "Review / Approval Summary",
        "Technical Trace",
    ]

    plan_text = repr(plan)
    assert "THIS MUST NOT APPEAR IN THE PLAN" not in plan_text
    assert "hidden-instrument-id" not in plan_text
    assert "hidden-lab-id" not in plan_text
    assert "hidden-manufacturer-id" not in plan_text
    assert "hidden-user-id" not in plan_text
    assert "Ruleset Snapshot" not in plan_text
    assert "Independent Regulatory Review" in plan_text
    assert "PENDING" in plan_text

    summary = next(section for section in plan.sections if section.title == "Evaluation Summary")
    assert len(summary.tables[0].rows) == 17
    assert all(row[-1] == "COMPLIANT*" for row in summary.tables[0].rows)
