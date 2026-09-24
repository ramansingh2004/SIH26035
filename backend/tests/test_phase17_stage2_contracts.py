"""Phase 17 Stage 2 API and no-N+1 boundary contracts."""

from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def test_phase17_stage2_openapi_has_dashboard_and_paginated_histories():
    schema = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=None,
        )
    ).openapi()
    paths = schema["paths"]

    assert "/api/v1/dashboard/summary" in paths

    for path in (
        "/api/v1/test-sessions/{identifier}/revisions",
        "/api/v1/test-runs/{identifier}/history",
        "/api/v1/reports/{identifier}/revisions",
    ):
        names = {item["name"] for item in paths[path]["get"]["parameters"]}
        assert {"page", "page_size"} <= names


def test_run_history_batches_result_events_and_dashboard_is_read_only():
    testing = Path("app/services/testing.py").read_text()
    repository = Path("app/repositories/testing.py").read_text()
    dashboard_service = Path("app/services/dashboard.py").read_text()

    assert "await self.repo.result_events(" in testing
    assert "async def result_events(" in repository
    assert "for r in results\\n                for e in await" not in testing

    assert ".add(" not in dashboard_service
    assert ".flush(" not in dashboard_service


def test_phase17_stage2_adds_no_migration():
    migrations = {path.stem for path in Path("alembic/versions").glob("*.py")}
    assert "0010_phase16" in migrations
    assert not any(name.startswith("0011_") for name in migrations)
