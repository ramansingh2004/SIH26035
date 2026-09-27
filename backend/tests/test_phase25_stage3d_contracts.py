"""Phase 25 Stage 3D native-schema and candidate-artifact contracts."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.candidate_stage3d import load_stage3d_candidate
from app.compliance.phase7 import (
    creep_registration,
    stability_registration,
    zero_return_registration,
)
from app.compliance.phase8 import tilting_registration, warm_up_registration
from app.compliance.stage3_native_schemas import (
    StabilityObservationV2,
    TareObservationV2,
    ZeroReturnContextV2,
)
from app.compliance.tare import section9_registration

REPO = Path(__file__).resolve().parents[2]


def _context_keys(registration):
    return {item.key for item in registration.contexts.registrations}


def _observation_keys(registration):
    return {item.key for item in registration.observations.registrations}


def test_stage3d_registers_native_v2_schemas_for_sections_6_to_10():
    assert ("ZERO_RETURN", "ZERO_RETURN", "v2") in _context_keys(
        zero_return_registration()
    )
    assert ("ZERO_RETURN", "ZERO_RETURN_V2", "v2") in _observation_keys(
        zero_return_registration()
    )

    for variant in ("SHORT", "EXTENDED"):
        assert ("CREEP", variant, "v2") in _context_keys(creep_registration())
    assert ("CREEP", "CREEP_V2", "v2") in _observation_keys(
        creep_registration()
    )

    assert (
        "STABILITY_EQUILIBRIUM",
        "FUNCTIONAL",
        "v2",
    ) in _context_keys(stability_registration())
    assert (
        "STABILITY_EQUILIBRIUM",
        "STABILITY_EQUILIBRIUM_V2",
        "v2",
    ) in _observation_keys(stability_registration())

    for variant in (
        "LEVEL_INDICATOR",
        "AUTOMATIC_TILT_SENSOR",
        "NO_LEVEL_DEVICE",
        "MOBILE_AUTOMATIC_TILT_SENSOR",
        "MOBILE_CARDANIC",
    ):
        assert ("TILTING", variant, "v2") in _context_keys(
            tilting_registration()
        )
    assert ("TILTING", "TILTING_V2", "v2") in _observation_keys(
        tilting_registration()
    )

    assert ("TARE", "DIGITAL_PRE_ROUNDING", "v2") in _context_keys(
        section9_registration()
    )
    assert ("TARE", "TARE_V2", "v2") in _observation_keys(
        section9_registration()
    )

    assert ("WARM_UP", "WARM_UP", "v2") in _context_keys(
        warm_up_registration()
    )
    assert ("WARM_UP", "WARM_UP_V2", "v2") in _observation_keys(
        warm_up_registration()
    )


def test_stage3d_zero_return_post_switch_shape_fails_closed():
    with pytest.raises(ValidationError, match="Post-switch"):
        ZeroReturnContextV2(
            range_no=1,
            scenario="TYPE",
            evaluation_context="TYPE_EVALUATION",
            test_load_g="1000",
            planned_hold_seconds="1800",
            stabilized=True,
            zero_tracking_disabled=True,
            post_switch_check_required=True,
        )


def test_stage3d_native_observations_require_new_quantitative_data():
    base = {
        "sequence_no": 1,
        "measured_at": "2026-09-27T10:00:00+00:00",
    }

    with pytest.raises(ValidationError, match="quantitative output"):
        StabilityObservationV2(
            **base,
            function="PRINTING",
            trial_no=1,
            equilibrium_stable=True,
            operation_performed=True,
        )

    with pytest.raises(ValidationError, match="complete weighing"):
        TareObservationV2(
            **base,
            observation_kind="WEIGHING",
            tare_scenario_code="S1",
            tare_type="SUBTRACTIVE",
            tare_value_g="100",
        )


def test_stage3d_candidate_covers_reg09_through_reg12():
    bundle = load_stage3d_candidate()

    assert {item.family for item in bundle.facts} == {
        "ZERO_RETURN",
        "CREEP",
        "STABILITY_EQUILIBRIUM",
        "TILTING",
        "TARE",
        "WARM_UP",
    }
    assert {
        register_id
        for fact in bundle.facts
        for register_id in fact.register_ids
    } == {"REG-09", "REG-10", "REG-11", "REG-12"}


def test_stage3d_candidate_remains_non_authoritative():
    bundle = load_stage3d_candidate()

    assert bundle.verification_status == (
        "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
    )
    assert bundle.activation_allowed is False
    assert bundle.independent_verifier == "PENDING"
    assert all(source.digest is None for source in bundle.sources)
    assert all(fact.activation_allowed is False for fact in bundle.facts)
    assert len(bundle.candidate_hash) == 64


def test_stage3d_candidate_targets_native_v2_contracts():
    bundle = load_stage3d_candidate()
    expected = {
        "ZERO_RETURN": ("zero_return_procedure_v2", "ZeroReturnContextV2"),
        "CREEP": ("creep_procedure_v2", "CreepContextV2"),
        "STABILITY_EQUILIBRIUM": (
            "stability_equilibrium_procedure_v2",
            "StabilityContextV2",
        ),
        "TILTING": ("tilting_procedure_v2", "TiltingContextV2"),
        "TARE": ("tare_procedure_v2", "TareContextV2"),
        "WARM_UP": ("warm_up_procedure_v2", "WarmUpContextV2"),
    }

    for fact in bundle.facts:
        kind, context = expected[fact.family]
        assert fact.runtime_projection.target_policy_kind == kind
        assert fact.runtime_projection.context_schema == context
        assert fact.runtime_projection.blockers


def test_stage3d_candidate_is_not_loaded_or_activated():
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

    assert "phase25_stage3d_candidate.json" not in ruleset_source
    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []


def test_stage3d_keeps_stage3c_v2_execution_blocked():
    dispatch = (
        REPO / "backend" / "app" / "compliance" / "stage3_dispatch.py"
    ).read_text(encoding="utf-8")

    assert "raise _blocked(ruleset, key)" in dispatch
