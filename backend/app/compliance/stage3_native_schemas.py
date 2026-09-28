"""Phase 25 Stage 3D native v2 procedure/observation schemas.

These schemas capture Sections 6–10 data that the legacy v1 schemas cannot
represent without information loss. They are data contracts only; Stage 3C
continues to block v2 evaluator execution.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from app.compliance.domain import (
    Digest,
    EnvironmentSnapshot,
    EquipmentCalibrationSnapshot,
    Frozen,
    Number,
    Observation,
    PositiveInt,
    RangeProcedureContext,
    Text,
    ordered_unique,
)


class Stage3EvidenceContextV2(RangeProcedureContext):
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


class ZeroReturnContextV2(Stage3EvidenceContextV2):
    test_code: Literal["ZERO_RETURN"] = "ZERO_RETURN"
    procedure_variant: Literal["ZERO_RETURN"] = "ZERO_RETURN"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["ZERO_RETURN_V2"] = "ZERO_RETURN_V2"
    test_load_g: Number = Field(ge=0)
    planned_hold_seconds: Number = Field(ge=0)
    stabilized: StrictBool
    zero_tracking_disabled: StrictBool
    post_switch_check_required: StrictBool
    post_switch_range_no: PositiveInt | None = None
    post_switch_window_seconds: Number | None = Field(None, ge=0)

    @model_validator(mode="after")
    def post_switch_shape(self):
        supplied = (
            self.post_switch_range_no is not None
            and self.post_switch_window_seconds is not None
        )
        if self.post_switch_check_required != supplied:
            raise ValueError(
                "Post-switch check requires range number and timing window together"
            )
        return self


class ZeroReturnObservationV2(Observation):
    test_code: Literal["ZERO_RETURN"] = "ZERO_RETURN"
    protocol: Literal["ZERO_RETURN_V2"] = "ZERO_RETURN_V2"
    observation_schema_version: Literal["v2"] = "v2"
    phase: Literal["PRE_LOAD_ZERO", "POST_UNLOAD_ZERO", "POST_SWITCH_ZERO"]
    indication_g: Number
    elapsed_seconds: Number = Field(ge=0)
    active_range_no: PositiveInt
    stabilized: StrictBool
    zero_tracking_active: StrictBool
    measured_at: AwareDatetime


class CreepContextV2(Stage3EvidenceContextV2):
    test_code: Literal["CREEP"] = "CREEP"
    procedure_variant: Literal["SHORT", "EXTENDED"]
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["CREEP_V2"] = "CREEP_V2"
    test_load_g: Number = Field(ge=0)
    planned_duration_seconds: Number = Field(gt=0)
    stabilized: StrictBool
    temperature_monitoring_active: StrictBool


class CreepObservationV2(Observation):
    test_code: Literal["CREEP"] = "CREEP"
    protocol: Literal["CREEP_V2"] = "CREEP_V2"
    observation_schema_version: Literal["v2"] = "v2"
    elapsed_seconds: Number = Field(ge=0)
    indication_g: Number
    temperature_c: Number
    stabilized: StrictBool
    measured_at: AwareDatetime


StabilityFunction = Literal["PRINTING", "STORAGE", "ZERO", "TARE"]


class StabilityContextV2(Stage3EvidenceContextV2):
    test_code: Literal["STABILITY_EQUILIBRIUM"] = "STABILITY_EQUILIBRIUM"
    procedure_variant: Literal["FUNCTIONAL"] = "FUNCTIONAL"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["STABILITY_EQUILIBRIUM_V2"] = "STABILITY_EQUILIBRIUM_V2"
    functions_under_test: tuple[StabilityFunction, ...] = Field(min_length=1)
    test_load_g: Number = Field(ge=0)
    worst_case_adjustment_confirmed: StrictBool
    manufacturer_documentation_evidence_hash: Digest | None = None

    @model_validator(mode="after")
    def canonical_functions(self):
        object.__setattr__(
            self,
            "functions_under_test",
            tuple(sorted(set(self.functions_under_test))),
        )
        return self


class StabilityObservationV2(Observation):
    test_code: Literal["STABILITY_EQUILIBRIUM"] = "STABILITY_EQUILIBRIUM"
    protocol: Literal["STABILITY_EQUILIBRIUM_V2"] = "STABILITY_EQUILIBRIUM_V2"
    observation_schema_version: Literal["v2"] = "v2"
    function: StabilityFunction
    trial_no: PositiveInt
    equilibrium_stable: StrictBool
    operation_performed: StrictBool
    event_output_g: Number | None = None
    final_weight_value_g: Number | None = None
    observation_window_seconds: Number | None = Field(None, ge=0)
    adjacent_values_count: int | None = Field(None, ge=0, strict=True)
    zero_or_tare_error_g: Number | None = None
    measured_at: AwareDatetime

    @model_validator(mode="after")
    def function_shape(self):
        if self.function in {"PRINTING", "STORAGE"}:
            required = (
                self.event_output_g,
                self.final_weight_value_g,
                self.observation_window_seconds,
                self.adjacent_values_count,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "Printing/storage stability observation requires quantitative output data"
                )
        if self.function in {"ZERO", "TARE"} and self.zero_or_tare_error_g is None:
            raise ValueError("Zero/tare stability observation requires accuracy error")
        return self


TiltMode = Literal[
    "LEVEL_INDICATOR",
    "AUTOMATIC_TILT_SENSOR",
    "NO_LEVEL_DEVICE",
    "MOBILE_AUTOMATIC_TILT_SENSOR",
    "MOBILE_CARDANIC",
]
TiltDirection = Literal["FORWARD", "BACKWARD", "LEFT", "RIGHT"]


class TiltingContextV2(Stage3EvidenceContextV2):
    test_code: Literal["TILTING"] = "TILTING"
    procedure_variant: TiltMode
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["TILTING_V2"] = "TILTING_V2"
    tilt_mode: TiltMode
    reference_tilt_value: Number
    test_tilt_value: Number
    directions: tuple[TiltDirection, ...] = Field(min_length=1)
    reference_position_confirmed: StrictBool
    zero_tracking_disabled: StrictBool
    level_indicator_limit: Number | None = None
    automatic_tilt_sensor_limit: Number | None = None
    close_to_max_load_g: Number | None = Field(None, ge=0)
    close_to_max_confirmed: StrictBool | None = None
    function_operating_range_load_g: Number | None = Field(None, ge=0)
    function_operating_range_confirmed: StrictBool | None = None
    protection_behavior_checked: StrictBool | None = None

    @model_validator(mode="after")
    def mode_and_directions(self):
        if self.tilt_mode != self.procedure_variant:
            raise ValueError("Tilt mode must match procedure variant")
        object.__setattr__(
            self,
            "directions",
            ordered_unique(self.directions, lambda value: value),
        )
        return self


class TiltingObservationV2(Observation):
    test_code: Literal["TILTING"] = "TILTING"
    protocol: Literal["TILTING_V2"] = "TILTING_V2"
    observation_schema_version: Literal["v2"] = "v2"
    direction: TiltDirection
    stage: Literal["REFERENCE", "TILTED"]
    tilt_value: Number
    load_g: Number = Field(ge=0)
    indication_g: Number
    additional_load_g: Number = Field(ge=0)
    zero_error_g: Number
    zero_tracking_active: StrictBool
    warning_generated: StrictBool | None = None
    display_operational: StrictBool | None = None
    printing_inhibited: StrictBool | None = None
    transmission_inhibited: StrictBool | None = None
    measured_at: AwareDatetime


class TareScenarioContextV2(Frozen):
    scenario_code: Text
    tare_type: Literal["ADDITIVE", "SUBTRACTIVE"]
    tare_value_g: Number = Field(ge=0)


class TareContextV2(Stage3EvidenceContextV2):
    test_code: Literal["TARE"] = "TARE"
    procedure_variant: Literal["DIGITAL_PRE_ROUNDING"] = "DIGITAL_PRE_ROUNDING"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["TARE_V2"] = "TARE_V2"
    stages: tuple[Literal["UP", "DOWN"], ...] = Field(min_length=1)
    tare_scenarios: tuple[TareScenarioContextV2, ...] = Field(min_length=1)
    stabilized: StrictBool
    tare_setting_accuracy_included: StrictBool

    @model_validator(mode="after")
    def canonical_scenarios(self):
        object.__setattr__(
            self,
            "tare_scenarios",
            ordered_unique(self.tare_scenarios, lambda item: item.scenario_code),
        )
        return self


class TareObservationV2(Observation):
    test_code: Literal["TARE"] = "TARE"
    protocol: Literal["TARE_V2"] = "TARE_V2"
    observation_schema_version: Literal["v2"] = "v2"
    observation_kind: Literal["WEIGHING", "TARE_SETTING"]
    tare_scenario_code: Text
    tare_type: Literal["ADDITIVE", "SUBTRACTIVE"]
    tare_value_g: Number = Field(ge=0)
    net_load_g: Number | None = Field(None, ge=0)
    gross_load_g: Number | None = Field(None, ge=0)
    indication_g: Number | None = None
    additional_load_g: Number | None = Field(None, ge=0)
    zero_error_g: Number | None = None
    direction: Literal["UP", "DOWN"] | None = None
    tare_setting_error_g: Number | None = None
    measured_at: AwareDatetime

    @model_validator(mode="after")
    def observation_shape(self):
        weighing_values = (
            self.net_load_g,
            self.gross_load_g,
            self.indication_g,
            self.additional_load_g,
            self.zero_error_g,
            self.direction,
        )
        if self.observation_kind == "WEIGHING":
            if any(value is None for value in weighing_values):
                raise ValueError(
                    "Tare weighing observation requires complete weighing values"
                )
            if self.tare_setting_error_g is not None:
                raise ValueError(
                    "Tare weighing observation cannot carry tare-setting error"
                )
        else:
            if self.tare_setting_error_g is None:
                raise ValueError(
                    "Tare-setting observation requires tare-setting error"
                )
            if any(value is not None for value in weighing_values):
                raise ValueError(
                    "Tare-setting observation cannot carry weighing-only values"
                )
        return self


class WarmUpContextV2(Stage3EvidenceContextV2):
    test_code: Literal["WARM_UP"] = "WARM_UP"
    procedure_variant: Literal["WARM_UP"] = "WARM_UP"
    procedure_schema_version: Literal["v2"] = "v2"
    protocol: Literal["WARM_UP_V2"] = "WARM_UP_V2"
    power_off_seconds: Number = Field(ge=0)
    test_load_g: Number = Field(ge=0)
    first_stable_indication_observed: StrictBool
    zero_set_after_power_on: StrictBool
    operating_manual_provision_confirmed: StrictBool | None = None
    ready_elapsed_seconds: Number | None = Field(None, ge=0)


class WarmUpObservationV2(Observation):
    test_code: Literal["WARM_UP"] = "WARM_UP"
    protocol: Literal["WARM_UP_V2"] = "WARM_UP_V2"
    observation_schema_version: Literal["v2"] = "v2"
    elapsed_seconds: Number = Field(ge=0)
    zero_indication_g: Number
    zero_additional_load_g: Number = Field(ge=0)
    load_g: Number = Field(ge=0)
    loaded_indication_g: Number
    loaded_additional_load_g: Number = Field(ge=0)
    temperature_c: Number | None = None
    stabilized: StrictBool
    instrument_ready: StrictBool
    result_indicated: StrictBool
    result_transmitted: StrictBool
    measured_at: AwareDatetime


__all__ = [
    "CreepContextV2",
    "CreepObservationV2",
    "StabilityContextV2",
    "StabilityObservationV2",
    "TareContextV2",
    "TareObservationV2",
    "TiltingContextV2",
    "TiltingObservationV2",
    "WarmUpContextV2",
    "WarmUpObservationV2",
    "ZeroReturnContextV2",
    "ZeroReturnObservationV2",
]
