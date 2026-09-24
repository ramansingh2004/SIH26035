"""Phase 16 Stage 3 official report generation, issue and revision acceptance."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.api.dependencies import object_storage
from app.compliance.canonical import content_hash
from app.core.errors import AppError
from app.models import Attachment
from app.models.report import Report, ReportFile
from app.models.review import ApprovalAction, SessionApprovalSnapshot
from app.models.testing import TestSession as SessionRecord
from app.services.report import ReportService
from tests.conftest import login
from tests.phase5_fixtures import install_synthetic, prepare_world
from tests.test_foundations_api import MemoryStorage
from tests.test_phase15_stage3 import (
    final_approve,
    technically_approved,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase16_stage3(world, monkeypatch):
    world = await prepare_world(world)
    await install_synthetic(world, monkeypatch)
    world.storage = MemoryStorage()
    world.app.dependency_overrides[object_storage] = lambda: world.storage
    return world


async def approved_session(client, world):
    session_path, _, _, _ = await technically_approved(client, world)
    approved, _ = await final_approve(client, world, session_path)
    assert approved.status_code == 200, approved.text
    assert approved.json()["workflow_status"] == "APPROVED"
    return session_path, approved


async def generate_report(client, world, session_path, *, date=None, key=None):
    await login(client, world, "officer")
    current = await client.get(session_path)
    issue_date = date or datetime.now(UTC).date()
    response = await client.post(
        session_path + "/reports",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": key or uuid4().hex,
        },
        json={
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": issue_date.isoformat(),
        },
    )
    return response


async def issue_report(client, report_body, *, key=None, predecessor=None):
    report = report_body["report"]
    generation = report_body["generation"]
    return await client.post(
        "/api/v1/reports/" + report["id"] + "/issue",
        headers={
            "If-Match": f'"{report["lock_version"]}"',
            "Idempotency-Key": key or uuid4().hex,
        },
        json={
            "generation_id": generation["id"],
            "expected_predecessor_id": predecessor,
        },
    )


async def test_official_noncompliant_generation_uses_approval_snapshot_and_pair(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, approved = await approved_session(client, world)

    session_id = UUID(approved.json()["id"])
    async with world.factory() as database:
        snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == session_id
            )
        )
        frozen_lab_name = snapshot.snapshot_json["laboratory"]["name"]

    async with world.factory() as database, database.begin():
        lab = await database.get(type(world.labs[0]), world.labs[0].id)
        lab.name = "Changed after final approval"
        lab.lock_version += 1

    generated = await generate_report(client, world, session_path)
    assert generated.status_code == 201, generated.text
    body = generated.json()
    report = body["report"]
    generation = body["generation"]
    files = body["files"]

    assert report["report_status"] == "UNISSUED"
    assert report["report_number"].startswith("R76-" + str(datetime.now(UTC).year) + "-")
    assert report["revision_no"] == 1
    assert generation["generation_status"] == "READY"
    assert generation["source_regulatory_revision"] == approved.json()["regulatory_revision"]
    assert (
        generation["report_context_snapshot"]["regulatory_record"]["laboratory"]["name"]
        == frozen_lab_name
    )
    assert (
        generation["report_context_snapshot"]["regulatory_record"]["session"]["compliance_outcome"]
        == "NONCOMPLIANT"
    )
    assert {row["format"] for row in files} == {"PDF", "DOCX"}
    assert generation["report_hash"]

    async with world.factory() as database:
        persisted = await database.get(Report, UUID(report["id"]))
        assert persisted.selected_generation_id is None
        assert (
            await database.scalar(
                select(func.count())
                .select_from(ReportFile)
                .where(ReportFile.report_generation_id == UUID(generation["id"]))
            )
            == 2
        )


async def test_per_report_repository_endpoints_and_download_are_lab_scoped(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    generated = await generate_report(client, world, session_path)
    assert generated.status_code == 201, generated.text
    body = generated.json()
    report_id = body["report"]["id"]

    detail = await client.get("/api/v1/reports/" + report_id)
    assert detail.status_code == 200
    assert detail.headers["etag"] == f'"{body["report"]["lock_version"]}"'

    generations = await client.get("/api/v1/reports/" + report_id + "/generations")
    assert generations.status_code == 200
    assert [row["attempt_no"] for row in generations.json()] == [1]

    files = await client.get("/api/v1/reports/" + report_id + "/files")
    assert files.status_code == 200
    assert {row["format"] for row in files.json()} == {"PDF", "DOCX"}

    for file_format in ("pdf", "docx"):
        download = await client.get(
            "/api/v1/reports/" + report_id + "/download",
            params={"format": file_format},
        )
        assert download.status_code == 200, download.text
        assert download.json()["report_status"] == "UNISSUED"
        assert download.json()["download_url"].startswith("https://private.invalid/download")

    await login(client, world, "other")
    assert (await client.get("/api/v1/reports/" + report_id)).status_code == 404
    assert (
        await client.get(
            "/api/v1/reports/" + report_id + "/download",
            params={"format": "pdf"},
        )
    ).status_code == 404


async def test_generation_idempotency_replays_without_competing_report(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    key = uuid4().hex

    first = await generate_report(
        client,
        world,
        session_path,
        key=key,
    )
    assert first.status_code == 201, first.text

    current = await client.get(session_path)
    replay = await client.post(
        session_path + "/reports",
        headers={
            "If-Match": '"0"',
            "Idempotency-Key": key,
        },
        json={
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": datetime.now(UTC).date().isoformat(),
        },
    )
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()

    session_id = UUID(current.json()["id"])
    async with world.factory() as database:
        assert (
            await database.scalar(
                select(func.count()).select_from(Report).where(Report.test_session_id == session_id)
            )
            == 1
        )


async def test_failed_generation_is_durable_and_regeneration_creates_new_attempt(
    client,
    phase16_stage3,
    monkeypatch,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)

    def fail(_context):
        raise RuntimeError("synthetic official renderer failure")

    monkeypatch.setattr("app.services.report.render_pair", fail)
    failed = await generate_report(client, world, session_path)
    assert failed.status_code == 201, failed.text
    body = failed.json()
    assert body["generation"]["generation_status"] == "FAILED"
    assert body["generation"]["error_code"] == "REPORT_GENERATION_FAILED"
    assert body["files"] == []

    from app.reporting.renderers import render_pair as real_render_pair

    monkeypatch.setattr("app.services.report.render_pair", real_render_pair)
    report = body["report"]
    regenerated = await client.post(
        "/api/v1/reports/" + report["id"] + "/regenerate",
        headers={
            "If-Match": f'"{report["lock_version"]}"',
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": datetime.now(UTC).date().isoformat(),
        },
    )
    assert regenerated.status_code == 201, regenerated.text
    retry = regenerated.json()
    assert retry["generation"]["attempt_no"] == 2
    assert retry["generation"]["generation_status"] == "READY"
    assert {row["format"] for row in retry["files"]} == {"PDF", "DOCX"}


async def test_issue_uses_exact_ready_bytes_and_is_idempotent(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    generated = await generate_report(client, world, session_path)
    assert generated.status_code == 201, generated.text
    body = generated.json()

    async with world.factory() as database:
        files = list(
            (
                await database.scalars(
                    select(ReportFile).where(
                        ReportFile.report_generation_id == UUID(body["generation"]["id"])
                    )
                )
            ).all()
        )
        attachments = [
            await database.get(
                Attachment,
                row.attachment_id,
            )
            for row in files
        ]
    bytes_before = {
        item.storage_key: world.storage.objects[item.storage_key].body for item in attachments
    }

    key = uuid4().hex
    issued = await issue_report(client, body, key=key)
    assert issued.status_code == 200, issued.text
    report = issued.json()
    assert report["report_status"] == "ISSUED"
    assert report["selected_generation_id"] == body["generation"]["id"]
    assert report["report_hash"] == body["generation"]["report_hash"]
    assert report["issuance_manifest"]["generation_id"] == body["generation"]["id"]

    for key_name, original in bytes_before.items():
        assert world.storage.objects[key_name].body == original

    replay = await client.post(
        "/api/v1/reports/" + report["id"] + "/issue",
        headers={
            "If-Match": '"0"',
            "Idempotency-Key": key,
        },
        json={
            "generation_id": body["generation"]["id"],
            "expected_predecessor_id": None,
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == report

    session = await client.get(session_path)
    assert session.json()["workflow_status"] == "REPORT_ISSUED"


async def test_issue_date_mismatch_requires_new_generation_attempt(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    generated = await generate_report(
        client,
        world,
        session_path,
        date=datetime.now(UTC).date() + timedelta(days=1),
    )
    assert generated.status_code == 201, generated.text

    issue = await issue_report(client, generated.json())
    assert issue.status_code == 409, issue.text
    assert issue.json()["error"]["code"] == "ISSUE_METADATA_MISMATCH"

    report = generated.json()["report"]
    regenerated = await client.post(
        "/api/v1/reports/" + report["id"] + "/regenerate",
        headers={
            "If-Match": f'"{report["lock_version"]}"',
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": datetime.now(UTC).date().isoformat(),
        },
    )
    assert regenerated.status_code == 201, regenerated.text
    assert regenerated.json()["generation"]["attempt_no"] == 2


async def test_reg17_blocks_nonverified_real_issue_context():
    snapshot = type(
        "Snapshot",
        (),
        {
            "snapshot_json": {
                "ruleset_record": {
                    "validation_summary": {
                        "authoritative": True,
                    }
                }
            }
        },
    )()
    with pytest.raises(AppError) as caught:
        ReportService._reg17_issue_gate(snapshot)
    assert getattr(caught.value, "code", None) == "TODO_REGULATORY_VALIDATION"


async def _approved_child_fixture(client, world, session_path, *, outcome="NONCOMPLIANT"):
    parent = await client.get(session_path)
    child = await client.post(
        session_path + "/revisions",
        headers={
            "If-Match": parent.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={"reason": "Synthetic post-issue report revision fixture."},
    )
    assert child.status_code == 201, child.text
    body = child.json()
    child_id = UUID(body["id"])
    parent_id = UUID(parent.json()["id"])

    async with world.factory() as database:
        parent_snapshot = await database.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == parent_id
            )
        )

    async with world.factory() as database, database.begin():
        row = await database.get(
            SessionRecord,
            child_id,
            with_for_update=True,
        )
        row.workflow_status = "APPROVED"
        row.evaluation_status = "COMPLETE"
        row.compliance_outcome = outcome
        row.approved_at = datetime.now(UTC)
        row.completed_at = row.approved_at
        row.lock_version += 1

        action = ApprovalAction(
            id=uuid4(),
            test_session_id=row.id,
            stage="FINAL_APPROVAL",
            decision="APPROVED",
            actor_id=world.users["officer"].id,
            regulatory_revision=row.regulatory_revision,
            scope_json={
                "schema_version": 1,
                "scope": "SYNTHETIC_REPORT_REVISION_FIXTURE",
            },
        )
        database.add(action)
        await database.flush()

        snapshot_json = deepcopy(parent_snapshot.snapshot_json)
        snapshot_json["session"] = deepcopy(snapshot_json["session"])
        snapshot_json["session"].update(
            {
                "id": str(row.id),
                "parent_session_id": str(row.parent_session_id),
                "root_session_id": str(row.root_session_id),
                "session_revision_no": row.session_revision_no,
                "revision_reason": row.revision_reason,
                "workflow_status": "APPROVED",
                "evaluation_status": "COMPLETE",
                "compliance_outcome": outcome,
                "regulatory_revision": row.regulatory_revision,
                "lock_version": row.lock_version,
            }
        )
        if outcome == "COMPLIANT":
            for section in snapshot_json.get("sections", []):
                if section.get("compliance_outcome") == "NONCOMPLIANT":
                    section["compliance_outcome"] = "COMPLIANT"
            for run in snapshot_json.get("runs", []):
                if run.get("compliance_outcome") == "NONCOMPLIANT":
                    run["compliance_outcome"] = "COMPLIANT"
            for result in snapshot_json.get("results", []):
                if result.get("compliance_outcome") == "NONCOMPLIANT":
                    result["compliance_outcome"] = "COMPLIANT"

        snapshot_json["approval_actions"] = [
            {
                "id": str(action.id),
                "test_session_id": str(row.id),
                "stage": "FINAL_APPROVAL",
                "decision": "APPROVED",
                "actor_id": str(world.users["officer"].id),
                "regulatory_revision": row.regulatory_revision,
                "scope_json": action.scope_json,
                "referenced_action_id": None,
                "comment": None,
                "reason": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        database.add(
            SessionApprovalSnapshot(
                id=uuid4(),
                test_session_id=row.id,
                approval_action_id=action.id,
                regulatory_revision=row.regulatory_revision,
                snapshot_schema_version=1,
                snapshot_json=snapshot_json,
                snapshot_hash=content_hash(snapshot_json),
                captured_by=world.users["officer"].id,
            )
        )
    return body


async def test_compliant_approved_snapshot_generates_official_pair(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    child = await _approved_child_fixture(
        client,
        world,
        session_path,
        outcome="COMPLIANT",
    )

    child_path = "/api/v1/test-sessions/" + child["id"]
    generated = await generate_report(client, world, child_path)
    assert generated.status_code == 201, generated.text
    body = generated.json()
    assert body["generation"]["generation_status"] == "READY"
    assert (
        body["generation"]["report_context_snapshot"]["regulatory_record"]["session"][
            "compliance_outcome"
        ]
        == "COMPLIANT"
    )
    assert {row["format"] for row in body["files"]} == {"PDF", "DOCX"}


async def test_report_revision_uses_same_number_and_supersedes_only_on_issue(
    client,
    phase16_stage3,
):
    world = phase16_stage3
    session_path, _ = await approved_session(client, world)
    generated = await generate_report(client, world, session_path)
    first_issue = await issue_report(client, generated.json())
    assert first_issue.status_code == 200, first_issue.text
    first = first_issue.json()

    child = await _approved_child_fixture(client, world, session_path)

    await login(client, world, "officer")
    source = await client.get("/api/v1/reports/" + first["id"])
    revision = await client.post(
        "/api/v1/reports/" + first["id"] + "/revisions",
        headers={
            "If-Match": source.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "test_session_id": child["id"],
            "revision_reason": "Controlled post-approval correction.",
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": datetime.now(UTC).date().isoformat(),
        },
    )
    assert revision.status_code == 201, revision.text
    successor = revision.json()
    assert successor["report"]["report_number"] == first["report_number"]
    assert successor["report"]["revision_no"] == first["revision_no"] + 1
    assert successor["report"]["report_status"] == "UNISSUED"

    competing = await client.post(
        "/api/v1/reports/" + first["id"] + "/revisions",
        headers={
            "If-Match": source.headers["etag"],
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "test_session_id": child["id"],
            "revision_reason": "Competing successor must not be created.",
            "intended_issuer_id": str(world.users["officer"].id),
            "planned_issue_date": datetime.now(UTC).date().isoformat(),
        },
    )
    assert competing.status_code == 409, competing.text
    assert competing.json()["error"]["code"] == "REPORT_CHAIN_CONFLICT"

    original_before = await client.get("/api/v1/reports/" + first["id"])
    assert original_before.json()["report_status"] == "ISSUED"

    issued = await issue_report(
        client,
        successor,
        predecessor=first["id"],
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["report_status"] == "ISSUED"

    original_after = await client.get("/api/v1/reports/" + first["id"])
    assert original_after.json()["report_status"] == "SUPERSEDED"

    chain = await client.get("/api/v1/reports/" + issued.json()["id"] + "/revisions")
    assert chain.status_code == 200
    assert chain.json()["total"] == 2
    assert [row["revision_no"] for row in chain.json()["items"]] == [1, 2]
