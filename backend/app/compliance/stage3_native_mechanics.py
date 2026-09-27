"""Phase 25 Stage 3E native v2 mechanics for Sections 6–10.

The functions in this module perform deterministic calculations against native
Stage 3 v2 observations. They do not choose regulatory thresholds, resolve
source phrases, load candidate rules, or publish compliance outcomes.

All acceptance limits passed to these mechanics must already be explicit.
"""

from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from app.compliance.domain import CalculationTraceEntry, Frozen, Number
from app.compliance.numbers import (
    Operator,
    Semantics,
    calculate_corrected_error,
    calculate_error,
    calculate_prerounding_indication,
    compare,
    exact,
)
from app.compliance.stage3_native_schemas import (
    CreepObservationV2,
    StabilityObservationV2,
    TareObservationV2,
    TiltingObservationV2,
    WarmUpObservationV2,
    ZeroReturnObservationV2,
)


class MechanicsLimit(Frozen):
    name: str
    value: Number = Field(ge=0)
    operator: Operator
    semantics: Semantics
    unit: Literal["g", "degC", "s", "1"] = "g"


class MechanicsLoadLimit(Frozen):
    load_g: Number = Field(ge=0)
    limit: MechanicsLimit


class MechanicsAssertion(Frozen):
    name: str
    actual: Number
    limit: MechanicsLimit
    passed: bool


class NativeMechanicsResult(Frozen):
    calculations: tuple[CalculationTraceEntry, ...]
    assertions: tuple[MechanicsAssertion, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.assertions)


def _assertion(name: str, actual, limit: MechanicsLimit):
    return MechanicsAssertion(
        name=name,
        actual=actual,
        limit=limit,
        passed=compare(
            actual,
            limit.value,
            operator=limit.operator,
            semantics=limit.semantics,
        ),
    )


def _exactly_one(rows, predicate, description: str):
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {description}")
    return matches[0]


def _load_limit(load_g, limits: Iterable[MechanicsLoadLimit]):
    matches = [item.limit for item in limits if item.load_g == load_g]
    if len(matches) != 1:
        raise ValueError("Expected exactly one explicit limit for applied load")
    return matches[0]


def zero_return_mechanics(
    rows: tuple[ZeroReturnObservationV2, ...],
    *,
    ordinary_limit: MechanicsLimit | None = None,
    post_switch_limit: MechanicsLimit | None = None,
) -> NativeMechanicsResult:
    before = _exactly_one(
        rows,
        lambda row: row.phase == "PRE_LOAD_ZERO",
        "pre-load zero observation",
    )
    after = _exactly_one(
        rows,
        lambda row: row.phase == "POST_UNLOAD_ZERO",
        "post-unload zero observation",
    )

    calculations = []
    assertions = []

    change = exact("subtract", after.indication_g, before.indication_g)
    calculations.append(
        CalculationTraceEntry(
            name="zero_return_change",
            expression="post_unload_zero - pre_load_zero",
            value=change,
            unit="g",
        )
    )
    if ordinary_limit is not None:
        assertions.append(
            _assertion("zero_return_change", change, ordinary_limit)
        )

    post_switch = [row for row in rows if row.phase == "POST_SWITCH_ZERO"]
    if len(post_switch) > 1:
        raise ValueError("Expected at most one post-switch zero observation")
    if post_switch:
        value = post_switch[0].indication_g
        calculations.append(
            CalculationTraceEntry(
                name="post_switch_zero",
                expression="post_switch_zero_indication",
                value=value,
                unit="g",
            )
        )
        if post_switch_limit is not None:
            assertions.append(
                _assertion("post_switch_zero", value, post_switch_limit)
            )
    elif post_switch_limit is not None:
        raise ValueError("Post-switch limit supplied without post-switch observation")

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


class CreepComparison(Frozen):
    name: str
    start_seconds: Number = Field(ge=0)
    end_seconds: Number = Field(gt=0)
    limit: MechanicsLimit


