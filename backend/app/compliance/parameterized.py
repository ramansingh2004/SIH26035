"""Phase 25 parameterized regulatory-policy primitives.

These types generalize policy *representation* without supplying regulatory
constants. They intentionally contain no OIML thresholds or default procedures.

Stage 2B does not make the candidate ruleset authoritative. Official values are
encoded only after controlled source verification and independent sign-off.
"""

from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.compliance.domain import Frozen, InstrumentSnapshot, Number, PositiveInt, Text
from app.compliance.numbers import Operator, Semantics, exact
from app.compliance.regulatory import MpeProfile

AccuracyClass = Literal["I", "II", "III", "IIII"]


class PolicyResolutionError(ValueError):
    """A parameterized policy cannot be selected or resolved deterministically."""


class PolicySelector(Frozen):
    accuracy_classes: tuple[AccuracyClass, ...] = ()
    evaluation_contexts: tuple[Text, ...] = ()
    indication_types: tuple[Text, ...] = ()
    range_types: tuple[Text, ...] = ()
    self_indicating: StrictBool | None = None

    @model_validator(mode="after")
    def unique_values(self):
        for values in (
            self.accuracy_classes,
            self.evaluation_contexts,
            self.indication_types,
            self.range_types,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Policy selector contains duplicate values")
        return self


def selector_state(
    selector: PolicySelector,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
) -> bool | None:
    """Return True, False or unknown without inventing missing instrument facts."""

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
        )
    )

    if selector.self_indicating is not None:
        states.append(
            None
            if instrument.is_self_indicating is None
            else instrument.is_self_indicating is selector.self_indicating
        )

    if False in states:
        return False
    if None in states:
        return None
    return True


def resolve_policy_case(cases, instrument: InstrumentSnapshot, evaluation_context: str):
    """Select exactly one policy case; unknown or overlapping cases are blocked."""

    matched = []
    unresolved = []
    for case in cases:
        state = selector_state(case.selector, instrument, evaluation_context)
        if state is True:
            matched.append(case)
        elif state is None:
            unresolved.append(case)

    if len(matched) > 1:
        raise PolicyResolutionError("Multiple parameterized policy cases match")
    if unresolved:
        raise PolicyResolutionError(
            "Required instrument fact is unknown or policy coverage is ambiguous"
        )
    if not matched:
        raise PolicyResolutionError("No parameterized policy case covers these facts")
    return matched[0]


class MassExpression(Frozen):
    """Exact mass expression resolved only from explicit instrument/rule inputs."""

    basis: Literal[
        "ABSOLUTE_G",
        "MIN",
        "MAX",
        "E",
        "D",
        "MAX_PLUS_TARE",
        "MPE",
    ]
    value: Number = Field(ge=0)


def resolve_mass_expression(
    expression: MassExpression,
    instrument: InstrumentSnapshot,
    range_no: int,
    *,
    mpe_g=None,
):
    selected = instrument.select_range(range_no)

    if expression.basis == "ABSOLUTE_G":
        return expression.value
    if expression.basis == "MIN":
        if selected.min_capacity_g is None:
            raise PolicyResolutionError("Min is required by the regulatory expression")
        base = selected.min_capacity_g
    elif expression.basis == "MAX":
        base = selected.max_capacity_g
    elif expression.basis == "E":
        base = selected.verification_interval_e_g
    elif expression.basis == "D":
        base = selected.scale_interval_d_g
    elif expression.basis == "MAX_PLUS_TARE":
        if instrument.maximum_tare_g is None:
            raise PolicyResolutionError(
                "Maximum/additive tare fact is required by the regulatory expression"
            )
        base = exact("add", selected.max_capacity_g, instrument.maximum_tare_g)
    elif expression.basis == "MPE":
        if mpe_g is None:
            raise PolicyResolutionError("MPE value is required by the regulatory expression")
        base = mpe_g
    else:  # pragma: no cover - Literal + pydantic keep this unreachable.
        raise PolicyResolutionError("Unknown mass-expression basis")

    return exact("multiply", base, expression.value)


