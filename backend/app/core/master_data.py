"""Exact storage/structural validation only; no regulatory classification rules."""

import re
from decimal import Context, Decimal, DecimalException, Inexact, localcontext

DECIMAL_TEXT = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def stored_decimal(value, precision: int, scale: int) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Metrological values must be decimal strings")
    if isinstance(value, str) and (len(value) > 128 or not DECIMAL_TEXT.fullmatch(value)):
        raise ValueError("Invalid decimal string")
    try:
        number = Decimal(value)
    except DecimalException:
        raise ValueError("Unsupported decimal representation") from None
    if not number.is_finite():
        raise ValueError("Finite values required")
    if number == 0:
        return Decimal(0)
    _, digits, exponent = number.as_tuple()
    while digits and digits[-1] == 0:
        digits, exponent = digits[:-1], exponent + 1
    if exponent < -scale or len(digits) + exponent > precision - scale:
        raise ValueError(f"Value cannot be stored exactly in NUMERIC({precision},{scale})")
    return number


def exact_intervals(maximum: Decimal, interval: Decimal) -> Decimal:
    # Inputs fit NUMERIC(20,6); 100 digits cover every terminating quotient.
    # Repeating quotients are rejected, never silently rounded or called regulatory failures.
    try:
        with localcontext(Context(prec=100, traps=[Inexact])):
            result = maximum / interval
        if not result.is_finite():
            raise ValueError("Finite positive interval required")
        return result
    except DecimalException:
        raise ValueError("Max/e has no supported exact finite decimal representation") from None
