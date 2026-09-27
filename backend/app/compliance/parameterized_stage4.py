"""Phase 25 Stage 4B parameterized v2 policies for Sections 11–15.

These contracts preserve source-native semantics without promoting candidate
values to verified regulatory rules.
"""

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import Frozen, Number, PositiveInt, Text, ordered_unique


class VoltageTargetV2(Frozen):
    target_id: Text
    source: Literal[
        "ABSOLUTE_V",
        "NOMINAL_MULTIPLIER",
        "MIN_DECLARED_MULTIPLIER",
        "MAX_DECLARED_MULTIPLIER",
        "MINIMUM_OPERATING_V",
    ]
    value: Number = Field(gt=0)


class VoltageVariationPolicyV2(Frozen):
    schema_version: Literal["v2"] = "v2"
    evaluation_context: Text
    power_supply_profile: Literal[
        "AC_MAINS",
        "EXTERNAL_SUPPLY",
        "BATTERY_NO_CHARGING",
        "VEHICLE_SUPPLY",
    ]
    required_voltage_targets: tuple[VoltageTargetV2, ...] = Field(min_length=1)
    required_loads_g: tuple[Number, ...] = Field(min_length=1)
    allow_switch_off: StrictBool
    require_functions_operational_when_indicating: StrictBool
    successive_phase_application_required: StrictBool = False

    @model_validator(mode="after")
    def canonical_values(self):
        object.__setattr__(
            self,
            "required_voltage_targets",
            ordered_unique(
                self.required_voltage_targets,
                lambda item: item.target_id,
            ),
        )
        if len(set(self.required_loads_g)) != len(self.required_loads_g):
            raise ValueError("Duplicate Stage 4 voltage load")
        object.__setattr__(
            self,
            "required_loads_g",
            tuple(sorted(self.required_loads_g)),
        )
        return self


class DisturbanceSeverityV2(Frozen):
    severity_id: Text
    standard_reference: Text
    application: Text
    level: str | None = None
    amplitude: Number | None = None
    amplitude_unit: Literal["V", "kV", "V/m", "%", "1"] | None = None
    duration_cycles: Number | None = Field(None, ge=0)
    duration_seconds: Number | None = Field(None, ge=0)
    frequency_start_mhz: Number | None = Field(None, ge=0)
    frequency_end_mhz: Number | None = Field(None, ge=0)
    polarity: Literal["POSITIVE", "NEGATIVE", "BOTH"] | None = None
    phase_angles_deg: tuple[Number, ...] = ()
    pulse_family: str | None = None
    port_category: str | None = None

    @model_validator(mode="after")
    def amplitude_shape(self):
        if (self.amplitude is None) != (self.amplitude_unit is None):
            raise ValueError("Disturbance amplitude and unit must be supplied together")
        return self


class DisturbancePolicyV2(Frozen):
    schema_version: Literal["v2"] = "v2"
    test_code: Literal[
        "DISTURBANCE_VOLTAGE_DIP",
        "DISTURBANCE_BURST",
        "DISTURBANCE_SURGE",
        "DISTURBANCE_ESD",
        "DISTURBANCE_RADIATED_RF",
        "DISTURBANCE_CONDUCTED_RF",
        "DISTURBANCE_VEHICLE_SUPPLY",
    ]
    procedure_variant: Text
    evaluation_context: Text
    severities: tuple[DisturbanceSeverityV2, ...] = Field(min_length=1)
    repetitions_per_severity: PositiveInt
    minimum_interval_seconds: Number | None = Field(None, ge=0)
    require_warm_up: StrictBool
    require_environment_stabilized: StrictBool
    require_peripherals_connected: StrictBool
    require_fault_response_evidence: StrictBool
    accepted_fault_responses: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def canonical_severities(self):
        object.__setattr__(
            self,
            "severities",
            ordered_unique(self.severities, lambda item: item.severity_id),
        )
        object.__setattr__(
            self,
            "accepted_fault_responses",
            tuple(sorted(set(self.accepted_fault_responses))),
        )
        return self


