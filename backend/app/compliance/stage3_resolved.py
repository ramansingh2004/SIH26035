"""Phase 25 Stage 3C3A resolved v2 policy contracts for Sections 6–10.

This module converts a selected parameterized Stage 3 v2 policy case into an
explicit immutable execution contract.

No regulatory values are supplied here. Semantic targets still require
explicit Stage3ResolutionFacts, and MPE-based limits require an explicit
caller-provided compatible-MPE resolver.
"""

from collections.abc import Callable

from app.compliance.domain import Frozen, InstrumentSnapshot, Number
from app.compliance.parameterized import PolicyResolutionError
from app.compliance.parameterized_stage3 import (
    CreepPolicyV2,
    LimitTarget,
    StabilityPolicyV2,
    TarePolicyV2,
    TiltingPolicyV2,
    WarmUpPolicyV2,
    ZeroReturnPolicyV2,
)
from app.compliance.stage3_resolution import (
    Stage3ResolutionFacts,
    resolve_limit_target_explicit,
    resolve_load_target_explicit,
    resolve_tare_value_target,
    resolve_tilt_target_explicit,
    select_stage3_policy_case,
)

MpeResolver = Callable[[Number], Number]


class ResolvedEvidenceRequirements(Frozen):
    require_environment: bool
    require_equipment: bool
    require_certificate: bool
    require_evidence: bool
    require_monotonic_timestamps: bool


def _evidence(case):
    return ResolvedEvidenceRequirements(
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
    )


def _limit_value(
    target: LimitTarget,
    *,
    instrument: InstrumentSnapshot,
    range_no: int,
    load_g: Number | None = None,
    mpe_for_load: MpeResolver | None = None,
):
    mpe_g = None
    if target.basis == "MPE":
        if load_g is None or mpe_for_load is None:
            raise PolicyResolutionError(
                "MPE-based Stage 3 limit requires load and compatible-MPE resolver"
            )
        mpe_g = mpe_for_load(load_g)

    return resolve_limit_target_explicit(
        target,
        instrument,
        range_no,
        mpe_g=mpe_g,
    ).value_g


# ---------------------------------------------------------------------------
# Section 6 — zero return and creep
# ---------------------------------------------------------------------------


class ResolvedZeroReturnPolicyV2(Frozen):
    minimum_count: int
    test_load_g: Number
    minimum_hold_seconds: Number
    limit_g: Number
    require_stabilization: bool
    require_zero_tracking_disabled: bool
    post_switch_limit_g: Number | None = None
    post_switch_window_seconds: Number | None = None
    evidence: ResolvedEvidenceRequirements


def resolve_zero_return_policy_v2(
    policy: ZeroReturnPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
) -> ResolvedZeroReturnPolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )
    load = resolve_load_target_explicit(
        case.test_load,
        instrument,
        range_no,
        facts=facts,
    ).value_g
    limit = _limit_value(
        case.limit,
        instrument=instrument,
        range_no=range_no,
        load_g=load,
    )

    post_switch_limit = None
    if case.post_switch_limit is not None:
        post_switch_limit = _limit_value(
            case.post_switch_limit,
            instrument=instrument,
            range_no=range_no,
            load_g=load,
        )

    return ResolvedZeroReturnPolicyV2(
        minimum_count=case.minimum_count,
        test_load_g=load,
        minimum_hold_seconds=case.minimum_hold_seconds,
        limit_g=limit,
        require_stabilization=case.require_stabilization,
        require_zero_tracking_disabled=case.require_zero_tracking_disabled,
        post_switch_limit_g=post_switch_limit,
        post_switch_window_seconds=case.post_switch_window_seconds,
        evidence=_evidence(case),
    )


class ResolvedCreepCriterionV2(Frozen):
    comparison: str
    start_seconds: Number
    end_seconds: Number
    limit_g: Number
    operator: str
    semantics: str


class ResolvedCreepRouteV2(Frozen):
    route_code: str
    minimum_duration_seconds: Number
    checkpoints_seconds: tuple[Number, ...]
    criteria: tuple[ResolvedCreepCriterionV2, ...]
    maximum_temperature_variation_c: Number | None = None


