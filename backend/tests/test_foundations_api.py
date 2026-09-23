"""Real PostgreSQL API tests. Storage double is isolated; live script tests real storage."""

import hashlib
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.api.dependencies import object_storage
from app.core.errors import AppError
from app.models import Attachment, AttachmentUpload, AuditEvent, UserRoleAssignment
from app.services.rulesets import seed_phase3
from app.storage.objects import ObjectStorage, StoredObject
from tests.conftest import login
from tests.test_storage import PDF


class MemoryStorage(ObjectStorage):
    provider = "minio"

    def __init__(self):
        self.objects = {}

    async def ready(self):
        return None

    async def presign_upload(self, key, content_type, size, seconds):
        return "https://private.invalid/" + key

    async def read(self, key, version=None):
        return self.objects[key]

    async def publish(self, key, obj):
        self.objects[key] = obj
        return "immutable-v1"

    async def presign_download(self, key, version, seconds):
        assert key in self.objects
        return "https://private.invalid/download?signature=SECRET"

    async def delete_staged(self, key):
        if not key.startswith("staged/"):
            raise AppError(
                422,
                "INVALID_STORAGE_KEY",
                "Cleanup is restricted to staged upload objects",
            )
        return 1 if self.objects.pop(key, None) is not None else 0


@pytest_asyncio.fixture
async def foundation(world):
    async with world.factory() as session, session.begin():
        for name, lab in (("local", 0), ("other", 1), ("officer", 0)):
            session.add(
                UserRoleAssignment(
                    user_id=world.users[name].id,
                    role_id=world.roles["LAB_TECHNICIAN"],
                    scope_type="LABORATORY",
                    laboratory_id=world.labs[lab].id,
                    assigned_by=world.users["admin"].id,
                )
            )
    async with world.factory() as session:
        world.ruleset_id = await seed_phase3(session)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def equipment(client, world):
    await login(client, world, "local")
    result = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "Mass standard",
            "reference_number": uuid4().hex,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


async def stage(client, world, row):
    result = await client.post(
        "/api/v1/attachments/presign",
        headers={"If-Match": f'"{row["lock_version"]}"'},
        json={
            "laboratory_id": row["laboratory_id"],
            "entity_type": "test_equipment",
            "entity_id": row["id"],
            "purpose": "calibration",
            "file_name": "certificate.pdf",
            "content_type": "application/pdf",
            "file_size": len(PDF),
            "sha256": hashlib.sha256(PDF).hexdigest(),
        },
    )
    assert result.status_code == 201, result.text
    async with world.factory() as session:
        upload = await session.get(AttachmentUpload, UUID(result.json()["upload_id"]))
        world.storage.objects[upload.storage_key] = StoredObject(
            PDF, "application/pdf", "staged-v1"
        )
    return result.json(), upload


