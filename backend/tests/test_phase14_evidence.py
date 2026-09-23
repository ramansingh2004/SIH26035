"""Phase 14 Stage 1 staged-evidence cleanup/retry integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models import AttachmentUpload, AuditEvent
from app.services.audit import RequestContext
from app.services.evidence_maintenance import EvidenceMaintenanceService
from app.storage.objects import StoredObject
from tests.test_foundations_api import MemoryStorage
from tests.test_storage import PDF

pytestmark = pytest.mark.asyncio


def upload_row(world, *, status="PENDING", expired=True):
    identifier = uuid4()
    lab = world.labs[0].id
    user = world.users["local"].id
    return AttachmentUpload(
        id=identifier,
        laboratory_id=lab,
        requested_by=user,
        target_type="test_equipment",
        target_id=uuid4(),
        purpose="calibration",
        storage_key=f"staged/{lab}/{user}/{identifier.hex}",
        expected_file_name="phase14.pdf",
        expected_content_type="application/pdf",
        expected_size=len(PDF),
        expected_sha256="0" * 64,
        upload_status=status,
        expires_at=datetime.now(UTC)
        + (timedelta(minutes=-1) if expired else timedelta(minutes=10)),
    )


async def success_events(world, identifier):
    async with world.factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "attachment.staged_deleted",
                AuditEvent.entity_type == "attachment_uploads",
                AuditEvent.entity_id == identifier,
            )
        )


async def test_phase14_expired_staged_upload_cleanup_is_idempotent(world):
    storage = MemoryStorage()
    row = upload_row(world)

    async with world.factory() as session, session.begin():
        session.add(row)

    storage.objects[row.storage_key] = StoredObject(
        PDF,
        "application/pdf",
        "staged-v1",
    )

    async with world.factory() as session:
        service = EvidenceMaintenanceService(
            session,
            storage,
            RequestContext(),
        )
        first = await service.cleanup_once()
        second = await service.cleanup_once()

    assert first["scanned"] >= 1
    assert first["cleaned"] == first["scanned"]
    assert first["failed"] == 0
    assert first["deleted_versions"] >= 1
    assert second == {
        "scanned": 0,
        "cleaned": 0,
        "failed": 0,
        "deleted_versions": 0,
    }
    assert row.storage_key not in storage.objects

    async with world.factory() as session:
        persisted = await session.get(AttachmentUpload, row.id)
        assert persisted.upload_status == "EXPIRED"

    assert await success_events(world, row.id) == 1


class FlakyStorage(MemoryStorage):
    def __init__(self):
        super().__init__()
        self.fail_key = None
        self.failures = 1

    async def delete_staged(self, key):
        if key == self.fail_key and self.failures:
            self.failures -= 1
            raise AppError(
                503,
                "STORAGE_UNAVAILABLE",
                "Injected Phase 14 cleanup failure",
            )
        return await super().delete_staged(key)


async def test_phase14_failed_cleanup_remains_retryable(world):
    storage = FlakyStorage()
    row = upload_row(world, status="FAILED", expired=False)

    async with world.factory() as session, session.begin():
        session.add(row)

    storage.objects[row.storage_key] = StoredObject(
        PDF,
        "application/pdf",
        "staged-v1",
    )
    storage.fail_key = row.storage_key

    async with world.factory() as session:
        service = EvidenceMaintenanceService(
            session,
            storage,
            RequestContext(),
        )

        first = await service.cleanup_once()
        assert first["scanned"] >= 1
        assert first["failed"] >= 1
        assert row.storage_key in storage.objects
        assert await success_events(world, row.id) == 0

        second = await service.cleanup_once()
        assert second["scanned"] >= 1
        assert row.storage_key not in storage.objects
        assert await success_events(world, row.id) == 1

        third = await service.cleanup_once()

    assert third["scanned"] == 0
    assert row.storage_key not in storage.objects
    assert await success_events(world, row.id) == 1


async def test_phase14_cleanup_never_accepts_published_evidence_key(world):
    storage = MemoryStorage()
    evidence_key = f"evidence/{uuid4()}/{uuid4()}/{uuid4().hex}"
    storage.objects[evidence_key] = StoredObject(
        PDF,
        "application/pdf",
        "immutable-v1",
    )

    with pytest.raises(AppError) as error:
        await storage.delete_staged(evidence_key)

    assert error.value.code == "INVALID_STORAGE_KEY"
    assert evidence_key in storage.objects