class DampHeatStageV2(Frozen):
    stage: Literal["INITIAL", "HIGH_HUMIDITY", "FINAL"]
    temperature_source: Literal[
        "REFERENCE_TEMPERATURE",
        "DECLARED_HIGH_TEMPERATURE",
    ]
    relative_humidity_percent: Number = Field(ge=0, le=100)
    minimum_stabilization_seconds: Number = Field(ge=0)
    minimum_exposure_seconds: Number = Field(ge=0)


class DampHeatPolicyV2(Frozen):
    schema_version: Literal["v2"] = "v2"
    evaluation_context: Text
    excluded_accuracy_classes: tuple[Literal["I", "II", "III", "IIII"], ...] = ()
    class_ii_minimum_e_g: Number | None = Field(None, ge=0)
    minimum_distinct_loads: PositiveInt
    stage_requirements: tuple[DampHeatStageV2, ...] = Field(min_length=3)
    require_same_reference_weights: StrictBool
    require_functions_operational: StrictBool

    @model_validator(mode="after")
    def stage_shape(self):
        stages = tuple(item.stage for item in self.stage_requirements)
        if stages != ("INITIAL", "HIGH_HUMIDITY", "FINAL"):
            raise ValueError("Damp-heat v2 stages must be INITIAL/HIGH_HUMIDITY/FINAL")
        return self


class SpanStabilityPolicyV2(Frozen):
    schema_version: Literal["v2"] = "v2"
    evaluation_context: Text
    excluded_accuracy_classes: tuple[Literal["I", "II", "III", "IIII"], ...] = ()
    test_load_target: Literal["CLOSE_TO_MAX"]
    maximum_duration_seconds: Number = Field(gt=0)
    minimum_measurements: PositiveInt
    minimum_interval_seconds: Number = Field(gt=0)
    maximum_interval_seconds: Number = Field(gt=0)
    required_power_disconnections: PositiveInt
    minimum_power_disconnection_seconds: Number = Field(gt=0)
    normal_recovery_seconds: Number = Field(gt=0)
    post_environmental_test_recovery_seconds: Number = Field(gt=0)
    first_measurement_repeat_count: PositiveInt
    require_same_reference_weights: StrictBool
    require_zero_tracking_disabled: StrictBool
    require_builtin_span_adjustment_active: StrictBool
    variation_formula: Literal["MAX_HALF_E_HALF_ABS_MPE"]
    trend_extension_required: StrictBool

    @model_validator(mode="after")
    def intervals(self):
        if self.minimum_interval_seconds > self.maximum_interval_seconds:
            raise ValueError("Span-stability v2 interval bounds reversed")
        return self


class EndurancePolicyV2(Frozen):
    schema_version: Literal["v2"] = "v2"
    evaluation_context: Text
    applicable_accuracy_classes: tuple[
        Literal["I", "II", "III", "IIII"], ...
    ] = Field(min_length=1)
    maximum_capacity_limit_g: Number = Field(gt=0)
    required_cycles: PositiveInt
    cycling_load_fraction_of_max: Number = Field(gt=0, le=1)
    require_after_other_tests: StrictBool
    require_loaded_equilibrium_each_cycle: StrictBool
    require_unloaded_equilibrium_each_cycle: StrictBool
    require_normal_loading_force: StrictBool
    durability_formula: Literal["ABS_CORRECTED_ERROR_CHANGE"]

    @model_validator(mode="after")
    def canonical_classes(self):
        object.__setattr__(
            self,
            "applicable_accuracy_classes",
            tuple(sorted(set(self.applicable_accuracy_classes))),
        )
        return self


__all__ = [
    "DampHeatPolicyV2",
    "DampHeatStageV2",
    "DisturbancePolicyV2",
    "DisturbanceSeverityV2",
    "EndurancePolicyV2",
    "SpanStabilityPolicyV2",
    "VoltageTargetV2",
    "VoltageVariationPolicyV2",
]
