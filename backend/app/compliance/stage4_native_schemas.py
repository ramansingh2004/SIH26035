"""Phase 25 Stage 4B native v2 data contracts for Sections 11–15."""

from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from app.compliance.domain import (
    Digest,
    EnvironmentSnapshot,
    EquipmentCalibrationSnapshot,
    Number,
    Observation,
    PositiveInt,
    RangeProcedureContext,
    Text,
    ordered_unique,
)


class Stage4EvidenceContextV2(RangeProcedureContext):
    environment: tuple[EnvironmentSnapshot, ...] = ()
    equipment: tuple[EquipmentCalibrationSnapshot, ...] = ()
    evidence_hashes: tuple[Digest, ...] = ()

    @model_validator(mode="after")
    def canonical_evidence(self):
        object.__setattr__(
            self,
            "equipment",
            ordered_unique(self.equipment, lambda item: item.reference),
        )
        object.__setattr__(
            self,
            "evidence_hashes",
            tuple(sorted(set(self.evidence_hashes))),
        )
        return self


class VoltageVariationContextV2(Stage4EvidenceContextV2):
    test_code: Literal["VOLTAGE_VARIATION"] = "VOLTAGE_VARIATION"
    procedure_variant: Literal[
        "AC_MAINS",
        "EXTERNAL_SUPPLY",
        "BATTERY_NO_CHARGING",
        "VEHICLE_SUPPLY",
    ]
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["VOLTAGE_VARIATION_V2"] = "VOLTAGE_VARIATION_V2"
    nominal_voltage_v: Number | None = Field(None, gt=0)
    declared_min_voltage_v: Number | None = Field(None, gt=0)
    declared_max_voltage_v: Number | None = Field(None, gt=0)
    minimum_operating_voltage_v: Number | None = Field(None, gt=0)
    phase_count: PositiveInt = 1
    protection_behavior_checked: StrictBool


class VoltageVariationObservationV2(Observation):
    test_code: Literal["VOLTAGE_VARIATION"] = "VOLTAGE_VARIATION"
    protocol: Literal["VOLTAGE_VARIATION_V2"] = "VOLTAGE_VARIATION_V2"
    observation_schema_version: Literal["v2"] = "v2"
    target_id: Text
    applied_voltage_v: Number = Field(gt=0)
    phase_no: PositiveInt | None = None
    load_g: Number = Field(ge=0)
    operational_state: Literal["INDICATING", "SWITCHED_OFF"]
    functions_operational: StrictBool
    indication_g: Number | None = None
    additional_load_g: Number | None = Field(None, ge=0)
    zero_error_g: Number | None = None
    measured_at: AwareDatetime

    @model_validator(mode="after")
    def measurement_shape(self):
        measurement = (
            self.indication_g,
            self.additional_load_g,
            self.zero_error_g,
        )
        if self.operational_state == "INDICATING" and any(
            value is None for value in measurement
        ):
            raise ValueError(
                "Indicating voltage-v2 observation requires measurement values"
            )
        return self


DisturbanceCode = Literal[
    "DISTURBANCE_VOLTAGE_DIP",
    "DISTURBANCE_BURST",
    "DISTURBANCE_SURGE",
    "DISTURBANCE_ESD",
    "DISTURBANCE_RADIATED_RF",
    "DISTURBANCE_CONDUCTED_RF",
    "DISTURBANCE_VEHICLE_SUPPLY",
]

DisturbanceVariant = Literal[
    "AC_MAINS_DIPS_INTERRUPTION",
    "BURST_LINES",
    "SURGE_LINES",
    "ESD",
    "RADIATED_RF",
    "CONDUCTED_RF",
    "SUPPLY_LINE_CONDUCTION",
    "NON_SUPPLY_LINE_COUPLING",
]


class DisturbanceContextV2(Stage4EvidenceContextV2):
    test_code: DisturbanceCode
    procedure_variant: DisturbanceVariant
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["DISTURBANCE_V2"] = "DISTURBANCE_V2"
    test_load_g: Number = Field(ge=0)
    warm_up_completed: StrictBool
    environment_stabilized: StrictBool
    peripherals_connected: StrictBool
    no_load_deviation_g: Number | None = None
    standard_identity: Text
    port_category: str | None = None


class DisturbanceObservationV2(Observation):
    test_code: DisturbanceCode
    protocol: Literal["DISTURBANCE_V2"] = "DISTURBANCE_V2"
    observation_schema_version: Literal["v2"] = "v2"
    severity_id: Text
    repetition_no: PositiveInt
    application: Text
    port_category: str | None = None
    polarity: Literal["POSITIVE", "NEGATIVE"] | None = None
    phase_angle_deg: Number | None = None
    frequency_mhz: Number | None = Field(None, ge=0)
    reference_indication_g: Number
    disturbed_indication_g: Number
    fault_detected: StrictBool
    fault_response: str | None = None
    fault_response_evidence_hash: Digest | None = None
    state_before: str | None = None
    state_during: str | None = None
    state_after: str | None = None
    measured_at: AwareDatetime

    @model_validator(mode="after")
    def fault_shape(self):
        if not self.fault_detected and (
            self.fault_response is not None
            or self.fault_response_evidence_hash is not None
        ):
            raise ValueError("Fault response requires fault_detected=true")
        return self