class ResolvedCreepPolicyV2(Frozen):
    test_load_g: Number
    require_stabilization: bool
    routes: tuple[ResolvedCreepRouteV2, ...]
    evidence: ResolvedEvidenceRequirements


def resolve_creep_policy_v2(
    policy: CreepPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
    mpe_for_load: MpeResolver | None = None,
) -> ResolvedCreepPolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )
    load = resolve_load_target_explicit(
        case.test_load,
        instrument,
        range_no,
        facts=facts,
    ).value_g

    routes = []
    for route in case.routes:
        criteria = []
        for criterion in route.criteria:
            criteria.append(
                ResolvedCreepCriterionV2(
                    comparison=criterion.comparison,
                    start_seconds=criterion.start_seconds,
                    end_seconds=criterion.end_seconds,
                    limit_g=_limit_value(
                        criterion.limit,
                        instrument=instrument,
                        range_no=range_no,
                        load_g=load,
                        mpe_for_load=mpe_for_load,
                    ),
                    operator=criterion.operator,
                    semantics=criterion.semantics,
                )
            )
        routes.append(
            ResolvedCreepRouteV2(
                route_code=route.route_code,
                minimum_duration_seconds=route.minimum_duration_seconds,
                checkpoints_seconds=route.checkpoints_seconds,
                criteria=tuple(criteria),
                maximum_temperature_variation_c=route.maximum_temperature_variation_c,
            )
        )

    return ResolvedCreepPolicyV2(
        test_load_g=load,
        require_stabilization=case.require_stabilization,
        routes=tuple(routes),
        evidence=_evidence(case),
    )


# ---------------------------------------------------------------------------
# Section 7 — stability of equilibrium
# ---------------------------------------------------------------------------


class ResolvedStabilityFunctionRuleV2(Frozen):
    function: str
    inhibit_when_unstable: bool
    permit_when_stable: bool
    observation_window_seconds: Number | None = None
    output_difference_limit_g: Number | None = None
    require_adjacent_values: bool


class ResolvedStabilityAccuracyRuleV2(Frozen):
    function: str
    minimum_trials: int
    limit_g: Number
    operator: str
    semantics: str


class ResolvedStabilityPolicyV2(Frozen):
    minimum_count: int
    test_load_g: Number
    require_worst_case_adjustment: bool
    require_manufacturer_documentation: bool
    function_rules: tuple[ResolvedStabilityFunctionRuleV2, ...]
    accuracy_rules: tuple[ResolvedStabilityAccuracyRuleV2, ...]
    evidence: ResolvedEvidenceRequirements


def resolve_stability_policy_v2(
    policy: StabilityPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
    mpe_for_load: MpeResolver | None = None,
) -> ResolvedStabilityPolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )
    load = resolve_load_target_explicit(
        case.test_load,
        instrument,
        range_no,
        facts=facts,
    ).value_g

    function_rules = []
    for rule in case.function_rules:
        output_limit = None
        if rule.output_difference_limit is not None:
            output_limit = _limit_value(
                rule.output_difference_limit,
                instrument=instrument,
                range_no=range_no,
                load_g=load,
                mpe_for_load=mpe_for_load,
            )
        function_rules.append(
            ResolvedStabilityFunctionRuleV2(
                function=rule.function,
                inhibit_when_unstable=rule.inhibit_when_unstable,
                permit_when_stable=rule.permit_when_stable,
                observation_window_seconds=rule.observation_window_seconds,
                output_difference_limit_g=output_limit,
                require_adjacent_values=rule.require_adjacent_values,
            )
        )

    accuracy_rules = tuple(
        ResolvedStabilityAccuracyRuleV2(
            function=rule.function,
            minimum_trials=rule.minimum_trials,
            limit_g=_limit_value(
                rule.limit,
                instrument=instrument,
                range_no=range_no,
                load_g=load,
                mpe_for_load=mpe_for_load,
            ),
            operator=rule.operator,
            semantics=rule.semantics,
        )
        for rule in case.accuracy_rules
    )

    return ResolvedStabilityPolicyV2(
        minimum_count=case.minimum_count,
        test_load_g=load,
        require_worst_case_adjustment=case.require_worst_case_adjustment,
        require_manufacturer_documentation=case.require_manufacturer_documentation,
        function_rules=tuple(function_rules),
        accuracy_rules=accuracy_rules,
        evidence=_evidence(case),
    )


