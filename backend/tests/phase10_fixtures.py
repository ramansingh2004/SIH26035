"""SYNTHETIC Phase 10 PostgreSQL/API integration fixtures only.

This pytest-only artifact extends the accepted Phase 9 fixture with the seven
Section 12 disturbance families (eight requirement slots because vehicle supply
has two subvariants). It does not create regulatory authority or physical
waveform evidence.
"""

from dataclasses import replace
from uuid import uuid4

from fastapi import Request

from app.api.dependencies import context, testing_service
from app.compliance.engine import R76Engine, synthetic_artifact
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.phase10 import DISTURBANCE_CODES
from app.compliance.ruleset import RuleSet
from app.compliance.suite import implemented_registry
from app.services.rulesets import RulesetService
from app.services.testing import TestingService
from domain_tests.fixtures.phase10_disturbances import (
    disturbance_context,
    disturbance_observations,
    disturbance_rules,
    variants,
)
from domain_tests.fixtures.synthetic import instrument
from tests.phase5_fixtures import create_session, prepare_world, seed_evidence
from tests.phase9_fixtures import (
    PHASE9_IMPLEMENTED_CODES,
    phase9_fixture_rules,
)

PHASE10_CODES = DISTURBANCE_CODES
PHASE10_IMPLEMENTED_CODES = (
    *PHASE9_IMPLEMENTED_CODES,
    *PHASE10_CODES,
)
PHASE10_SLOT_IDENTITIES = tuple(
    (code, variant) for code in PHASE10_CODES for variant in variants(code)
)


def _rename_rule(rule: dict, mapping: dict[str, str]) -> dict:
    result = dict(rule)
    result["key"] = mapping.get(result["key"], result["key"])
    result["dependencies"] = [mapping.get(value, value) for value in result["dependencies"]]
    return result


def phase10_fixture_rules() -> RuleSet:
    """One labelled synthetic artifact through Phase 10."""

    payload = phase9_fixture_rules().model_dump(mode="json")
    payload["metadata"]["version"] = "SYNTHETIC_TEST_PHASE10_INTEGRATION"
    payload["metadata"]["edition"] = "TEST-PHASE10-v1"
    payload["metadata"]["supported_test_codes"] = list(PHASE10_IMPLEMENTED_CODES)
    tests = {item["code"]: item for item in payload["tests"]}
    existing_rule_keys = {rule["key"] for rule in payload["rules"]}

    for code in PHASE10_CODES:
        specialized = disturbance_rules(code).model_dump(mode="json")
        rename = {}
        definition = dict(specialized["tests"][0])

        for rule in specialized["rules"]:
            if rule["key"] == "BASE":
                continue
            renamed = _rename_rule(rule, rename)
            if renamed["key"] not in existing_rule_keys:
                payload["rules"].append(renamed)
                existing_rule_keys.add(renamed["key"])

        definition["dependencies"] = [
            rename.get(value, value) for value in definition["dependencies"]
        ]
        target = tests[code]
        target.update(
            source=definition["source"],
            verification=definition["verification"],
            dependencies=definition["dependencies"],
            implemented=True,
        )

    return RuleSet.model_validate(payload)


def phase10_fixture_engine() -> R76Engine:
    registrations = tuple(
        replace(item, synthetic_fixture=True)
        for item in implemented_registry().registrations
        if item.test_code in PHASE10_IMPLEMENTED_CODES
    )
    return R76Engine(EvaluatorRegistry(registrations))


class SyntheticPhase10TestingService(TestingService):
    __test__ = False

    def __init__(self, session, request_context):
        super().__init__(session, request_context)
        self.engine = phase10_fixture_engine()

    def artifact_is_production(self, rules):
        assert synthetic_artifact(rules)
        return True

    def require_production_output(self, synthetic):
        assert synthetic is True


async def install_phase10_synthetic(world, monkeypatch):
    from app.services import rulesets as service_module
    from app.services.audit import RequestContext

    fixture = phase10_fixture_rules()
    with monkeypatch.context() as patch:
        patch.setattr(
            service_module,
            "load_ruleset",
            lambda: fixture,
        )
        async with world.factory() as session, session.begin():
            row = await RulesetService(
                session,
                RequestContext(),
            ).insert_artifact()
            row.ruleset_status = "ACTIVE"
            row.validation_summary = {
                "authoritative": True,
                "SYNTHETIC_TEST_FIXTURE_ONLY": True,
            }
            world.synthetic_ruleset_id = str(row.id)

    async def service(request: Request):
        async with world.factory() as session:
            yield SyntheticPhase10TestingService(
                session,
                context(request),
            )

    world.app.dependency_overrides[testing_service] = service