def creep_mechanics(
    rows: tuple[CreepObservationV2, ...],
    *,
    comparisons: tuple[CreepComparison, ...],
    temperature_variation_limit: MechanicsLimit | None = None,
) -> NativeMechanicsResult:
    by_elapsed = {row.elapsed_seconds: row for row in rows}
    if len(by_elapsed) != len(rows):
        raise ValueError("Duplicate creep elapsed-time observation")

    calculations = []
    assertions = []

    for item in comparisons:
        start = by_elapsed.get(item.start_seconds)
        end = by_elapsed.get(item.end_seconds)
        if start is None or end is None:
            raise ValueError(
                f"Creep comparison {item.name} requires both explicit checkpoints"
            )
        actual = exact("subtract", end.indication_g, start.indication_g)
        calculations.append(
            CalculationTraceEntry(
                name=item.name,
                expression="end_indication - start_indication",
                value=actual,
                unit="g",
            )
        )
        assertions.append(_assertion(item.name, actual, item.limit))

    if temperature_variation_limit is not None:
        temperatures = [row.temperature_c for row in rows]
        if not temperatures:
            raise ValueError("Temperature variation requires creep observations")
        variation = exact(
            "subtract",
            max(temperatures),
            min(temperatures),
        )
        calculations.append(
            CalculationTraceEntry(
                name="creep_temperature_variation",
                expression="max_temperature - min_temperature",
                value=variation,
                unit="degC",
            )
        )
        assertions.append(
            _assertion(
                "creep_temperature_variation",
                variation,
                temperature_variation_limit,
            )
        )

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def stability_mechanics(
    rows: tuple[StabilityObservationV2, ...],
    *,
    print_storage_limit: MechanicsLimit | None = None,
    zero_tare_limit: MechanicsLimit | None = None,
    adjacent_values_limit: MechanicsLimit | None = None,
) -> NativeMechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        if row.function in {"PRINTING", "STORAGE"}:
            difference = exact(
                "subtract",
                row.event_output_g,
                row.final_weight_value_g,
            )
            name = f"{row.sequence_no}:{row.function.lower()}_output_difference"
            calculations.append(
                CalculationTraceEntry(
                    name=name,
                    expression="event_output - final_weight_value",
                    value=difference,
                    unit="g",
                )
            )
            if print_storage_limit is not None:
                assertions.append(
                    _assertion(name, difference, print_storage_limit)
                )

            if adjacent_values_limit is not None:
                adjacent = row.adjacent_values_count
                if adjacent is None:
                    raise ValueError(
                        "Adjacent-values limit requires adjacent-values observation"
                    )
                adjacent_name = (
                    f"{row.sequence_no}:{row.function.lower()}_adjacent_values"
                )
                adjacent_value = exact("add", str(adjacent), "0")
                calculations.append(
                    CalculationTraceEntry(
                        name=adjacent_name,
                        expression="observed_adjacent_value_count",
                        value=adjacent_value,
                        unit="1",
                    )
                )
                assertions.append(
                    _assertion(
                        adjacent_name,
                        adjacent_value,
                        adjacent_values_limit,
                    )
                )
        else:
            error = row.zero_or_tare_error_g
            if error is None:
                raise ValueError("Zero/tare observation requires accuracy error")
            name = f"{row.sequence_no}:{row.function.lower()}_accuracy_error"
            calculations.append(
                CalculationTraceEntry(
                    name=name,
                    expression="observed_zero_or_tare_error",
                    value=error,
                    unit="g",
                )
            )
            if zero_tare_limit is not None:
                assertions.append(_assertion(name, error, zero_tare_limit))

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def _tilt_corrected(row: TiltingObservationV2, e_g):
    prerounding = calculate_prerounding_indication(
        row.indication_g,
        e_g,
        row.additional_load_g,
    )
    error = calculate_error(prerounding, row.load_g)
    return prerounding, calculate_corrected_error(error, row.zero_error_g)


