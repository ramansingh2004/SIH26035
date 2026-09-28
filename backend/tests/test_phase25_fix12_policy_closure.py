"""Phase 25 Fix 12 policy expressiveness/runtime closure contracts."""

import inspect
from types import SimpleNamespace

from app.compliance.domain import InstrumentSnapshot
from app.compliance.eccentricity import (
    EccentricityContext,
    EccentricityPosition,
    section3_registration,
)
from app.compliance.parameterized import (
    DiscriminationPolicyCaseV2,
    DiscriminationPolicyV2,
    EccentricityPolicyCaseV2,
    EccentricityPolicyV2,
    MassExpression,
    PolicyNumericCondition,
    PolicySelector,
    SensitivityPolicyCaseV2,
    SensitivityPolicyV2,
    TemperatureExpression,
    TemperatureZeroPolicyCaseV2,
    TemperatureZeroPolicyV2,
    resolve_policy_case,
)
from app.compliance.parameterized_stage3 import (
    Stage3Selector,
    TiltingPolicyCaseV2,
    TiltingPolicyV2,
    TiltingProtectionV2,
    TiltTarget,
)
from app.compliance.phase7 import (
    discrimination_registration,
    sensitivity_registration,
)
from app.compliance.phase8 import (
    TiltingEvaluator,
    temperature_zero_registration,
    tilting_registration,
)
from app.compliance.policy_adapters import (
    adapt_eccentricity_policy,
    adapt_temperature_zero_policy,
)
from app.compliance.repeatability import section5_registration
from app.compliance.section4_v2 import resolve_discrimination_policy_v2
from app.compliance.weighing import section1_registration


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
        "is_portable": True,
        "is_mobile": False,
        "load_receptor_type": "PLATFORM",
        "support_point_count": 4,
        "declared_temp_min_c": "-10",
        "declared_temp_max_c": "40",
        "level_indicator_available": False,
        "automatic_tilt_sensor": False,
    }
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


def selector(**changes):
    data = {
        "accuracy_classes": ("III",),
        "evaluation_contexts": ("TYPE_EXAMINATION",),
    }
    data.update(changes)
    return PolicySelector(**data)


def test_fix12_numeric_selector_supports_exact_source_operators():
    item = instrument()
    low_max = SimpleNamespace(
        selector=selector(
            numeric_conditions=(
                PolicyNumericCondition(
                    feature="MAX_CAPACITY_G",
                    operator="<=",
                    value="20000",
                ),
            )
        )
    )
    high_max = SimpleNamespace(
        selector=selector(
            numeric_conditions=(
                PolicyNumericCondition(
                    feature="MAX_CAPACITY_G",
                    operator=">",
                    value="20000",
                ),
            )
        )
    )
    assert resolve_policy_case(
        (low_max, high_max),
        item,
        "TYPE_EXAMINATION",
        range_no=1,
    ) is low_max

    min_e = SimpleNamespace(
        selector=selector(
            numeric_conditions=(
                PolicyNumericCondition(
                    feature="MIN_CAPACITY_E",
                    operator="==",
                    value="20",
                ),
            )
        )
    )
    assert resolve_policy_case(
        (min_e,),
        item,
        "TYPE_EXAMINATION",
        range_no=1,
    ) is min_e


