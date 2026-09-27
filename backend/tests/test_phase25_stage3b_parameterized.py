"""Phase 25 Stage 3B parameterized-policy contracts."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.compliance.domain import InstrumentSnapshot
from app.compliance.parameterized import PolicyResolutionError
from app.compliance.parameterized_stage3 import (
    CreepCriterionV2,
    CreepPolicyCaseV2,
    CreepPolicyV2,
    CreepRouteV2,
    LimitTarget,
    LoadTarget,
    StabilityAccuracyRuleV2,
    StabilityFunctionRuleV2,
    StabilityPolicyCaseV2,
    StabilityPolicyV2,
    Stage3Selector,
    TarePolicyCaseV2,
    TarePolicyV2,
    TareScenarioV2,
    TareSettingAccuracyV2,
    TiltingPolicyCaseV2,
    TiltingPolicyV2,
    TiltingProtectionV2,
    TiltTarget,
    WarmUpPolicyCaseV2,
    WarmUpPolicyV2,
    ZeroReturnPolicyCaseV2,
    ZeroReturnPolicyV2,
    resolve_limit_target,
    resolve_load_target,
    resolve_stage3_case,
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
                "max_capacity_g": "10000",
                "verification_interval_e_g": "5",
                "scale_interval_d_g": "5",
                "verification_intervals_n": "2000",
            },
            {
                "range_no": 2,
                "min_capacity_g": "10000",
                "max_capacity_g": "20000",
                "verification_interval_e_g": "10",
                "scale_interval_d_g": "10",
                "verification_intervals_n": "2000",
            },
        ],
        "range_type": "MULTIPLE",
        "indication_type": "DIGITAL",
        "is_self_indicating": True,
        "is_electronic": True,
        "is_mobile": False,
        "level_indicator_available": True,
        "automatic_tilt_sensor": False,
        "power_supply_type": "AC_MAINS",
        "maximum_tare_g": "5000",
    }
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


COMMON = {
    "require_environment": False,
    "require_equipment": False,
    "require_certificate": False,
    "require_evidence": False,
    "require_monotonic_timestamps": True,
}


def test_stage3b_load_and_limit_primitives_resolve_only_explicit_mechanics():
    inst = instrument()

    assert str(resolve_load_target(LoadTarget(basis="MAX"), inst, 2)) == "20000"
    assert (
        resolve_load_target(
            LoadTarget(basis="MAX_FRACTION", value="0.5"),
            inst,
            2,
        )
        == Decimal("10000")
    )

    assert str(
        resolve_limit_target(
            LimitTarget(basis="SELECTED_E", multiplier="0.5"),
            inst,
            2,
        )
    ) == "5.0"
    assert str(
        resolve_limit_target(
            LimitTarget(basis="RANGE_E", range_no=1, multiplier="0.5"),
            inst,
            2,
        )
    ) == "2.5"

    with pytest.raises(PolicyResolutionError, match="verified runtime derivation"):
        resolve_load_target(LoadTarget(basis="CLOSE_TO_MAX"), inst, 2)

    with pytest.raises(PolicyResolutionError, match="MPE-based"):
        resolve_limit_target(
            LimitTarget(basis="MPE", multiplier="1"),
            inst,
            2,
        )


def test_stage3b_zero_return_and_creep_models_represent_source_branches():
    selector = Stage3Selector(
        accuracy_classes=("III",),
        evaluation_contexts=("TYPE_EVALUATION",),
    )

    zero = ZeroReturnPolicyV2(
        schema_version="v2",
        cases=(
            ZeroReturnPolicyCaseV2(
                selector=selector,
                minimum_count=2,
                test_load=LoadTarget(basis="CLOSE_TO_MAX"),
                minimum_hold_seconds="1800",
                limit=LimitTarget(basis="SELECTED_E", multiplier="0.5"),
                require_stabilization=True,
                require_zero_tracking_disabled=True,
                post_switch_limit=LimitTarget(
                    basis="RANGE_E",
                    range_no=1,
                    multiplier="1",
                ),
                post_switch_window_seconds="300",
                **COMMON,
            ),
        ),
    )
    assert zero.cases[0].post_switch_window_seconds == 300

    creep = CreepPolicyV2(
        schema_version="v2",
        cases=(
            CreepPolicyCaseV2(
                selector=selector,
                test_load=LoadTarget(basis="CLOSE_TO_MAX"),
                require_stabilization=True,
                routes=(
                    CreepRouteV2(
                        route_code="SHORT_30_MIN",
                        minimum_duration_seconds="1800",
                        checkpoints_seconds=("0", "900", "1800"),
                        criteria=(
                            CreepCriterionV2(
                                comparison="FROM_INITIAL",
                                start_seconds="0",
                                end_seconds="1800",
                                limit=LimitTarget(
                                    basis="SELECTED_E",
                                    multiplier="0.5",
                                ),
                                operator="<=",
                                semantics="ABSOLUTE",
                            ),
                            CreepCriterionV2(
                                comparison="BETWEEN_CHECKPOINTS",
                                start_seconds="900",
                                end_seconds="1800",
                                limit=LimitTarget(
                                    basis="SELECTED_E",
                                    multiplier="0.2",
                                ),
                                operator="<=",
                                semantics="ABSOLUTE",
                            ),
                        ),
                        maximum_temperature_variation_c="2",
                    ),
                    CreepRouteV2(
                        route_code="EXTENDED_4_HOUR",
                        minimum_duration_seconds="14400",
                        checkpoints_seconds=(
                            "0",
                            "300",
                            "900",
                            "1800",
                            "3600",
                            "7200",
                            "10800",
                            "14400",
                        ),
                        criteria=(
                            CreepCriterionV2(
                                comparison="FROM_INITIAL",
                                start_seconds="0",
                                end_seconds="14400",
                                limit=LimitTarget(
                                    basis="MPE",
                                    multiplier="1",
                                ),
                                operator="<=",
                                semantics="ABSOLUTE",
                            ),
                        ),
                        maximum_temperature_variation_c="2",
                    ),
                ),
                **COMMON,
            ),
        ),
    )
    assert {route.route_code for route in creep.cases[0].routes} == {
        "SHORT_30_MIN",
        "EXTENDED_4_HOUR",
    }


def test_stage3b_stability_tilting_tare_and_warmup_models_are_parameterized():
    selector = Stage3Selector(
        accuracy_classes=("III",),
        evaluation_contexts=("TYPE_EVALUATION",),
    )

    stability = StabilityPolicyV2(
        schema_version="v2",
        cases=(
            StabilityPolicyCaseV2(
                selector=selector,
                minimum_count=10,
                test_load=LoadTarget(basis="MAX_FRACTION", value="0.5"),
                require_worst_case_adjustment=True,
                require_manufacturer_documentation=True,
                function_rules=(
                    StabilityFunctionRuleV2(
                        function="PRINTING",
                        inhibit_when_unstable=True,
                        permit_when_stable=True,
                        observation_window_seconds="5",
                        output_difference_limit=LimitTarget(
                            basis="SELECTED_E",
                            multiplier="1",
                        ),
                        require_adjacent_values=True,
                    ),
                    StabilityFunctionRuleV2(
                        function="ZERO",
                        inhibit_when_unstable=True,
                        permit_when_stable=True,
                        require_adjacent_values=False,
                    ),
                ),
                accuracy_rules=(
                    StabilityAccuracyRuleV2(
                        function="ZERO",
                        minimum_trials=5,
                        limit=LimitTarget(
                            basis="SELECTED_E",
                            multiplier="0.25",
                        ),
                        operator="<=",
                        semantics="ABSOLUTE",
                    ),
                ),
                **COMMON,
            ),
        ),
    )
    assert stability.cases[0].accuracy_rules[0].minimum_trials == 5

    tilting = TiltingPolicyV2(
        schema_version="v2",
        cases=(
            TiltingPolicyCaseV2(
                selector=selector,
                tilt_mode="LEVEL_INDICATOR",
                required_directions=("FORWARD", "BACKWARD", "LEFT", "RIGHT"),
                reference_tilt=TiltTarget(basis="ABSOLUTE", value="0"),
                test_tilt=TiltTarget(basis="LEVEL_INDICATOR_LIMIT"),
                required_loads=(
                    LoadTarget(basis="MPE_TRANSITION", transition_index=1),
                    LoadTarget(basis="CLOSE_TO_MAX"),
                ),
                unloaded_limit=LimitTarget(
                    basis="SELECTED_E",
                    multiplier="2",
                ),
                loaded_limit=LimitTarget(
                    basis="MPE",
                    multiplier="1",
                ),
                require_reference_position=True,
                require_zero_tracking_disabled=True,
                protection=TiltingProtectionV2(),
                **COMMON,
            ),
        ),
    )
    assert tilting.cases[0].required_loads[0].basis == "MPE_TRANSITION"

    tare = TarePolicyV2(
        schema_version="v2",
        cases=(
            TarePolicyCaseV2(
                selector=selector,
                scenarios=(
                    TareScenarioV2(
                        scenario_code="SUBTRACTIVE",
                        tare_type="SUBTRACTIVE",
                        tare_value={
                            "basis": "MAX_TARE_FRACTION",
                            "value": "0.5",
                        },
                        minimum_count=5,
                        stages=("UP", "DOWN"),
                        required_net_loads=(
                            LoadTarget(basis="MIN"),
                            LoadTarget(basis="MPE_TRANSITION", transition_index=1),
                            LoadTarget(basis="CLOSE_TO_MAX"),
                        ),
                    ),
                ),
                enforce_gross_equals_tare_plus_net=True,
                require_declared_tare_capacity=True,
                require_stabilization=True,
                weighing_limit=LimitTarget(basis="MPE", multiplier="1"),
                tare_setting_accuracy=TareSettingAccuracyV2(
                    enabled=True,
                    minimum_trials=1,
                    limit=LimitTarget(
                        basis="SELECTED_E",
                        multiplier="0.25",
                    ),
                ),
                **COMMON,
            ),
        ),
    )
    assert tare.cases[0].scenarios[0].tare_value.value == 0.5

    warmup = WarmUpPolicyV2(
        schema_version="v2",
        cases=(
            WarmUpPolicyCaseV2(
                selector=selector,
                minimum_count=4,
                minimum_power_off_seconds="28800",
                required_checkpoints_seconds=("0", "300", "900", "1800"),
                checkpoint_tolerance_seconds="5",
                test_load=LoadTarget(basis="CLOSE_TO_MAX"),
                loaded_limit=LimitTarget(basis="MPE", multiplier="1"),
                require_first_stable_indication=True,
                require_zero_after_power_on=True,
                require_stabilized_observations=True,
                require_operating_manual_provision=False,
                permit_result_indication_before_ready=False,
                permit_result_transmission_before_ready=False,
                **COMMON,
            ),
        ),
    )
    assert warmup.cases[0].required_checkpoints_seconds == (
        0,
        300,
        900,
        1800,
    )


def test_stage3b_selector_fails_closed_on_unknown_required_fact():
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
                **COMMON,
            ),
        ),
    )

    with pytest.raises(PolicyResolutionError, match="unknown"):
        resolve_stage3_case(
            policy.cases,
            instrument(automatic_tilt_sensor=None),
            "TYPE_EVALUATION",
        )


def test_stage3b_candidate_runtime_ruleset_remains_unpromoted():
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