def tilting_mechanics(
    rows: tuple[TiltingObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    unloaded_limit: MechanicsLimit | None,
    loaded_limits: tuple[MechanicsLoadLimit, ...],
) -> NativeMechanicsResult:
    calculations = []
    assertions = []

    keys = sorted({(row.direction, row.load_g) for row in rows})
    for direction, load_g in keys:
        reference = _exactly_one(
            rows,
            lambda row, direction=direction, load_g=load_g: (
                row.direction == direction
                and row.load_g == load_g
                and row.stage == "REFERENCE"
            ),
            f"{direction}/{load_g} reference tilt observation",
        )
        tilted = _exactly_one(
            rows,
            lambda row, direction=direction, load_g=load_g: (
                row.direction == direction
                and row.load_g == load_g
                and row.stage == "TILTED"
            ),
            f"{direction}/{load_g} tilted observation",
        )

        reference_p, reference_ec = _tilt_corrected(
            reference,
            verification_interval_e_g,
        )
        tilted_p, tilted_ec = _tilt_corrected(
            tilted,
            verification_interval_e_g,
        )

        if load_g == 0:
            actual = exact("subtract", tilted_p, reference_p)
            limit = unloaded_limit
            expression = "tilted_prerounding - reference_prerounding"
        else:
            actual = exact("subtract", tilted_ec, reference_ec)
            limit = _load_limit(load_g, loaded_limits)
            expression = "tilted_corrected_error - reference_corrected_error"

        name = f"{direction.lower()}:{load_g}:tilt_difference"
        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression=expression,
                value=actual,
                unit="g",
            )
        )
        if limit is not None:
            assertions.append(_assertion(name, actual, limit))

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def tare_mechanics(
    rows: tuple[TareObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    weighing_limits: tuple[MechanicsLoadLimit, ...],
    tare_setting_limit: MechanicsLimit | None = None,
    gross_identity_limit: MechanicsLimit | None = None,
) -> NativeMechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        if row.observation_kind == "WEIGHING":
            prerounding = calculate_prerounding_indication(
                row.indication_g,
                verification_interval_e_g,
                row.additional_load_g,
            )
            error = calculate_error(prerounding, row.net_load_g)
            corrected = calculate_corrected_error(error, row.zero_error_g)
            corrected_name = f"{row.sequence_no}:tare_corrected_error"
            calculations.append(
                CalculationTraceEntry(
                    name=corrected_name,
                    expression="P=I+0.5e-deltaL; E=P-net; Ec=E-E0",
                    value=corrected,
                    unit="g",
                )
            )
            assertions.append(
                _assertion(
                    corrected_name,
                    corrected,
                    _load_limit(row.net_load_g, weighing_limits),
                )
            )

            gross_delta = exact(
                "subtract",
                row.gross_load_g,
                exact("add", row.tare_value_g, row.net_load_g),
            )
            gross_name = f"{row.sequence_no}:gross_identity_delta"
            calculations.append(
                CalculationTraceEntry(
                    name=gross_name,
                    expression="gross - (tare + net)",
                    value=gross_delta,
                    unit="g",
                )
            )
            if gross_identity_limit is not None:
                assertions.append(
                    _assertion(
                        gross_name,
                        gross_delta,
                        gross_identity_limit,
                    )
                )
        else:
            name = f"{row.sequence_no}:tare_setting_error"
            calculations.append(
                CalculationTraceEntry(
                    name=name,
                    expression="observed_tare_setting_error",
                    value=row.tare_setting_error_g,
                    unit="g",
                )
            )
            if tare_setting_limit is not None:
                assertions.append(
                    _assertion(name, row.tare_setting_error_g, tare_setting_limit)
                )

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def warm_up_mechanics(
    rows: tuple[WarmUpObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    loaded_limits: tuple[MechanicsLoadLimit, ...],
    pre_ready_behavior_limit: MechanicsLimit | None = None,
) -> NativeMechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        zero_p = calculate_prerounding_indication(
            row.zero_indication_g,
            verification_interval_e_g,
            row.zero_additional_load_g,
        )
        zero_error = calculate_error(zero_p, "0")
        loaded_p = calculate_prerounding_indication(
            row.loaded_indication_g,
            verification_interval_e_g,
            row.loaded_additional_load_g,
        )
        loaded_error = calculate_error(loaded_p, row.load_g)
        corrected = calculate_corrected_error(loaded_error, zero_error)

        name = f"{row.sequence_no}:warm_up_corrected_error"
        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression="loaded_error - contemporaneous_zero_error",
                value=corrected,
                unit="g",
            )
        )
        assertions.append(
            _assertion(
                name,
                corrected,
                _load_limit(row.load_g, loaded_limits),
            )
        )

        if pre_ready_behavior_limit is not None:
            violation = (
                "1"
                if (
                    not row.instrument_ready
                    and (row.result_indicated or row.result_transmitted)
                )
                else "0"
            )
            behavior_name = f"{row.sequence_no}:pre_ready_result_activity"
            calculations.append(
                CalculationTraceEntry(
                    name=behavior_name,
                    expression="1 if result indicated/transmitted before ready else 0",
                    value=violation,
                    unit="1",
                )
            )
            assertions.append(
                _assertion(
                    behavior_name,
                    violation,
                    pre_ready_behavior_limit,
                )
            )

    return NativeMechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


__all__ = [
    "CreepComparison",
    "MechanicsAssertion",
    "MechanicsLimit",
    "MechanicsLoadLimit",
    "NativeMechanicsResult",
    "creep_mechanics",
    "stability_mechanics",
    "tare_mechanics",
    "tilting_mechanics",
    "warm_up_mechanics",
    "zero_return_mechanics",
]