def test_fix12_temperature_zero_can_select_conditional_five_degree_branch():
    cold = TemperatureZeroPolicyCaseV2(
        selector=selector(
            numeric_conditions=(
                PolicyNumericCondition(
                    feature="DECLARED_TEMP_MIN_C",
                    operator="<=",
                    value="5",
                ),
            )
        ),
        minimum_count=3,
        temperature_sequence=(
            TemperatureExpression(basis="DECLARED_MIN"),
            TemperatureExpression(basis="ABSOLUTE_C", value="5"),
            TemperatureExpression(basis="DECLARED_MAX"),
        ),
        normalization_span_c="5",
        limit_multiplier_e="1",
        operator="<=",
        semantics="ABSOLUTE",
        require_stabilized_observations=True,
        require_zero_tracking_disabled=True,
        require_declared_temperature_range=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=True,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    warm = cold.model_copy(
        update={
            "selector": selector(
                numeric_conditions=(
                    PolicyNumericCondition(
                        feature="DECLARED_TEMP_MIN_C",
                        operator=">",
                        value="5",
                    ),
                )
            ),
            "minimum_count": 2,
            "temperature_sequence": (
                TemperatureExpression(basis="DECLARED_MIN"),
                TemperatureExpression(basis="DECLARED_MAX"),
            ),
        }
    )
    policy = TemperatureZeroPolicyV2(schema_version="v2", cases=(cold, warm))
    resolved = adapt_temperature_zero_policy(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EXAMINATION",
        range_no=1,
    )
    assert tuple(map(str, resolved.required_temperature_sequence_c)) == (
        "-10",
        "5",
        "40",
    )


def test_fix12_eccentricity_more_than_four_supports_uses_declared_positions():
    item = instrument(support_point_count=6)
    policy = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            EccentricityPolicyCaseV2(
                selector=selector(
                    load_receptor_types=("PLATFORM",),
                    numeric_conditions=(
                        PolicyNumericCondition(
                            feature="SUPPORT_POINT_COUNT",
                            operator=">",
                            value="4",
                        ),
                    ),
                ),
                procedure_variant="WEIGHTS",
                test_load=MassExpression(basis="MAX", value="0.333333"),
                minimum_count=1,
                position_strategy="MORE_THAN_FOUR_SUPPORTS",
                allowed_receptor_types=("PLATFORM",),
                require_position_coordinates=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    context = EccentricityContext(
        procedure_variant="WEIGHTS",
        range_no=1,
        scenario="FIX12",
        evaluation_context="TYPE_EXAMINATION",
        load_receptor_type="PLATFORM",
        support_count=6,
        positions=tuple(
            EccentricityPosition(
                position_code=f"P{i}",
                x_mm=str(i),
                y_mm=str(i),
            )
            for i in range(1, 7)
        ),
    )
    resolved = adapt_eccentricity_policy(
        policy,
        instrument=item,
        evaluation_context="TYPE_EXAMINATION",
        range_no=1,
        procedure_context=context,
    )
    assert len(resolved.required_positions) == 6


def test_fix12_eccentricity_rolling_strategy_has_direction_contract():
    policy = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            EccentricityPolicyCaseV2(
                selector=selector(load_receptor_types=("PLATFORM",)),
                procedure_variant="ROLLING_LOAD",
                test_load=MassExpression(basis="MAX", value="0.5"),
                minimum_count=1,
                position_strategy="ROLLING_LOAD",
                required_rolling_directions=("FORWARD", "REVERSE"),
                allowed_receptor_types=("PLATFORM",),
                require_position_coordinates=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    context = EccentricityContext(
        procedure_variant="ROLLING_LOAD",
        range_no=1,
        scenario="FIX12",
        evaluation_context="TYPE_EXAMINATION",
        load_receptor_type="PLATFORM",
        support_count=4,
        positions=(
            EccentricityPosition(position_code="A", x_mm="0", y_mm="0"),
            EccentricityPosition(position_code="B", x_mm="1", y_mm="1"),
        ),
    )
    resolved = adapt_eccentricity_policy(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EXAMINATION",
        range_no=1,
        procedure_context=context,
    )
    assert {
        (item.position_code, item.rolling_direction)
        for item in resolved.required_positions
    } == {
        ("A", "FORWARD"),
        ("A", "REVERSE"),
        ("B", "FORWARD"),
        ("B", "REVERSE"),
    }


def test_fix12_native_discrimination_executes_analog_multi_load_policy():
    item = instrument(indication_type="ANALOG", is_self_indicating=False)
    policy = DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                selector=PolicySelector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("TYPE_EXAMINATION",),
                    indication_types=("ANALOG",),
                    self_indicating=False,
                ),
                indication_mode="ANALOG",
                minimum_count=2,
                test_loads=(
                    MassExpression(basis="MIN", value="1"),
                    MassExpression(basis="MAX", value="1"),
                ),
                extra_load=MassExpression(basis="E", value="1"),
                minimum_displacement_mm="1",
                operator=">=",
                semantics="ABSOLUTE",
                require_stabilization=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    resolved = resolve_discrimination_policy_v2(
        policy,
        instrument=item,
        evaluation_context="TYPE_EXAMINATION",
        range_no=1,
    )
    assert resolved.indication_mode == "ANALOG"
    assert len(resolved.loads) == 2


def test_fix12_sensitivity_capacity_branch_is_exactly_selectable():
    item = instrument(
        max_capacity_g="30000",
        verification_intervals_n="3000",
        ranges=[
            {
                "range_no": 1,
                "min_capacity_g": "200",
                "max_capacity_g": "30000",
                "verification_interval_e_g": "10",
                "scale_interval_d_g": "10",
                "verification_intervals_n": "3000",
            }
        ],
        indication_type="ANALOG",
        is_self_indicating=False,
    )
    low_selector = PolicySelector(
        accuracy_classes=("III", "IIII"),
        evaluation_contexts=("TYPE_EXAMINATION",),
        self_indicating=False,
        numeric_conditions=(
            PolicyNumericCondition(
                feature="MAX_CAPACITY_G",
                operator="<=",
                value="30000",
            ),
        ),
    )
    high_selector = low_selector.model_copy(
        update={
            "numeric_conditions": (
                PolicyNumericCondition(
                    feature="MAX_CAPACITY_G",
                    operator=">",
                    value="30000",
                ),
            )
        }
    )
    common = dict(
        minimum_count=2,
        test_loads=(MassExpression(basis="MAX", value="1"),),
        extra_load=MassExpression(basis="E", value="1"),
        minimum_displacement_mm="1",
        operator=">=",
        semantics="ABSOLUTE",
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=True,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    low = SensitivityPolicyCaseV2(selector=low_selector, **common)
    high = SensitivityPolicyCaseV2(selector=high_selector, **common)
    policy = SensitivityPolicyV2(schema_version="v2", cases=(low, high))
    assert resolve_policy_case(
        policy.cases,
        item,
        "TYPE_EXAMINATION",
        range_no=1,
    ) is low


def test_fix12_tilting_v2_is_no_longer_deliberately_blocked():
    source = inspect.getsource(TiltingEvaluator)
    assert "_tilting_policy" in source
    assert "load_stage3_policy_for_runtime" not in source

    policy = TiltingPolicyV2(
        schema_version="v2",
        cases=(
            TiltingPolicyCaseV2(
                selector=Stage3Selector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("TYPE_EXAMINATION",),
                    is_portable=True,
                    level_indicator_available=False,
                    automatic_tilt_sensor=False,
                ),
                tilt_mode="NO_LEVEL_DEVICE",
                required_directions=("FORWARD", "BACKWARD", "LEFT", "RIGHT"),
                reference_tilt=TiltTarget(basis="ABSOLUTE", value="0"),
                test_tilt=TiltTarget(basis="FIXED_RATIO", value="0.05"),
                required_loads=(
                    {"basis": "MAX_FRACTION", "value": "0.5"},
                ),
                unloaded_limit={"basis": "SELECTED_E", "multiplier": "2"},
                unloaded_operator="<=",
                unloaded_semantics="ABSOLUTE",
                loaded_limit={"basis": "MPE", "multiplier": "1"},
                require_reference_position=True,
                require_zero_tracking_disabled=True,
                protection=TiltingProtectionV2(),
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    assert policy.cases[0].tilt_mode == "NO_LEVEL_DEVICE"


def test_fix12_implementation_versions_are_explicit():
    assert section1_registration().implementation_version == "section1-fix12-v2"
    assert temperature_zero_registration().implementation_version == "section2-fix12-v2"
    assert section3_registration().implementation_version == "section3-fix12-v2"
    assert discrimination_registration().implementation_version == (
        "section4-discrimination-fix12-v2"
    )
    assert sensitivity_registration().implementation_version == (
        "section4-sensitivity-fix12-v2"
    )
    assert section5_registration().implementation_version == "section5-fix12-v2"
    assert tilting_registration().implementation_version == "section8-fix12-v2"
