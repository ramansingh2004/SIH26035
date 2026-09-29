from app.reporting.context import full_demo_report_context
from app.reporting.full_demo import (
    EXPECTED_FULL_DEMO_COUNTS,
    validate_full_demo_record,
)
from app.reporting.renderers import build_plan, render_pair
from scripts.verify_phase26_stage7 import fixture_record


def test_stage7_full_demo_context_and_plan_are_permanently_non_official():
    record = fixture_record()
    counts = validate_full_demo_record(record)
    assert counts == EXPECTED_FULL_DEMO_COUNTS

    context = full_demo_report_context(
        record,
        requested_by="stage7-demo-user",
        source_regulatory_revision=77,
    )
    plan = build_plan(context)

    assert context["document_kind"] == "FULL_DEMO_REPORT"
    assert context["demonstration"]["demo_only"] is True
    assert context["demonstration"]["not_for_regulatory_use"] is True
    assert context["document_control"]["report_status"] == "DEMONSTRATION_ONLY"
    assert "NOT AN OFFICIAL OIML CERTIFICATE" in plan.status
    assert plan.watermark == "SIMULATED / DEMONSTRATION ONLY"

    titles = [section.title for section in plan.sections]
    for title in (
        "Document Control",
        "Demonstration Declaration",
        "Executive Summary - All 17 Sections",
        "Test Equipment",
        "Environmental Conditions",
        "Test Runs, Observations and Stored Results",
        "Construction Examination",
        "Checklist",
        "Evidence Register",
        "Reproducibility Manifest",
    ):
        assert title in titles


def test_stage7_full_demo_renders_pdf_and_docx_from_same_full_plan():
    context = full_demo_report_context(
        fixture_record(),
        requested_by="stage7-demo-user",
        source_regulatory_revision=77,
    )
    rendered = render_pair(context)

    assert set(rendered) == {"pdf", "docx"}
    assert rendered["pdf"][0].startswith(b"%PDF-")
    assert rendered["docx"][0].startswith(b"PK")
    assert len(rendered["pdf"][0]) > 1000
    assert len(rendered["docx"][0]) > 1000
