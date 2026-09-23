"""Phase 14 Stage 3 evidence-integrity and regression tests."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import object_storage
from app.models import Attachment, AttachmentLink
from app.models.testing import TestRunEquipment
from tests.conftest import login
from tests.phase5_fixtures import (
    install_synthetic,
    populate,
    prepare_world,
    seed_evidence,
    started_run,
)
from tests.test_foundations_api import MemoryStorage

pytestmark = pytest.mark.asyncio

TestRunEquipment.__test__ = False


@pytest_asyncio.fixture
async def phase14_stage3(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def _calibrated_run_equipment(client, world):
    _, run_path, _ = await started_run(client, world)

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC_REFERENCE_STANDARD",
            "reference_number": "PHASE14-STAGE3-" + uuid4().hex,
            "calibration_certificate_no": "SYNTHETIC-CERT",
            "calibration_date": "2000-01-01",
            "calibration_due_date": "2000-12-31",
        },
    )
    assert equipment.status_code == 201, equipment.text

    certificate_id = uuid4()
    certificate_sha = "d" * 64
    async with world.factory() as database, database.begin():
        database.add(
            Attachment(
                id=certificate_id,
                laboratory_id=world.labs[0].id,
                attachment_type="EVIDENCE",
                file_name="synthetic-calibration-stage3.pdf",
                content_type="application/pdf",
                file_size=1,
                storage_provider="minio",
                storage_key="SYNTHETIC/" + uuid4().hex,
                object_version="synthetic-stage3-v1",
                sha256=certificate_sha,
                uploaded_by=world.users["local"].id,
                metadata_json={"SYNTHETIC_TEST_FIXTURE_ONLY": True},
            )
        )

    current = await client.get(run_path)
    linked = await client.post(
        run_path + "/equipment/" + equipment.json()["id"],
        headers={"If-Match": current.headers["etag"]},
        json={"calibration_attachment_id": str(certificate_id)},
    )
    assert linked.status_code == 201, linked.text
    return run_path, linked.json(), certificate_id


async def test_phase14_cross_lab_calibration_certificate_is_hidden(
    client,
    phase14_stage3,
):
    world = phase14_stage3
    _, run_path, _ = await started_run(client, world)

    local_equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC",
            "reference_number": uuid4().hex,
        },
    )
    assert local_equipment.status_code == 201, local_equipment.text

    foreign_certificate = uuid4()
    async with world.factory() as database, database.begin():
        database.add(
            Attachment(
                id=foreign_certificate,
                laboratory_id=world.labs[1].id,
                attachment_type="EVIDENCE",
                file_name="foreign.pdf",
                content_type="application/pdf",
                file_size=1,
                storage_provider="minio",
                storage_key="SYNTHETIC/" + uuid4().hex,
                object_version="foreign-v1",
                sha256="e" * 64,
                uploaded_by=world.users["other"].id,
                metadata_json={"SYNTHETIC_TEST_FIXTURE_ONLY": True},
            )
        )

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/equipment/" + local_equipment.json()["id"],
        headers={"If-Match": current.headers["etag"]},
        json={"calibration_attachment_id": str(foreign_certificate)},
    )
    assert response.status_code == 404


async def test_phase14_capture_rejects_missing_calibration_link_integrity(
    client,
    phase14_stage3,
):
    world = phase14_stage3
    run_path, equipment_link, certificate_id = await _calibrated_run_equipment(
        client,
        world,
    )
    await populate(client, world, run_path)
    await seed_evidence(world, run_path.rsplit("/", 1)[1])

    async with world.factory() as database, database.begin():
        link = await database.scalar(
            select(AttachmentLink).where(
                AttachmentLink.attachment_id == certificate_id,
                AttachmentLink.entity_type == "test_run_equipment",
                AttachmentLink.entity_id == UUID(equipment_link["id"]),
                AttachmentLink.purpose == "calibration",
                AttachmentLink.unlinked_at.is_(None),
            )
        )
        assert link is not None
        link.unlinked_at = link.created_at

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "EVIDENCE_INTEGRITY_ERROR"


async def test_phase14_database_rejects_calibration_snapshot_mutation(
    client,
    phase14_stage3,
):
    world = phase14_stage3
    _, equipment_link, _ = await _calibrated_run_equipment(client, world)

    with pytest.raises(
        IntegrityError,
        match="Captured calibration snapshot is immutable",
    ):
        async with world.factory() as database, database.begin():
            row = await database.get(
                TestRunEquipment,
                UUID(equipment_link["id"]),
                with_for_update=True,
            )
            snapshot = dict(row.equipment_snapshot)
            snapshot["calibration_attachment_sha256"] = "f" * 64
            row.equipment_snapshot = snapshot


async def test_phase14_evidence_change_stales_current_result(
    client,
    phase14_stage3,
):
    world = phase14_stage3
    _, run_path, _ = await started_run(client, world)
    await populate(client, world, run_path)
    attachment_id = await seed_evidence(world, run_path.rsplit("/", 1)[1])

    current = await client.get(run_path)
    evaluated = await client.post(
        run_path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
    )
    assert evaluated.status_code == 200, evaluated.text

    observations = (await client.get(run_path + "/observations")).json()
    target = observations[0]

    linked = await client.post(
        f"/api/v1/attachments/{attachment_id}/link",
        json={
            "entity_type": "test_observations",
            "entity_id": target["id"],
            "purpose": "phase14_source_evidence",
        },
        headers={"If-Match": f'"{target["lock_version"]}"'},
    )
    assert linked.status_code == 201, linked.text

    stale = (await client.get(run_path)).json()
    assert stale["current_result_id"] is None
    assert stale["evaluation_status"] == "STALE"
    assert stale["compliance_outcome"] == "UNDETERMINED"


async def test_phase14_cross_lab_attachment_download_is_hidden(
    client,
    phase14_stage3,
):
    world = phase14_stage3
    foreign_id = uuid4()
    async with world.factory() as database, database.begin():
        database.add(
            Attachment(
                id=foreign_id,
                laboratory_id=world.labs[1].id,
                attachment_type="EVIDENCE",
                file_name="foreign-private.pdf",
                content_type="application/pdf",
                file_size=1,
                storage_provider="minio",
                storage_key="SYNTHETIC/" + uuid4().hex,
                object_version="foreign-private-v1",
                sha256="a" * 64,
                uploaded_by=world.users["other"].id,
                metadata_json={"SYNTHETIC_TEST_FIXTURE_ONLY": True},
            )
        )

    await login(client, world, "local")
    response = await client.get(f"/api/v1/attachments/{foreign_id}/download")
    assert response.status_code == 404
