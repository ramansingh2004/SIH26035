"""Phase 25 Stage 4B deterministic native-v2 mechanics for Sections 11–15.

This module deliberately receives explicit limits and does not source,
interpret, or verify regulatory thresholds.
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
from app.compliance.stage4_native_schemas import (
    DampHeatObservationV2,
    DisturbanceObservationV2,
    EnduranceObservationV2,
    SpanStabilityObservationV2,
    VoltageVariationObservationV2,
)


class Stage4Limit(Frozen):
    name: str
    value: Number = Field(ge=0)
    operator: Operator
    semantics: Semantics
    unit: Literal["g", "V", "s", "1"] = "g"


class Stage4LoadLimit(Frozen):
    load_g: Number = Field(ge=0)
    limit: Stage4Limit


class Stage4Assertion(Frozen):
    name: str
    actual: Number
    limit: Stage4Limit
    passed: bool


class Stage4MechanicsResult(Frozen):
    calculations: tuple[CalculationTraceEntry, ...]
    assertions: tuple[Stage4Assertion, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.assertions)


def _assertion(name: str, actual, limit: Stage4Limit):
    return Stage4Assertion(
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


def _load_limit(load_g, limits: Iterable[Stage4LoadLimit]):
    matches = [item.limit for item in limits if item.load_g == load_g]
    if len(matches) != 1:
        raise ValueError("Expected exactly one explicit Stage 4 load limit")
    return matches[0]


def _corrected(indication_g, additional_load_g, load_g, zero_error_g, e_g):
    prerounding = calculate_prerounding_indication(
        indication_g,
        e_g,
        additional_load_g,
    )
    error = calculate_error(prerounding, load_g)
    corrected = calculate_corrected_error(error, zero_error_g)
    return prerounding, corrected


def voltage_variation_mechanics(
    rows: tuple[VoltageVariationObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    load_limits: tuple[Stage4LoadLimit, ...],
) -> Stage4MechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        if row.operational_state == "SWITCHED_OFF":
            continue

        _, corrected = _corrected(
            row.indication_g,
            row.additional_load_g,
            row.load_g,
            row.zero_error_g,
            verification_interval_e_g,
        )
        name = f"{row.sequence_no}:voltage_corrected_error"
        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression="P=I+0.5e-deltaL; E=P-L; Ec=E-E0",
                value=corrected,
                unit="g",
            )
        )
        assertions.append(
            _assertion(name, corrected, _load_limit(row.load_g, load_limits))
        )

    return Stage4MechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def disturbance_mechanics(
    rows: tuple[DisturbanceObservationV2, ...],
    *,
    deviation_limit: Stage4Limit,
    accepted_fault_responses: tuple[str, ...] = (),
) -> Stage4MechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        deviation = exact(
            "subtract",
            row.disturbed_indication_g,
            row.reference_indication_g,
        )
        name = f"{row.sequence_no}:disturbance_deviation"
        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression="disturbed_indication - reference_indication",
                value=deviation,
                unit="g",
            )
        )

        if row.fault_detected:
            accepted = (
                row.fault_response is not None
                and row.fault_response in accepted_fault_responses
            )
            actual = "0" if accepted else "1"
            fault_limit = Stage4Limit(
                name="accepted_fault_response_required",
                value="0",
                operator="==",
                semantics="SIGNED",
                unit="1",
            )
            assertions.append(
                _assertion(
                    f"{row.sequence_no}:fault_response",
                    actual,
                    fault_limit,
                )
            )
        else:
            assertions.append(_assertion(name, deviation, deviation_limit))

    return Stage4MechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def damp_heat_mechanics(
    rows: tuple[DampHeatObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    load_limits: tuple[Stage4LoadLimit, ...],
) -> Stage4MechanicsResult:
    calculations = []
    assertions = []

    for row in rows:
        _, corrected = _corrected(
            row.indication_g,
            row.additional_load_g,
            row.load_g,
            row.zero_error_g,
            verification_interval_e_g,
        )
        name = f"{row.sequence_no}:{row.stage.lower()}_corrected_error"
        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression="P=I+0.5e-deltaL; E=P-L; Ec=E-E0",
                value=corrected,
                unit="g",
            )
        )
        assertions.append(
            _assertion(name, corrected, _load_limit(row.load_g, load_limits))
        )

    return Stage4MechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


def span_stability_mechanics(
    rows: tuple[SpanStabilityObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    variation_limit: Stage4Limit,
) -> Stage4MechanicsResult:
    if not rows:
        raise ValueError("Span-stability mechanics require observations")

    calculations = []
    corrected_values = []

    for row in rows:
        _, corrected = _corrected(
            row.loaded_indication_g,
            row.loaded_additional_load_g,
            row.load_g,
            calculate_error(
                calculate_prerounding_indication(
                    row.zero_indication_g,
                    verification_interval_e_g,
                    row.zero_additional_load_g,
                ),
                "0",
            ),
            verification_interval_e_g,
        )
        if row.influence_correction_g != 0:
            corrected = exact(
                "add",
                corrected,
                row.influence_correction_g,
            )

        corrected_values.append(corrected)
        calculations.append(
            CalculationTraceEntry(
                name=f"{row.sequence_no}:span_corrected_error",
                expression="loaded_error - zero_error + influence_correction",
                value=corrected,
                unit="g",
            )
        )

    variation = exact(
        "subtract",
        max(corrected_values),
        min(corrected_values),
    )
    calculations.append(
        CalculationTraceEntry(
            name="span_variation",
            expression="max(corrected_error)-min(corrected_error)",
            value=variation,
            unit="g",
        )
    )

    return Stage4MechanicsResult(
        calculations=tuple(calculations),
        assertions=(
            _assertion("span_variation", variation, variation_limit),
        ),
    )


def endurance_mechanics(
    rows: tuple[EnduranceObservationV2, ...],
    *,
    verification_interval_e_g: Number,
    durability_limits: tuple[Stage4LoadLimit, ...],
) -> Stage4MechanicsResult:
    calculations = []
    assertions = []
    points = sorted({row.point_id for row in rows})

    for point_id in points:
        initial = [
            row
            for row in rows
            if row.point_id == point_id and row.phase == "INITIAL"
        ]
        final = [
            row
            for row in rows
            if row.point_id == point_id and row.phase == "FINAL"
        ]
        if len(initial) != 1 or len(final) != 1:
            raise ValueError(
                "Endurance mechanics require exactly one initial/final row per point"
            )

        initial_row = initial[0]
        final_row = final[0]
        if initial_row.load_g != final_row.load_g:
            raise ValueError("Initial and final endurance loads must match")

        _, initial_ec = _corrected(
            initial_row.indication_g,
            initial_row.additional_load_g,
            initial_row.load_g,
            initial_row.zero_error_g,
            verification_interval_e_g,
        )
        _, final_ec = _corrected(
            final_row.indication_g,
            final_row.additional_load_g,
            final_row.load_g,
            final_row.zero_error_g,
            verification_interval_e_g,
        )
        durability = exact(
            "subtract",
            final_ec,
            initial_ec,
        ).copy_abs()
        name = f"{point_id}:durability_error"

        calculations.append(
            CalculationTraceEntry(
                name=name,
                expression="abs(Ec_final-Ec_initial)",
                value=durability,
                unit="g",
            )
        )
        assertions.append(
            _assertion(
                name,
                durability,
                _load_limit(initial_row.load_g, durability_limits),
            )
        )

    return Stage4MechanicsResult(
        calculations=tuple(calculations),
        assertions=tuple(assertions),
    )


__all__ = [
    "Stage4Assertion",
    "Stage4Limit",
    "Stage4LoadLimit",
    "Stage4MechanicsResult",
    "damp_heat_mechanics",
    "disturbance_mechanics",
    "endurance_mechanics",
    "span_stability_mechanics",
    "voltage_variation_mechanics",
]
