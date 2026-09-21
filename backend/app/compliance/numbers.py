"""Exact arithmetic, independent of the ambient Decimal context and persistence scales."""

from decimal import (
    ROUND_HALF_EVEN,
    Clamped,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    FloatOperation,
    Inexact,
    InvalidOperation,
    Overflow,
    Rounded,
    Subnormal,
    Underflow,
    localcontext,
)
from typing import Annotated, Literal

from pydantic import BeforeValidator


class EvaluationNotPossible(ValueError):
    code = "EVALUATION_NOT_POSSIBLE"


def arithmetic_context(precision=50):
    return Context(
        prec=precision,
        rounding=ROUND_HALF_EVEN,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[
            InvalidOperation,
            DivisionByZero,
            Overflow,
            Underflow,
            Inexact,
            Rounded,
            Subnormal,
            Clamped,
            FloatOperation,
        ],
    )


def decimal_value(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Metrology requires a decimal string or Decimal, never float")
    try:
        result = Decimal(value, context=arithmetic_context())
    except DecimalException as exc:
        raise ValueError("Invalid decimal string") from exc
    if not result.is_finite():
        raise ValueError("Metrology must be finite")
    # An implementation resource bound, not a regulatory scale or rounding rule.
    if len(result.as_tuple().digits) + abs(result.as_tuple().exponent) > 10000:
        raise EvaluationNotPossible("Exact arithmetic resource bound exceeded")
    return result


Number = Annotated[Decimal, BeforeValidator(decimal_value)]
Operator = Literal["<", "<=", ">", ">=", "==", "!="]
Semantics = Literal["SIGNED", "ABSOLUTE"]


def exact(operation: str, *values: Decimal | str) -> Decimal:
    operands = tuple(decimal_value(v) for v in values)
    # Enough coefficient/exponent space for these finite operations. Division is
    # still trapped: no finite precision can make a repeating quotient exact.
    precision = max(
        50, sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in operands) + 16
    )
    ctx = arithmetic_context(precision)
    try:
        with localcontext(ctx):
            if operation == "add":
                return operands[0] + operands[1]
            if operation == "subtract":
                return operands[0] - operands[1]
            if operation == "multiply":
                return operands[0] * operands[1]
            if operation == "divide":
                return operands[0] / operands[1]
    except DecimalException as exc:
        raise EvaluationNotPossible("Exact finite arithmetic could not be established") from exc
    raise ValueError("Unknown arithmetic operation")


def compare(
    value: Decimal | str, limit: Decimal | str, *, operator: Operator, semantics: Semantics
) -> bool:
    left, right = decimal_value(value), decimal_value(limit)
    if semantics == "ABSOLUTE":
        if right < 0:
            raise ValueError("An absolute-value limit must be nonnegative")
        left = left.copy_abs()
    elif semantics != "SIGNED":
        raise ValueError("Unknown comparison semantics")
    operations = {
        "<": lambda: left < right,
        "<=": lambda: left <= right,
        ">": lambda: left > right,
        ">=": lambda: left >= right,
        "==": lambda: left == right,
        "!=": lambda: left != right,
    }
    if operator not in operations:
        raise ValueError("Unknown comparison operator")
    return operations[operator]()


def compare_ratio(
    numerator: Decimal | str,
    denominator: Decimal | str,
    limit: Decimal | str,
    *,
    operator: Operator,
) -> bool:
    denominator = decimal_value(denominator)
    if denominator <= 0:
        raise ValueError("Ratio denominator must be positive")
    return compare(
        numerator, exact("multiply", denominator, limit), operator=operator, semantics="SIGNED"
    )


def calculate_n(max_capacity_g: Decimal | str, e_g: Decimal | str) -> Decimal:
    if decimal_value(max_capacity_g) <= 0 or decimal_value(e_g) <= 0:
        raise ValueError("Max and e must be positive")
    return exact("divide", max_capacity_g, e_g)


def calculate_prerounding_indication(
    indication_g: Decimal | str, e_g: Decimal | str, delta_load_g: Decimal | str
) -> Decimal:
    if decimal_value(e_g) <= 0:
        raise ValueError("e must be positive")
    return exact(
        "subtract", exact("add", indication_g, exact("multiply", "0.5", e_g)), delta_load_g
    )


def calculate_error(prerounding_indication_g: Decimal | str, load_g: Decimal | str) -> Decimal:
    return exact("subtract", prerounding_indication_g, load_g)


def calculate_corrected_error(error_g: Decimal | str, zero_error_g: Decimal | str) -> Decimal:
    return exact("subtract", error_g, zero_error_g)


def canonical_unit(value: Decimal | str, unit: str) -> tuple[Decimal, str]:
    """Physical unit conversion only; no regulatory constants or tolerances."""
    units = {
        "g": ("1", "g"),
        "kg": ("1000", "g"),
        "mg": ("0.001", "g"),
        "V": ("1", "V"),
        "mV": ("0.001", "V"),
        "degC": ("1", "degC"),
        "%": ("1", "%"),
        "hPa": ("1", "hPa"),
        "kPa": ("10", "hPa"),
        "s": ("1", "s"),
        "min": ("60", "s"),
        "h": ("3600", "s"),
    }
    if unit not in units:
        raise ValueError("Unknown/noncanonical physical unit")
    factor, canonical = units[unit]
    return exact("multiply", value, factor), canonical
