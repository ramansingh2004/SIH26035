"""Phase 17 Stage 1 route/query boundary contracts."""

from app.core.config import Settings
from app.main import create_app


def test_phase17_repository_and_dashboard_boundary():
    paths = set(
        create_app(
            Settings(
                _env_file=None,
                environment="test",
                database_url=None,
            )
        ).openapi()["paths"]
    )
    assert "/api/v1/reports" in paths
    assert "/api/v1/instruments/{identifier}/history" in paths
    assert "/api/v1/test-sessions" in paths
    assert "/api/v1/dashboard/summary" in paths


def test_phase17_stage1_query_parameters_are_bounded():
    schema = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=None,
        )
    ).openapi()

    report_get = schema["paths"]["/api/v1/reports"]["get"]
    names = {item["name"] for item in report_get["parameters"]}
    assert {
        "page",
        "page_size",
        "laboratory_id",
        "manufacturer_id",
        "instrument_id",
        "report_number",
        "workflow_status",
        "evaluation_status",
        "compliance_outcome",
        "report_status",
        "created_from",
        "created_to",
        "search",
    } <= names

    history_get = schema["paths"]["/api/v1/instruments/{identifier}/history"]["get"]
    history_names = {item["name"] for item in history_get["parameters"]}
    assert {"page", "page_size"} <= history_names
