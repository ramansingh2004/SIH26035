"""Phase 25 Stage 3C2 deterministic-resolution contracts."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.compliance.domain import InstrumentSnapshot
from app.compliance.parameterized import PolicyResolutionError
from app.compliance.parameterized_stage3 import (
    LimitTarget,
    LoadTarget,
    Stage3Selector,
    TareValueTarget,
    TiltTarget,
    WarmUpPolicyCaseV2,
    WarmUpPolicyV2,
)
from app.compliance.stage3_resolution import (
    Stage3ResolutionFacts,
    resolve_limit_target_explicit,
    resolve_load_target_explicit,
    resolve_tare_value_target,
    resolve_tilt_target_explicit,
    select_stage3_policy_case,
)

REPO = Path(__file__).resolve().parents[2]


def instrument(**changes):
    data = {
        "accuracy_class": "III",
        "min_capacity_g": "200",
        "max_capacity_g": "20000",
        "verification_interval_e_g": "10",
        "scale_interval_d_g": "10",
        "verification_intervals_n": "2000",
        "ranges": [
            {
                "range_no": 1,
                "min_capacity_g": "200",
                "max_capacity_g": "20000",
                "verification_interval_e_g": "10",
                "scale_interval_d_g": "10",
                "verification_intervals_n": "2000",
            }
        ],
        "range_type": "SINGLE",
        "indication_type": "DIGITAL",
        "is_self_indicating": True,
        "is_electronic": True,
        "is_mobile": False,
        "level_indicator_available": True,
        "automatic_tilt_sensor": False,
        "power_supply_type": "AC_MAINS",
        "maximum_tare_g": "6000",
    }
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


def test_stage3c2_explicit_and_relative_load_targets_resolve_exactly():
    inst = instrument()

    resolved = resolve_load_target_explicit(
        LoadTarget(basis="MAX_FRACTION", value="0.5"),
        inst,
        1,
    )
    assert resolved.value_g == Decimal("10000")

    resolved = resolve_load_target_explicit(
        LoadTarget(basis="MIN"),
        inst,
        1,
    )
    assert resolved.value_g == Decimal("200")


def test_stage3c2_semantic_load_targets_fail_closed_without_explicit_facts():
    inst = instrument()

    with pytest.raises(PolicyResolutionError, match="CLOSE_TO_MAX"):
        resolve_load_target_explicit(
            LoadTarget(basis="CLOSE_TO_MAX"),
            inst,
            1,
        )

    with pytest.raises(PolicyResolutionError, match="MPE_TRANSITION"):
        resolve_load_target_explicit(
            LoadTarget(basis="MPE_TRANSITION", transition_index=1),
            inst,
            1,
        )


def test_stage3c2_semantic_load_targets_use_only_explicit_resolution_facts():
    inst = instrument()
    facts = Stage3ResolutionFacts(
        close_to_max_g="19500",
        function_operating_range_g="10000",
        mpe_transition_loads_g=("5000", "15000"),
    )

    assert resolve_load_target_explicit(
        LoadTarget(basis="CLOSE_TO_MAX"),
        inst,
        1,
        facts=facts,
    ).value_g == Decimal("19500")

    assert resolve_load_target_explicit(
        LoadTarget(basis="MPE_TRANSITION", transition_index=2),
        inst,
        1,
        facts=facts,
    ).value_g == Decimal("15000")


def test_stage3c2_limits_tilt_and_tare_require_explicit_inputs():
    inst = instrument()

    assert resolve_limit_target_explicit(
        LimitTarget(basis="SELECTED_E", multiplier="0.5"),
        inst,
        1,
    ).value_g == Decimal("5")

    assert resolve_limit_target_explicit(
        LimitTarget(basis="MPE", multiplier="1"),
        inst,
        1,
        mpe_g=Decimal("15"),
    ).value_g == Decimal("15")

    with pytest.raises(PolicyResolutionError, match="LEVEL_INDICATOR_LIMIT"):
        resolve_tilt_target_explicit(TiltTarget(basis="LEVEL_INDICATOR_LIMIT"))

    assert resolve_tilt_target_explicit(
        TiltTarget(basis="LEVEL_INDICATOR_LIMIT"),
        facts=Stage3ResolutionFacts(level_indicator_limit="0.02"),
    ).value == Decimal("0.02")

    assert resolve_tare_value_target(
        TareValueTarget(basis="MAX_TARE_FRACTION", value="0.5"),
        inst,
    ).value_g == Decimal("3000")


def test_stage3c2_selector_remains_fail_closed_on_unknown_required_fact():
    common = {
        "require_environment": False,
        "require_equipment": False,
        "require_certificate": False,
        "require_evidence": False,
        "require_monotonic_timestamps": True,
    }
    policy = WarmUpPolicyV2(
        schema_version="v2",
        cases=(
            WarmUpPolicyCaseV2(
                selector=Stage3Selector(
                    automatic_tilt_sensor=True,
                    evaluation_contexts=("TYPE_EVALUATION",),
                ),
                minimum_count=1,
                minimum_power_off_seconds="0",
                required_checkpoints_seconds=("0",),
                checkpoint_tolerance_seconds="0",
                test_load=LoadTarget(basis="MAX"),
                loaded_limit=LimitTarget(
                    basis="SELECTED_E",
                    multiplier="1",
                ),
                require_first_stable_indication=False,
                require_zero_after_power_on=False,
                require_stabilized_observations=False,
                require_operating_manual_provision=False,
                permit_result_indication_before_ready=False,
                permit_result_transmission_before_ready=False,
                **common,
            ),
        ),
    )

    with pytest.raises(PolicyResolutionError, match="unknown"):
        select_stage3_policy_case(
            policy.cases,
            instrument=instrument(automatic_tilt_sensor=None),
            evaluation_context="TYPE_EVALUATION",
        )


def test_stage3c2_runtime_candidate_still_is_not_promoted():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
