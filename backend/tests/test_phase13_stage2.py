"""Phase 13 Stage 2 real-PostgreSQL initializer checks."""

from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.checklist import ChecklistResponse
from app.models.identity import RefreshSession
from app.schemas.checklist import ChecklistResponsePatch
from app.services.audit import RequestContext
from app.services.authorization import Principal
from app.services.checklist import ChecklistService
from tests.phase12_fixtures import start_phase12_examination
from tests.phase13_stage2_fixtures import prepare_phase13_stage2_world

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase13_stage2(world, monkeypatch):
    return await prepare_phase13_stage2_world(world, monkeypatch)


async def actor_for(world):
    async with world.factory() as database:
        family_id = await database.scalar(
            select(RefreshSession.family_id)
            .where(
                RefreshSession.user_id == world.users["local"].id,
                RefreshSession.revoked_at.is_(None),
            )
            .limit(1)
        )
    return Principal(
        user_id=world.users["local"].id,
        family_id=family_id,
    )


async def test_phase13_initializer_is_idempotent_for_existing_session(
    client,
    phase13_stage2,
):
    session_path, _ = await start_phase12_examination(
        client,
        phase13_stage2,
    )
    session_id = UUID(session_path.rsplit("/", 1)[1])
    actor = await actor_for(phase13_stage2)

    async with phase13_stage2.factory() as database:
        initial_count = await database.scalar(
            select(func.count())
            .select_from(ChecklistResponse)
            .where(ChecklistResponse.test_session_id == session_id)
        )

    assert initial_count > 0

    async with phase13_stage2.factory() as database:
        service = ChecklistService(database, RequestContext())
        first = await service.initialize(actor, session_id)
        second = await service.initialize(actor, session_id)

    assert first["responses_added"] == 0
    assert second["responses_added"] == 0

    async with phase13_stage2.factory() as database:
        count = await database.scalar(
            select(func.count())
            .select_from(ChecklistResponse)
            .where(ChecklistResponse.test_session_id == session_id)
        )

    assert count == initial_count
    assert count == first["catalog_total"]
    assert count == second["catalog_total"]


async def test_phase13_candidate_catalog_initializes_as_review_blocked(
    client,
    phase13_stage2,
):
    session_path, _ = await start_phase12_examination(
        client,
        phase13_stage2,
    )
    session_id = UUID(session_path.rsplit("/", 1)[1])
    actor = await actor_for(phase13_stage2)

    async with phase13_stage2.factory() as database:
        service = ChecklistService(database, RequestContext())
        initialized = await service.initialize(actor, session_id)

    assert initialized["catalog_total"] > 0
    assert initialized["evaluation_status"] == "REVIEW_REQUIRED"
    assert initialized["compliance_outcome"] == "UNDETERMINED"
    assert initialized["review_required"] == initialized["catalog_total"]


async def test_phase13_candidate_rows_are_not_editable(
    client,
    phase13_stage2,
):
    session_path, _ = await start_phase12_examination(
        client,
        phase13_stage2,
    )
    session_id = UUID(session_path.rsplit("/", 1)[1])
    actor = await actor_for(phase13_stage2)

    async with phase13_stage2.factory() as database:
        service = ChecklistService(database, RequestContext())
        await service.initialize(actor, session_id)
        rows = await service.rows(actor, session_id)
        first = rows[0]
        with pytest.raises(AppError) as captured:
            await service.patch(
                actor,
                session_id,
                UUID(first["checklist_rule_id"]),
                f'"{first["lock_version"]}"',
                ChecklistResponsePatch(response_result="PASS"),
            )

    assert captured.value.code == "CHECKLIST_ROW_NOT_EDITABLE"
