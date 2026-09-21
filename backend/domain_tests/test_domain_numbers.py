from decimal import ROUND_DOWN, Decimal, Inexact, Rounded, localcontext

import pytest
from pydantic import ValidationError

from app.compliance.domain import InstrumentSnapshot, ObservationBatch
from app.compliance.numbers import (
    EvaluationNotPossible,
    calculate_corrected_error,
    calculate_error,
    calculate_n,
    calculate_prerounding_indication,
    canonical_unit,
    compare,
    compare_ratio,
    decimal_value,
    exact,
)
from app.compliance.regulatory import RegulatoryBlocked, calculate_mpe
from app.compliance.ruleset import load_ruleset
from domain_tests.fixtures.synthetic import (
    context,
    evaluate,
    instrument,
    observations,
    ruleset,
)


@pytest.mark.parametrize(
    "factory,field,value",
    [
        (instrument, "accuracy_class", "II"),
        (context, "scenario", "changed"),
        (lambda: observations().rows[0], "sequence_no", 99),
        (evaluate, "engine_version", "changed"),
        (lambda: instrument().ranges[0], "range_no", 9),
        (lambda: context().environment, "temperature_c", Decimal("9")),
    ],
)
def test_immutable(factory, field, value):
    with pytest.raises(ValidationError, match="frozen"):
        setattr(factory(), field, value)


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        "-Infinity",
        Decimal("sNaN"),
        Decimal("Infinity"),
        True,
        10,
    ],
)
def test_invalid_metrology(value):
    with pytest.raises(ValueError):
        decimal_value(value)
    with pytest.raises(ValueError):
        instrument(max_capacity_g=value)


def test_unknown_fields_storage_ids_and_unknown_facts():
    for factory, extra in ((instrument, {"id": "storage-id"}), (context, {"extra": True})):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            factory(**extra)
    assert instrument(is_electronic=None).is_electronic is None
    with pytest.raises(ValidationError):
        instrument(is_electronic="false")


def test_golden_arithmetic():
    p = calculate_prerounding_indication("10020", "10", "5")
    e = calculate_error(p, "10000")
    ec = calculate_corrected_error(e, "0")
    assert (p, e, ec) == (Decimal("10020"), Decimal("20"), Decimal("20"))
    assert calculate_n("10000", "10") == Decimal("1000")


def test_local_context_exactness_and_no_quantization():
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = ROUND_DOWN
        ambient.Emax = 3
        ambient.traps[Inexact] = False
        ambient.traps[Rounded] = False
        assert exact("add", "99999.000000000001", "0.000000000002") == Decimal("99999.000000000003")
        assert exact("multiply", "123456789.123456789", "1000") == Decimal("123456789123.456789")
        assert exact("divide", "1", "8") == Decimal("0.125")
        test_golden_arithmetic()
        with pytest.raises(EvaluationNotPossible):
            calculate_n("10", "3")
        assert ambient.prec == 2 and not ambient.flags[Inexact]


@pytest.mark.parametrize("a,b", [("1", "3"), ("2", "7"), ("1", "0")])
def test_inexact_or_undefined_division_blocks(a, b):
    with pytest.raises(EvaluationNotPossible, match="Exact finite"):
        exact("divide", a, b)


@pytest.mark.parametrize(
    "operator,expected",
    [("<", False), ("<=", True), (">", False), (">=", True), ("==", True), ("!=", False)],
)
def test_exact_boundary_operators(operator, expected):
    assert compare("10", "10", operator=operator, semantics="SIGNED") is expected
    assert compare("-10", "10", operator=operator, semantics="ABSOLUTE") is expected


def test_signed_absolute_no_epsilon_and_ratio_cross_multiplication():
    assert compare("-20", "10", operator="<", semantics="SIGNED")
    assert not compare("-20", "10", operator="<", semantics="ABSOLUTE")
    assert not compare("10.0000000000000000000000001", "10", operator="<=", semantics="SIGNED")
    assert compare_ratio("1", "3", "0.3333333333333333333333333", operator=">")
    with pytest.raises(ValueError):
        compare("-2", "-1", operator="<=", semantics="ABSOLUTE")
    with pytest.raises(ValueError):
        compare("1", "2", operator="approximately", semantics="SIGNED")
    with pytest.raises(ValueError):
        compare_ratio("1", "0", "1", operator="<")