@pytest.mark.asyncio
async def test_catalog_inspection_and_verification_gate(client, foundation):
    world = foundation
    await login(client, world)
    result = await client.get("/api/v1/rulesets/" + world.ruleset_id)
    assert result.status_code == 200
    version = result.headers["etag"]
    tests = (await client.get(f"/api/v1/rulesets/{world.ruleset_id}/tests")).json()["items"]
    assert len(tests) == 28
    assert {t["section_number"] for t in tests if t["parent_definition_id"] is None} == set(
        range(1, 18)
    )
    assert not any(t["implemented"] or t["supported"] for t in tests)
    assert (await client.get(f"/api/v1/rulesets/{world.ruleset_id}/checklist")).json()[
        "total"
    ] == 27
    denied = await client.post(
        f"/api/v1/rulesets/{world.ruleset_id}/activate", headers={"If-Match": version}
    )
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "RULESET_NOT_VERIFIED"
    valid = await client.post(
        f"/api/v1/rulesets/{world.ruleset_id}/validate", headers={"If-Match": version}
    )
    assert valid.status_code == 200 and not valid.json()["validation_summary"]["authoritative"]
    await login(client, world, "viewer")
    assert (await client.get("/api/v1/rulesets")).status_code == 200
    assert (
        await client.post(
            f"/api/v1/rulesets/{world.ruleset_id}/validate",
            headers={"If-Match": valid.headers["etag"]},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_equipment_crud_versions_lifecycle_and_audit(client, foundation):
    world = foundation
    row = await equipment(client, world)
    path = "/api/v1/test-equipment/" + row["id"]
    assert (await client.get(path)).status_code == 200
    assert (await client.get("/api/v1/test-equipment")).json()["total"] >= 1
    assert (await client.patch(path, json={"model": "A"})).status_code == 428
    changed = await client.patch(path, json={"model": "A"}, headers={"If-Match": '"1"'})
    assert changed.status_code == 200 and changed.headers["etag"] == '"2"'
    assert (
        await client.patch(path, json={"model": "B"}, headers={"If-Match": '"1"'})
    ).status_code == 412
    archived = await client.post(
        path + "/archive", json={"reason": "Retired"}, headers={"If-Match": '"2"'}
    )
    assert archived.status_code == 200 and not archived.json()["is_active"]
    assert (
        await client.patch(path, json={"model": "C"}, headers={"If-Match": '"3"'})
    ).status_code == 409
    async with world.factory() as session:
        events = (
            await session.scalars(select(AuditEvent).where(AuditEvent.entity_id == UUID(row["id"])))
        ).all()
        assert len(events) == 3
        assert {e.action for e in events} == {
            "equipment.created",
            "equipment.updated",
            "equipment.archived",
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("name,status", [("viewer", 403), ("admin", 403), ("other", 404)])
async def test_equipment_permissions_and_lab_isolation(client, foundation, name, status):
    row = await equipment(client, foundation)
    await login(client, foundation, name)
    path = "/api/v1/test-equipment/" + row["id"]
    assert (
        await client.patch(path, json={"model": "denied"}, headers={"If-Match": '"1"'})
    ).status_code == status
    if name == "other":
        assert (await client.get(path)).status_code == 404
        assert (
            await client.get(
                "/api/v1/test-equipment", params={"laboratory_id": row["laboratory_id"]}
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_attachment_roundtrip_link_archive_and_private_audit(client, foundation):
    world = foundation
    row = await equipment(client, world)
    staged, _ = await stage(client, world, row)
    complete = await client.post(
        "/api/v1/attachments/complete",
        json={"upload_id": staged["upload_id"]},
        headers={"If-Match": '"1"'},
    )
    assert complete.status_code == 201, complete.text
    item = complete.json()
    path = "/api/v1/attachments/" + item["id"]
    download = await client.get(path + "/download")
    assert (
        download.status_code == 200 and download.json()["sha256"] == hashlib.sha256(PDF).hexdigest()
    )
    assert (
        await client.delete(path, params={"reason": "blocked"}, headers={"If-Match": '"1"'})
    ).status_code == 409
    second = await equipment(client, world)
    linked = await client.post(
        path + "/link",
        json={"entity_type": "test_equipment", "entity_id": second["id"], "purpose": "supporting"},
        headers={"If-Match": '"1"'},
    )
    assert linked.status_code == 201
    for link_id, match in (
        (item["link_id"], item["target_etag"]),
        (linked.json()["id"], linked.json()["target_etag"]),
    ):
        response = await client.delete(
            path + "/links/" + link_id,
            params={"reason": "Incorrect association"},
            headers={"If-Match": match},
        )
        assert response.status_code == 200
    assert (
        await client.delete(
            path,
            params={"reason": "Retired"},
            headers={"If-Match": response.json()["attachment_etag"]},
        )
    ).status_code == 204
    assert (await client.get(path + "/download")).status_code == 409
    async with world.factory() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.laboratory_id == world.labs[0].id)
            )
        ).all()
        payload = str([(e.before_json, e.after_json) for e in events])
        assert "SECRET" not in payload and "signature" not in payload and "https://" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["size", "mime", "hash", "expired", "forged_key", "target_changed"]
)
async def test_failed_finalization_never_publishes(client, foundation, kind):
    world = foundation
    row = await equipment(client, world)
    staged, upload = await stage(client, world, row)
    if kind in ("size", "mime", "hash"):
        body = (
            PDF + b"x"
            if kind == "size"
            else PDF.replace(b"Catalog", b"catalog")
            if kind == "hash"
            else PDF
        )
        world.storage.objects[upload.storage_key] = StoredObject(
            body, "text/plain" if kind == "mime" else "application/pdf", "v1"
        )
    elif kind == "target_changed":
        assert (
            await client.patch(
                "/api/v1/test-equipment/" + row["id"],
                json={"model": "Changed"},
                headers={"If-Match": '"1"'},
            )
        ).status_code == 200
    else:
        async with world.factory() as session, session.begin():
            persisted = await session.get(AttachmentUpload, upload.id)
            if kind == "expired":
                from datetime import UTC, datetime, timedelta

                persisted.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            else:
                persisted.storage_key = (
                    f"staged/{world.labs[1].id}/{world.users['other'].id}/{uuid4().hex}"
                )
    response = await client.post(
        "/api/v1/attachments/complete",
        json={"upload_id": staged["upload_id"]},
        headers={"If-Match": '"1"'},
    )
    assert response.status_code in (409, 410, 412, 422), response.text
    async with world.factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.laboratory_id == world.labs[0].id)
            )
            == 0
        )
        persisted = await session.get(AttachmentUpload, upload.id)
        assert persisted.completed_attachment_id is None
        assert not await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.laboratory_id == world.labs[0].id,
                AuditEvent.action == "attachment.finalized",
            )
        )


