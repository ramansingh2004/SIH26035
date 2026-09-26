"""Phase 25 Stage 2B contracts for parameterized regulatory policy schemas."""

import json

import pytest

from app.compliance.domain import InstrumentSnapshot
from app.compliance.numbers import decimal_value
from app.compliance.parameterized import (
    DirectedLoadExpression,
    DiscriminationPolicyCaseV2,
    DiscriminationPolicyV2,
    EccentricityPolicyCaseV2,
    EccentricityPolicyV2,
    MassExpression,
    MpeProfileSetV2,
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
    resolve_mass_expression,
    resolve_mpe_profile,
    resolve_policy_case,
    resolve_temperature_expression,
)
from app.compliance.regulatory import MpeProfile


def instrument(**changes):
    base = dict(
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
        maximum_tare_g="5000",
        declared_temp_min_c="-10",
        declared_temp_max_c="40",
    )
    base.update(changes)
    return InstrumentSnapshot.model_validate(base)


def test_parameterized_mass_expressions_use_exact_instrument_facts():
    item = instrument()

    assert (
        resolve_mass_expression(
            MassExpression(basis="MIN", value="1"),
            item,
            1,
        )
        == decimal_value("200")
    )
    assert (
        resolve_mass_expression(
            MassExpression(basis="MAX", value="0.5"),
            item,
            1,
        )
        == decimal_value("10000")
    )
    assert (
        resolve_mass_expression(
            MassExpression(basis="E", value="500"),
            item,
            1,
        )
        == decimal_value("5000")
    )
    assert (
        resolve_mass_expression(
            MassExpression(basis="D", value="1.4"),
            item,
            1,
        )
        == decimal_value("14")
    )
    assert (
        str(
            resolve_mass_expression(
                MassExpression(basis="MAX_PLUS_TARE", value="0.3"),
                item,
                1,
            )
        )
        == "7500.0"
    )
    assert (
        str(
            resolve_mass_expression(
                MassExpression(basis="MPE", value="2"),
                item,
                1,
                mpe_g="10",
            )
        )
        == "20"
    )


def test_parameterized_mass_expressions_never_guess_missing_facts():
    no_min = instrument(
        min_capacity_g=None,
        ranges=[
            dict(
                range_no=1,
                min_capacity_g=None,
                max_capacity_g="20000",
                verification_interval_e_g="10",
                scale_interval_d_g="10",
                verification_intervals_n="2000",
            )
        ],
    )
    no_tare = instrument(maximum_tare_g=None)

    with pytest.raises(PolicyResolutionError):
        resolve_mass_expression(MassExpression(basis="MIN", value="1"), no_min, 1)
    with pytest.raises(PolicyResolutionError):
        resolve_mass_expression(MassExpression(basis="MAX_PLUS_TARE", value="0.3"), no_tare, 1)
    with pytest.raises(PolicyResolutionError):
        resolve_mass_expression(MassExpression(basis="MPE", value="1"), instrument(), 1)


def test_parameterized_rules_reject_binary_float_inputs():
    with pytest.raises(ValueError):
        MassExpression(basis="MAX", value=0.5)


