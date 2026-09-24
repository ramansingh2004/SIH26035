"""Phase 17 Stage 1 repository/search/history acceptance."""

import pytest
import pytest_asyncio

from app.api.dependencies import object_storage
from tests.conftest import login
from tests.phase5_fixtures import install_synthetic, prepare_world
from tests.test_foundations_api import MemoryStorage
from tests.test_phase16_stage3 import approved_session, generate_report

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase17_stage1(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def test_report_and_session_search_with_instrument_history(
    client,
    phase17_stage1,
):
    world = phase17_stage1
    session_path, approved = await approved_session(client, world)
    generated = await generate_report(client, world, session_path)
    assert generated.status_code == 201, generated.text

    report = generated.json()["report"]
    session = approved.json()
    instrument_id = session["instrument_id"]

    instrument = await client.get("/api/v1/instruments/" + instrument_id)
    assert instrument.status_code == 200, instrument.text
    instrument_body = instrument.json()

    repository = await client.get(
        "/api/v1/reports",
        params={
            "search": instrument_body["model_name"],
            "report_status": "UNISSUED",
            "compliance_outcome": "NONCOMPLIANT",
        },
    )
    assert repository.status_code == 200, repository.text
    repo_body = repository.json()
    assert repo_body["total"] >= 1
    item = next(row for row in repo_body["items"] if row["id"] == report["id"])
    assert item["report_number"] == report["report_number"]
    assert item["workflow_status"] == "APPROVED"
    assert item["evaluation_status"] == "COMPLETE"
    assert item["compliance_outcome"] == "NONCOMPLIANT"
    assert item["report_status"] == "UNISSUED"
    assert item["is_current_issued"] is False
    assert item["is_superseded"] is False
    assert item["manufacturer_id"] == instrument_body["manufacturer_id"]

    by_number = await client.get(
        "/api/v1/reports",
        params={"report_number": report["report_number"]},
    )
    assert by_number.status_code == 200
    assert [row["id"] for row in by_number.json()["items"]] == [report["id"]]

    sessions = await client.get(
        "/api/v1/test-sessions",
        params={"report_number": report["report_number"]},
    )
    assert sessions.status_code == 200, sessions.text
    assert [row["id"] for row in sessions.json()["items"]] == [session["id"]]

    session_search = await client.get(
        "/api/v1/test-sessions",
        params={"search": instrument_body["model_name"]},
    )
    assert session_search.status_code == 200
    assert session["id"] in {row["id"] for row in session_search.json()["items"]}

    history = await client.get(
        f"/api/v1/instruments/{instrument_id}/history",
        params={"page": 1, "page_size": 10},
    )
    assert history.status_code == 200, history.text
    history_body = history.json()
    assert history_body["page"] == 1
    assert history_body["page_size"] == 10
    assert history_body["total"] >= 1
    history_item = next(row for row in history_body["items"] if row["session_id"] == session["id"])
    assert history_item["session_revision_no"] == session["session_revision_no"]
    assert history_item["workflow_status"] == "APPROVED"
    assert history_item["evaluation_status"] == "COMPLETE"
    assert history_item["compliance_outcome"] == "NONCOMPLIANT"
    assert history_item["report_id"] == report["id"]
    assert history_item["report_number"] == report["report_number"]
    assert history_item["report_status"] == "UNISSUED"
    assert history_item["run_count"] >= 1
    assert history_item["retest_count"] >= 0

    await login(client, world, "other")
    hidden_reports = await client.get("/api/v1/reports")
    assert hidden_reports.status_code == 200
    assert report["id"] not in {row["id"] for row in hidden_reports.json()["items"]}

    hidden_history = await client.get(f"/api/v1/instruments/{instrument_id}/history")
    assert hidden_history.status_code == 404


async def test_report_repository_explicit_lab_scope_rejects_other_lab_filter(
    client,
    phase17_stage1,
):
    world = phase17_stage1
    await login(client, world, "viewer")
    response = await client.get(
        "/api/v1/reports",
        params={"laboratory_id": str(world.labs[1].id)},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