# ---------------------------------------------------------------------------
# Section 8 — tilting
# ---------------------------------------------------------------------------


class ResolvedTiltingLoadV2(Frozen):
    load_g: Number
    loaded_limit_g: Number


class ResolvedTiltingPolicyV2(Frozen):
    tilt_mode: str
    required_directions: tuple[str, ...]
    reference_tilt_value: Number
    test_tilt_value: Number
    loads: tuple[ResolvedTiltingLoadV2, ...]
    unloaded_limit_g: Number
    require_reference_position: bool
    require_zero_tracking_disabled: bool
    protection: dict[str, bool | None]
    evidence: ResolvedEvidenceRequirements


def resolve_tilting_policy_v2(
    policy: TiltingPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
    mpe_for_load: MpeResolver | None = None,
) -> ResolvedTiltingPolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )

    loads = []
    for target in case.required_loads:
        load = resolve_load_target_explicit(
            target,
            instrument,
            range_no,
            facts=facts,
        ).value_g
        loads.append(
            ResolvedTiltingLoadV2(
                load_g=load,
                loaded_limit_g=_limit_value(
                    case.loaded_limit,
                    instrument=instrument,
                    range_no=range_no,
                    load_g=load,
                    mpe_for_load=mpe_for_load,
                ),
            )
        )

    return ResolvedTiltingPolicyV2(
        tilt_mode=case.tilt_mode,
        required_directions=case.required_directions,
        reference_tilt_value=resolve_tilt_target_explicit(
            case.reference_tilt,
            facts=facts,
        ).value,
        test_tilt_value=resolve_tilt_target_explicit(
            case.test_tilt,
            facts=facts,
        ).value,
        loads=tuple(loads),
        unloaded_limit_g=_limit_value(
            case.unloaded_limit,
            instrument=instrument,
            range_no=range_no,
            load_g=0,
            mpe_for_load=mpe_for_load,
        ),
        require_reference_position=case.require_reference_position,
        require_zero_tracking_disabled=case.require_zero_tracking_disabled,
        protection=case.protection.model_dump(),
        evidence=_evidence(case),
    )


# ---------------------------------------------------------------------------
# Section 9 — tare
# ---------------------------------------------------------------------------


class ResolvedTareLoadV2(Frozen):
    net_load_g: Number
    weighing_limit_g: Number


class ResolvedTareScenarioV2(Frozen):
    scenario_code: str
    tare_type: str
    tare_value_g: Number
    minimum_count: int
    stages: tuple[str, ...]
    loads: tuple[ResolvedTareLoadV2, ...]


class ResolvedTareSettingAccuracyV2(Frozen):
    enabled: bool
    minimum_trials: int | None = None
    limit_g: Number | None = None


class ResolvedTarePolicyV2(Frozen):
    scenarios: tuple[ResolvedTareScenarioV2, ...]
    enforce_gross_equals_tare_plus_net: bool
    require_declared_tare_capacity: bool
    require_stabilization: bool
    tare_setting_accuracy: ResolvedTareSettingAccuracyV2
    evidence: ResolvedEvidenceRequirements


