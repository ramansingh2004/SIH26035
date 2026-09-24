"""Phase 17 Stage 2 dashboard and paginated history acceptance."""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.api.dependencies import object_storage
from tests.conftest import login
from tests.phase5_fixtures import (
    create_session,
    install_synthetic,
    prepare_world,
    started_run,
)
from tests.test_foundations_api import MemoryStorage
from tests.test_phase16_stage3 import (
    approved_session,
    generate_report,
    issue_report,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase17_stage2(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def test_scoped_dashboard_keeps_status_axes_separate_and_shows_activity(
    client,
    phase17_stage2,
):
    world = phase17_stage2
    session_path, _ = await approved_session(client, world)
    generated = await generate_report(client, world, session_path)
    assert generated.status_code == 201, generated.text
    issued = await issue_report(client, generated.json())
    assert issued.status_code == 200, issued.text

    await login(client, world, "viewer")
    response = await client.get(
        "/api/v1/dashboard/summary",
        params={"page_size": 100},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert str(world.labs[0].id) in body["laboratory_ids"]
    assert body["session_total"] >= 1
    assert body["workflow_counts"]["REPORT_ISSUED"] >= 1
    assert body["evaluation_counts"]["COMPLETE"] >= 1
    assert body["outcome_counts"]["NONCOMPLIANT"] >= 1
    assert body["issued_session_count"] >= 1
    assert body["report_status_counts"]["ISSUED"] >= 1
    assert body["report_total"] >= 1

    actions = {item["action"] for item in body["recent_activity"]["items"]}
    assert "report.issued" in actions

    denied = await client.get(
        "/api/v1/dashboard/summary",
        params={"laboratory_id": str(world.labs[1].id)},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    await login(client, world, "other")
    other = await client.get("/api/v1/dashboard/summary")
    assert other.status_code == 200
    assert str(world.labs[0].id) not in other.json()["laboratory_ids"]

    await login(client, world, "admin")
    global_admin = await client.get("/api/v1/dashboard/summary")
    assert global_admin.status_code == 403


async def test_session_revision_and_retest_history_are_paginated(
    client,
    phase17_stage2,
):
    world = phase17_stage2

    created, _, _ = await create_session(
        client,
        world,
        synthetic=True,
    )
    session_path = "/api/v1/test-sessions/" + created.json()["id"]
    child = await client.post(
        session_path + "/revisions",
        headers={
            "If-Match": created.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={"reason": "Phase 17 pagination acceptance."},
    )
    assert child.status_code == 201, child.text

    first_page = await client.get(
        session_path + "/revisions",
        params={"page": 1, "page_size": 1},
    )
    second_page = await client.get(
        session_path + "/revisions",
        params={"page": 2, "page_size": 1},
    )
    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert first_page.json()["total"] == 2
    assert second_page.json()["total"] == 2
    assert first_page.json()["items"][0]["session_revision_no"] == 1
    assert second_page.json()["items"][0]["session_revision_no"] == 2

    _, run_path, requirement = await started_run(client, world)
    current = await client.get(run_path)
    retest = await client.post(
        run_path + "/retests",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={"reason": "Phase 17 retest history."},
    )
    assert retest.status_code == 201, retest.text

    run_page_1 = await client.get(
        run_path + "/history",
        params={"page": 1, "page_size": 1},
    )
    run_page_2 = await client.get(
        run_path + "/history",
        params={"page": 2, "page_size": 1},
    )
    assert run_page_1.status_code == 200, run_page_1.text
    assert run_page_2.status_code == 200, run_page_2.text

    first = run_page_1.json()["runs"]
    second = run_page_2.json()["runs"]
    assert first["total"] == 2
    assert second["total"] == 2
    assert first["items"][0]["run_no"] == 1
    assert first["items"][0]["is_selected"] is True
    assert second["items"][0]["run_no"] == 2
    assert second["items"][0]["retest_of_run_id"] == requirement["selected_run_id"]
