"""Durable retry primitives. Future callers authorize BEFORE any stored replay."""

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.repositories.idempotency import IdempotencyRepository


@dataclass(frozen=True)
class Reservation:
    id: UUID
    replay: bool
    response_status: int | None
    response_body: dict | None


class IdempotencyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IdempotencyRepository(session)

    async def reserve(
        self,
        actor_id: UUID,
        scope_key: str,
        operation: str,
        key: str,
        payload: dict,
        authorize: Callable[[], Awaitable[None]],
    ) -> Reservation:
        if scope_key != "GLOBAL":
            scope_key = str(UUID(scope_key))
        if not 1 <= len(key) <= 200 or not 1 <= len(operation) <= 100:
            raise AppError(422, "INVALID_IDEMPOTENCY_KEY", "Invalid operation/key length")
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        async with self.session.begin():
            await authorize()
            row, created = await self.repo.reserve(
                actor_id=actor_id,
                scope_key=scope_key,
                operation=operation,
                key=key,
                request_hash=request_hash,
                operation_status="IN_PROGRESS",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                resource_ids={},
            )
            if not created:
                if row.request_hash != request_hash:
                    raise AppError(
                        409, "IDEMPOTENCY_CONFLICT", "Key already used with another payload"
                    )
                if row.operation_status != "SUCCEEDED":
                    raise AppError(
                        409,
                        "OPERATION_IN_PROGRESS",
                        "Operation needs reconciliation before retry",
                        {"retry_after_seconds": 2, "operation_status": row.operation_status},
                    )
            return Reservation(row.id, not created, row.response_status, row.response_body)

    async def complete(
        self,
        identifier: UUID,
        actor_id: UUID,
        scope_key: str,
        status: int,
        body: dict,
        resource_ids: dict,
    ):
        """Call INSIDE the owning mutation transaction, together with audit and changes."""
        if not self.session.in_transaction():
            raise RuntimeError("Idempotency completion requires the owning transaction")
        row = await self.repo.locked(identifier)
        if row is None or row.actor_id != actor_id or row.scope_key != scope_key:
            raise AppError(403, "PERMISSION_DENIED", "Reservation scope mismatch")
        if row.operation_status != "IN_PROGRESS":
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "Reservation is already finalized")
        row.operation_status = "SUCCEEDED"
        row.response_status, row.response_body, row.resource_ids = status, body, resource_ids
