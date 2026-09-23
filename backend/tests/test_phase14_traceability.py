"""Phase 14 Stage 2 equipment/evidence and environment traceability tests."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.api.dependencies import object_storage
from app.models import Attachment, AttachmentLink
from app.models.testing import TestRun as RunRecord
from app.models.testing import TestSession as SessionRecord
from app.schemas.testing import EnvironmentData
from app.services.audit import RequestContext
from tests.phase5_fixtures import (
    SyntheticTestingService,
    install_synthetic,
    populate,
    prepare_world,
    seed_evidence,
    started_run,
)
from tests.test_foundations_api import MemoryStorage

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase14(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def test_phase14_environment_row_requires_actual_measurement():
    with pytest.raises(ValueError):
        EnvironmentData.model_validate(
            {
                "measured_at": "2000-01-01T00:00:00Z",
                "phase": "INITIAL",
            }
        )

    with pytest.raises(ValueError):
        EnvironmentData.model_validate(
            {
                "measured_at": "2000-01-01T00:00:00Z",
                "temperature_c": "20",
                "phase": "   ",
            }
        )


async def test_phase14_multi_day_environment_is_chronological_and_captured(
    client,
    phase14,
):
    session_path, run_path, _ = await started_run(client, phase14)
    await populate(client, phase14, run_path)

    for measured_at, phase, temperature in (
        ("2000-01-03T00:00:00Z", "AFTER", "22"),
        ("2000-01-02T00:00:00Z", "DURING", "21"),
    ):
        current = await client.get(run_path)
        response = await client.post(
            run_path + "/environment",
            headers={"If-Match": current.headers["etag"]},
            json={
                "measured_at": measured_at,
                "temperature_c": temperature,
                "phase": phase,
            },
        )
        assert response.status_code == 201, response.text

    rows = (await client.get(run_path + "/environment")).json()
    assert [row["measured_at"] for row in rows] == [
        "2000-01-01T00:00:00Z",
        "2000-01-02T00:00:00Z",
        "2000-01-03T00:00:00Z",
    ]

    await seed_evidence(phase14, run_path.rsplit("/", 1)[1])

    async with phase14.factory() as database:
        service = SyntheticTestingService(database, RequestContext())
        session = await database.get(
            SessionRecord,
            UUID(session_path.rsplit("/", 1)[1]),
        )
        run = await database.get(
            RunRecord,
            UUID(run_path.rsplit("/", 1)[1]),
        )
        _, snapshot, _ = await service.capture(session, run)

    environment = snapshot.procedure_context.environment
    assert [item.measured_at.isoformat().replace("+00:00", "Z") for item in environment] == [
        "2000-01-01T00:00:00Z",
        "2000-01-02T00:00:00Z",
        "2000-01-03T00:00:00Z",
    ]


async def test_phase14_calibration_evidence_identity_is_frozen_and_link_protected(
    client,
    phase14,
):
    _, run_path, _ = await started_run(client, phase14)

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(phase14.labs[0].id),
            "category": "SYNTHETIC_REFERENCE_STANDARD",
            "reference_number": "PHASE14-" + uuid4().hex,
            "calibration_certificate_no": "SYNTHETIC-CERT",
            "calibration_date": "2000-01-01",
            "calibration_due_date": "2000-12-31",
        },
    )
    assert equipment.status_code == 201, equipment.text

    certificate_id = uuid4()
    certificate_sha = "c" * 64
    async with phase14.factory() as database, database.begin():
        database.add(
            Attachment(
                id=certificate_id,
                laboratory_id=phase14.labs[0].id,
                attachment_type="EVIDENCE",
                file_name="synthetic-calibration.pdf",
                content_type="application/pdf",
                file_size=1,
                storage_provider="minio",
                storage_key="SYNTHETIC/" + uuid4().hex,
                object_version="synthetic-version-1",
                sha256=certificate_sha,
                uploaded_by=phase14.users["local"].id,
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
    payload = linked.json()

    snapshot = payload["equipment_snapshot"]
    assert snapshot["calibration_attachment_id"] == str(certificate_id)
    assert snapshot["calibration_attachment_sha256"] == certificate_sha
    assert snapshot["calibration_attachment_object_version"] == "synthetic-version-1"
    assert snapshot["regulatory_validation_status"] == "TODO_REGULATORY_VALIDATION"

    async with phase14.factory() as database:
        evidence_link = await database.scalar(
            select(AttachmentLink).where(
                AttachmentLink.attachment_id == certificate_id,
                AttachmentLink.entity_type == "test_run_equipment",
                AttachmentLink.entity_id == UUID(payload["id"]),
                AttachmentLink.purpose == "calibration",
                AttachmentLink.unlinked_at.is_(None),
            )
        )
    assert evidence_link is not None

    unlink = await client.delete(
        f"/api/v1/attachments/{certificate_id}/links/{evidence_link.id}",
        params={"reason": "Attempt to break calibration evidence mapping"},
        headers={"If-Match": f'"{payload["lock_version"]}"'},
    )
    assert unlink.status_code == 409, unlink.text
    assert unlink.json()["error"]["code"] == "EVIDENCE_PROTECTED"

    archive = await client.delete(
        f"/api/v1/attachments/{certificate_id}",
        params={"reason": "Attempt to archive bound calibration evidence"},
        headers={"If-Match": '"1"'},
    )
    assert archive.status_code == 409, archive.text
    assert archive.json()["error"]["code"] == "PROTECTED_EVIDENCE"