@pytest.mark.parametrize(
    "value,unit,expected,canonical",
    [
        ("1.2", "kg", "1200", "g"),
        ("1000", "mg", "1", "g"),
        ("500", "mV", "0.5", "V"),
        ("1", "min", "60", "s"),
        ("1", "kPa", "10", "hPa"),
        ("20", "degC", "20", "degC"),
    ],
)
def test_units(value, unit, expected, canonical):
    assert canonical_unit(value, unit) == (Decimal(expected), canonical)


@pytest.mark.parametrize(
    "load,expected", [("9999.999", "10"), ("10000", "10"), ("10000.001", "20")]
)
def test_synthetic_mpe_pinned_rules_and_boundary(load, expected):
    limit = calculate_mpe(
        load_g=load,
        selected_range=instrument().ranges[0],
        accuracy_class="III",
        evaluation_context="SYNTHETIC",
        ruleset=ruleset(),
        rule_id="MPE",
    )
    assert limit.value == Decimal(expected) and limit.operator == "<="
    assert limit.rule_references


def test_mpe_candidate_never_authoritative_or_fallback():
    for rs, key in ((load_ruleset(), "MPE_PENDING"), (ruleset(), "ABSENT")):
        with pytest.raises(RegulatoryBlocked):
            calculate_mpe(
                load_g="10000",
                selected_range=instrument().ranges[0],
                accuracy_class="III",
                evaluation_context="SYNTHETIC",
                ruleset=rs,
                rule_id=key,
            )


def test_structural_ranges_and_no_wrong_interval():
    one = instrument()
    assert len(one.ranges) == 1
    with pytest.raises(ValueError, match="Selected range"):
        one.select_range(2)
    for bad in ([], [one.ranges[0], one.ranges[0]]):
        with pytest.raises(ValueError):
            instrument(ranges=bad)
    low = one.ranges[0].model_dump() | dict(
        range_no=1,
        max_capacity_g="1000",
        verification_interval_e_g="1",
        scale_interval_d_g="1",
        verification_intervals_n="1000",
    )
    high = one.ranges[0].model_dump() | {"range_no": 2}
    multiple = instrument(range_type="MULTIPLE", ranges=[high, low])
    assert tuple(r.range_no for r in multiple.ranges) == (1, 2)
    assert multiple.select_range(1).verification_interval_e_g == Decimal("1")
    assert multiple.select_range(2).verification_interval_e_g == Decimal("10")
    with pytest.raises(ValueError, match="n \\* e"):
        InstrumentSnapshot.model_validate(one.model_dump() | {"verification_intervals_n": "2001"})
    with pytest.raises(ValueError):
        instrument(ranges=[low])


def test_batch_duplicate_and_ordering():
    rows = observations().rows
    assert observations(rows=tuple(reversed(rows))).rows == rows
    with pytest.raises(ValueError, match="Duplicate"):
        observations(rows=(rows[0], rows[0]))
    with pytest.raises(ValueError, match="Mixed"):
        ObservationBatch(
            test_code="OTHER", protocol="SYNTHETIC", observation_schema_version="v1", rows=rows
        )


def test_decimal_default_context_cannot_disable_domain_traps():
    from decimal import DefaultContext, DivisionByZero, InvalidOperation

    saved = DefaultContext.copy()
    try:
        DefaultContext.prec = 1
        DefaultContext.traps[DivisionByZero] = False
        DefaultContext.traps[InvalidOperation] = False
        DefaultContext.traps[Inexact] = False
        with pytest.raises(EvaluationNotPossible):
            exact("divide", "1", "0")
        with pytest.raises(EvaluationNotPossible):
            exact("divide", "1", "3")
        with pytest.raises(ValueError):
            decimal_value("not a number")
        test_golden_arithmetic()
    finally:
        DefaultContext.prec = saved.prec
        DefaultContext.traps = saved.traps
