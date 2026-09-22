"""Phase 9 Stage 1 typed-contract and registry wiring tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.compliance.phase9 import (
    DAMP_HEAT,
    SPAN_STABILITY,
    DampHeatContext,
    DampHeatObservation,
    SpanStabilityContext,
    SpanStabilityObservation,
)
from app.compliance.suite import (
    IMPLEMENTED_TEST_CODES,
    implemented_registry,
)
from app.schemas.testing import ObservationData, ProcedureUpdate

NOW = datetime(2000, 1, 1, tzinfo=UTC).isoformat()


def test_phase9_registry_extends_phase8():
    registry = implemented_registry()
    codes = tuple(item.test_code for item in registry.registrations)
    assert codes == IMPLEMENTED_TEST_CODES
    assert DAMP_HEAT in codes
    assert SPAN_STABILITY in codes


@pytest.mark.parametrize(
    "context",
    [
        DampHeatContext.model_validate(
            dict(
                evaluation_context="SYNTHETIC",
                range_no=1,
                scenario="fixture",
                stages=["INITIAL", "HIGH_HUMIDITY", "FINAL"],
                loads_g=["1000", "10000"],
                same_reference_weights_confirmed=True,
            )
        ),
        SpanStabilityContext.model_validate(
            dict(
                evaluation_context="SYNTHETIC",
                range_no=1,
                scenario="fixture",
                test_load_g="10000",
                planned_duration_s="1000",
                same_reference_weights_confirmed=True,
            )
        ),
    ],
)
def test_phase9_http_contract_accepts_typed_context(context):
    parsed = ProcedureUpdate(procedure_context=context).procedure_context
    assert type(parsed) is type(context)


def test_phase9_observation_envelope_rejects_disagreement():
    row = DampHeatObservation.model_validate(
        dict(
            sequence_no=1,
            stage="INITIAL",
            load_g="1000",
            indication_g="1000",
            additional_load_g="5",
            zero_error_g="0",
            temperature_c="20",
            relative_humidity_percent="50",
            stage_elapsed_s="100",
            exposure_elapsed_s="100",
            stabilized=True,
            functions_operational=True,
            measured_at=NOW,
        )
    )
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=1,
            observation_type=SPAN_STABILITY,
            payload_schema_version="v1",
            payload=row,
        )


def test_damp_heat_context_rejects_duplicate_stage():
    with pytest.raises(ValidationError, match="Duplicate damp-heat stage"):
        DampHeatContext.model_validate(
            dict(
                evaluation_context="SYNTHETIC",
                range_no=1,
                scenario="fixture",
                stages=["INITIAL", "INITIAL"],
                loads_g=["1000"],
                same_reference_weights_confirmed=True,
            )
        )


def test_span_power_event_requires_duration():
    with pytest.raises(
        ValidationError,
        match="Power disconnection duration required",
    ):
        SpanStabilityObservation.model_validate(
            dict(
                sequence_no=1,
                measurement_no=1,
                elapsed_s="0",
                location="LAB",
                temperature_c="20",
                relative_humidity_percent="50",
                barometric_pressure_hpa="1000",
                power_disconnection_event=True,
                temperature_test_event=False,
                damp_heat_event=False,
                load_g="10000",
                zero_indication_g="0",
                zero_additional_load_g="5",
                loaded_indication_g="10000",
                loaded_additional_load_g="5",
                measured_at=NOW,
            )
        )