class TemperatureExpression(Frozen):
    basis: Literal["ABSOLUTE_C", "DECLARED_MIN", "DECLARED_MAX"]
    value: Number | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.basis == "ABSOLUTE_C" and self.value is None:
            raise ValueError("Absolute temperature requires a value")
        if self.basis != "ABSOLUTE_C" and self.value is not None:
            raise ValueError("Declared temperature bounds cannot carry an absolute value")
        return self


def resolve_temperature_expression(
    expression: TemperatureExpression,
    instrument: InstrumentSnapshot,
):
    if expression.basis == "ABSOLUTE_C":
        return expression.value
    if expression.basis == "DECLARED_MIN":
        if instrument.declared_temp_min_c is None:
            raise PolicyResolutionError("Declared minimum temperature is required")
        return instrument.declared_temp_min_c
    if instrument.declared_temp_max_c is None:
        raise PolicyResolutionError("Declared maximum temperature is required")
    return instrument.declared_temp_max_c


class MpeProfileSetV2(Frozen):
    schema_version: Literal["v2"]
    profiles: tuple[MpeProfile, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_profiles(self):
        keys = [(item.accuracy_class, item.evaluation_context) for item in self.profiles]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate MPE class/evaluation-context profile")
        return self


def resolve_mpe_profile(
    profile_set: MpeProfileSetV2,
    *,
    accuracy_class: str,
    evaluation_context: str,
) -> MpeProfile:
    matches = [
        profile
        for profile in profile_set.profiles
        if profile.accuracy_class == accuracy_class
        and profile.evaluation_context == evaluation_context
    ]
    if len(matches) != 1:
        raise PolicyResolutionError("MPE profile coverage is missing or ambiguous")
    return matches[0]


class DirectedLoadExpression(Frozen):
    direction: Literal["UP", "DOWN"]
    load: MassExpression


class WeighingPolicyCaseV2(Frozen):
    selector: PolicySelector
    minimum_count: PositiveInt
    stages: tuple[Literal["UP", "DOWN"], ...] = Field(min_length=1)
    required_loads: tuple[DirectedLoadExpression, ...] = ()
    transition_loads: tuple[DirectedLoadExpression, ...] = ()
    require_min: StrictBool
    require_max: StrictBool
    require_preload: StrictBool
    require_stabilization: StrictBool
    minimum_warmup_seconds: Number = Field(ge=0)
    zero_condition: Text
    require_environment: StrictBool
    temperature_min_c: Number | None = None
    temperature_max_c: Number | None = None
    humidity_min_percent: Number | None = Field(None, ge=0, le=100)
    humidity_max_percent: Number | None = Field(None, ge=0, le=100)
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


class WeighingPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[WeighingPolicyCaseV2, ...] = Field(min_length=1)


class TemperatureZeroPolicyCaseV2(Frozen):
    selector: PolicySelector
    minimum_count: PositiveInt
    temperature_sequence: tuple[TemperatureExpression, ...] = Field(min_length=2)
    normalization_span_c: Number = Field(gt=0)
    limit_multiplier_e: Number = Field(ge=0)
    operator: Operator
    semantics: Semantics
    require_stabilized_observations: StrictBool
    require_zero_tracking_disabled: StrictBool
    require_declared_temperature_range: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


class TemperatureZeroPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[TemperatureZeroPolicyCaseV2, ...] = Field(min_length=1)


class EccentricityPositionV2(Frozen):
    position_code: Text
    rolling_direction: Literal["FORWARD", "REVERSE"] | None = None


class EccentricityPolicyCaseV2(Frozen):
    selector: PolicySelector
    procedure_variant: Literal["WEIGHTS", "ROLLING_LOAD"]
    test_load: MassExpression
    minimum_count: PositiveInt
    position_strategy: Literal[
        "EXPLICIT",
        "UP_TO_FOUR_SUPPORTS",
        "MORE_THAN_FOUR_SUPPORTS",
        "SPECIAL_RECEPTOR",
        "ROLLING_LOAD",
    ]
    explicit_positions: tuple[EccentricityPositionV2, ...] = ()
    allowed_receptor_types: tuple[Text, ...] = Field(min_length=1)
    required_support_count: PositiveInt | None = None
    require_position_coordinates: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def position_contract(self):
        if self.position_strategy == "EXPLICIT" and not self.explicit_positions:
            raise ValueError("Explicit eccentricity strategy requires positions")
        if self.position_strategy != "EXPLICIT" and self.explicit_positions:
            raise ValueError("Derived eccentricity strategy cannot carry explicit positions")
        if self.procedure_variant == "WEIGHTS" and any(
            item.rolling_direction is not None for item in self.explicit_positions
        ):
            raise ValueError("Weights eccentricity positions cannot carry rolling direction")
        if self.procedure_variant =="ROLLING_LOAD" and self.position_strategy == "EXPLICIT" and any(
            item.rolling_direction is None for item in self.explicit_positions
        ):
            raise ValueError("Explicit rolling-load positions require rolling direction")
        return self


class EccentricityPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[EccentricityPolicyCaseV2, ...] = Field(min_length=1)


class DiscriminationPolicyCaseV2(Frozen):
    selector: PolicySelector
    indication_mode: Literal["DIGITAL", "ANALOG"]
    minimum_count: PositiveInt
    test_loads: tuple[MassExpression, ...] = Field(min_length=1)
    extra_load: MassExpression
    minimum_indication_change: MassExpression | None = None
    minimum_displacement_mm: Number | None = Field(None, ge=0)
    operator: Operator
    semantics: Semantics
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def mode_limit(self):
        if self.indication_mode == "DIGITAL" and self.minimum_indication_change is None:
            raise ValueError("Digital discrimination requires an indication-change expression")
        if self.indication_mode == "ANALOG" and self.minimum_displacement_mm is None:
            raise ValueError("Analog discrimination requires a displacement threshold")
        return self


class DiscriminationPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[DiscriminationPolicyCaseV2, ...] = Field(min_length=1)


class SensitivityPolicyCaseV2(Frozen):
    selector: PolicySelector
    minimum_count: PositiveInt
    test_loads: tuple[MassExpression, ...] = Field(min_length=1)
    extra_load: MassExpression
    minimum_displacement_mm: Number = Field(ge=0)
    operator: Operator
    semantics: Semantics
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool


class SensitivityPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[SensitivityPolicyCaseV2, ...] = Field(min_length=1)


class RepeatabilitySeriesPolicyV2(Frozen):
    series_code: Text
    load: MassExpression
    minimum_repetitions: PositiveInt
    range_limit_basis: Literal["MPE", "E"]
    range_limit_multiplier: Number = Field(ge=0)
    range_operator: Operator
    range_semantics: Semantics


class RepeatabilityPolicyCaseV2(Frozen):
    selector: PolicySelector
    error_basis: Literal["RAW", "CORRECTED"]
    series: tuple[RepeatabilitySeriesPolicyV2, ...] = Field(min_length=1)
    required_zero_reset: StrictBool | None = None
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool

    @model_validator(mode="after")
    def unique_series(self):
        keys = [series.series_code for series in self.series]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate repeatability series")
        return self


class RepeatabilityPolicyV2(Frozen):
    schema_version: Literal["v2"]
    cases: tuple[RepeatabilityPolicyCaseV2, ...] = Field(min_length=1)


__all__ = [
    "DiscriminationPolicyV2",
    "DirectedLoadExpression",
    "EccentricityPolicyV2",
    "EccentricityPositionV2",
    "MassExpression",
    "MpeProfileSetV2",
    "PolicyResolutionError",
    "PolicySelector",
    "RepeatabilityPolicyV2",
    "SensitivityPolicyV2",
    "TemperatureExpression",
    "TemperatureZeroPolicyV2",
    "WeighingPolicyV2",
    "resolve_mass_expression",
    "resolve_mpe_profile",
    "resolve_policy_case",
    "resolve_temperature_expression",
    "selector_state",
]
