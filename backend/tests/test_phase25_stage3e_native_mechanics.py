"""Phase 25 Stage 3E native mechanics and vector-preparation contracts."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.compliance.stage3_native_mechanics import (
    CreepComparison,
    MechanicsLimit,
    MechanicsLoadLimit,
    creep_mechanics,
    stability_mechanics,
    tare_mechanics,
    tilting_mechanics,
    warm_up_mechanics,
    zero_return_mechanics,
)
from app.compliance.stage3_native_schemas import (
    CreepObservationV2,
    StabilityObservationV2,
    TareObservationV2,
    TiltingObservationV2,
    WarmUpObservationV2,
    ZeroReturnObservationV2,
)

HERE = Path(__file__).resolve().parent
VECTOR_PATH = HERE / "fixtures" / "phase25_stage3e_independent_vectors.json"
REPO = Path(__file__).resolve().parents[2]


def _limit(data):
    return MechanicsLimit.model_validate(data)


def _load_limits(items):
    return tuple(
        MechanicsLoadLimit(
            load_g=item["load_g"],
            limit=_limit(item["limit"]),
        )
        for item in items
    )


def _calculations(result):
    return {item.name: item.value for item in result.calculations}


def _run(vector):
    family = vector["family"]

    if family == "ZERO_RETURN":
        rows = tuple(
            ZeroReturnObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return zero_return_mechanics(
            rows,
            ordinary_limit=_limit(vector["limits"]["ordinary"]),
        )

    if family == "CREEP":
        rows = tuple(
            CreepObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        comparisons = tuple(
            CreepComparison(
                name=item["name"],
                start_seconds=item["start_seconds"],
                end_seconds=item["end_seconds"],
                limit=_limit(item["limit"]),
            )
            for item in vector["comparisons"]
        )
        return creep_mechanics(
            rows,
            comparisons=comparisons,
            temperature_variation_limit=_limit(
                vector["temperature_variation_limit"]
            ),
        )

    if family == "STABILITY_EQUILIBRIUM":
        rows = tuple(
            StabilityObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return stability_mechanics(
            rows,
            print_storage_limit=_limit(
                vector["limits"]["print_storage"]
            ),
            zero_tare_limit=_limit(vector["limits"]["zero_tare"]),
            adjacent_values_limit=_limit(vector["limits"]["adjacent"]),
        )

    if family == "TILTING":
        rows = tuple(
            TiltingObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return tilting_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            unloaded_limit=_limit(vector["unloaded_limit"]),
            loaded_limits=_load_limits(vector["loaded_limits"]),
        )

    if family == "TARE":
        rows = tuple(
            TareObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return tare_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            weighing_limits=_load_limits(vector["weighing_limits"]),
            tare_setting_limit=_limit(vector["tare_setting_limit"]),
            gross_identity_limit=_limit(vector["gross_identity_limit"]),
        )

    if family == "WARM_UP":
        rows = tuple(
            WarmUpObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return warm_up_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            loaded_limits=_load_limits(vector["loaded_limits"]),
            pre_ready_behavior_limit=_limit(
                vector["pre_ready_behavior_limit"]
            ),
        )

    raise AssertionError(f"Unexpected vector family: {family}")


def _vectors():
    data = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    return data, data["vectors"]


def test_stage3e_vector_set_is_explicitly_non_authoritative_and_pending_review():
    data, vectors = _vectors()

    assert data["authority"] == "NON_AUTHORITATIVE_MECHANICS_ONLY"
    assert data["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert data["regulatory_signoff"] is False
    assert len(vectors) == 12


def test_stage3e_vector_set_has_positive_and_negative_case_per_family():
    _, vectors = _vectors()
    families = {
        "ZERO_RETURN",
        "CREEP",
        "STABILITY_EQUILIBRIUM",
        "TILTING",
        "TARE",
        "WARM_UP",
    }

    assert {item["family"] for item in vectors} == families
    for family in families:
        family_vectors = [item for item in vectors if item["family"] == family]
        assert {item["expected_passed"] for item in family_vectors} == {
            True,
            False,
        }


@pytest.mark.parametrize(
    "vector",
    _vectors()[1],
    ids=lambda item: item["id"],
)
def test_stage3e_native_mechanics_vectors(vector):
    result = _run(vector)

    assert result.passed is vector["expected_passed"]
    calculations = _calculations(result)
    for name, expected in vector["expected"].items():
        assert calculations[name] == Decimal(expected)


def test_stage3e_mechanics_are_not_wired_into_authoritative_runtime():
    dispatch = (
        REPO / "backend" / "app" / "compliance" / "stage3_dispatch.py"
    ).read_text(encoding="utf-8")
    phase7 = (
        REPO / "backend" / "app" / "compliance" / "phase7.py"
    ).read_text(encoding="utf-8")
    phase8 = (
        REPO / "backend" / "app" / "compliance" / "phase8.py"
    ).read_text(encoding="utf-8")
    tare = (
        REPO / "backend" / "app" / "compliance" / "tare.py"
    ).read_text(encoding="utf-8")

    assert "raise _blocked(ruleset, key)" in dispatch
    for source in (dispatch, phase7, phase8, tare):
        assert "stage3_native_mechanics" not in source


def test_stage3e_does_not_promote_stage3d_candidate():
    candidate_path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
        / "phase25_stage3d_candidate.json"
    )
    data = json.loads(candidate_path.read_text(encoding="utf-8"))

    assert data["verification_status"] == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert data["activation_allowed"] is False
    assert data["independent_verifier"] == "PENDING"
    assert all(source["digest"] is None for source in data["sources"])
