"""Phase 13 real-PostgreSQL/FastAPI checklist integration."""

import pytest
import pytest_asyncio

from tests.conftest import login
from tests.phase13_fixtures import (
    GROUPS,
    attach_checklist_evidence,
    fill_required_rows,
    prepare_phase13_world,
    start_phase13_examination,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase13(world, monkeypatch):
    return await prepare_phase13_world(world, monkeypatch)


async def summary(client, session_path):
    return await client.get(session_path + "/checklist/summary")


async def complete(client, session_path):
    current = await summary(client, session_path)
    return await client.post(
        session_path + "/checklist/complete",
        headers={"If-Match": current.headers["etag"]},
    )


async def test_phase13_start_examination_initializes_versioned_catalog(
    client,
    phase13,
):
    session_path, _ = await start_phase13_examination(client, phase13)

    rows = (await client.get(session_path + "/checklist")).json()
    assert len(rows) == 4
    assert {row["group_code"] for row in rows} == set(GROUPS)
    assert {row["requirement_key"]: row["applicability_status"] for row in rows} == {
        "GENERAL_SYNTHETIC_VERIFIED": "REQUIRED",
        "DIRECT_SALES_SYNTHETIC_VERIFIED": "NOT_APPLICABLE",
        "ELECTRONIC_SYNTHETIC_VERIFIED": "REQUIRED",
        "SOFTWARE_SYNTHETIC_VERIFIED": "REQUIRED",
    }
    direct = next(
        row for row in rows if row["requirement_key"] == "DIRECT_SALES_SYNTHETIC_VERIFIED"
    )
    assert direct["response_result"] == "NOT_APPLICABLE"
    assert direct["examined_by"] is None
    assert direct["examined_at"] is None

    section = await client.get(session_path + "/sections/17")
    assert section.status_code == 200
    assert section.json()["evaluation_status"] == "NOT_STARTED"


async def test_phase13_filters_groups_and_responses(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)

    electronic = await client.get(
        session_path + "/checklist",
        params={"group": "ELECTRONIC"},
    )
    assert electronic.status_code == 200
    assert len(electronic.json()) == 1
    assert electronic.json()[0]["group_code"] == "ELECTRONIC"

    excluded = await client.get(
        session_path + "/checklist",
        params={"response_result": "NOT_APPLICABLE"},
    )
    assert excluded.status_code == 200
    assert len(excluded.json()) == 1
    assert excluded.json()[0]["group_code"] == "DIRECT_SALES"


async def test_phase13_incomplete_checklist_cannot_complete(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)
    response = await complete(client, session_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "CHECKLIST_INCOMPLETE"


async def test_phase13_required_evidence_blocks_then_allows_completion(
    client,
    phase13,
):
    session_path, _ = await start_phase13_examination(client, phase13)
    rows = await fill_required_rows(client, session_path)
    electronic = rows["ELECTRONIC_SYNTHETIC_VERIFIED"]

    blocked = await complete(client, session_path)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "CHECKLIST_INCOMPLETE"
    assert (
        "ELECTRONIC_SYNTHETIC_VERIFIED" in blocked.json()["error"]["details"]["missing_rule_keys"]
    )

    await attach_checklist_evidence(
        client,
        phase13,
        session_path,
        electronic,
    )

    finished = await complete(client, session_path)
    assert finished.status_code == 200, finished.text
    assert finished.json()["evaluation_status"] == "COMPLETE"
    assert finished.json()["compliance_outcome"] == "COMPLIANT"
    assert finished.json()["passed"] == 3
    assert finished.json()["not_applicable"] == 1

    section = await client.get(session_path + "/sections/17")
    assert section.json()["evaluation_status"] == "COMPLETE"
    assert section.json()["compliance_outcome"] == "COMPLIANT"


async def test_phase13_fail_is_answered_complete_noncompliant(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)
    rows = await fill_required_rows(
        client,
        session_path,
        fail_key="GENERAL_SYNTHETIC_VERIFIED",
    )
    await attach_checklist_evidence(
        client,
        phase13,
        session_path,
        rows["ELECTRONIC_SYNTHETIC_VERIFIED"],
    )

    finished = await complete(client, session_path)
    assert finished.status_code == 200, finished.text
    assert finished.json()["evaluation_status"] == "COMPLETE"
    assert finished.json()["compliance_outcome"] == "NONCOMPLIANT"
    assert finished.json()["failed"] == 1


async def test_phase13_row_update_requires_current_etag(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)
    row = next(
        value
        for value in (await client.get(session_path + "/checklist")).json()
        if value["applicability_status"] == "REQUIRED"
    )
    path = session_path + "/checklist/" + row["checklist_rule_id"]

    first = await client.patch(
        path,
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={"remarks": "first"},
    )
    assert first.status_code == 200, first.text

    stale = await client.patch(
        path,
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={"remarks": "stale"},
    )
    assert stale.status_code == 412


async def test_phase13_required_row_cannot_be_manually_na(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)
    row = next(
        value
        for value in (await client.get(session_path + "/checklist")).json()
        if value["applicability_status"] == "REQUIRED"
    )

    response = await client.patch(
        session_path + "/checklist/" + row["checklist_rule_id"],
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={"response_result": "NOT_APPLICABLE"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CHECKLIST_NA_NOT_PERMITTED"


async def test_phase13_lab_isolation(client, phase13):
    session_path, _ = await start_phase13_examination(client, phase13)
    await login(client, phase13, "other")
    assert (await client.get(session_path + "/checklist")).status_code == 404
    assert (await client.get(session_path + "/checklist/summary")).status_code == 404
