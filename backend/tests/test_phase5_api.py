"""Real PostgreSQL integration. Synthetic authority is confined to test dependency overrides."""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.api.dependencies import testing_service as service_dependency
from app.compliance.canonical import content_hash
from app.models import AuditEvent
from app.models.testing import TestSession as SessionRecord
from app.services.audit import AuditService
from app.services.testing import TestingService as SessionService
from tests.conftest import login
from tests.phase5_fixtures import (
    configured,
    create_session,
    install_synthetic,
    populate,
    prepare_world,
    seed_evidence,
    started_run,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase5(world):
    return await prepare_world(world)


@pytest_asyncio.fixture
async def synthetic(phase5, monkeypatch):
    await install_synthetic(phase5, monkeypatch)
    return phase5


async def evaluation(client, path, *, key=None):
    current = await client.get(path)
    return await client.post(
        path + "/evaluate",
        headers={"If-Match": current.headers["etag"], "Idempotency-Key": key or uuid4().hex},
    )


async def test_candidate_session_17_sections_snapshot_and_idempotency(client, phase5):
    created, payload, key = await create_session(client, phase5)
    assert created.json()["workflow_status"] == "DRAFT"
    assert created.json()["compliance_outcome"] == "UNDETERMINED"
    identifier = created.json()["id"]
    sections = (await client.get(f"/api/v1/test-sessions/{identifier}/sections")).json()
    assert len(sections) == 17
    assert {s["section_number"] for s in sections} == set(range(1, 18))
    assert all(s["applicability_status"] == "REQUIRES_REVIEW" for s in sections)
    replay = await client.post(
        "/api/v1/test-sessions", json=payload, headers={"Idempotency-Key": key}
    )
    assert replay.status_code == 201 and replay.json() == created.json()
    conflict = await client.post(
        "/api/v1/test-sessions",
        json=payload | {"notes": "different"},
        headers={"Idempotency-Key": key},
    )
    assert conflict.status_code == 409
    async with phase5.factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == UUID(identifier), AuditEvent.action == "session.created"
                )
            )
            == 1
        )


async def test_candidate_gate_explicit_plan_and_no_initial_runs(client, phase5):
    configured_response, path = await configured(client, phase5)
    preview = await client.post(path + "/applicability")
    assert preview.status_code == 200
    assert len(preview.json()["plan"]["slots"]) == 28
    assert not preview.json()["confirmable"]
    assert all(s["decision"]["unresolved_rule_ids"] for s in preview.json()["plan"]["slots"])
    denied = await client.post(
        path + "/confirm-applicability",
        headers={"If-Match": configured_response.headers["etag"]},
        json={"elections": {}},
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "TODO_REGULATORY_VALIDATION"
    assert (await client.get(path + "/requirements")).json() == []


@pytest.mark.parametrize("name,status", [("viewer", 403), ("admin", 403), ("other", 404)])
async def test_permissions_lab_isolation_before_mutation(client, phase5, name, status):
    created, _, _ = await create_session(client, phase5)
    path = "/api/v1/test-sessions/" + created.json()["id"]
    await login(client, phase5, name)
    result = await client.patch(path, json={"notes": "forbidden"}, headers={"If-Match": '"1"'})
    assert result.status_code == status
    if name == "other":
        assert (await client.get(path)).status_code == 404


async def test_session_etags_revisions_and_protected_workflow(client, phase5):
    created, _, _ = await create_session(client, phase5)
    path = "/api/v1/test-sessions/" + created.json()["id"]
    assert (await client.patch(path, json={"notes": "change"})).status_code == 428
    assert (
        await client.patch(path, json={"notes": "change"}, headers={"If-Match": '"8"'})
    ).status_code == 412
    assert (
        await client.patch(path, json={"workflow_status": "APPROVED"}, headers={"If-Match": '"1"'})
    ).status_code == 422
    key = uuid4().hex
    response = await client.post(
        path + "/revisions",
        headers={"If-Match": '"1"', "Idempotency-Key": key},
        json={"reason": "Fresh test revision"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["parent_session_id"] == created.json()["id"]
    assert response.json()["session_revision_no"] == 2
    assert response.json()["workflow_status"] == "INSTRUMENT_CONFIGURATION"
    assert (await client.get(path)).json() == created.json()
    revisions = (await client.get(path + "/revisions")).json()
    assert revisions["total"] == 2
    assert [item["session_revision_no"] for item in revisions["items"]] == [1, 2]
    for state in ("UNDER_REVIEW", "APPROVED", "REPORT_ISSUED", "REJECTED", "CANCELLED"):
        protected, _, _ = await create_session(client, phase5)
        protected_path = "/api/v1/test-sessions/" + protected.json()["id"]
        async with phase5.factory() as session, session.begin():
            row = await session.get(SessionRecord, UUID(protected.json()["id"]))
            row.workflow_status = state
        assert (
            await client.patch(
                protected_path,
                json={"notes": "forbidden"},
                headers={"If-Match": '"1"'},
            )
        ).status_code == 409


async def test_session_failure_rolls_back_sections_and_success_audit(client, phase5, monkeypatch):
    original = AuditService.record

    def fail(self, action, *args, **kwargs):
        if action == "session.created":
            raise RuntimeError("Injected transaction failure")
        return original(self, action, *args, **kwargs)

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        await create_session(client, phase5)
    async with phase5.factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(SessionRecord)
                .where(SessionRecord.laboratory_id == phase5.labs[0].id)
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.laboratory_id == phase5.labs[0].id,
                    AuditEvent.action == "session.created",
                )
            )
            == 0
        )


