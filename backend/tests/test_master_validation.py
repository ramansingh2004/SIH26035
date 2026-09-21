"""Structural master-data tests; none asserts regulatory validity."""

from decimal import Decimal, localcontext
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.master_data import decimal_text, exact_intervals, stored_decimal
from app.schemas.master_data import (
    ConfigurationRequest,
    InstrumentCreate,
    InstrumentPatch,
    RangeData,
)


def instrument_payload(lab=None, manufacturer=None, **changes):
    return {
        "laboratory_id": str(lab or uuid4()),
        "manufacturer_id": str(manufacturer or uuid4()),
        "model_name": "Structural test model",
        "accuracy_class": "III",
        "max_capacity_g": "10000",
        "min_capacity_g": "0",
        "scale_interval_d_g": "0.1",
        "verification_interval_e_g": "10",
        **changes,
    }


@pytest.mark.parametrize(
    "value",
    [
        0.1,
        10,
        True,
        "NaN",
        "Infinity",
        "-Infinity",
        "1.0000001",
        "100000000000000",
        "1e999999",
        " 1 ",
        "",
    ],
)
def test_rejects_float_nonfinite_and_unrepresentable_mass(value):
    with pytest.raises(ValidationError):
        InstrumentCreate.model_validate(instrument_payload(max_capacity_g=value))


@pytest.mark.parametrize("value", ["0.1", "10000.000001", "99999999999999.999999", "1.2300000"])
def test_exact_numeric_roundtrip(value):
    data = InstrumentCreate.model_validate(
        instrument_payload(max_capacity_g=value, min_capacity_g=None)
    )
    assert Decimal(data.model_dump(mode="json")["max_capacity_g"]) == Decimal(value)
    assert isinstance(data.model_dump()["max_capacity_g"], Decimal)


@pytest.mark.parametrize(
    "changes",
    [
        {"max_capacity_g": "0"},
        {"scale_interval_d_g": "-1"},
        {"verification_interval_e_g": "0"},
        {"min_capacity_g": "-1"},
        {"min_capacity_g": "10000"},
        {"accuracy_class": "IV"},
        {"metadata_json": {"unverified_assumption": False}},
        {"metadata_schema_version": 2},
        {"min_voltage": "220", "max_voltage": "110"},
        {"nominal_voltage": "230", "max_voltage": "220"},
        {"declared_temp_min_c": "20", "declared_temp_max_c": "10"},
        {"declared_temp_min_c": "0.0001"},
        {"nominal_voltage": "1.00001"},
    ],
)
def test_invalid_structural_configuration(changes):
    with pytest.raises(ValidationError):
        InstrumentCreate.model_validate(instrument_payload(**changes))


def test_unknown_facts_and_descriptors_not_regulatory_assumptions():
    data = InstrumentCreate.model_validate(
        instrument_payload(range_type="Declared special arrangement")
    )
    assert data.is_electronic is None
    assert data.metadata_json.is_direct_sales is None
    assert data.metadata_json.interfaces is None
    assert data.model_dump(mode="json")["metadata_json"]["vehicle_powered"] is None


def test_exact_arithmetic_independent_of_ambient_context():
    with localcontext() as context:
        context.prec = 2
        assert exact_intervals(Decimal("10000.000001"), Decimal("0.000001")) == Decimal(
            "10000000001"
        )
        assert stored_decimal("99999999999999.999999", 20, 6) == Decimal("99999999999999.999999")
        assert decimal_text(Decimal("-0.000")) == "0"


def test_repeating_ratio_is_not_rounded():
    with pytest.raises(ValueError, match="exact finite"):
        exact_intervals(Decimal("10"), Decimal("3"))


def test_unrepresentable_exponent_is_a_validation_error():
    with pytest.raises(ValidationError):
        InstrumentCreate.model_validate(instrument_payload(max_capacity_g="1e9999999999999999999"))


def test_partial_schema_preserves_omitted_versus_explicit_null():
    patch = InstrumentPatch.model_validate({"min_capacity_g": None})
    assert patch.model_dump(exclude_unset=True) == {"min_capacity_g": None}
    with pytest.raises(ValidationError):
        InstrumentPatch.model_validate({"laboratory_id": str(uuid4())})


def test_range_positive_number_and_minmax():
    with pytest.raises(ValidationError):
        RangeData(
            range_no=0, max_capacity_g="1", scale_interval_d_g="1", verification_interval_e_g="1"
        )


def test_configuration_schema_has_no_compliance_switch():
    with pytest.raises(ValidationError):
        ConfigurationRequest.model_validate(instrument_payload(regulatory_verified=True))