class DampHeatContextV2(Stage4EvidenceContextV2):
    test_code: Literal["DAMP_HEAT"] = "DAMP_HEAT"
    procedure_variant: Literal["STEADY_STATE"] = "STEADY_STATE"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["DAMP_HEAT_V2"] = "DAMP_HEAT_V2"
    declared_low_temperature_c: Number
    declared_high_temperature_c: Number
    reference_temperature_c: Number
    loads_g: tuple[Number, ...] = Field(min_length=1)
    same_reference_weights_confirmed: StrictBool

    @model_validator(mode="after")
    def unique_loads(self):
        if len(set(self.loads_g)) != len(self.loads_g):
            raise ValueError("Duplicate damp-heat-v2 load")
        return self


class DampHeatObservationV2(Observation):
    test_code: Literal["DAMP_HEAT"] = "DAMP_HEAT"
    protocol: Literal["DAMP_HEAT_V2"] = "DAMP_HEAT_V2"
    observation_schema_version: Literal["v2"] = "v2"
    stage: Literal["INITIAL", "HIGH_HUMIDITY", "FINAL"]
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    temperature_c: Number
    relative_humidity_percent: Number = Field(ge=0, le=100)
    stabilization_elapsed_s: Number = Field(ge=0)
    exposure_elapsed_s: Number = Field(ge=0)
    stabilized: StrictBool
    functions_operational: StrictBool
    measured_at: AwareDatetime


class SpanStabilityContextV2(Stage4EvidenceContextV2):
    test_code: Literal["SPAN_STABILITY"] = "SPAN_STABILITY"
    procedure_variant: Literal["LONG_DURATION"] = "LONG_DURATION"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["SPAN_STABILITY_V2"] = "SPAN_STABILITY_V2"
    test_load_g: Number = Field(ge=0)
    planned_duration_s: Number = Field(gt=0)
    same_reference_weights_confirmed: StrictBool
    zero_tracking_disabled: StrictBool
    builtin_span_adjustment_active: StrictBool
    temperature_test_completed: StrictBool
    damp_heat_completed_if_applicable: StrictBool
    extension_completed: StrictBool = False


class SpanStabilityObservationV2(Observation):
    test_code: Literal["SPAN_STABILITY"] = "SPAN_STABILITY"
    protocol: Literal["SPAN_STABILITY_V2"] = "SPAN_STABILITY_V2"
    observation_schema_version: Literal["v2"] = "v2"
    measurement_no: PositiveInt
    repeat_no: PositiveInt
    elapsed_s: Number = Field(ge=0)
    recovery_elapsed_s: Number = Field(ge=0)
    after_environmental_test: StrictBool
    power_disconnection_event: StrictBool
    power_disconnection_duration_s: Number | None = Field(None, ge=0)
    extension_measurement: StrictBool = False
    load_g: Number = Field(ge=0)
    zero_indication_g: Number
    zero_additional_load_g: Number = Field(ge=0)
    loaded_indication_g: Number
    loaded_additional_load_g: Number = Field(ge=0)
    influence_correction_g: Number = "0"
    measured_at: AwareDatetime

    @model_validator(mode="after")
    def power_event_shape(self):
        if self.power_disconnection_event != (
            self.power_disconnection_duration_s is not None
        ):
            raise ValueError(
                "Power disconnection event and duration must be supplied together"
            )
        return self


class EnduranceContextV2(Stage4EvidenceContextV2):
    test_code: Literal["ENDURANCE"] = "ENDURANCE"
    procedure_variant: Literal["MECHANICAL_CYCLING"] = "MECHANICAL_CYCLING"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["ENDURANCE_V2"] = "ENDURANCE_V2"
    cycling_target_load_g: Number = Field(ge=0)
    planned_cycles: PositiveInt
    completed_cycles: int = Field(ge=0, strict=True)
    after_other_tests_confirmed: StrictBool
    loaded_equilibrium_each_cycle_confirmed: StrictBool
    unloaded_equilibrium_each_cycle_confirmed: StrictBool
    normal_loading_force_confirmed: StrictBool
    same_reference_weights_confirmed: StrictBool
    abnormal_events: tuple[Text, ...] = ()
    abnormal_events_resolved: StrictBool = True


class EnduranceObservationV2(Observation):
    test_code: Literal["ENDURANCE"] = "ENDURANCE"
    protocol: Literal["ENDURANCE_V2"] = "ENDURANCE_V2"
    observation_schema_version: Literal["v2"] = "v2"
    phase: Literal["INITIAL", "FINAL"]
    point_id: Text
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    stabilized: StrictBool
    measured_at: AwareDatetime


__all__ = [
    "DampHeatContextV2",
    "DampHeatObservationV2",
    "DisturbanceContextV2",
    "DisturbanceObservationV2",
    "EnduranceContextV2",
    "EnduranceObservationV2",
    "SpanStabilityContextV2",
    "SpanStabilityObservationV2",
    "VoltageVariationContextV2",
    "VoltageVariationObservationV2",
]