def resolve_tare_policy_v2(
    policy: TarePolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
    mpe_for_load: MpeResolver | None = None,
) -> ResolvedTarePolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )

    scenarios = []
    for scenario in case.scenarios:
        tare_value = resolve_tare_value_target(
            scenario.tare_value,
            instrument,
        ).value_g
        loads = []
        for target in scenario.required_net_loads:
            net_load = resolve_load_target_explicit(
                target,
                instrument,
                range_no,
                facts=facts,
            ).value_g
            loads.append(
                ResolvedTareLoadV2(
                    net_load_g=net_load,
                    weighing_limit_g=_limit_value(
                        case.weighing_limit,
                        instrument=instrument,
                        range_no=range_no,
                        load_g=net_load,
                        mpe_for_load=mpe_for_load,
                    ),
                )
            )
        scenarios.append(
            ResolvedTareScenarioV2(
                scenario_code=scenario.scenario_code,
                tare_type=scenario.tare_type,
                tare_value_g=tare_value,
                minimum_count=scenario.minimum_count,
                stages=scenario.stages,
                loads=tuple(loads),
            )
        )

    accuracy = case.tare_setting_accuracy
    accuracy_limit = None
    if accuracy.limit is not None:
        if accuracy.limit.basis == "MPE":
            raise PolicyResolutionError(
                "Tare-setting accuracy MPE limit requires a dedicated verified load basis"
            )
        accuracy_limit = _limit_value(
            accuracy.limit,
            instrument=instrument,
            range_no=range_no,
        )

    return ResolvedTarePolicyV2(
        scenarios=tuple(scenarios),
        enforce_gross_equals_tare_plus_net=case.enforce_gross_equals_tare_plus_net,
        require_declared_tare_capacity=case.require_declared_tare_capacity,
        require_stabilization=case.require_stabilization,
        tare_setting_accuracy=ResolvedTareSettingAccuracyV2(
            enabled=accuracy.enabled,
            minimum_trials=accuracy.minimum_trials,
            limit_g=accuracy_limit,
        ),
        evidence=_evidence(case),
    )


# ---------------------------------------------------------------------------
# Section 10 — warm-up
# ---------------------------------------------------------------------------


class ResolvedWarmUpPolicyV2(Frozen):
    minimum_count: int
    minimum_power_off_seconds: Number
    required_checkpoints_seconds: tuple[Number, ...]
    checkpoint_tolerance_seconds: Number
    test_load_g: Number
    loaded_limit_g: Number
    require_first_stable_indication: bool
    require_zero_after_power_on: bool
    require_stabilized_observations: bool
    require_operating_manual_provision: bool
    permit_result_indication_before_ready: bool
    permit_result_transmission_before_ready: bool
    evidence: ResolvedEvidenceRequirements


def resolve_warm_up_policy_v2(
    policy: WarmUpPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    facts: Stage3ResolutionFacts | None = None,
    mpe_for_load: MpeResolver | None = None,
) -> ResolvedWarmUpPolicyV2:
    case = select_stage3_policy_case(
        policy.cases,
        instrument=instrument,
        evaluation_context=evaluation_context,
    )
    load = resolve_load_target_explicit(
        case.test_load,
        instrument,
        range_no,
        facts=facts,
    ).value_g

    return ResolvedWarmUpPolicyV2(
        minimum_count=case.minimum_count,
        minimum_power_off_seconds=case.minimum_power_off_seconds,
        required_checkpoints_seconds=case.required_checkpoints_seconds,
        checkpoint_tolerance_seconds=case.checkpoint_tolerance_seconds,
        test_load_g=load,
        loaded_limit_g=_limit_value(
            case.loaded_limit,
            instrument=instrument,
            range_no=range_no,
            load_g=load,
            mpe_for_load=mpe_for_load,
        ),
        require_first_stable_indication=case.require_first_stable_indication,
        require_zero_after_power_on=case.require_zero_after_power_on,
        require_stabilized_observations=case.require_stabilized_observations,
        require_operating_manual_provision=case.require_operating_manual_provision,
        permit_result_indication_before_ready=case.permit_result_indication_before_ready,
        permit_result_transmission_before_ready=case.permit_result_transmission_before_ready,
        evidence=_evidence(case),
    )


__all__ = [
    "ResolvedCreepPolicyV2",
    "ResolvedStabilityPolicyV2",
    "ResolvedTarePolicyV2",
    "ResolvedTiltingPolicyV2",
    "ResolvedWarmUpPolicyV2",
    "ResolvedZeroReturnPolicyV2",
    "resolve_creep_policy_v2",
    "resolve_stability_policy_v2",
    "resolve_tare_policy_v2",
    "resolve_tilting_policy_v2",
    "resolve_warm_up_policy_v2",
    "resolve_zero_return_policy_v2",
]
