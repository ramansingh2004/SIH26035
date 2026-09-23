"""Phase 12 real-PostgreSQL/FastAPI construction integration."""

from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.models.construction import ConstructionExamination, ConstructionItem
from app.models.identity import RefreshSession
from app.services.audit import RequestContext
from app.services.authorization import Principal
from app.services.construction import ConstructionService
from tests.conftest import login
from tests.phase12_fixtures import (
    CATEGORIES,
    attach_document_evidence,
    fill_items,
    prepare_phase12_world,
    start_phase12_examination,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase12(world, monkeypatch):
    return await prepare_phase12_world(world, monkeypatch)


async def construction(client, session_path):
    return await client.get(session_path + "/construction")


async def complete(client, session_path):
    current = await construction(client, session_path)
    return await client.post(
        session_path + "/construction/complete",
        headers={"If-Match": current.headers["etag"]},
    )


async def test_phase12_start_examination_initializes_all_categories(
    client,
    phase12,
):
    session_path, response = await start_phase12_examination(client, phase12)
    assert response.json()["workflow_status"] == "EXAMINATION"

    dossier = await construction(client, session_path)
    assert dossier.status_code == 200, dossier.text
    assert dossier.json()["evaluation_status"] == "NOT_STARTED"
    assert dossier.json()["compliance_outcome"] == "UNDETERMINED"

    items = (await client.get(session_path + "/construction/items")).json()
    assert len(items) == 8
    assert {item["category"] for item in items} == set(CATEGORIES)
    assert all(item["examination_state"] == "NOT_EXAMINED" for item in items)

    section = await client.get(session_path + "/sections/16")
    assert section.status_code == 200
    assert section.json()["evaluation_status"] == "NOT_STARTED"


async def test_phase12_initializer_is_idempotent_for_existing_session(
    client,
    phase12,
):
    session_path, _ = await start_phase12_examination(client, phase12)
    session_id = UUID(session_path.rsplit("/", 1)[1])

    async with phase12.factory() as database:
        family_id = await database.scalar(
            select(RefreshSession.family_id)
            .where(
                RefreshSession.user_id == phase12.users["local"].id,
                RefreshSession.revoked_at.is_(None),
            )
            .limit(1)
        )

    async with phase12.factory() as database:
        service = ConstructionService(database, RequestContext())
        actor = Principal(
            user_id=phase12.users["local"].id,
            family_id=family_id,
        )
        first = await service.initialize(actor, session_id)
        second = await service.initialize(actor, session_id)

    assert first["id"] == second["id"]

    async with phase12.factory() as database:
        examination_id = await database.scalar(
            select(ConstructionExamination.id).where(
                ConstructionExamination.test_session_id == session_id
            )
        )
        count = await database.scalar(
            select(func.count())
            .select_from(ConstructionItem)
            .where(ConstructionItem.construction_examination_id == examination_id)
        )
    assert count == 8


async def test_phase12_incomplete_dossier_cannot_complete(client, phase12):
    session_path, _ = await start_phase12_examination(client, phase12)
    response = await complete(client, session_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "CONSTRUCTION_INCOMPLETE"


async def test_phase12_required_evidence_blocks_then_allows_completion(
    client,
    phase12,
):
    session_path, _ = await start_phase12_examination(client, phase12)
    items = await fill_items(client, session_path)
    document = items["DOCUMENTS_PHOTOS.SYNTHETIC_ITEM"]

    blocked = await complete(client, session_path)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "CONSTRUCTION_INCOMPLETE"
    assert (
        "DOCUMENTS_PHOTOS.SYNTHETIC_ITEM" in blocked.json()["error"]["details"]["missing_item_keys"]
    )

    document = await attach_document_evidence(
        client,
        phase12,
        session_path,
        document,
    )
    assert document["lock_version"] > items["DOCUMENTS_PHOTOS.SYNTHETIC_ITEM"]["lock_version"]

    finished = await complete(client, session_path)
    assert finished.status_code == 200, finished.text
    assert finished.json()["evaluation_status"] == "COMPLETE"
    assert finished.json()["compliance_outcome"] == "COMPLIANT"
    assert finished.json()["examined_by"]

    section = await client.get(session_path + "/sections/16")
    assert section.json()["evaluation_status"] == "COMPLETE"
    assert section.json()["compliance_outcome"] == "COMPLIANT"


async def test_phase12_fail_is_complete_noncompliant(client, phase12):
    session_path, _ = await start_phase12_examination(client, phase12)
    items = await fill_items(
        client,
        session_path,
        fail_key="GENERAL.SYNTHETIC_ITEM",
    )
    await attach_document_evidence(
        client,
        phase12,
        session_path,
        items["DOCUMENTS_PHOTOS.SYNTHETIC_ITEM"],
    )

    finished = await complete(client, session_path)
    assert finished.status_code == 200, finished.text
    assert finished.json()["evaluation_status"] == "COMPLETE"
    assert finished.json()["compliance_outcome"] == "NONCOMPLIANT"

    section = await client.get(session_path + "/sections/16")
    assert section.json()["evaluation_status"] == "COMPLETE"
    assert section.json()["compliance_outcome"] == "NONCOMPLIANT"


async def test_phase12_item_update_requires_current_etag(client, phase12):
    session_path, _ = await start_phase12_examination(client, phase12)
    item = (await client.get(session_path + "/construction/items")).json()[0]
    path = session_path + "/construction/items/" + item["id"]

    first = await client.patch(
        path,
        headers={"If-Match": f'"{item["lock_version"]}"'},
        json={"remarks": "first"},
    )
    assert first.status_code == 200

    stale = await client.patch(
        path,
        headers={"If-Match": f'"{item["lock_version"]}"'},
        json={"remarks": "stale"},
    )
    assert stale.status_code == 412


async def test_phase12_completed_dossier_is_invalidated_by_item_change(
    client,
    phase12,
):
    session_path, _ = await start_phase12_examination(client, phase12)
    items = await fill_items(client, session_path)
    await attach_document_evidence(
        client,
        phase12,
        session_path,
        items["DOCUMENTS_PHOTOS.SYNTHETIC_ITEM"],
    )
    finished = await complete(client, session_path)
    assert finished.status_code == 200

    item = (await client.get(session_path + "/construction/items")).json()[0]
    changed = await client.patch(
        session_path + "/construction/items/" + item["id"],
        headers={"If-Match": f'"{item["lock_version"]}"'},
        json={"remarks": "post-completion source edit"},
    )
    assert changed.status_code == 200, changed.text

    dossier = await construction(client, session_path)
    assert dossier.json()["examined_by"] is None
    assert dossier.json()["examined_at"] is None
    assert dossier.json()["evaluation_status"] == "IN_PROGRESS"
    assert dossier.json()["compliance_outcome"] == "UNDETERMINED"


async def test_phase12_start_examination_requires_testing_state(
    client,
    phase12,
):
    from tests.phase11_fixtures import configured_phase11

    response, session_path = await configured_phase11(client, phase12)
    attempted = await client.post(
        session_path + "/start-examination",
        headers={"If-Match": response.headers["etag"]},
    )
    assert attempted.status_code == 409
    assert attempted.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_phase12_lab_isolation(client, phase12):
    session_path, _ = await start_phase12_examination(client, phase12)
    await login(client, phase12, "other")
    assert (await construction(client, session_path)).status_code == 404
    assert (await client.get(session_path + "/construction/items")).status_code == 404
