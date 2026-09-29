from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stage7_backend_has_distinct_full_demo_report_path():
    api = (ROOT / "backend/app/api/v1/report.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/app/services/report.py").read_text(encoding="utf-8")
    context = (ROOT / "backend/app/reporting/context.py").read_text(encoding="utf-8")
    renderer = (ROOT / "backend/app/reporting/renderers.py").read_text(encoding="utf-8")

    assert "/full-demo-report-previews" in api
    assert "create_full_demo_report_preview" in service
    assert "is_full_demo_execution_ruleset" in service
    assert "validate_full_demo_record" in service
    assert "FULL_DEMO_REPORT" in context
    assert "FULL_DEMO_REPORT" in renderer
    assert "NOT AN OFFICIAL OIML CERTIFICATE" in renderer


def test_stage7_keeps_compact_demo_and_official_paths_separate():
    service = (ROOT / "backend/app/services/report.py").read_text(encoding="utf-8")
    renderer = (ROOT / "backend/app/reporting/renderers.py").read_text(encoding="utf-8")
    context = (ROOT / "backend/app/reporting/context.py").read_text(encoding="utf-8")

    assert "create_simulated_approved_preview" in service
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in service
    assert 'document_kind == "SIMULATED_APPROVED_REPORT"' in renderer
    assert 'document_kind == "FULL_DEMO_REPORT"' in renderer
    assert '"document_kind": "OFFICIAL_REPORT"' in context


def test_stage7_frontend_switches_completed_v3_to_full_report_endpoint():
    panel = (
        ROOT / "frontend/src/components/reports/report-session-panel.tsx"
    ).read_text(encoding="utf-8")
    api = (ROOT / "frontend/src/lib/reports/api.ts").read_text(encoding="utf-8")

    assert "createFullDemoReport" in api
    assert "/full-demo-report-previews" in api
    assert "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3" in panel
    assert "Generate complete 17-section demo report" in panel
    assert "NOT AN OFFICIAL OIML CERTIFICATE" in panel
