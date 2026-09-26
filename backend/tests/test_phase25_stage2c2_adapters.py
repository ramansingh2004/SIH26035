"""Phase 25 Stage 2C2 deterministic adapter contracts."""

import json
from pathlib import Path

import pytest

from app.compliance.domain import InstrumentSnapshot
from app.compliance.numbers import decimal_value
from app.compliance.parameterized import (
    DirectedLoadExpression,
    DiscriminationPolicyCaseV2,
    DiscriminationPolicyV2,
    EccentricityPolicyCaseV2,
    EccentricityPolicyV2,
    EccentricityPositionV2,
    MassExpression,
    PolicyResolutionError,
    PolicySelector,
    RepeatabilityPolicyCaseV2,
    RepeatabilityPolicyV2,
    RepeatabilitySeriesPolicyV2,
    SensitivityPolicyCaseV2,
    SensitivityPolicyV2,
    TemperatureExpression,
    TemperatureZeroPolicyCaseV2,
    TemperatureZeroPolicyV2,
    WeighingPolicyCaseV2,
    WeighingPolicyV2,
)
from app.compliance.policy_adapters import (
    adapt_discrimination_policy,
    adapt_eccentricity_policy,
    adapt_repeatability_policy,
    adapt_sensitivity_policy,
    adapt_temperature_zero_policy,
    adapt_weighing_policy,
)


def instrument(**changes):
    data = dict(
        accuracy_class="III",
        min_capacity_g="200",
        max_capacity_g="20000",
        verification_interval_e_g="10",
        scale_interval_d_g="10",
        verification_intervals_n="2000",
        ranges=[
            dict(
                range_no=1,
                min_capacity_g="200",
                max_capacity_g="20000",
                verification_interval_e_g="10",
                scale_interval_d_g="10",
                verification_intervals_n="2000",
            )
        ],
        range_type="SINGLE",
        indication_type="DIGITAL",
        is_self_indicating=True,
        load_receptor_type="PLATFORM",
        support_point_count=4,
        maximum_tare_g="5000",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
    )
    data.update(changes)
    return InstrumentSnapshot.model_validate(data)


SELECTOR = PolicySelector(
    accuracy_classes=("III",),
    evaluation_contexts=("TYPE_EVALUATION",),
)


def test_stage2c2_weighing_adapter_resolves_instrument_relative_loads():
    policy = WeighingPolicyV2(
        schema_version="v2",
        cases=(
            WeighingPolicyCaseV2(
                selector=SELECTOR,
                minimum_count=10,
                stages=("UP", "DOWN"),
                required_loads=(
                    DirectedLoadExpression(
                        direction="UP",
                        load=MassExpression(basis="MAX", value="0.5"),
                    ),
                    DirectedLoadExpression(
                        direction="DOWN",
                        load=MassExpression(basis="E", value="500"),
                    ),
                ),
                require_min=True,
                require_max=True,
                require_preload=True,
                require_stabilization=True,
                minimum_warmup_seconds="0",
                zero_condition="ZERO",
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )

    resolved = adapt_weighing_policy(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
    )

    assert {point.load_g for point in resolved.required_loads} == {
        decimal_value("10000"),
        decimal_value("5000"),
    }
    assert resolved.evaluation_context == "TYPE_EVALUATION"
    assert resolved.indication_type == "DIGITAL"


def test_stage2c2_temperature_adapter_resolves_declared_bounds():
    policy = TemperatureZeroPolicyV2(
        schema_version="v2",
        cases=(
            TemperatureZeroPolicyCaseV2(
                selector=SELECTOR,
                minimum_count=3,
                temperature_sequence=(
                    TemperatureExpression(basis="DECLARED_MIN"),
                    TemperatureExpression(basis="ABSOLUTE_C", value="5"),
                    TemperatureExpression(basis="DECLARED_MAX"),
                ),
                normalization_span_c="5",
                limit_multiplier_e="1",
                operator="<",
                semantics="ABSOLUTE",
                require_stabilized_observations=True,
                require_zero_tracking_disabled=True,
                require_declared_temperature_range=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )

    resolved = adapt_temperature_zero_policy(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
    )

    assert resolved.required_temperature_sequence_c == (
        decimal_value("-10"),
        decimal_value("5"),
        decimal_value("40"),
    )
    assert resolved.accuracy_class == "III"


def test_stage2c2_eccentricity_adapter_executes_explicit_positions_only():
    explicit = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            EccentricityPolicyCaseV2(
                selector=SELECTOR,
                procedure_variant="WEIGHTS",
                test_load=MassExpression(basis="MAX_PLUS_TARE", value="0.3"),
                minimum_count=1,
                position_strategy="EXPLICIT",
                explicit_positions=(
                    EccentricityPositionV2(position_code="P1"),
                ),
                allowed_receptor_types=("PLATFORM",),
                required_support_count=4,
                require_position_coordinates=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )

    resolved = adapt_eccentricity_policy(
        explicit,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
    )
    assert resolved.test_load_g == decimal_value("7500")
    assert resolved.required_positions[0].position_code == "P1"

    derived = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            explicit.cases[0].model_copy(
                update={
                    "position_strategy": "UP_TO_FOUR_SUPPORTS",
                    "explicit_positions": (),
                }
            ),
        ),
    )
    with pytest.raises(PolicyResolutionError):
        adapt_eccentricity_policy(
            derived,
            instrument=instrument(),
            evaluation_context="TYPE_EVALUATION",
            range_no=1,
        )


def test_stage2c2_discrimination_adapter_blocks_multi_load_downgrade():
    common = dict(
        selector=SELECTOR,
        indication_mode="DIGITAL",
        minimum_count=1,
        extra_load=MassExpression(basis="D", value="1.4"),
        minimum_indication_change=MassExpression(basis="D", value="1"),
        operator=">=",
        semantics="SIGNED",
        require_stabilization=True,
        require_environment=True,
        require_equipment=True,
        require_certificate=True,
        require_evidence=True,
        require_monotonic_timestamps=True,
    )
    one = DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                **common,
                test_loads=(MassExpression(basis="MAX", value="0.5"),),
            ),
        ),
    )
    resolved = adapt_discrimination_policy(
        one,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
    )
    assert resolved.test_load_g == decimal_value("10000")
    assert resolved.extra_load_g == decimal_value("14")

    multi = DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                **common,
                test_loads=(
                    MassExpression(basis="MIN", value="1"),
                    MassExpression(basis="MAX", value="1"),
                ),
            ),
        ),
    )
    with pytest.raises(PolicyResolutionError):
        adapt_discrimination_policy(
            multi,
            instrument=instrument(),
            evaluation_context="TYPE_EVALUATION",
            range_no=1,
        )