async def test_synthetic_vertical_slice_versions_stale_and_hashes(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    first = await evaluation(client, path)
    assert first.status_code == 200, first.text
    result = first.json()
    assert (
        result["evaluation_status"] == "COMPLETE" and result["compliance_outcome"] == "NONCOMPLIANT"
    )
    assert result["deterministic_result"]["synthetic_fixture"] is True
    assert result["input_hash"] == content_hash(result["evaluation_input_snapshot"])
    assert result["result_hash"] == content_hash(result["deterministic_result"])
    assert result["calculations_json"][0]["corrected_error_g"] == "20"
    assert (await evaluation(client, path)).json()["id"] == result["id"]
    observations = (await client.get(path + "/observations")).json()
    source = observations[0]
    payload = {
        k: source[k]
        for k in ("sequence_no", "observation_type", "payload_schema_version", "payload")
    }
    payload["payload"]["indication_g"] = "10000"
    response = await client.patch(
        path + "/observations/" + source["id"],
        headers={"If-Match": f'"{source["lock_version"]}"'},
        json=payload,
    )
    assert response.status_code == 200, response.text
    stale = (await client.get(path)).json()
    assert stale["current_result_id"] is None and stale["evaluation_status"] == "STALE"
    assert (await client.get(path + "/results/" + result["id"])).json() == result
    second = await evaluation(client, path)
    assert second.status_code == 200, second.text
    assert second.json()["evaluation_version"] == 2
    assert second.json()["supersedes_result_id"] == result["id"]
    assert second.json()["compliance_outcome"] == "COMPLIANT"
    events = (await client.get(path + "/history")).json()["events"]
    assert {e["event_type"] for e in events} == {"CURRENT", "STALE", "SUPERSEDED"}


async def test_incomplete_procedure_returns_422_without_result(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    response = await evaluation(client, path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_REQUIRED_OBSERVATIONS"
    assert (await client.get(path)).json()["evaluation_status"] == "INCOMPLETE"
    assert (await client.get(path + "/results")).json() == []


async def test_current_negative_can_complete_but_not_mutate_afterward(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    assert (await evaluation(client, path)).status_code == 200
    current = await client.get(path)
    response = await client.post(path + "/complete", headers={"If-Match": current.headers["etag"]})
    assert response.status_code == 200, response.text
    assert response.json()["compliance_outcome"] == "NONCOMPLIANT"
    assert (
        await client.post(
            path + "/environment",
            headers={"If-Match": response.headers["etag"]},
            json={"measured_at": "2000-01-01T00:00:00Z", "temperature_c": "20"},
        )
    ).status_code == 409


async def test_retest_does_not_silently_select_or_erase_history(client, synthetic):
    parent_path, path, requirement = await started_run(client, synthetic)
    before = await client.get(path)
    response = await client.post(
        path + "/retests",
        headers={"If-Match": before.headers["etag"], "Idempotency-Key": uuid4().hex},
        json={"reason": "Synthetic retest"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["run_no"] == 2 and response.json()["current_result_id"] is None
    current = (await client.get(parent_path + "/requirements")).json()
    selected = next(r for r in current if r["id"] == requirement["id"])
    assert selected["selected_run_id"] == requirement["selected_run_id"]
    denied = await client.post(
        "/api/v1/test-requirements/" + requirement["id"] + "/select-run",
        headers={"If-Match": f'"{selected["lock_version"]}"'},
        json={"run_id": response.json()["id"], "reason": "Incomplete retest cannot replace"},
    )
    assert denied.status_code == 409


async def test_result_payload_database_immutable(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    result = await evaluation(client, path)
    assert result.status_code == 200, result.text
    for sql in (
        "UPDATE test_run_results SET reason='changed' WHERE id=:id",
        "DELETE FROM test_run_results WHERE id=:id",
    ):
        async with synthetic.factory() as session:
            with pytest.raises(DBAPIError):
                async with session.begin():
                    await session.execute(text(sql), {"id": UUID(result.json()["id"])})


async def test_evaluation_source_race_rejected_without_result(client, synthetic, monkeypatch):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    import threading

    from domain_tests.fixtures.weighing import fixture_engine
    from tests.phase5_fixtures import SyntheticTestingService

    started, release = threading.Event(), threading.Event()
    delegate = fixture_engine()

    @dataclass(frozen=True)
    class SlowEngine:
        registry = delegate.registry
        engine_version = delegate.engine_version

        def evaluate(self, **arguments):
            started.set()
            assert release.wait(10)
            return delegate.evaluate(**arguments)

    original = SyntheticTestingService.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.engine = SlowEngine()

    monkeypatch.setattr(SyntheticTestingService, "__init__", initialize)
    pending = asyncio.create_task(evaluation(client, path))
    assert await asyncio.to_thread(started.wait, 10)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=synthetic.app),
            base_url="https://test.local",
            headers=dict(client.headers),
        ) as other:
            current = await other.get(path)
            changed = await other.post(
                path + "/environment",
                headers={"If-Match": current.headers["etag"]},
                json={"measured_at": "2000-01-01T00:00:03Z", "temperature_c": "20"},
            )
            assert changed.status_code == 201, changed.text
    finally:
        release.set()
    response = await pending
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "SOURCE_CHANGED_DURING_EVALUATION"
    )
    assert (await client.get(path + "/results")).json() == []


async def test_fixture_cannot_be_created_or_used_by_production_dependency(client, synthetic):
    _, payload, _ = await create_session(client, synthetic, synthetic=True)
    synthetic.app.dependency_overrides.pop(service_dependency)
    denied = await client.post(
        "/api/v1/test-sessions", json=payload, headers={"Idempotency-Key": uuid4().hex}
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "RULESET_INVALID"
    service = SessionService(None, None)
    from app.core.errors import AppError

    with pytest.raises(AppError) as error:
        service.require_production_output(True)
    assert error.value.code == "SYNTHETIC_RESULT_FORBIDDEN"


async def test_regulatory_blocker_is_persisted_explanatory_result(client, synthetic, monkeypatch):
    from dataclasses import replace

    from app.compliance.engine import R76Engine
    from app.compliance.evaluators import EvaluatorRegistry
    from app.compliance.weighing import WeighingEvaluator
    from domain_tests.fixtures.weighing import fixture_engine
    from tests.phase5_fixtures import SyntheticTestingService

    @dataclass(frozen=True)
    class Blocked(WeighingEvaluator):
        def required_rules(self, **kwargs):
            return (*super().required_rules(**kwargs), "MISSING_SYNTHETIC_DEPENDENCY")

    original = SyntheticTestingService.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        registration = fixture_engine().registry.registrations[0]
        self.engine = R76Engine(
            EvaluatorRegistry(
                (
                    replace(
                        registration,
                        evaluator=Blocked(),
                        implementation_version="synthetic-blocked-v1",
                    ),
                )
            )
        )

    monkeypatch.setattr(SyntheticTestingService, "__init__", initialize)
    _, path, _ = await started_run(client, synthetic)
    response = await evaluation(client, path)
    assert response.status_code == 200, response.text
    assert response.json()["evaluation_status"] == "REVIEW_REQUIRED"
    assert response.json()["compliance_outcome"] == "UNDETERMINED"
    assert response.json()["issue_code"] == "TODO_REGULATORY_VALIDATION"
    current = await client.get(path)
    assert current.json()["current_result_id"] == response.json()["id"]
    assert (
        await client.post(path + "/complete", headers={"If-Match": current.headers["etag"]})
    ).status_code == 409


async def test_evaluation_audit_failure_rolls_back_payload_and_pointer(
    client, synthetic, monkeypatch
):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    original = AuditService.record

    def fail(self, action, *args, **kwargs):
        if action == "test_run.evaluated":
            raise RuntimeError("Injected result audit failure")
        return original(self, action, *args, **kwargs)

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        await evaluation(client, path)
    assert (await client.get(path)).json()["current_result_id"] is None
    assert (await client.get(path + "/results")).json() == []


@pytest.mark.parametrize("name,status", [("other", 404), ("admin", 403)])
async def test_run_source_and_result_cross_scope(client, synthetic, name, status):
    _, path, _ = await started_run(client, synthetic)
    await login(client, synthetic, name)
    for suffix in ("", "/observations", "/environment", "/equipment", "/results", "/history"):
        assert (await client.get(path + suffix)).status_code == status


async def test_no_float_environment_and_duplicate_sequence(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    current = await client.get(path)
    assert (
        await client.post(
            path + "/environment",
            headers={"If-Match": current.headers["etag"]},
            json={"measured_at": "2000-01-01T00:00:00Z", "temperature_c": 20.0},
        )
    ).status_code == 422
    source = (await client.get(path + "/observations")).json()[0]
    data = {
        k: source[k]
        for k in ("sequence_no", "observation_type", "payload_schema_version", "payload")
    }
    assert (
        await client.post(
            path + "/observations", headers={"If-Match": current.headers["etag"]}, json=data
        )
    ).status_code == 409


async def test_session_snapshot_survives_master_edit_and_revoked_grant(client, phase5):
    from sqlalchemy import update

    from app.models import UserRoleAssignment

    created, _, _ = await create_session(client, phase5)
    path = "/api/v1/test-sessions/" + created.json()["id"]
    master_path = "/api/v1/instruments/" + created.json()["instrument_id"]
    master = await client.get(master_path)
    changed = await client.patch(
        master_path,
        json={"model_name": "Later master edit"},
        headers={"If-Match": master.headers["etag"]},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get(path)).json()["instrument_snapshot"] == created.json()[
        "instrument_snapshot"
    ]
    async with phase5.factory() as session, session.begin():
        await session.execute(
            update(UserRoleAssignment)
            .where(
                UserRoleAssignment.user_id == phase5.users["local"].id,
                UserRoleAssignment.revoked_at.is_(None),
            )
            .values(
                revoked_at=func.now(),
                revoked_by=phase5.users["admin"].id,
                revocation_reason="Test immediate revocation",
            )
        )
    assert (await client.get(path)).status_code == 403


async def test_equipment_snapshot_isolation_and_unlink_invalidation(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    assert (await evaluation(client, path)).status_code == 200
    linked = (await client.get(path + "/equipment")).json()[0]
    equipment_path = "/api/v1/test-equipment/" + linked["equipment_id"]
    master = await client.get(equipment_path)
    changed = await client.patch(
        equipment_path,
        json={"model": "Edited after capture"},
        headers={"If-Match": master.headers["etag"]},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get(path + "/equipment")).json()[0]["equipment_snapshot"] == linked[
        "equipment_snapshot"
    ]
    before = (await client.get(path)).json()
    removed = await client.delete(
        path + "/equipment/" + linked["equipment_id"],
        headers={"If-Match": f'"{linked["lock_version"]}"'},
    )
    assert removed.status_code == 204, removed.text
    after = (await client.get(path)).json()
    assert after["input_revision"] == before["input_revision"] + 1
    assert after["current_result_id"] is None and after["evaluation_status"] == "STALE"
    await login(client, synthetic, "other")
    foreign = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(synthetic.labs[1].id),
            "category": "SYNTHETIC",
            "reference_number": uuid4().hex,
        },
    )
    assert foreign.status_code == 201, foreign.text
    await login(client, synthetic, "local")
    denied = await client.post(
        path + "/equipment/" + foreign.json()["id"],
        json={},
        headers={"If-Match": f'"{after["lock_version"]}"'},
    )
    assert denied.status_code == 404
    assert (await client.get(path + "/equipment")).json() == []


async def test_environment_exact_update_delete_and_parent_membership(client, synthetic):
    from decimal import Decimal

    _, path, _ = await started_run(client, synthetic)
    current = await client.get(path)
    value = "20.12345678901234567890123456789"
    data = {"measured_at": "2000-01-01T00:00:00Z", "temperature_c": value}
    reading = await client.post(
        path + "/environment", json=data, headers={"If-Match": current.headers["etag"]}
    )
    assert reading.status_code == 201, reading.text
    assert Decimal(reading.json()["temperature_c"]) == Decimal(value)
    revision = (await client.get(path)).json()["input_revision"]
    update = await client.patch(
        path + "/environment/" + reading.json()["id"],
        json=data | {"phase": "after"},
        headers={"If-Match": reading.headers["etag"]},
    )
    assert update.status_code == 200, update.text
    assert (await client.get(path)).json()["input_revision"] == revision + 1
    _, other, _ = await started_run(client, synthetic)
    assert (
        await client.delete(
            other + "/environment/" + reading.json()["id"],
            headers={"If-Match": update.headers["etag"]},
        )
    ).status_code == 404
    assert (
        await client.delete(
            path + "/environment/" + reading.json()["id"],
            headers={"If-Match": update.headers["etag"]},
        )
    ).status_code == 204
    assert (await client.get(path + "/environment")).json() == []


async def test_completed_retest_selection_preserves_previous_history(client, synthetic):
    parent, path, requirement = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    first = await evaluation(client, path)
    assert first.status_code == 200, first.text
    current = await client.get(path)
    retest = await client.post(
        path + "/retests",
        json={"reason": "Synthetic second attempt"},
        headers={"If-Match": current.headers["etag"], "Idempotency-Key": uuid4().hex},
    )
    assert retest.status_code == 201, retest.text
    second_path = "/api/v1/test-runs/" + retest.json()["id"]
    assert (
        await client.post(second_path + "/start", headers={"If-Match": retest.headers["etag"]})
    ).status_code == 200
    await populate(client, synthetic, second_path)
    await seed_evidence(synthetic, retest.json()["id"])
    assert (await evaluation(client, second_path)).status_code == 200
    req = next(
        r
        for r in (await client.get(parent + "/requirements")).json()
        if r["id"] == requirement["id"]
    )
    selected = await client.post(
        "/api/v1/test-requirements/" + req["id"] + "/select-run",
        json={"run_id": retest.json()["id"], "reason": "Verified synthetic selection policy"},
        headers={"If-Match": f'"{req["lock_version"]}"'},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["selected_run_id"] == retest.json()["id"]
    assert (await client.get(path + "/results/" + first.json()["id"])).json() == first.json()
    history = (await client.get(second_path + "/history")).json()
    assert history["selections"][-1]["previous_run_id"] == requirement["selected_run_id"]
    dashboard = (await client.get(parent + "/dashboard")).json()
    assert dashboard["session"]["compliance_outcome"] == "NONCOMPLIANT"
    assert dashboard["session"]["evaluation_status"] != "COMPLETE"


async def test_evaluation_replay_precedes_stale_etag_but_checks_authorization(client, synthetic):
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    before = await client.get(path)
    headers = {"If-Match": before.headers["etag"], "Idempotency-Key": uuid4().hex}
    first = await client.post(path + "/evaluate", headers=headers)
    assert first.status_code == 200, first.text
    replay = await client.post(path + "/evaluate", headers=headers)
    assert replay.status_code == 200 and replay.json() == first.json()
    await login(client, synthetic, "other")
    assert (await client.post(path + "/evaluate", headers=headers)).status_code == 404


async def test_evidence_link_invalidates_source_and_result_links_are_protected(client, synthetic):
    from app.api.dependencies import object_storage
    from app.models import AttachmentLink
    from tests.test_foundations_api import MemoryStorage

    # Metadata/lifecycle regression only: no claim of a real object-storage round trip.
    synthetic.app.dependency_overrides[object_storage] = MemoryStorage
    _, path, _ = await started_run(client, synthetic)
    await populate(client, synthetic, path)
    attachment_id = await seed_evidence(synthetic, path.rsplit("/", 1)[1])
    evaluated = await evaluation(client, path)
    assert evaluated.status_code == 200, evaluated.text
    observation = (await client.get(path + "/observations")).json()[0]
    attachment_path = "/api/v1/attachments/" + str(attachment_id)
    linked = await client.post(
        attachment_path + "/link",
        json={
            "entity_type": "test_observations",
            "entity_id": observation["id"],
            "purpose": "observed_evidence",
        },
        headers={"If-Match": f'"{observation["lock_version"]}"'},
    )
    assert linked.status_code == 201, linked.text
    assert (await client.get(path)).json()["current_result_id"] is None
    async with synthetic.factory() as session:
        result_link = await session.scalar(
            select(AttachmentLink).where(
                AttachmentLink.entity_type == "test_run_results",
                AttachmentLink.entity_id == UUID(evaluated.json()["id"]),
            )
        )
    protected = await client.delete(
        attachment_path + "/links/" + str(result_link.id),
        params={"reason": "Must preserve historical evidence"},
        headers={"If-Match": '"1"'},
    )
    assert protected.status_code == 409
    assert protected.json()["error"]["code"] == "EVIDENCE_PROTECTED"
    await login(client, synthetic, "other")
    denied = await client.post(
        attachment_path + "/link",
        json={
            "entity_type": "test_runs",
            "entity_id": path.rsplit("/", 1)[1],
            "purpose": "denied",
        },
        headers={"If-Match": '"1"'},
    )
    assert denied.status_code == 404
