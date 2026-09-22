"""Phase 6 real-PostgreSQL integration for Sections 3, 5 and 9.

Determined outcomes use the isolated SYNTHETIC_TEST_ONLY artifact.  The production
candidate remains blocked by the existing regulatory gates.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.compliance.canonical import content_hash
from domain_tests.fixtures.core_reusable import ECCENTRICITY, REPEATABILITY, TARE
from tests.conftest import login
from tests.phase6_fixtures import (
    CONTEXTS,
    OBSERVATIONS,
    PHASE6_IMPLEMENTED_CODES,
    populate_phase6_run,
    prepare_phase6_world,
    started_phase6_runs,
)

pytestmark = pytest.mark.asyncio
PHASE6_CODES = (ECCENTRICITY, REPEATABILITY, TARE)


@pytest_asyncio.fixture
async def phase6(world, monkeypatch):
    return await prepare_phase6_world(world, monkeypatch)


async def evaluate(client, path, *, key=None):
    current = await client.get(path)
    return await client.post(
        path + "/evaluate",
        headers={"If-Match": current.headers["etag"], "Idempotency-Key": key or uuid4().hex},
    )


async def test_phase6_confirmation_creates_typed_runs_for_new_evaluators(client, phase6):
    session_path, paths, requirements = await started_phase6_runs(client, phase6)
    assert set(paths) == set(PHASE6_IMPLEMENTED_CODES)
    assert set(PHASE6_CODES) <= set(paths)
    for code in PHASE6_CODES:
        requirement = requirements[code]
        assert requirement["applicability_status"] == "REQUIRED"
        assert requirement["selected_run_id"]
        run = (await client.get(paths[code])).json()
        assert run["observation_schema_version"] == "v1"
        assert run["procedure_schema_version"] == "v1"
        assert run["evaluation_status"] == "IN_PROGRESS"
        assert run["procedure_context"] == {}
    sections = (await client.get(session_path + "/sections")).json()
    assert len(sections) == 17


@pytest.mark.parametrize("code", PHASE6_CODES)
async def test_phase6_specialized_context_and_observation_round_trip(client, phase6, code):
    _, paths, _ = await started_phase6_runs(client, phase6)
    run_path = paths[code]
    context = CONTEXTS[code](environment=(), equipment=(), evidence_hashes=())
    current = await client.get(run_path)
    updated = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": context.model_dump(mode="json")},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["procedure_context"]["test_code"] == code
    row = OBSERVATIONS[code]().rows[0]
    current = await client.get(run_path)
    stored = await client.post(
        run_path + "/observations",
        headers={"If-Match": current.headers["etag"]},
        json={
            "sequence_no": row.sequence_no,
            "observation_type": code,
            "payload_schema_version": "v1",
            "payload": row.model_dump(mode="json"),
        },
    )
    assert stored.status_code == 201, stored.text
    assert stored.json()["payload"]["test_code"] == code
    assert (await client.get(run_path + "/observations")).json()[0] == stored.json()


@pytest.mark.parametrize("code", PHASE6_CODES)
async def test_phase6_synthetic_end_to_end_result_is_versioned_and_hashed(client, phase6, code):
    _, paths, _ = await started_phase6_runs(client, phase6)
    run_path = paths[code]
    await populate_phase6_run(client, phase6, code, run_path)
    response = await evaluate(client, run_path)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["evaluation_status"] == "COMPLETE"
    assert result["compliance_outcome"] == "COMPLIANT"
    assert result["deterministic_result"]["test_code"] == code
    assert result["deterministic_result"]["synthetic_fixture"] is True
    assert result["input_hash"] == content_hash(result["evaluation_input_snapshot"])
    assert result["result_hash"] == content_hash(result["deterministic_result"])
    assert result["evaluation_version"] == 1
    assert result["source_input_revision"] == (await client.get(run_path)).json()["input_revision"]
    assert result["calculations_json"]
    replay = await evaluate(client, run_path)
    assert replay.status_code == 200
    assert replay.json()["id"] == result["id"]


@pytest.mark.parametrize("code", PHASE6_CODES)
async def test_phase6_source_edit_stales_and_appends_noncompliant_version(client, phase6, code):
    _, paths, _ = await started_phase6_runs(client, phase6)
    run_path = paths[code]
    await populate_phase6_run(client, phase6, code, run_path)
    first = await evaluate(client, run_path)
    assert first.status_code == 200, first.text
    first_result = first.json()
    observations = (await client.get(run_path + "/observations")).json()
    source = observations[0]
    payload = {
        "sequence_no": source["sequence_no"],
        "observation_type": source["observation_type"],
        "payload_schema_version": source["payload_schema_version"],
        "payload": dict(source["payload"]),
    }
    payload["payload"]["indication_g"] = "9999"
    changed = await client.patch(
        run_path + "/observations/" + source["id"],
        headers={"If-Match": f'"{source["lock_version"]}"'},
        json=payload,
    )
    assert changed.status_code == 200, changed.text
    stale = (await client.get(run_path)).json()
    assert stale["current_result_id"] is None
    assert stale["evaluation_status"] == "STALE"
    assert stale["compliance_outcome"] == "UNDETERMINED"
    assert (await client.get(run_path + "/results/" + first_result["id"])).json() == first_result

    second = await evaluate(client, run_path)
    assert second.status_code == 200, second.text
    result = second.json()
    assert result["evaluation_version"] == 2
    assert result["supersedes_result_id"] == first_result["id"]
    assert result["compliance_outcome"] == "NONCOMPLIANT"
    history = (await client.get(run_path + "/history")).json()
    assert {event["event_type"] for event in history["events"]} == {
        "CURRENT",
        "STALE",
        "SUPERSEDED",
    }


async def test_phase6_cross_test_payload_and_context_are_rejected(client, phase6):
    _, paths, _ = await started_phase6_runs(client, phase6)
    eccentricity_path = paths[ECCENTRICITY]
    tare_row = OBSERVATIONS[TARE]().rows[0]
    current = await client.get(eccentricity_path)
    response = await client.post(
        eccentricity_path + "/observations",
        headers={"If-Match": current.headers["etag"]},
        json={
            "sequence_no": tare_row.sequence_no,
            "observation_type": TARE,
            "payload_schema_version": "v1",
            "payload": tare_row.model_dump(mode="json"),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPATIBLE_OBSERVATION"

    tare_context = CONTEXTS[TARE](environment=(), equipment=(), evidence_hashes=())
    current = await client.get(eccentricity_path)
    response = await client.patch(
        eccentricity_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": tare_context.model_dump(mode="json")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INCOMPATIBLE_PROCEDURE"


async def test_phase6_sections_aggregate_but_future_work_keeps_session_unfinished(client, phase6):
    session_path, paths, _ = await started_phase6_runs(client, phase6)
    for code in PHASE6_CODES:
        await populate_phase6_run(client, phase6, code, paths[code])
        response = await evaluate(client, paths[code])
        assert response.status_code == 200, response.text
    sections = (await client.get(session_path + "/sections")).json()
    by_number = {section["section_number"]: section for section in sections}
    for number in (3, 5, 9):
        assert by_number[number]["evaluation_status"] == "COMPLETE"
        assert by_number[number]["compliance_outcome"] == "COMPLIANT"
    session = (await client.get(session_path)).json()
    assert session["evaluation_status"] != "COMPLETE"
    assert session["compliance_outcome"] == "UNDETERMINED"


async def test_phase6_lab_isolation_applies_to_new_run_types(client, phase6):
    _, paths, _ = await started_phase6_runs(client, phase6)
    run_path = paths[ECCENTRICITY]
    await login(client, phase6, "other")
    assert (await client.get(run_path)).status_code == 404
    assert (await client.get(run_path + "/observations")).status_code == 404