@pytest.mark.asyncio
async def test_attachment_owner_cross_lab_and_protected_targets(client, foundation):
    world = foundation
    row = await equipment(client, world)
    staged, _ = await stage(client, world, row)
    await login(client, world, "officer")
    response = await client.post(
        "/api/v1/attachments/complete",
        json={"upload_id": staged["upload_id"]},
        headers={"If-Match": '"1"'},
    )
    assert response.status_code == 404  # Same laboratory, different upload owner.
    await login(client, world, "other")
    assert (
        await client.post(
            "/api/v1/attachments/complete",
            json={"upload_id": staged["upload_id"]},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 404
    await login(client, world, "local")
    complete = await client.post(
        "/api/v1/attachments/complete",
        json={"upload_id": staged["upload_id"]},
        headers={"If-Match": '"1"'},
    )
    assert complete.status_code == 201
    item = complete.json()
    await login(client, world, "other")
    assert (await client.get(f"/api/v1/attachments/{item['id']}/download")).status_code == 404
    other = await client.post(
        "/api/v1/test-equipment", json={"laboratory_id": str(world.labs[1].id), "category": "Mass"}
    )
    await login(client, world, "local")
    assert (
        await client.post(
            f"/api/v1/attachments/{item['id']}/link",
            json={
                "entity_type": "test_equipment",
                "entity_id": other.json()["id"],
                "purpose": "cross",
            },
            headers={"If-Match": '"1"'},
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/attachments/{item['id']}/link",
            json={"entity_type": "test_equipment", "entity_id": str(uuid4()), "purpose": "missing"},
            headers={"If-Match": '"1"'},
        )
    ).status_code == 404
    # A user authorized in both laboratories still cannot cross-link evidence.
    async with world.factory() as session, session.begin():
        session.add(
            UserRoleAssignment(
                user_id=world.users["local"].id,
                role_id=world.roles["LAB_TECHNICIAN"],
                scope_type="LABORATORY",
                laboratory_id=world.labs[1].id,
                assigned_by=world.users["admin"].id,
            )
        )
    response = await client.post(
        f"/api/v1/attachments/{item['id']}/link",
        json={"entity_type": "test_equipment", "entity_id": other.json()["id"], "purpose": "cross"},
        headers={"If-Match": '"1"'},
    )
    assert response.status_code == 409
    assert (
        await client.post(
            f"/api/v1/test-equipment/{row['id']}/archive",
            json={"reason": "Retired"},
            headers={"If-Match": item["target_etag"]},
        )
    ).status_code == 200
    assert (
        await client.delete(
            f"/api/v1/attachments/{item['id']}/links/{item['link_id']}",
            params={"reason": "Blocked"},
            headers={"If-Match": '"3"'},
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_catalog_database_immutability(foundation):
    for query in (
        "UPDATE rule_sets SET configuration_hash = 'tampered' WHERE id = :id",
        "UPDATE test_definitions SET implemented = true WHERE rule_set_id = :id",
    ):
        with pytest.raises(DBAPIError):
            async with foundation.factory() as session, session.begin():
                await session.execute(text(query), {"id": UUID(foundation.ruleset_id)})
