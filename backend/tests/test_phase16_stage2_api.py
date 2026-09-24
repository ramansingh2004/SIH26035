"""Phase 16 Stage 2 unofficial preview API and private-file acceptance."""

from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.api.dependencies import object_storage
from app.models import Attachment
from tests.conftest import login
from tests.phase5_fixtures import create_session, prepare_world
from tests.test_foundations_api import MemoryStorage

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase16_stage2(world):
    world = await prepare_world(world)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def create_preview(client, world):
    created, _, _ = await create_session(client, world)
    session_path = "/api/v1/test-sessions/" + created.json()["id"]
    response = await client.post(
        session_path + "/report-previews",
        headers={"If-Match": created.headers["etag"]},
    )
    assert response.status_code == 201, response.text
    return created, session_path, response


async def test_unofficial_preview_allows_incomplete_session_and_publishes_pair(
    client,
    phase16_stage2,
):
    world = phase16_stage2
    created, _, response = await create_preview(client, world)
    preview = response.json()

    assert preview["preview_status"] == "READY"
    assert preview["source_regulatory_revision"] == created.json()["regulatory_revision"]
    context = preview["preview_context_snapshot"]
    assert context["document_kind"] == "UNOFFICIAL_PREVIEW"
    assert context["document_control"]["report_number"] is None
    assert context["document_control"]["revision_no"] is None
    assert context["document_control"]["report_status"] == "UNOFFICIAL_PREVIEW"
    assert len(context["regulatory_record"]["sections"]) == 17

    ids = preview["file_attachment_ids"]
    assert set(ids) == {"pdf", "docx"}

    async with world.factory() as database:
        attachments = [
            await database.get(Attachment, UUID(ids[file_format]))
            for file_format in ("pdf", "docx")
        ]
    pdf, docx = attachments
    assert pdf.attachment_type == "REPORT_PREVIEW"
    assert docx.attachment_type == "REPORT_PREVIEW"
    assert pdf.content_type == "application/pdf"
    assert (
        docx.content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert pdf.storage_key.startswith("previews/")
    assert docx.storage_key.startswith("previews/")
    assert world.storage.objects[pdf.storage_key].body.startswith(b"%PDF-")
    assert world.storage.objects[docx.storage_key].body.startswith(b"PK")


async def test_preview_read_download_and_cross_lab_isolation(
    client,
    phase16_stage2,
):
    world = phase16_stage2
    _, _, created = await create_preview(client, world)
    preview = created.json()
    preview_path = "/api/v1/report-previews/" + preview["id"]

    detail = await client.get(preview_path)
    assert detail.status_code == 200
    assert detail.json()["context_hash"] == preview["context_hash"]

    for file_format in ("pdf", "docx"):
        download = await client.get(
            preview_path + "/download",
            params={"format": file_format},
        )
        assert download.status_code == 200, download.text
        assert download.json()["format"] == file_format
        assert download.json()["download_url"].startswith("https://private.invalid/download")

    await login(client, world, "other")
    assert (await client.get(preview_path)).status_code == 404
    assert (
        await client.get(
            preview_path + "/download",
            params={"format": "pdf"},
        )
    ).status_code == 404


async def test_preview_generation_permission_is_not_global_admin_wildcard(
    client,
    phase16_stage2,
):
    world = phase16_stage2
    created, _, _ = await create_session(client, world)

    await login(client, world, "admin")
    response = await client.post(
        "/api/v1/test-sessions/" + created.json()["id"] + "/report-previews",
        headers={"If-Match": created.headers["etag"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_preview_context_is_frozen_after_live_master_change(
    client,
    phase16_stage2,
):
    world = phase16_stage2
    _, _, created = await create_preview(client, world)
    preview = created.json()
    old_name = preview["preview_context_snapshot"]["regulatory_record"]["laboratory"]["name"]

    async with world.factory() as database, database.begin():
        lab = await database.get(type(world.labs[0]), world.labs[0].id)
        lab.name = "Changed after preview capture"
        lab.lock_version += 1

    detail = await client.get("/api/v1/report-previews/" + preview["id"])
    assert detail.status_code == 200
    assert (
        detail.json()["preview_context_snapshot"]["regulatory_record"]["laboratory"]["name"]
        == old_name
    )


async def test_preview_renderer_failure_is_durable_and_has_no_partial_attachments(
    client,
    phase16_stage2,
    monkeypatch,
):
    world = phase16_stage2

    def fail(_context):
        raise RuntimeError("synthetic renderer failure")

    monkeypatch.setattr("app.services.report.render_pair", fail)
    created, _, _ = await create_session(client, world)
    response = await client.post(
        "/api/v1/test-sessions/" + created.json()["id"] + "/report-previews",
        headers={"If-Match": created.headers["etag"]},
    )
    assert response.status_code == 201, response.text
    preview = response.json()
    assert preview["preview_status"] == "FAILED"
    assert preview["error_code"] == "REPORT_GENERATION_FAILED"
    assert preview["file_attachment_ids"] == {}

    async with world.factory() as database:
        assert (
            await database.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(
                    Attachment.attachment_type == "REPORT_PREVIEW",
                    Attachment.metadata_json["report_preview_id"].astext == preview["id"],
                )
            )
            == 0
        )


async def test_active_preview_files_are_protected(
    client,
    phase16_stage2,
):
    world = phase16_stage2
    _, _, created = await create_preview(client, world)
    preview = created.json()
    attachment_id = preview["file_attachment_ids"]["pdf"]

    generic_download = await client.get("/api/v1/attachments/" + attachment_id + "/download")
    assert generic_download.status_code == 404

    blocked = await client.delete(
        "/api/v1/attachments/" + attachment_id,
        params={"reason": "Generated documents use report lifecycle APIs"},
        headers={"If-Match": '"1"'},
    )
    assert blocked.status_code == 404, blocked.text
