"""Phase 10 real-PostgreSQL/FastAPI integration tests.

All determined outcomes use isolated SYNTHETIC_TEST fixtures. Production
REG-13/REG-16 regulatory blockers remain unchanged.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.compliance.canonical import content_hash
from app.compliance.phase10 import (
    DISTURBANCE_BURST,
    DISTURBANCE_SURGE,
    DISTURBANCE_VEHICLE_SUPPLY,
)
from domain_tests.fixtures.phase10_disturbances import (
    disturbance_context,
    disturbance_observations,
)
from tests.conftest import login
from tests.phase10_fixtures import (
    PHASE10_SLOT_IDENTITIES,
    populate_phase10_run,
    prepare_phase10_world,
    started_phase10_runs,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def phase10(world, monkeypatch):
    return await prepare_phase10_world(world, monkeypatch)


async def evaluate(client, path, *, key=None):
    current = await client.get(path)
    return await client.post(
        path + "/evaluate",
        headers={
            "If-Match": current.headers["etag"],
            "Idempotency-Key": key or uuid4().hex,
        },
    )


async def test_phase10_confirmation_creates_all_typed_disturbance_slots(
    client,
    phase10,
):
    session_path, paths, requirements = await started_phase10_runs(
        client,
        phase10,
    )
    assert set(paths) == set(PHASE10_SLOT_IDENTITIES)

    vehicle = {variant for code, variant in paths if code == DISTURBANCE_VEHICLE_SUPPLY}
    assert vehicle == {
        "SUPPLY_LINE_CONDUCTION",
        "NON_SUPPLY_LINE_COUPLING",
    }

    for identity in PHASE10_SLOT_IDENTITIES:
        requirement = requirements[identity]
        assert requirement["applicability_status"] == "REQUIRED"
        assert requirement["selected_run_id"]

        run = (await client.get(paths[identity])).json()
        assert run["observation_schema_version"] == "v1"
        assert run["procedure_schema_version"] == "v1"
        assert run["evaluation_status"] == "IN_PROGRESS"
        assert run["procedure_context"] == {}

    sections = (await client.get(session_path + "/sections")).json()
    assert len(sections) == 17


async def test_phase10_all_contexts_and_observations_round_trip(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)

    for identity in PHASE10_SLOT_IDENTITIES:
        code, variant = identity
        run_path = paths[identity]
        context = disturbance_context(
            code,
            variant=variant,
        )
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
        assert updated.json()["procedure_context"]["procedure_variant"] == variant

        row = disturbance_observations(
            code,
            variant=variant,
        ).rows[0]
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


async def test_phase10_all_disturbance_slots_evaluate_and_hash(
    client,
    phase10,
):
    session_path, paths, _ = await started_phase10_runs(
        client,
        phase10,
    )

    for identity in PHASE10_SLOT_IDENTITIES:
        run_path = paths[identity]
        await populate_phase10_run(
            client,
            phase10,
            identity,
            run_path,
        )

        response = await evaluate(client, run_path)
        assert response.status_code == 200, response.text
        result = response.json()

        assert result["evaluation_status"] == "COMPLETE"
        assert result["compliance_outcome"] == "COMPLIANT"
        assert result["deterministic_result"]["test_code"] == identity[0]
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
        assert all(item["waveform_reference"] for item in captured["severity_cases"])

        replay = await evaluate(client, run_path)
        assert replay.status_code == 200
        assert replay.json()["id"] == result["id"]

    sections = (await client.get(session_path + "/sections")).json()
    section12 = next(item for item in sections if item["section_number"] == 12)
    assert section12["evaluation_status"] == "COMPLETE"
    assert section12["compliance_outcome"] == "COMPLIANT"


async def test_phase10_excessive_unhandled_disturbance_is_noncompliant(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]

    await populate_phase10_run(
        client,
        phase10,
        identity,
        run_path,
        observations=disturbance_observations(
            DISTURBANCE_BURST,
            deviation_g="11",
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["evaluation_status"] == "COMPLETE"
    assert result["compliance_outcome"] == "NONCOMPLIANT"
    assert all(
        item["code"] == "DISTURBANCE_EFFECT_NOT_ACCEPTABLY_HANDLED"
        for item in result["failed_conditions_json"]
    )


async def test_phase10_valid_handled_fault_is_compliant(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]

    await populate_phase10_run(
        client,
        phase10,
        identity,
        run_path,
        observations=disturbance_observations(
            DISTURBANCE_BURST,
            deviation_g="11",
            handled=True,
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 200, response.text
    assert response.json()["compliance_outcome"] == "COMPLIANT"


async def test_phase10_missing_verified_severity_is_incomplete(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]

    await populate_phase10_run(
        client,
        phase10,
        identity,
        run_path,
        procedure=disturbance_context(
            DISTURBANCE_BURST,
            omit_severity=True,
        ),
    )

    response = await evaluate(client, run_path)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == ("MISSING_REQUIRED_OBSERVATIONS")


async def test_phase10_cross_family_payload_is_rejected(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]
    row = disturbance_observations(
        DISTURBANCE_SURGE,
    ).rows[0]

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/observations",
        headers={"If-Match": current.headers["etag"]},
        json={
            "sequence_no": row.sequence_no,
            "observation_type": DISTURBANCE_SURGE,
            "payload_schema_version": "v1",
            "payload": row.model_dump(mode="json"),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ("INCOMPATIBLE_OBSERVATION")


async def test_phase10_source_edit_stales_and_versions_result(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]

    await populate_phase10_run(
        client,
        phase10,
        identity,
        run_path,
    )
    first = await evaluate(client, run_path)
    assert first.status_code == 200, first.text
    first_result = first.json()

    observations = (await client.get(run_path + "/observations")).json()
    source = observations[0]
    payload = {
        "sequence_no": source["sequence_no"],
        "observation_type": source["observation_type"],
        "payload_schema_version": (source["payload_schema_version"]),
        "payload": dict(source["payload"]),
    }
    payload["payload"]["disturbed_indication_g"] = "1011"

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


async def test_phase10_lab_isolation_applies_to_disturbance_runs(
    client,
    phase10,
):
    _, paths, _ = await started_phase10_runs(client, phase10)
    identity = (DISTURBANCE_BURST, "BURST_LINES")
    run_path = paths[identity]

    await login(client, phase10, "other")
    assert (await client.get(run_path)).status_code == 404
    assert (await client.get(run_path + "/observations")).status_code == 404
