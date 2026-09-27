"""Phase 25 Stage 4B contracts, native schemas, mechanics and candidate safety."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.candidate_stage4b import load_stage4b_candidate
from app.compliance.phase8 import voltage_variation_registration
from app.compliance.phase9 import damp_heat_registration, span_stability_registration
from app.compliance.phase10 import disturbance_registrations
from app.compliance.phase11 import endurance_registration
from app.compliance.regulatory import SUPPORTED_KINDS
from app.compliance.stage4_native_mechanics import (
    Stage4Limit,
    Stage4LoadLimit,
    damp_heat_mechanics,
    disturbance_mechanics,
    endurance_mechanics,
    span_stability_mechanics,
    voltage_variation_mechanics,
)
from app.compliance.stage4_native_schemas import (
    DampHeatObservationV2,
    DisturbanceObservationV2,
    EnduranceObservationV2,
    SpanStabilityObservationV2,
    VoltageVariationObservationV2,
)

REPO = Path(__file__).resolve().parents[2]
VECTOR_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "phase25_stage4b_mechanics_vectors.json"
)


def _limit(value, *, unit="g"):
    return Stage4Limit(
        name="explicit_test_limit",
        value=value,
        operator="<=",
        semantics="ABSOLUTE",
        unit=unit,
    )


def _load_limits(items):
    return tuple(
        Stage4LoadLimit(
            load_g=item["load_g"],
            limit=_limit(item["value"]),
        )
        for item in items
    )


def _run(vector):
    family = vector["family"]

    if family == "VOLTAGE_VARIATION":
        rows = tuple(
            VoltageVariationObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return voltage_variation_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            load_limits=_load_limits(vector["limits"]),
        )

    if family == "ELECTRICAL_DISTURBANCES":
        rows = tuple(
            DisturbanceObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return disturbance_mechanics(
            rows,
            deviation_limit=_limit(vector["deviation_limit"]),
            accepted_fault_responses=tuple(vector["accepted_fault_responses"]),
        )

    if family == "DAMP_HEAT":
        rows = tuple(
            DampHeatObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return damp_heat_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            load_limits=_load_limits(vector["limits"]),
        )

    if family == "SPAN_STABILITY":
        rows = tuple(
            SpanStabilityObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return span_stability_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            variation_limit=_limit(vector["variation_limit"]),
        )

    if family == "ENDURANCE":
        rows = tuple(
            EnduranceObservationV2.model_validate(item)
            for item in vector["observations"]
        )
        return endurance_mechanics(
            rows,
            verification_interval_e_g=vector["verification_interval_e_g"],
            durability_limits=_load_limits(vector["limits"]),
        )

    raise AssertionError(f"Unexpected Stage 4 family: {family}")


def _vector_data():
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def _context_keys(registration):
    return {item.key for item in registration.contexts.registrations}


def _observation_keys(registration):
    return {item.key for item in registration.observations.registrations}


def _policy_kinds(registration):
    return {item.kind for item in registration.policy_schemas}


def test_stage4b_supported_kinds_include_all_v2_procedure_families():
    assert {
        "voltage_variation_procedure_v2",
        "disturbance_procedure_v2",
        "damp_heat_procedure_v2",
        "span_stability_procedure_v2",
        "endurance_procedure_v2",
    } <= set(SUPPORTED_KINDS)


def test_stage4b_voltage_registration_advertises_v2_contracts():
    registration = voltage_variation_registration()
    for variant in (
        "AC_MAINS",
        "EXTERNAL_SUPPLY",
        "BATTERY_NO_CHARGING",
        "VEHICLE_SUPPLY",
    ):
        assert ("VOLTAGE_VARIATION", variant, "v2") in _context_keys(registration)
    assert (
        "VOLTAGE_VARIATION",
        "VOLTAGE_VARIATION_V2",
        "v2",
    ) in _observation_keys(registration)
    assert "voltage_variation_procedure_v2" in _policy_kinds(registration)
    assert "mpe_profile_set_v2" in _policy_kinds(registration)


def test_stage4b_disturbance_registrations_advertise_v2_contracts():
    registrations = disturbance_registrations()
    assert len(registrations) == 7
    for registration in registrations:
        assert any(key[2] == "v2" for key in _context_keys(registration))
        assert (
            registration.test_code,
            "DISTURBANCE_V2",
            "v2",
        ) in _observation_keys(registration)
        assert "disturbance_procedure_v2" in _policy_kinds(registration)


def test_stage4b_sections_13_to_15_advertise_v2_contracts():
    damp = damp_heat_registration()
    span = span_stability_registration()
    endurance = endurance_registration()

    assert ("DAMP_HEAT", "STEADY_STATE", "v2") in _context_keys(damp)
    assert ("DAMP_HEAT", "DAMP_HEAT_V2", "v2") in _observation_keys(damp)
    assert "damp_heat_procedure_v2" in _policy_kinds(damp)
    assert "mpe_profile_set_v2" in _policy_kinds(damp)

    assert ("SPAN_STABILITY", "LONG_DURATION", "v2") in _context_keys(span)
    assert (
        "SPAN_STABILITY",
        "SPAN_STABILITY_V2",
        "v2",
    ) in _observation_keys(span)
    assert "span_stability_procedure_v2" in _policy_kinds(span)
    assert "mpe_profile_set_v2" in _policy_kinds(span)

    assert (
        "ENDURANCE",
        "MECHANICAL_CYCLING",
        "v2",
    ) in _context_keys(endurance)
    assert ("ENDURANCE", "ENDURANCE_V2", "v2") in _observation_keys(endurance)
    assert "endurance_procedure_v2" in _policy_kinds(endurance)
    assert "mpe_profile_set_v2" in _policy_kinds(endurance)


def test_stage4b_native_voltage_schema_fails_closed_for_missing_measurement():
    with pytest.raises(ValidationError, match="requires measurement values"):
        VoltageVariationObservationV2(
            sequence_no=1,
            target_id="LOW",
            applied_voltage_v="200",
            load_g="1000",
            operational_state="INDICATING",
            functions_operational=True,
            measured_at="2026-09-27T10:00:00+00:00",
        )


def test_stage4b_candidate_remains_non_authoritative():
    candidate = load_stage4b_candidate()

    assert candidate.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert candidate.activation_allowed is False
    assert candidate.independent_verifier == "PENDING"
    assert all(source.digest is None for source in candidate.sources)
    assert all(fact.activation_allowed is False for fact in candidate.facts)
    assert {fact.family for fact in candidate.facts} == {
        "VOLTAGE_VARIATION",
        "ELECTRICAL_DISTURBANCES",
        "DAMP_HEAT",
        "SPAN_STABILITY",
        "ENDURANCE",
    }
    assert len(candidate.candidate_hash) == 64


def test_stage4b_candidate_is_not_runtime_loaded_or_activated():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    ruleset_source = (
        REPO / "backend" / "app" / "compliance" / "ruleset.py"
    ).read_text(encoding="utf-8")
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))

    assert "phase25_stage4b_candidate.json" not in ruleset_source
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []


def test_stage4b_vectors_are_non_authoritative_and_balanced():
    data = _vector_data()

    assert data["authority"] == "NON_AUTHORITATIVE_MECHANICS_ONLY"
    assert data["review_status"] == "PENDING_INDEPENDENT_REVIEW"
    assert data["regulatory_signoff"] is False
    assert len(data["vectors"]) == 10

    families = {
        "VOLTAGE_VARIATION",
        "ELECTRICAL_DISTURBANCES",
        "DAMP_HEAT",
        "SPAN_STABILITY",
        "ENDURANCE",
    }
    assert {item["family"] for item in data["vectors"]} == families
    for family in families:
        assert {
            item["expected_passed"]
            for item in data["vectors"]
            if item["family"] == family
        } == {True, False}


@pytest.mark.parametrize(
    "vector",
    _vector_data()["vectors"],
    ids=lambda item: item["id"],
)
def test_stage4b_native_mechanics_vectors(vector):
    result = _run(vector)

    assert result.passed is vector["expected_passed"]
    calculations = {item.name: item.value for item in result.calculations}
    for name, expected in vector["expected"].items():
        assert calculations[name] == Decimal(expected)


def test_stage4b_native_mechanics_are_not_authoritative_runtime_wired():
    for relative in (
        "app/compliance/phase8.py",
        "app/compliance/phase9.py",
        "app/compliance/phase10.py",
        "app/compliance/phase11.py",
    ):
        source = (REPO / "backend" / relative).read_text(encoding="utf-8")
        assert "stage4_native_mechanics" not in source
