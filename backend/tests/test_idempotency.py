import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import AppError, denied
from app.models import IdempotencyKey
from app.services.idempotency import IdempotencyService

pytestmark = pytest.mark.asyncio


async def permitted():
    return None


async def test_persistent_replay_conflict_and_authorization(world):
    key = uuid4().hex
    actor = world.users["admin"].id
    async with world.factory() as session:
        service = IdempotencyService(session)
        first = await service.reserve(
            actor, "GLOBAL", "fixture-action", key, {"value": 1}, permitted
        )
        assert not first.replay
    # Simulates a new worker/process: no process-local reservation state.
    async with world.factory() as session:
        service = IdempotencyService(session)
        with pytest.raises(AppError) as exc:
            await service.reserve(actor, "GLOBAL", "fixture-action", key, {"value": 1}, permitted)
        assert exc.value.code == "OPERATION_IN_PROGRESS"
        with pytest.raises(AppError) as exc:
            await service.reserve(actor, "GLOBAL", "fixture-action", key, {"value": 2}, permitted)
        assert exc.value.code == "IDEMPOTENCY_CONFLICT"
        async with session.begin():
            await service.complete(
                first.id, actor, "GLOBAL", 201, {"id": "fixture"}, {"schema_version": 1, "ids": []}
            )

    async def forbidden():
        raise denied()

    async with world.factory() as session:
        service = IdempotencyService(session)
        with pytest.raises(AppError) as exc:
            await service.reserve(actor, "GLOBAL", "fixture-action", key, {"value": 1}, forbidden)
        assert exc.value.status == 403
        replay = await service.reserve(
            actor, "GLOBAL", "fixture-action", key, {"value": 1}, permitted
        )
        assert (
            replay.replay
            and replay.response_status == 201
            and replay.response_body == {"id": "fixture"}
        )


async def test_concurrent_reservation_and_atomic_completion(world):
    actor = world.users["admin"].id
    key = uuid4().hex

    async def reserve():
        async with world.factory() as session:
            try:
                return await IdempotencyService(session).reserve(
                    actor, "GLOBAL", "fixture-action", key, {}, permitted
                )
            except AppError as exc:
                return exc

    results = await asyncio.gather(reserve(), reserve())
    assert sum(isinstance(r, AppError) for r in results) == 1
    reservation = next(r for r in results if not isinstance(r, AppError))
    with pytest.raises(RuntimeError):
        async with world.factory() as session, session.begin():
            await IdempotencyService(session).complete(reservation.id, actor, "GLOBAL", 200, {}, {})
            raise RuntimeError("mutation failed")
    async with world.factory() as session:
        row = await session.scalar(
            select(IdempotencyKey).where(IdempotencyKey.id == reservation.id)
        )
        assert row.operation_status == "IN_PROGRESS"
