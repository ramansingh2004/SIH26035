"""Phase 8 Stage 1 typed-contract and registry wiring tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.compliance.phase8 import (
    TEMPERATURE_ZERO,
    TILTING,
    VOLTAGE_VARIATION,
    WARM_UP,
    TemperatureZeroContext,
    TemperatureZeroObservation,
    TiltingContext,
    VoltageVariationContext,
    WarmUpContext,
)
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.schemas.testing import ObservationData, ProcedureUpdate

NOW = datetime(2000, 1, 1, tzinfo=UTC).isoformat()


def _ctx(cls, **values):
    base = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
    )
    base.update(values)
    return cls.model_validate(base)


@pytest.mark.parametrize(
    "context",
    [
        _ctx(
            TemperatureZeroContext,
            temperature_sequence_c=["0", "10"],
            zero_tracking_disabled=True,
        ),
        _ctx(
            TiltingContext,
            procedure_variant="NO_LEVEL_DEVICE",
            tilt_mode="NO_LEVEL_DEVICE",
            reference_tilt_value="0",
            test_tilt_value="0.05",
            directions=["FORWARD", "BACKWARD", "LEFT", "RIGHT"],
            reference_position_confirmed=True,
            protection_behavior_checked=False,
        ),
        _ctx(
            WarmUpContext,
            power_off_seconds="28800",
            test_load_g="10000",
            first_stable_indication_observed=True,
            zero_set_after_power_on=True,
        ),
        _ctx(
            VoltageVariationContext,
            procedure_variant="AC_MAINS",
            power_supply_profile="AC_MAINS",
            reference_voltage_v="230",
            protection_behavior_checked=True,
        ),
    ],
)
def test_phase8_http_contract_accepts_typed_context(context):
    parsed = ProcedureUpdate(procedure_context=context).procedure_context
    assert type(parsed) is type(context)


def test_phase8_registry_extends_phase7():
    registry = implemented_registry()
    codes = tuple(item.test_code for item in registry.registrations)
    assert codes == IMPLEMENTED_TEST_CODES
    for code in (
        TEMPERATURE_ZERO,
        TILTING,
        WARM_UP,
        VOLTAGE_VARIATION,
    ):
        assert code in codes


def test_phase8_observation_envelope_rejects_disagreement():
    row = TemperatureZeroObservation.model_validate(
        dict(
            sequence_no=1,
            temperature_c="0",
            indication_g="0",
            additional_load_g="5",
            stabilized=True,
            zero_tracking_active=False,
            measured_at=NOW,
        )
    )
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=1,
            observation_type=WARM_UP,
            payload_schema_version="v1",
            payload=row,
        )


def test_temperature_context_rejects_duplicate_points():
    with pytest.raises(ValidationError, match="Duplicate temperature"):
        _ctx(
            TemperatureZeroContext,
            temperature_sequence_c=["0", "0"],
            zero_tracking_disabled=True,
        )


def test_tilting_context_requires_matching_mode_and_variant():
    with pytest.raises(ValidationError, match="Tilt mode"):
        _ctx(
            TiltingContext,
            procedure_variant="LEVEL_INDICATOR",
            tilt_mode="NO_LEVEL_DEVICE",
            reference_tilt_value="0",
            test_tilt_value="0.05",
            directions=["FORWARD"],
            reference_position_confirmed=True,
        )
