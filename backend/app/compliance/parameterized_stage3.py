"""Phase 25 Stage 3B parameterized policy contracts for Sections 6–10.

These types represent regulatory procedure choices without embedding OIML
constants or silently resolving source phrases such as "close to Max".

Stage 3B does not connect these policies to evaluator dispatch and does not
make any candidate rule VERIFIED.
"""

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import Frozen, InstrumentSnapshot, Number, PositiveInt, Text
from app.compliance.numbers import Operator, Semantics, exact
from app.compliance.parameterized import AccuracyClass, PolicyResolutionError


class Stage3Selector(Frozen):
    accuracy_classes: tuple[AccuracyClass, ...] = ()
    evaluation_contexts: tuple[Text, ...] = ()
    indication_types: tuple[Text, ...] = ()
    range_types: tuple[Text, ...] = ()
    power_supply_types: tuple[Text, ...] = ()
    is_electronic: StrictBool | None = None
    is_mobile: StrictBool | None = None
    level_indicator_available: StrictBool | None = None
    automatic_tilt_sensor: StrictBool | None = None

    @model_validator(mode="after")
    def unique_values(self):
        for values in (
            self.accuracy_classes,
            self.evaluation_contexts,
            self.indication_types,
            self.range_types,
            self.power_supply_types,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Stage 3 selector contains duplicate values")
        return self


def stage3_selector_state(
    selector: Stage3Selector,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
) -> bool | None:
    states: list[bool | None] = []

    def choice(allowed, value):
        if not allowed:
            return True
        if value is None:
            return None
        return value in allowed

    states.extend(
        (
            choice(selector.accuracy_classes, instrument.accuracy_class),
            choice(selector.evaluation_contexts, evaluation_context),
            choice(selector.indication_types, instrument.indication_type),
            choice(selector.range_types, instrument.range_type),
            choice(selector.power_supply_types, instrument.power_supply_type),
        )
    )

    for expected, actual in (
        (selector.is_electronic, instrument.is_electronic),
        (selector.is_mobile, instrument.is_mobile),
        (selector.level_indicator_available, instrument.level_indicator_available),
        (selector.automatic_tilt_sensor, instrument.automatic_tilt_sensor),
    ):
        if expected is not None:
            states.append(None if actual is None else actual is expected)

    if False in states:
        return False
    if None in states:
        return None
    return True


def resolve_stage3_case(cases, instrument: InstrumentSnapshot, evaluation_context: str):
    matched = []
    unresolved = []

    for case in cases:
        state = stage3_selector_state(case.selector, instrument, evaluation_context)
        if state is True:
            matched.append(case)
        elif state is None:
            unresolved.append(case)

    if len(matched) > 1:
        raise PolicyResolutionError("Multiple Stage 3 policy cases match")
    if unresolved:
        raise PolicyResolutionError(
            "Required Stage 3 instrument fact is unknown or coverage is ambiguous"
        )
    if not matched:
        raise PolicyResolutionError("No Stage 3 policy case covers these facts")
    return matched[0]


class LoadTarget(Frozen):
    basis: Literal[
        "ABSOLUTE_G",
        "MIN",
        "MAX",
        "MAX_FRACTION",
        "CLOSE_TO_MAX",
        "MPE_TRANSITION",
        "FUNCTION_OPERATING_RANGE",
    ]
    value: Number | None = Field(None, ge=0)
    transition_index: PositiveInt | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.basis in {"ABSOLUTE_G", "MAX_FRACTION"} and self.value is None:
            raise ValueError(f"{self.basis} requires value")
        if self.basis not in {"ABSOLUTE_G", "MAX_FRACTION"} and self.value is not None:
            raise ValueError(f"{self.basis} cannot carry numeric value")
        if self.basis == "MPE_TRANSITION" and self.transition_index is None:
            raise ValueError("MPE_TRANSITION requires transition_index")
        if self.basis != "MPE_TRANSITION" and self.transition_index is not None:
            raise ValueError("transition_index is valid only for MPE_TRANSITION")
        return self


def resolve_load_target(
    target: LoadTarget,
    instrument: InstrumentSnapshot,
    range_no: int,
):
    selected = instrument.select_range(range_no)

    if target.basis == "ABSOLUTE_G":
        return target.value
    if target.basis == "MIN":
        if selected.min_capacity_g is None:
            raise PolicyResolutionError("Selected range Min is unknown")
        return selected.min_capacity_g
    if target.basis == "MAX":
        return selected.max_capacity_g
    if target.basis == "MAX_FRACTION":
        return exact("multiply", selected.max_capacity_g, target.value)

    raise PolicyResolutionError(
        f"{target.basis} requires a verified runtime derivation or explicit test-plan fact"
    )


class LimitTarget(Frozen):
    basis: Literal[
        "ABSOLUTE_G",
        "SELECTED_E",
        "RANGE_E",
        "MPE",
    ]
    multiplier: Number = Field(ge=0)
    range_no: PositiveInt | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.basis == "RANGE_E" and self.range_no is None:
            raise ValueError("RANGE_E requires explicit range_no")
        if self.basis != "RANGE_E" and self.range_no is not None:
            raise ValueError("range_no is valid only for RANGE_E")
        return self


def resolve_limit_target(
    target: LimitTarget,
    instrument: InstrumentSnapshot,
    selected_range_no: int,
    *,
    mpe_g=None,
):
    if target.basis == "ABSOLUTE_G":
        return target.multiplier

    if target.basis == "SELECTED_E":
        base = instrument.select_range(selected_range_no).verification_interval_e_g
    elif target.basis == "RANGE_E":
        base = instrument.select_range(target.range_no).verification_interval_e_g
    elif target.basis == "MPE":
        if mpe_g is None:
            raise PolicyResolutionError("MPE-based limit requires an explicit MPE value")
        base = mpe_g
    else:  # pragma: no cover
        raise PolicyResolutionError("Unknown Stage 3 limit basis")

    return exact("multiply", base, target.multiplier)


class CommonEvidencePolicyV2(Frozen):
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


# ---------------------------------------------------------------------------
# Section 6 — time dependence
# ---------------------------------------------------------------------------


class ZeroReturnPolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    minimum_count: PositiveInt
    test_load: LoadTarget
    minimum_hold_seconds: Number = Field(ge=0)
    limit: LimitTarget
    require_stabilization: StrictBool
    require_zero_tracking_disabled: StrictBool
    post_switch_limit: LimitTarget | None = None
    post_switch_window_seconds: Number | None = Field(None, ge=0)

    @model_validator(mode="after")
    def post_switch_pair(self):
        if (self.post_switch_limit is None) != (self.post_switch_window_seconds is None):
            raise ValueError(
                "Post-switch zero-return limit and window must be provided together"
            )
        return self


class ZeroReturnPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[ZeroReturnPolicyCaseV2, ...] = Field(min_length=1)


class CreepCriterionV2(Frozen):
    comparison: Literal["FROM_INITIAL", "BETWEEN_CHECKPOINTS"]
    start_seconds: Number = Field(ge=0)
    end_seconds: Number = Field(gt=0)
    limit: LimitTarget
    operator: Operator
    semantics: Semantics

    @model_validator(mode="after")
    def interval(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Creep criterion end must be after start")
        if self.comparison == "FROM_INITIAL" and self.start_seconds != 0:
            raise ValueError("FROM_INITIAL creep criterion must start at zero")
        return self


class CreepRouteV2(Frozen):
    route_code: Text
    minimum_duration_seconds: Number = Field(gt=0)
    checkpoints_seconds: tuple[Number, ...] = Field(min_length=2)
    criteria: tuple[CreepCriterionV2, ...] = Field(min_length=1)
    maximum_temperature_variation_c: Number | None = Field(None, ge=0)

    @model_validator(mode="after")
    def canonical_checkpoints(self):
        values = tuple(sorted(self.checkpoints_seconds))
        if len(values) != len(set(values)):
            raise ValueError("Duplicate creep checkpoint")
        if values[0] != 0:
            raise ValueError("Creep route must include zero-time checkpoint")
        object.__setattr__(self, "checkpoints_seconds", values)
        return self


class CreepPolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    test_load: LoadTarget
    require_stabilization: StrictBool
    routes: tuple[CreepRouteV2, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_routes(self):
        codes = [item.route_code for item in self.routes]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate creep route")
        return self


class CreepPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[CreepPolicyCaseV2, ...] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Section 7 — stability of equilibrium
# ---------------------------------------------------------------------------


StabilityFunction = Literal["PRINTING", "STORAGE", "ZERO", "TARE"]


class StabilityFunctionRuleV2(Frozen):
    function: StabilityFunction
    inhibit_when_unstable: StrictBool
    permit_when_stable: StrictBool
    observation_window_seconds: Number | None = Field(None, ge=0)
    output_difference_limit: LimitTarget | None = None
    require_adjacent_values: StrictBool


class StabilityAccuracyRuleV2(Frozen):
    function: Literal["ZERO", "TARE"]
    minimum_trials: PositiveInt
    limit: LimitTarget
    operator: Operator
    semantics: Semantics


class StabilityPolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    minimum_count: PositiveInt
    test_load: LoadTarget
    require_worst_case_adjustment: StrictBool
    require_manufacturer_documentation: StrictBool
    function_rules: tuple[StabilityFunctionRuleV2, ...] = Field(min_length=1)
    accuracy_rules: tuple[StabilityAccuracyRuleV2, ...] = ()

    @model_validator(mode="after")
    def unique_functions(self):
        functions = [item.function for item in self.function_rules]
        if len(functions) != len(set(functions)):
            raise ValueError("Duplicate stability function rule")
        accuracy = [item.function for item in self.accuracy_rules]
        if len(accuracy) != len(set(accuracy)):
            raise ValueError("Duplicate stability accuracy rule")
        return self


class StabilityPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[StabilityPolicyCaseV2, ...] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Section 8 — tilting
# ---------------------------------------------------------------------------


class TiltTarget(Frozen):
    basis: Literal[
        "ABSOLUTE",
        "LEVEL_INDICATOR_LIMIT",
        "AUTOMATIC_SENSOR_LIMIT",
        "FIXED_RATIO",
    ]
    value: Number | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.basis in {"ABSOLUTE", "FIXED_RATIO"} and self.value is None:
            raise ValueError(f"{self.basis} tilt target requires value")
        if self.basis in {"LEVEL_INDICATOR_LIMIT", "AUTOMATIC_SENSOR_LIMIT"} and (
            self.value is not None
        ):
            raise ValueError(f"{self.basis} tilt target cannot carry value")
        return self


class TiltingProtectionV2(Frozen):
    warning_required: StrictBool | None = None
    display_operational_required: StrictBool | None = None
    printing_inhibited_required: StrictBool | None = None
    transmission_inhibited_required: StrictBool | None = None


class TiltingPolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    tilt_mode: Text
    required_directions: tuple[
        Literal["FORWARD", "BACKWARD", "LEFT", "RIGHT"], ...
    ] = Field(min_length=1)
    reference_tilt: TiltTarget
    test_tilt: TiltTarget
    required_loads: tuple[LoadTarget, ...] = Field(min_length=1)
    unloaded_limit: LimitTarget
    loaded_limit: LimitTarget
    require_reference_position: StrictBool
    require_zero_tracking_disabled: StrictBool
    protection: TiltingProtectionV2

    @model_validator(mode="after")
    def unique_directions(self):
        if len(self.required_directions) != len(set(self.required_directions)):
            raise ValueError("Duplicate tilting direction")
        return self


class TiltingPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[TiltingPolicyCaseV2, ...] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Section 9 — tare
# ---------------------------------------------------------------------------


class TareValueTarget(Frozen):
    basis: Literal["ABSOLUTE_G", "MAX_TARE_FRACTION"]
    value: Number = Field(ge=0)


class TareScenarioV2(Frozen):
    scenario_code: Text
    tare_type: Literal["ADDITIVE", "SUBTRACTIVE"]
    tare_value: TareValueTarget
    minimum_count: PositiveInt
    stages: tuple[Literal["UP", "DOWN"], ...] = Field(min_length=1)
    required_net_loads: tuple[LoadTarget, ...] = Field(min_length=1)


class TareSettingAccuracyV2(Frozen):
    enabled: StrictBool
    minimum_trials: PositiveInt | None = None
    limit: LimitTarget | None = None

    @model_validator(mode="after")
    def enabled_shape(self):
        if self.enabled and (self.minimum_trials is None or self.limit is None):
            raise ValueError("Enabled tare-setting accuracy requires trials and limit")
        if not self.enabled and (self.minimum_trials is not None or self.limit is not None):
            raise ValueError("Disabled tare-setting accuracy cannot carry requirements")
        return self


class TarePolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    scenarios: tuple[TareScenarioV2, ...] = Field(min_length=1)
    enforce_gross_equals_tare_plus_net: StrictBool
    require_declared_tare_capacity: StrictBool
    require_stabilization: StrictBool
    weighing_limit: LimitTarget
    tare_setting_accuracy: TareSettingAccuracyV2

    @model_validator(mode="after")
    def unique_scenarios(self):
        codes = [item.scenario_code for item in self.scenarios]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate tare scenario")
        return self


class TarePolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[TarePolicyCaseV2, ...] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Section 10 — warm-up
# ---------------------------------------------------------------------------


class WarmUpPolicyCaseV2(CommonEvidencePolicyV2):
    selector: Stage3Selector
    minimum_count: PositiveInt
    minimum_power_off_seconds: Number = Field(ge=0)
    required_checkpoints_seconds: tuple[Number, ...] = Field(min_length=1)
    checkpoint_tolerance_seconds: Number = Field(ge=0)
    test_load: LoadTarget
    loaded_limit: LimitTarget
    require_first_stable_indication: StrictBool
    require_zero_after_power_on: StrictBool
    require_stabilized_observations: StrictBool
    require_operating_manual_provision: StrictBool
    permit_result_indication_before_ready: StrictBool
    permit_result_transmission_before_ready: StrictBool

    @model_validator(mode="after")
    def checkpoints(self):
        ordered = tuple(sorted(self.required_checkpoints_seconds))
        if len(ordered) != len(set(ordered)):
            raise ValueError("Duplicate warm-up checkpoint")
        object.__setattr__(self, "required_checkpoints_seconds", ordered)
        return self


class WarmUpPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[WarmUpPolicyCaseV2, ...] = Field(min_length=1)


__all__ = [
    "CreepCriterionV2",
    "CreepPolicyV2",
    "CreepRouteV2",
    "LimitTarget",
    "LoadTarget",
    "StabilityAccuracyRuleV2",
    "StabilityFunctionRuleV2",
    "StabilityPolicyV2",
    "Stage3Selector",
    "TarePolicyV2",
    "TareScenarioV2",
    "TareSettingAccuracyV2",
    "TiltTarget",
    "TiltingPolicyV2",
    "TiltingProtectionV2",
    "WarmUpPolicyV2",
    "ZeroReturnPolicyV2",
    "resolve_limit_target",
    "resolve_load_target",
    "resolve_stage3_case",
    "stage3_selector_state",
]
