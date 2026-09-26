"""Deterministic Stage 2C2 adapters for parameterized regulatory policies.

The adapters resolve v2 policy expressions against an immutable instrument
snapshot and evaluation context. They do not provide regulatory defaults and
they fail closed when a v2 construct cannot be represented safely by the
existing v1 evaluator contract.
"""

from app.compliance.domain import InstrumentSnapshot
from app.compliance.eccentricity import EccentricityPolicy, PositionRequirement
from app.compliance.parameterized import (
    DiscriminationPolicyV2,
    EccentricityPolicyV2,
    MpeProfileSetV2,
    PolicyResolutionError,
    RepeatabilityPolicyV2,
    SensitivityPolicyV2,
    TemperatureZeroPolicyV2,
    WeighingPolicyV2,
    resolve_mass_expression,
    resolve_mpe_profile,
    resolve_policy_case,
    resolve_temperature_expression,
)
from app.compliance.phase7 import DiscriminationPolicy, SensitivityPolicy
from app.compliance.phase8 import TemperatureZeroPolicy
from app.compliance.repeatability import (
    RepeatabilityPolicy,
    RepeatabilitySeriesPolicy,
)
from app.compliance.weighing import CoveragePoint, WeighingPolicy


def _required_text(name: str, value: str | None) -> str:
    if value is None:
        raise PolicyResolutionError(f"{name} is required to resolve the policy")
    return value


def adapt_mpe_profile_set(
    policy: MpeProfileSetV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
):
    return resolve_mpe_profile(
        policy,
        accuracy_class=instrument.accuracy_class,
        evaluation_context=evaluation_context,
    )


def adapt_weighing_policy(
    policy: WeighingPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
) -> WeighingPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    required_loads = tuple(
        CoveragePoint(
            direction=item.direction,
            load_g=resolve_mass_expression(item.load, instrument, range_no),
        )
        for item in case.required_loads
    )
    transition_loads = tuple(
        CoveragePoint(
            direction=item.direction,
            load_g=resolve_mass_expression(item.load, instrument, range_no),
        )
        for item in case.transition_loads
    )
    return WeighingPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        indication_type=_required_text("indication_type", instrument.indication_type),
        range_type=_required_text("range_type", instrument.range_type),
        interval_basis="e",
        minimum_count=case.minimum_count,
        stages=case.stages,
        required_loads=required_loads,
        transition_loads=transition_loads,
        require_min=case.require_min,
        require_max=case.require_max,
        require_preload=case.require_preload,
        require_stabilization=case.require_stabilization,
        minimum_warmup_seconds=case.minimum_warmup_seconds,
        zero_condition=case.zero_condition,
        require_environment=case.require_environment,
        temperature_min_c=case.temperature_min_c,
        temperature_max_c=case.temperature_max_c,
        humidity_min_percent=case.humidity_min_percent,
        humidity_max_percent=case.humidity_max_percent,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
    )


def adapt_temperature_zero_policy(
    policy: TemperatureZeroPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
) -> TemperatureZeroPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    sequence = tuple(
        resolve_temperature_expression(item, instrument)
        for item in case.temperature_sequence
    )
    return TemperatureZeroPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        minimum_count=case.minimum_count,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
        accuracy_class=instrument.accuracy_class,
        required_temperature_sequence_c=sequence,
        normalization_span_c=case.normalization_span_c,
        limit_multiplier_e=case.limit_multiplier_e,
        operator=case.operator,
        semantics=case.semantics,
        require_stabilized_observations=case.require_stabilized_observations,
        require_zero_tracking_disabled=case.require_zero_tracking_disabled,
        require_declared_temperature_range=case.require_declared_temperature_range,
    )


def adapt_eccentricity_policy(
    policy: EccentricityPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
) -> EccentricityPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    if case.position_strategy != "EXPLICIT":
        raise PolicyResolutionError(
            "Geometry-derived eccentricity positions require native v2 evaluator support"
        )
    return EccentricityPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        indication_type=_required_text("indication_type", instrument.indication_type),
        range_type=_required_text("range_type", instrument.range_type),
        procedure_variant=case.procedure_variant,
        test_load_g=resolve_mass_expression(case.test_load, instrument, range_no),
        minimum_count=case.minimum_count,
        required_positions=tuple(
            PositionRequirement(
                position_code=item.position_code,
                rolling_direction=item.rolling_direction,
            )
            for item in case.explicit_positions
        ),
        allowed_receptor_types=case.allowed_receptor_types,
        required_support_count=case.required_support_count,
        require_position_coordinates=case.require_position_coordinates,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
    )


def adapt_discrimination_policy(
    policy: DiscriminationPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    mpe_g=None,
) -> DiscriminationPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    if len(case.test_loads) != 1:
        raise PolicyResolutionError(
            "Multi-load discrimination requires native v2 evaluator support"
        )
    minimum_change = (
        None
        if case.minimum_indication_change is None
        else resolve_mass_expression(
            case.minimum_indication_change,
            instrument,
            range_no,
            mpe_g=mpe_g,
        )
    )
    return DiscriminationPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        minimum_count=case.minimum_count,
        require_stabilization=case.require_stabilization,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
        indication_mode=case.indication_mode,
        test_load_g=resolve_mass_expression(case.test_loads[0], instrument, range_no),
        extra_load_g=resolve_mass_expression(
            case.extra_load,
            instrument,
            range_no,
            mpe_g=mpe_g,
        ),
        minimum_indication_change_g=minimum_change,
        minimum_displacement_mm=case.minimum_displacement_mm,
        operator=case.operator,
        semantics=case.semantics,
    )


def adapt_sensitivity_policy(
    policy: SensitivityPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    mpe_g=None,
) -> SensitivityPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    if len(case.test_loads) != 1:
        raise PolicyResolutionError(
            "Multi-load sensitivity requires native v2 evaluator support"
        )
    return SensitivityPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        minimum_count=case.minimum_count,
        require_stabilization=case.require_stabilization,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
        test_load_g=resolve_mass_expression(case.test_loads[0], instrument, range_no),
        extra_load_g=resolve_mass_expression(
            case.extra_load,
            instrument,
            range_no,
            mpe_g=mpe_g,
        ),
        minimum_displacement_mm=case.minimum_displacement_mm,
        operator=case.operator,
        semantics=case.semantics,
    )


def adapt_repeatability_policy(
    policy: RepeatabilityPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
) -> RepeatabilityPolicy:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    return RepeatabilityPolicy(
        schema_version="v1",
        evaluation_context=evaluation_context,
        indication_type=_required_text("indication_type", instrument.indication_type),
        range_type=_required_text("range_type", instrument.range_type),
        error_basis=case.error_basis,
        series=tuple(
            RepeatabilitySeriesPolicy(
                series_code=item.series_code,
                load_g=resolve_mass_expression(item.load, instrument, range_no),
                minimum_repetitions=item.minimum_repetitions,
                range_limit_basis=item.range_limit_basis,
                range_limit_multiplier=item.range_limit_multiplier,
                range_operator=item.range_operator,
                range_semantics=item.range_semantics,
            )
            for item in case.series
        ),
        required_zero_reset=case.required_zero_reset,
        require_stabilization=case.require_stabilization,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
    )


__all__ = [
    "adapt_discrimination_policy",
    "adapt_eccentricity_policy",
    "adapt_mpe_profile_set",
    "adapt_repeatability_policy",
    "adapt_sensitivity_policy",
    "adapt_temperature_zero_policy",
    "adapt_weighing_policy",
]
