"""Phase 8 real-PostgreSQL/API integration tests.

All determined outcomes use an isolated SYNTHETIC_TEST fixture artifact.
Production REG-05/11/12/16 gates remain unchanged.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.compliance.canonical import content_hash
from app.compliance.phase8 import (
    TEMPERATURE_ZERO,
    TILTING,
    VOLTAGE_VARIATION,
    WARM_UP,
)
from domain_tests.fixtures.phase8_influence import (
    temperature_observations,
    warm_up_context,
)
from tests.conftest import login
from tests.phase8_fixtures import (
    CONTEXTS,
    OBSERVATIONS,
    PHASE8_CODES,
    populate_phase8_run,
    prepare_phase8_world,
    started_phase8_runs,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase8(world, monkeypatch):
    return await prepare_phase8_world(world, monkeypatch)


async def evaluate(client, path, *, key=None):
    current = await client.get(path)
    return await client.post(
        path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": key or uuid4().hex,
        },
    )


async def test_phase8_confirmation_creates_typed_runs(
    client,
    phase8,
):
    session_path, paths, requirements = await started_phase8_runs(
        client,
        phase8,
    )
    assert set(PHASE8_CODES) <= set(paths)

    for code in PHASE8_CODES:
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


@pytest.mark.parametrize("code", PHASE8_CODES)
async def test_phase8_context_and_observation_round_trip(
    client,
    phase8,
    code,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[code]

    context = CONTEXTS[code]()
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

    listing = (await client.get(run_path + "/observations")).json()
    assert listing[0] == stored.json()


@pytest.mark.parametrize("code", PHASE8_CODES)
async def test_phase8_synthetic_end_to_end_result_is_hashed(
    client,
    phase8,
    code,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[code]
    await populate_phase8_run(
        client,
        phase8,
        code,
        run_path,
    )

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
    assert result["calculations_json"]
    assert result["acceptance_limits_json"]

    replay = await evaluate(client, run_path)
    assert replay.status_code == 200
    assert replay.json()["id"] == result["id"]


async def test_phase8_warm_up_power_off_prerequisite_is_incomplete(
    client,
    phase8,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[WARM_UP]
    await populate_phase8_run(
        client,
        phase8,
        WARM_UP,
        run_path,
        procedure=warm_up_context(power_off_seconds="99"),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == ("EVALUATION_NOT_POSSIBLE")


async def test_phase8_cross_test_payload_is_rejected(
    client,
    phase8,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[TEMPERATURE_ZERO]
    row = OBSERVATIONS[VOLTAGE_VARIATION]().rows[0]
    current = await client.get(run_path)

    response = await client.post(
        run_path + "/observations",
        headers={"If-Match": current.headers["etag"]},
        json={
            "sequence_no": row.sequence_no,
            "observation_type": VOLTAGE_VARIATION,
            "payload_schema_version": "v1",
            "payload": row.model_dump(mode="json"),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ("INCOMPATIBLE_OBSERVATION")


async def test_phase8_sections_2_8_10_11_aggregate(
    client,
    phase8,
):
    session_path, paths, _ = await started_phase8_runs(
        client,
        phase8,
    )

    for code in PHASE8_CODES:
        await populate_phase8_run(
            client,
            phase8,
            code,
            paths[code],
        )
        response = await evaluate(client, paths[code])
        assert response.status_code == 200, response.text

    sections = (await client.get(session_path + "/sections")).json()
    by_number = {section["section_number"]: section for section in sections}
    for number in (2, 8, 10, 11):
        assert by_number[number]["evaluation_status"] == "COMPLETE"
        assert by_number[number]["compliance_outcome"] == "COMPLIANT"

    session = (await client.get(session_path)).json()
    assert session["evaluation_status"] != "COMPLETE"
    assert session["compliance_outcome"] == "UNDETERMINED"


async def test_phase8_temperature_source_edit_stales_and_versions(
    client,
    phase8,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[TEMPERATURE_ZERO]
    await populate_phase8_run(
        client,
        phase8,
        TEMPERATURE_ZERO,
        run_path,
    )

    first = await evaluate(client, run_path)
    assert first.status_code == 200, first.text
    first_result = first.json()

    observations = (await client.get(run_path + "/observations")).json()
    source = next(item for item in observations if item["sequence_no"] == 2)
    payload = {
        "sequence_no": source["sequence_no"],
        "observation_type": source["observation_type"],
        "payload_schema_version": (source["payload_schema_version"]),
        "payload": dict(source["payload"]),
    }
    payload["payload"]["indication_g"] = "10"

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

    expected = temperature_observations(drift_g="10")
    assert (
        str(expected.rows[1].indication_g)
        == (result["evaluation_input_snapshot"]["observations"][1]["indication_g"])
    )


async def test_phase8_lab_isolation_applies_to_new_run_types(
    client,
    phase8,
):
    _, paths, _ = await started_phase8_runs(client, phase8)
    run_path = paths[TILTING]

    await login(client, phase8, "other")
    assert (await client.get(run_path)).status_code == 404
    assert (await client.get(run_path + "/observations")).status_code == 404
