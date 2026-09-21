from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def reserve(self, **values):
        identifier = uuid4()
        inserted = await self.session.scalar(
            insert(IdempotencyKey)
            .values(id=identifier, **values)
            .on_conflict_do_nothing(constraint="uq_idempotency_request")
            .returning(IdempotencyKey.id)
        )
        row = await self.session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.actor_id == values["actor_id"],
                IdempotencyKey.scope_key == values["scope_key"],
                IdempotencyKey.operation == values["operation"],
                IdempotencyKey.key == values["key"],
            )
        )
        return row, inserted is not None

    async def locked(self, identifier: UUID):
        return await self.session.scalar(
            select(IdempotencyKey).where(IdempotencyKey.id == identifier).with_for_update()
        )