def test_policy_selector_requires_unique_determinate_coverage():
    item = instrument()
    case = WeighingPolicyCaseV2(
        selector=PolicySelector(
            accuracy_classes=("III",),
            evaluation_contexts=("TYPE_EVALUATION",),
            indication_types=("DIGITAL",),
        ),
        minimum_count=10,
        stages=("UP", "DOWN"),
        required_loads=(
            DirectedLoadExpression(direction="UP", load=MassExpression(basis="MAX", value="1")),
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
    )
    policy = WeighingPolicyV2(schema_version="v2", cases=(case,))

    resolved = resolve_policy_case(policy.cases, item, "TYPE_EVALUATION")
    assert resolved is case

    unknown = item.model_copy(update={"indication_type": None})
    with pytest.raises(PolicyResolutionError):
        resolve_policy_case(policy.cases, unknown, "TYPE_EVALUATION")

    with pytest.raises(PolicyResolutionError):
        resolve_policy_case(policy.cases, item, "INITIAL_VERIFICATION")


def test_mpe_profile_set_resolves_by_class_and_evaluation_context():
    profile_set = MpeProfileSetV2(
        schema_version="v2",
        profiles=(
            MpeProfile(
                schema_version="v1",
                accuracy_class="III",
                evaluation_context="TYPE_EVALUATION",
                operator="<=",
                semantics="ABSOLUTE",
                bands=(
                    dict(
                        lower_e="0",
                        upper_e="500",
                        lower_operator=">=",
                        upper_operator="<=",
                        multiplier_e="0.5",
                    ),
                ),
            ),
            MpeProfile(
                schema_version="v1",
                accuracy_class="III",
                evaluation_context="SUBSEQUENT_CONTROL",
                operator="<=",
                semantics="ABSOLUTE",
                bands=(
                    dict(
                        lower_e="0",
                        upper_e="500",
                        lower_operator=">=",
                        upper_operator="<=",
                        multiplier_e="1",
                    ),
                ),
            ),
        ),
    )

    resolved = resolve_mpe_profile(
        profile_set,
        accuracy_class="III",
        evaluation_context="TYPE_EVALUATION",
    )
    assert str(resolved.bands[0].multiplier_e) == "0.5"

    with pytest.raises(PolicyResolutionError):
        resolve_mpe_profile(
            profile_set,
            accuracy_class="II",
            evaluation_context="TYPE_EVALUATION",
        )


def test_temperature_expressions_require_declared_bounds_when_selected():
    item = instrument()
    assert (
        str(
            resolve_temperature_expression(
                TemperatureExpression(basis="DECLARED_MIN"),
                item,
            )
        )
        == "-10"
    )
    assert (
        str(
            resolve_temperature_expression(
                TemperatureExpression(basis="DECLARED_MAX"),
                item,
            )
        )
        == "40"
    )

    missing = item.model_copy(update={"declared_temp_min_c": None})
    with pytest.raises(PolicyResolutionError):
        resolve_temperature_expression(
            TemperatureExpression(basis="DECLARED_MIN"),
            missing,
        )


def test_sections_1_to_5_v2_schemas_accept_parameterized_policies():
    selector = PolicySelector(
        accuracy_classes=("III",),
        evaluation_contexts=("TYPE_EVALUATION",),
    )

    temperature = TemperatureZeroPolicyV2(
        schema_version="v2",
        cases=(
            TemperatureZeroPolicyCaseV2(
                selector=selector,
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
    assert temperature.schema_version == "v2"

    eccentricity = EccentricityPolicyV2(
        schema_version="v2",
        cases=(
            EccentricityPolicyCaseV2(
                selector=selector,
                procedure_variant="WEIGHTS",
                test_load=MassExpression(basis="MAX_PLUS_TARE", value="0.333333"),
                position_strategy="UP_TO_FOUR_SUPPORTS",
                require_position_coordinates=True,
                require_environment=True,
                require_equipment=True,
                require_certificate=True,
                require_evidence=True,
                require_monotonic_timestamps=True,
            ),
        ),
    )
    assert eccentricity.cases[0].test_load.basis == "MAX_PLUS_TARE"

    discrimination = DiscriminationPolicyV2(
        schema_version="v2",
        cases=(
            DiscriminationPolicyCaseV2(
                selector=selector,
                indication_mode="DIGITAL",
                minimum_count=3,
                test_loads=(
                    MassExpression(basis="MIN", value="1"),
                    MassExpression(basis="MAX", value="0.5"),
                    MassExpression(basis="MAX", value="1"),
                ),
                extra_load=MassExpression(basis="D", value="1.4"),
                minimum_indication_change=MassExpression(basis="D", value="1"),
                operator=">=",
                semantics="SIGNED",
            ),
        ),
    )
    assert discrimination.cases[0].extra_load.basis == "D"

    sensitivity = SensitivityPolicyV2(
        schema_version="v2",
        cases=(
            SensitivityPolicyCaseV2(
                selector=PolicySelector(
                    accuracy_classes=("III",),
                    evaluation_contexts=("TYPE_EVALUATION",),
                    self_indicating=False,
                ),
                minimum_count=2,
                test_loads=(
                    MassExpression(basis="ABSOLUTE_G", value="0"),
                    MassExpression(basis="MAX", value="1"),
                ),
                extra_load=MassExpression(basis="MPE", value="1"),
                minimum_displacement_mm="1",
                operator=">=",
                semantics="SIGNED",
            ),
        ),
    )
    assert sensitivity.cases[0].extra_load.basis == "MPE"

    repeatability = RepeatabilityPolicyV2(
        schema_version="v2",
        cases=(
            RepeatabilityPolicyCaseV2(
                selector=selector,
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
    assert {series.load.basis for series in repeatability.cases[0].series} == {"MAX"}


def test_stage2b_does_not_promote_candidate_ruleset():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    root = repo / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
