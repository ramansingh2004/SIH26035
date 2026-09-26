"""Native parameterized Section 4 policy resolution.

This module resolves multi-load discrimination and sensitivity policies without
collapsing them into the legacy single-load v1 policy shape. It contains no
regulatory defaults or OIML constants.
"""

from collections.abc import Callable

from pydantic import Field, model_validator

from app.compliance.domain import Frozen, InstrumentSnapshot, Number, PositiveInt, StrictBool
from app.compliance.numbers import Operator, Semantics
from app.compliance.parameterized import (
    DiscriminationPolicyV2,
    MassExpression,
    PolicyResolutionError,
    SensitivityPolicyV2,
    resolve_mass_expression,
    resolve_policy_case,
)


class ResolvedDiscriminationLoad(Frozen):
    test_load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    minimum_indication_change_g: Number | None = Field(None, ge=0)
    minimum_displacement_mm: Number | None = Field(None, ge=0)


class ResolvedDiscriminationPolicyV2(Frozen):
    schema_version: str = "resolved-v2"
    evaluation_context: str
    minimum_count: PositiveInt
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool
    indication_mode: str
    operator: Operator
    semantics: Semantics
    loads: tuple[ResolvedDiscriminationLoad, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_loads(self):
        if len({item.test_load_g for item in self.loads}) != len(self.loads):
            raise ValueError("Duplicate resolved discrimination load")
        return self


class ResolvedSensitivityLoad(Frozen):
    test_load_g: Number = Field(ge=0)
    extra_load_g: Number = Field(ge=0)
    minimum_displacement_mm: Number = Field(ge=0)


class ResolvedSensitivityPolicyV2(Frozen):
    schema_version: str = "resolved-v2"
    evaluation_context: str
    minimum_count: PositiveInt
    require_stabilization: StrictBool
    require_environment: StrictBool
    require_equipment: StrictBool
    require_certificate: StrictBool
    require_evidence: StrictBool
    require_monotonic_timestamps: StrictBool
    operator: Operator
    semantics: Semantics
    loads: tuple[ResolvedSensitivityLoad, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_loads(self):
        if len({item.test_load_g for item in self.loads}) != len(self.loads):
            raise ValueError("Duplicate resolved sensitivity load")
        return self


MpeForLoad = Callable[[Number], Number]


def _test_load(
    expression: MassExpression,
    instrument: InstrumentSnapshot,
    range_no: int,
):
    if expression.basis == "MPE":
        raise PolicyResolutionError(
            "A Section 4 test-load expression cannot be based on MPE because "
            "the MPE itself depends on the selected load"
        )
    return resolve_mass_expression(expression, instrument, range_no)


def _at_load(
    expression: MassExpression,
    *,
    instrument: InstrumentSnapshot,
    range_no: int,
    test_load_g,
    mpe_for_load: MpeForLoad | None,
):
    mpe_g = None
    if expression.basis == "MPE":
        if mpe_for_load is None:
            raise PolicyResolutionError("MPE-based expression requires an MPE resolver")
        mpe_g = mpe_for_load(test_load_g)
    return resolve_mass_expression(
        expression,
        instrument,
        range_no,
        mpe_g=mpe_g,
    )


def resolve_discrimination_policy_v2(
    policy: DiscriminationPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    mpe_for_load: MpeForLoad | None = None,
) -> ResolvedDiscriminationPolicyV2:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    test_loads = tuple(
        _test_load(expression, instrument, range_no) for expression in case.test_loads
    )
    if len(set(test_loads)) != len(test_loads):
        raise PolicyResolutionError("Discrimination test-load expressions resolve to duplicates")

    loads = []
    for test_load_g in test_loads:
        minimum_change = (
            None
            if case.minimum_indication_change is None
            else _at_load(
                case.minimum_indication_change,
                instrument=instrument,
                range_no=range_no,
                test_load_g=test_load_g,
                mpe_for_load=mpe_for_load,
            )
        )
        loads.append(
            ResolvedDiscriminationLoad(
                test_load_g=test_load_g,
                extra_load_g=_at_load(
                    case.extra_load,
                    instrument=instrument,
                    range_no=range_no,
                    test_load_g=test_load_g,
                    mpe_for_load=mpe_for_load,
                ),
                minimum_indication_change_g=minimum_change,
                minimum_displacement_mm=case.minimum_displacement_mm,
            )
        )

    return ResolvedDiscriminationPolicyV2(
        evaluation_context=evaluation_context,
        minimum_count=case.minimum_count,
        require_stabilization=case.require_stabilization,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
        indication_mode=case.indication_mode,
        operator=case.operator,
        semantics=case.semantics,
        loads=tuple(loads),
    )


def resolve_sensitivity_policy_v2(
    policy: SensitivityPolicyV2,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
    range_no: int,
    mpe_for_load: MpeForLoad | None = None,
) -> ResolvedSensitivityPolicyV2:
    case = resolve_policy_case(policy.cases, instrument, evaluation_context)
    test_loads = tuple(
        _test_load(expression, instrument, range_no) for expression in case.test_loads
    )
    if len(set(test_loads)) != len(test_loads):
        raise PolicyResolutionError("Sensitivity test-load expressions resolve to duplicates")

    loads = tuple(
        ResolvedSensitivityLoad(
            test_load_g=test_load_g,
            extra_load_g=_at_load(
                case.extra_load,
                instrument=instrument,
                range_no=range_no,
                test_load_g=test_load_g,
                mpe_for_load=mpe_for_load,
            ),
            minimum_displacement_mm=case.minimum_displacement_mm,
        )
        for test_load_g in test_loads
    )
    return ResolvedSensitivityPolicyV2(
        evaluation_context=evaluation_context,
        minimum_count=case.minimum_count,
        require_stabilization=case.require_stabilization,
        require_environment=case.require_environment,
        require_equipment=case.require_equipment,
        require_certificate=case.require_certificate,
        require_evidence=case.require_evidence,
        require_monotonic_timestamps=case.require_monotonic_timestamps,
        operator=case.operator,
        semantics=case.semantics,
        loads=loads,
    )


__all__ = [
    "ResolvedDiscriminationLoad",
    "ResolvedDiscriminationPolicyV2",
    "ResolvedSensitivityLoad",
    "ResolvedSensitivityPolicyV2",
    "resolve_discrimination_policy_v2",
    "resolve_sensitivity_policy_v2",
]