def test_stage2c2_sensitivity_adapter_requires_explicit_mpe_for_mpe_expression():
    policy = SensitivityPolicyV2(
        schema_version="v2",
        cases=(
            SensitivityPolicyCaseV2(
                selector=PolicySelector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("TYPE_EVALUATION",),
                    self_indicating=False,
                ),
                minimum_count=1,
                test_loads=(MassExpression(basis="MAX", value="1"),),
                extra_load=MassExpression(basis="MPE", value="1"),
                minimum_displacement_mm="1",
                operator=">=",
                semantics="SIGNED",
                require_stabilization=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    item = instrument(is_self_indicating=False, indication_type="ANALOG")

    with pytest.raises(PolicyResolutionError):
        adapt_sensitivity_policy(
            policy,
            instrument=item,
            evaluation_context="TYPE_EVALUATION",
            range_no=1,
        )

    resolved = adapt_sensitivity_policy(
        policy,
        instrument=item,
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
        mpe_g="10",
    )
    assert resolved.extra_load_g == decimal_value("10")


def test_stage2c2_repeatability_adapter_resolves_max_relative_series():
    policy = RepeatabilityPolicyV2(
        schema_version="v2",
        cases=(
            RepeatabilityPolicyCaseV2(
                selector=SELECTOR,
                error_basis="CORRECTED",
                series=(
                    RepeatabilitySeriesPolicyV2(
                        series_code="HALF_MAX",
                        load=MassExpression(basis="MAX", value="0.5"),
                        minimum_repetitions=10,
                        range_limit_basis="MPE",
                        range_limit_multiplier="1",
                        range_operator="<=",
                        range_semantics="ABSOLUTE",
                    ),
                    RepeatabilitySeriesPolicyV2(
                        series_code="MAX",
                        load=MassExpression(basis="MAX", value="1"),
                        minimum_repetitions=10,
                        range_limit_basis="MPE",
                        range_limit_multiplier="1",
                        range_operator="<=",
                        range_semantics="ABSOLUTE",
                    ),
                ),
                require_stabilization=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )

    resolved = adapt_repeatability_policy(
        policy,
        instrument=instrument(),
        evaluation_context="TYPE_EVALUATION",
        range_no=1,
    )
    by_code = {series.series_code: series for series in resolved.series}
    assert by_code["HALF_MAX"].load_g == decimal_value("10000")
    assert by_code["MAX"].load_g == decimal_value("20000")


def test_stage2c2_candidate_ruleset_remains_unpromoted():
    repo = Path(__file__).resolve().parents[2]
    rules = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((rules / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((rules / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
