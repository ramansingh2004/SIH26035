"""Phase 11 real-PostgreSQL/FastAPI integration tests.

All determined outcomes use an isolated SYNTHETIC_TEST fixture artifact.
Production REG-14/REG-16 gates remain unchanged.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.compliance.canonical import content_hash
from app.compliance.phase11 import ENDURANCE
from domain_tests.fixtures.phase11_endurance import (
    endurance_context,
    endurance_observations,
)
from tests.conftest import login
from tests.phase11_fixtures import (
    populate_phase11_run,
    prepare_phase11_world,
    started_phase11_runs,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase11(world, monkeypatch):
    return await prepare_phase11_world(world, monkeypatch)


async def evaluate(client, path, *, key=None):
    current = await client.get(path)
    return await client.post(
        path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": key or uuid4().hex,
        },
    )


async def test_phase11_confirmation_creates_typed_endurance_run(
    client,
    phase11,
):
    session_path, paths, requirements = await started_phase11_runs(
        client,
        phase11,
    )
    assert ENDURANCE in paths

    requirement = requirements[ENDURANCE]
    assert requirement["applicability_status"] == "REQUIRED"
    assert requirement["selected_run_id"]

    run = (await client.get(paths[ENDURANCE])).json()
    assert run["observation_schema_version"] == "v1"
    assert run["procedure_schema_version"] == "v1"
    assert run["evaluation_status"] == "IN_PROGRESS"
    assert run["procedure_context"] == {}

    sections = (await client.get(session_path + "/sections")).json()
    assert len(sections) == 17


async def test_phase11_context_and_observations_round_trip(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]

    context = endurance_context()
    context = type(context).model_validate(
        context.model_dump(mode="python")
        | {
            "environment": (),
            "equipment": (),
            "evidence_hashes": (),
        }
    )
    current = await client.get(run_path)
    updated = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": context.model_dump(mode="json")},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["procedure_context"]["test_code"] == ENDURANCE

    row = endurance_observations().rows[0]
    current = await client.get(run_path)
    stored = await client.post(
        run_path + "/observations",
        headers={"If-Match": current.headers["etag"]},
        json={
            "sequence_no": row.sequence_no,
            "observation_type": ENDURANCE,
            "payload_schema_version": "v1",
            "payload": row.model_dump(mode="json"),
        },
    )
    assert stored.status_code == 201, stored.text
    assert stored.json()["payload"]["phase"] == "INITIAL"


async def test_phase11_synthetic_end_to_end_result_is_hashed(
    client,
    phase11,
):
    session_path, paths, _ = await started_phase11_runs(
        client,
        phase11,
    )
    run_path = paths[ENDURANCE]
    await populate_phase11_run(
        client,
        phase11,
        run_path,
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 200, response.text
    result = response.json()

    assert result["evaluation_status"] == "COMPLETE"
    assert result["compliance_outcome"] == "COMPLIANT"
    assert result["deterministic_result"]["test_code"] == ENDURANCE
    assert result["deterministic_result"]["synthetic_fixture"] is True
    assert result["input_hash"] == content_hash(result["evaluation_input_snapshot"])
    assert result["result_hash"] == content_hash(result["deterministic_result"])
    assert result["evaluation_version"] == 1
    assert result["calculations_json"]
    assert result["acceptance_limits_json"]

    captured = result["evaluation_input_snapshot"]["procedure_context"]
    assert captured["environment"]
    assert captured["equipment"]
    assert captured["evidence_hashes"]
    assert captured["equipment"][0]["calibration_certificate_no"]
    assert captured["equipment"][0]["certificate_content_hash"]

    replay = await evaluate(client, run_path)
    assert replay.status_code == 200
    assert replay.json()["id"] == result["id"]

    sections = (await client.get(session_path + "/sections")).json()
    section15 = next(item for item in sections if item["section_number"] == 15)
    assert section15["evaluation_status"] == "COMPLETE"
    assert section15["compliance_outcome"] == "COMPLIANT"


async def test_phase11_incomplete_cycles_are_blocked(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]
    await populate_phase11_run(
        client,
        phase11,
        run_path,
        procedure=endurance_context(
            completed_cycles=9,
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == ("MISSING_REQUIRED_OBSERVATIONS")


async def test_phase11_missing_final_point_is_blocked(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]
    await populate_phase11_run(
        client,
        phase11,
        run_path,
        observations=endurance_observations(
            omit_final=True,
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == ("MISSING_REQUIRED_OBSERVATIONS")


async def test_phase11_durability_failure_is_noncompliant(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]
    await populate_phase11_run(
        client,
        phase11,
        run_path,
        observations=endurance_observations(
            final_errors=("11", "10"),
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["evaluation_status"] == "COMPLETE"
    assert result["compliance_outcome"] == "NONCOMPLIANT"
    assert result["failed_conditions_json"][0]["code"] == ("ENDURANCE_DURABILITY_LIMIT_EXCEEDED")


async def test_phase11_source_edit_stales_and_versions(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]
    await populate_phase11_run(
        client,
        phase11,
        run_path,
    )

    first = await evaluate(client, run_path)
    assert first.status_code == 200, first.text
    first_result = first.json()

    observations = (await client.get(run_path + "/observations")).json()
    source = next(
        item
        for item in observations
        if item["payload"]["phase"] == "FINAL" and item["payload"]["point_id"] == "P25"
    )
    payload = {
        "sequence_no": source["sequence_no"],
        "observation_type": source["observation_type"],
        "payload_schema_version": (source["payload_schema_version"]),
        "payload": dict(source["payload"]),
    }
    payload["payload"]["indication_g"] = "5011"

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

    second = await evaluate(client, run_path)
    assert second.status_code == 200, second.text
    result = second.json()
    assert result["evaluation_version"] == 2
    assert result["supersedes_result_id"] == first_result["id"]
    assert result["compliance_outcome"] == "NONCOMPLIANT"


async def test_phase11_lab_isolation_applies_to_endurance(
    client,
    phase11,
):
    _, paths, _ = await started_phase11_runs(client, phase11)
    run_path = paths[ENDURANCE]

    await login(client, phase11, "other")
    assert (await client.get(run_path)).status_code == 404
    assert (await client.get(run_path + "/observations")).status_code == 404