async def configured_phase10(client, world):
    response, _, _ = await create_session(
        client,
        world,
        synthetic=True,
    )
    path = "/api/v1/test-sessions/" + response.json()["id"]
    snapshot = instrument(
        indication_type="DIGITAL",
        is_self_indicating=False,
        load_receptor_type="RECTANGULAR",
        support_point_count=4,
        tare_type="SUBTRACTIVE",
        maximum_tare_g="5000",
        zero_tracking_available=True,
        level_indicator_available=False,
        automatic_tilt_sensor=False,
        is_portable=False,
        is_mobile=False,
        power_supply_type="AC",
        nominal_voltage="230",
        min_voltage="200",
        max_voltage="250",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
        vehicle_powered=True,
    )
    response = await client.post(
        path + "/configure",
        headers={"If-Match": response.headers["etag"]},
        json={"instrument_snapshot": snapshot.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text
    return response, path


async def started_phase10_runs(client, world):
    response, session_path = await configured_phase10(client, world)

    preview = await client.post(session_path + "/applicability")
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmable"] is True

    response = await client.post(
        session_path + "/confirm-applicability",
        headers={"If-Match": response.headers["etag"]},
        json={"elections": {}},
    )
    assert response.status_code == 200, response.text

    requirements = (await client.get(session_path + "/requirements")).json()
    selected = {
        (
            item["slot_snapshot"]["test_code"],
            item["slot_snapshot"]["procedure_variant"],
        ): item
        for item in requirements
        if (
            item["slot_snapshot"]["test_code"],
            item["slot_snapshot"]["procedure_variant"],
        )
        in PHASE10_SLOT_IDENTITIES
    }
    assert set(selected) == set(PHASE10_SLOT_IDENTITIES)

    response = await client.post(
        session_path + "/start-testing",
        headers={"If-Match": response.headers["etag"]},
    )
    assert response.status_code == 200, response.text

    paths = {}
    for identity, requirement in selected.items():
        run_path = "/api/v1/test-runs/" + requirement["selected_run_id"]
        current = await client.get(run_path)
        started = await client.post(
            run_path + "/start",
            headers={"If-Match": current.headers["etag"]},
        )
        assert started.status_code == 200, started.text
        paths[identity] = run_path

    return session_path, paths, selected


async def populate_phase10_run(
    client,
    world,
    identity,
    run_path,
    *,
    procedure=None,
    observations=None,
):
    code, variant = identity
    current = await client.get(run_path)

    if procedure is None:
        procedure = disturbance_context(
            code,
            variant=variant,
        )
    procedure = type(procedure).model_validate(
        procedure.model_dump(mode="python")
        | {
            "environment": (),
            "equipment": (),
            "evidence_hashes": (),
        }
    )

    response = await client.patch(
        run_path + "/procedure-context",
        headers={"If-Match": current.headers["etag"]},
        json={"procedure_context": procedure.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text

    batch = observations or disturbance_observations(
        code,
        variant=variant,
    )
    for row in batch.rows:
        current = await client.get(run_path)
        response = await client.post(
            run_path + "/observations",
            headers={"If-Match": current.headers["etag"]},
            json={
                "sequence_no": row.sequence_no,
                "observation_type": code,
                "payload_schema_version": (row.observation_schema_version),
                "payload": row.model_dump(mode="json"),
            },
        )
        assert response.status_code == 201, response.text

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/environment",
        headers={"If-Match": current.headers["etag"]},
        json={
            "measured_at": "2000-01-01T00:00:00Z",
            "temperature_c": "20",
            "relative_humidity_percent": "50",
            "barometric_pressure_hpa": "1000",
            "phase": "SYNTHETIC_PHASE10",
        },
    )
    assert response.status_code == 201, response.text

    equipment = await client.post(
        "/api/v1/test-equipment",
        json={
            "laboratory_id": str(world.labs[0].id),
            "category": "SYNTHETIC",
            "reference_number": (f"SYNTHETIC_PHASE10_{code}_{uuid4().hex}"),
        },
    )
    assert equipment.status_code == 201, equipment.text

    current = await client.get(run_path)
    response = await client.post(
        run_path + "/equipment/" + equipment.json()["id"],
        headers={"If-Match": current.headers["etag"]},
        json={},
    )
    assert response.status_code == 201, response.text

    await seed_evidence(
        world,
        run_path.rsplit("/", 1)[1],
    )


async def prepare_phase10_world(world, monkeypatch):
    world = await prepare_world(world)
    await install_phase10_synthetic(world, monkeypatch)
    return world
