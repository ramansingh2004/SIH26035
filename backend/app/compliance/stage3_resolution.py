"""Phase 25 Stage 3C2 deterministic resolution primitives.

This module resolves parameterized Stage 3 policy targets only from explicit
instrument facts, explicit resolution facts, or an explicit MPE supplied by
the caller.

It does not infer regulatory phrases such as "close to Max", derive an MPE
transition from unverified policy, or make any candidate rule authoritative.
"""

from pydantic import Field, model_validator

from app.compliance.domain import Frozen, InstrumentSnapshot, Number
from app.compliance.numbers import exact
from app.compliance.parameterized import PolicyResolutionError
from app.compliance.parameterized_stage3 import (
    LimitTarget,
    LoadTarget,
    TareValueTarget,
    TiltTarget,
    resolve_limit_target,
    resolve_load_target,
    resolve_stage3_case,
)


class Stage3ResolutionFacts(Frozen):
    """Explicit facts needed for source-semantic Stage 3 targets.

    These values are inputs to deterministic resolution. Supplying them does not
    make them regulatory truth; authoritative execution still requires a
    verified pinned RuleSet dependency.
    """

    close_to_max_g: Number | None = Field(None, ge=0)
    function_operating_range_g: Number | None = Field(None, ge=0)
    mpe_transition_loads_g: tuple[Number, ...] = ()
    level_indicator_limit: Number | None = None
    automatic_sensor_limit: Number | None = None

    @model_validator(mode="after")
    def transitions(self):
        if len(self.mpe_transition_loads_g) != len(set(self.mpe_transition_loads_g)):
            raise ValueError("Duplicate explicit MPE-transition load")
        return self


class ResolvedLoadTarget(Frozen):
    basis: str
    value_g: Number


class ResolvedLimitTarget(Frozen):
    basis: str
    value_g: Number


class ResolvedTiltTarget(Frozen):
    basis: str
    value: Number


class ResolvedTareValue(Frozen):
    basis: str
    value_g: Number


def resolve_load_target_explicit(
    target: LoadTarget,
    instrument: InstrumentSnapshot,
    range_no: int,
    *,
    facts: Stage3ResolutionFacts | None = None,
) -> ResolvedLoadTarget:
    """Resolve a Stage 3 load without inventing semantic source values."""

    facts = facts or Stage3ResolutionFacts()

    if target.basis in {"ABSOLUTE_G", "MIN", "MAX", "MAX_FRACTION"}:
        value = resolve_load_target(target, instrument, range_no)
        return ResolvedLoadTarget(basis=target.basis, value_g=value)

    if target.basis == "CLOSE_TO_MAX":
        if facts.close_to_max_g is None:
            raise PolicyResolutionError(
                "CLOSE_TO_MAX requires an explicit Stage 3 resolution fact"
            )
        value = facts.close_to_max_g
    elif target.basis == "FUNCTION_OPERATING_RANGE":
        if facts.function_operating_range_g is None:
            raise PolicyResolutionError(
                "FUNCTION_OPERATING_RANGE requires an explicit Stage 3 resolution fact"
            )
        value = facts.function_operating_range_g
    elif target.basis == "MPE_TRANSITION":
        index = target.transition_index
        if index is None:  # guarded by the policy model, kept fail-closed.
            raise PolicyResolutionError("MPE_TRANSITION index is missing")
        if index > len(facts.mpe_transition_loads_g):
            raise PolicyResolutionError(
                "MPE_TRANSITION requires an explicit transition-load resolution fact"
            )
        value = facts.mpe_transition_loads_g[index - 1]
    else:  # pragma: no cover
        raise PolicyResolutionError("Unknown Stage 3 load target")

    selected = instrument.select_range(range_no)
    if value > selected.max_capacity_g:
        raise PolicyResolutionError("Resolved Stage 3 load exceeds selected range Max")
    if value < 0:  # pragma: no cover - Number validation protects this.
        raise PolicyResolutionError("Resolved Stage 3 load cannot be negative")

    return ResolvedLoadTarget(basis=target.basis, value_g=value)


def resolve_limit_target_explicit(
    target: LimitTarget,
    instrument: InstrumentSnapshot,
    range_no: int,
    *,
    mpe_g=None,
) -> ResolvedLimitTarget:
    value = resolve_limit_target(
        target,
        instrument,
        range_no,
        mpe_g=mpe_g,
    )
    return ResolvedLimitTarget(basis=target.basis, value_g=value)


def resolve_tilt_target_explicit(
    target: TiltTarget,
    *,
    facts: Stage3ResolutionFacts | None = None,
) -> ResolvedTiltTarget:
    facts = facts or Stage3ResolutionFacts()

    if target.basis in {"ABSOLUTE", "FIXED_RATIO"}:
        if target.value is None:  # guarded by model validation.
            raise PolicyResolutionError("Explicit tilt target value is missing")
        return ResolvedTiltTarget(basis=target.basis, value=target.value)

    if target.basis == "LEVEL_INDICATOR_LIMIT":
        if facts.level_indicator_limit is None:
            raise PolicyResolutionError(
                "LEVEL_INDICATOR_LIMIT requires an explicit Stage 3 resolution fact"
            )
        value = facts.level_indicator_limit
    elif target.basis == "AUTOMATIC_SENSOR_LIMIT":
        if facts.automatic_sensor_limit is None:
            raise PolicyResolutionError(
                "AUTOMATIC_SENSOR_LIMIT requires an explicit Stage 3 resolution fact"
            )
        value = facts.automatic_sensor_limit
    else:  # pragma: no cover
        raise PolicyResolutionError("Unknown Stage 3 tilt target")

    return ResolvedTiltTarget(basis=target.basis, value=value)


def resolve_tare_value_target(
    target: TareValueTarget,
    instrument: InstrumentSnapshot,
) -> ResolvedTareValue:
    if target.basis == "ABSOLUTE_G":
        value = target.value
    else:
        if instrument.maximum_tare_g is None:
            raise PolicyResolutionError(
                "MAX_TARE_FRACTION requires declared maximum tare"
            )
        value = exact("multiply", instrument.maximum_tare_g, target.value)

    if instrument.maximum_tare_g is not None and value > instrument.maximum_tare_g:
        raise PolicyResolutionError("Resolved tare value exceeds declared maximum tare")

    return ResolvedTareValue(basis=target.basis, value_g=value)


def select_stage3_policy_case(
    cases,
    *,
    instrument: InstrumentSnapshot,
    evaluation_context: str,
):
    """Public Stage 3 selector wrapper used by later runtime adapters."""

    return resolve_stage3_case(cases, instrument, evaluation_context)


__all__ = [
    "ResolvedLimitTarget",
    "ResolvedLoadTarget",
    "ResolvedTareValue",
    "ResolvedTiltTarget",
    "Stage3ResolutionFacts",
    "resolve_limit_target_explicit",
    "resolve_load_target_explicit",
    "resolve_tare_value_target",
    "resolve_tilt_target_explicit",
    "select_stage3_policy_case",
]
