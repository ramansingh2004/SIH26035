"""Phase 25 Stage 3C3A resolved-v2 policy contracts."""

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
)
from app.compliance.stage3_resolution import Stage3ResolutionFacts
from app.compliance.stage3_resolved import (
    resolve_creep_policy_v2,
    resolve_stability_policy_v2,
    resolve_tare_policy_v2,
    resolve_tilting_policy_v2,
    resolve_warm_up_policy_v2,
    resolve_zero_return_policy_v2,
)

REPO = Path(__file__).resolve().parents[2]

COMMON = {
    "require_environment": False,
    "require_equipment": False,
    "require_certificate": False,
    "require_evidence": False,
    "require_monotonic_timestamps": True,
}


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


def selector():
    return Stage3Selector(
        accuracy_classes=("III",),
        evaluation_contexts=("TYPE_EVALUATION",),
    )


def facts():
    return Stage3ResolutionFacts(
        close_to_max_g="19500",
        function_operating_range_g="10000",
        mpe_transition_loads_g=("5000", "15000"),
        level_indicator_limit="0.02",
        automatic_sensor_limit="0.03",
    )


def mpe(load):
    return Decimal("15") if Decimal(load) >= Decimal("10000") else Decimal("10")


def test_stage3c3a_zero_return_resolves_explicit_contract():
    policy = ZeroReturnPolicyV2(
        schema_version="v2",
        cases=(
            ZeroReturnPolicyCaseV2(
                selector=selector(),
                minimum_count=2,
                test_load=LoadTarget(basis="CLOSE_TO_MAX"),
                minimum_hold_seconds="1800",
                limit=LimitTarget(basis="SELECTED_E", multiplier="0.5"),
                require_stabilization=True,
                require_zero_tracking_disabled=True,
                post_switch_limit=LimitTarget(
                    basis="SELECTED_E",
                    multiplier="1",
                ),
                post_switch_window_seconds="300",
                **COMMON,
            ),
        ),
    )

    resolved = resolve_zero_return_policy_v2(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        facts=facts(),
    )

    assert resolved.test_load_g == Decimal("19500")
    assert resolved.limit_g == Decimal("5")
    assert resolved.post_switch_limit_g == Decimal("10")


def test_stage3c3a_creep_preserves_distinct_routes_and_mpe_branch():
    policy = CreepPolicyV2(
        schema_version="v2",
        cases=(
            CreepPolicyCaseV2(
                selector=selector(),
                test_load=LoadTarget(basis="CLOSE_TO_MAX"),
                require_stabilization=True,
                routes=(
                    CreepRouteV2(
                        route_code="SHORT",
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
                        ),
                        maximum_temperature_variation_c="2",
                    ),
                    CreepRouteV2(
                        route_code="EXTENDED",
                        minimum_duration_seconds="14400",
                        checkpoints_seconds=("0", "14400"),
                        criteria=(
                            CreepCriterionV2(
                                comparison="FROM_INITIAL",
                                start_seconds="0",
                                end_seconds="14400",
                                limit=LimitTarget(basis="MPE", multiplier="1"),
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

    resolved = resolve_creep_policy_v2(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        facts=facts(),
        mpe_for_load=mpe,
    )

    assert {item.route_code for item in resolved.routes} == {"SHORT", "EXTENDED"}
    by_code = {item.route_code: item for item in resolved.routes}
    assert by_code["SHORT"].criteria[0].limit_g == Decimal("5")
    assert by_code["EXTENDED"].criteria[0].limit_g == Decimal("15")


def test_stage3c3a_stability_resolves_numeric_function_and_accuracy_rules():
    policy = StabilityPolicyV2(
        schema_version="v2",
        cases=(
            StabilityPolicyCaseV2(
                selector=selector(),
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

    resolved = resolve_stability_policy_v2(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
    )

    assert resolved.test_load_g == Decimal("10000")
    assert resolved.function_rules[0].output_difference_limit_g == Decimal("10")
    assert resolved.accuracy_rules[0].limit_g == Decimal("2.50")


def test_stage3c3a_tilting_resolves_per_load_mpe_and_tilt_facts():
    policy = TiltingPolicyV2(
        schema_version="v2",
        cases=(
            TiltingPolicyCaseV2(
                selector=selector(),
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
                unloaded_operator="<=",
                unloaded_semantics="ABSOLUTE",
                loaded_limit=LimitTarget(basis="MPE", multiplier="1"),
                require_reference_position=True,
                require_zero_tracking_disabled=True,
                protection=TiltingProtectionV2(),
                **COMMON,
            ),
        ),
    )

    resolved = resolve_tilting_policy_v2(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        facts=facts(),
        mpe_for_load=mpe,
    )

    assert resolved.test_tilt_value == Decimal("0.02")
    assert [(item.load_g, item.loaded_limit_g) for item in resolved.loads] == [
        (Decimal("5000"), Decimal("10")),
        (Decimal("19500"), Decimal("15")),
    ]
    assert resolved.unloaded_limit_g == Decimal("20")


def test_stage3c3a_tare_and_warmup_resolve_without_runtime_wiring():
    tare = TarePolicyV2(
        schema_version="v2",
        cases=(
            TarePolicyCaseV2(
                selector=selector(),
                scenarios=(
                    TareScenarioV2(
                        scenario_code="SUB",
                        tare_type="SUBTRACTIVE",
                        tare_value={
                            "basis": "MAX_TARE_FRACTION",
                            "value": "0.5",
                        },
                        minimum_count=5,
                        stages=("UP", "DOWN"),
                        required_net_loads=(
                            LoadTarget(basis="MIN"),
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

    resolved_tare = resolve_tare_policy_v2(
        tare,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        facts=facts(),
        mpe_for_load=mpe,
    )

    assert resolved_tare.scenarios[0].tare_value_g == Decimal("3000")
    assert resolved_tare.scenarios[0].loads[-1].weighing_limit_g == Decimal("15")
    assert resolved_tare.tare_setting_accuracy.limit_g == Decimal("2.50")

    warm = WarmUpPolicyV2(
        schema_version="v2",
        cases=(
            WarmUpPolicyCaseV2(
                selector=selector(),
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

    resolved_warm = resolve_warm_up_policy_v2(
        warm,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        facts=facts(),
        mpe_for_load=mpe,
    )
    assert resolved_warm.test_load_g == Decimal("19500")
    assert resolved_warm.loaded_limit_g == Decimal("15")


def test_stage3c3a_mpe_targets_fail_closed_without_compatible_resolver():
    policy = WarmUpPolicyV2(
        schema_version="v2",
        cases=(
            WarmUpPolicyCaseV2(
                selector=selector(),
                minimum_count=1,
                minimum_power_off_seconds="0",
                required_checkpoints_seconds=("0",),
                checkpoint_tolerance_seconds="0",
                test_load=LoadTarget(basis="MAX"),
                loaded_limit=LimitTarget(basis="MPE", multiplier="1"),
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

    with pytest.raises(PolicyResolutionError, match="compatible-MPE"):
        resolve_warm_up_policy_v2(
            policy,
            instrument=instrument(),
            evaluation_context="TYPE_EVALUATION",
            range_no=1,
        )


def test_stage3c3a_candidate_ruleset_remains_unpromoted():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe_data = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe_data["rules"][0]["key"] == "MPE_PENDING"
    assert mpe_data["rules"][0]["parameters"][0]["value"] is None
