"""Phase 11 Stage 1 typed-contract and registry wiring tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.compliance.phase11 import ENDURANCE, EnduranceContext, EnduranceObservation
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.schemas.testing import ObservationData, ProcedureUpdate


def endurance_context(**changes):
    payload = dict(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="fixture",
        cycling_target_load_g="10000",
        planned_cycles=10,
        completed_cycles=10,
        cycle_started_at="2000-01-02T00:00:00Z",
        cycle_ended_at="2000-01-03T00:00:00Z",
        same_reference_weights_confirmed=True,
    )
    payload.update(changes)
    return EnduranceContext.model_validate(payload)


def endurance_observation(**changes):
    payload = dict(
        sequence_no=1,
        phase="INITIAL",
        point_id="P1",
        load_g="10000",
        indication_g="10000",
        additional_load_g="5",
        zero_error_g="0",
        measured_at=datetime(2000, 1, 1, tzinfo=UTC),
    )
    payload.update(changes)
    return EnduranceObservation.model_validate(payload)


def test_phase11_registry_adds_endurance():
    codes = tuple(x.test_code for x in implemented_registry().registrations)
    assert codes == IMPLEMENTED_TEST_CODES
    assert ENDURANCE in codes


def test_phase11_http_contract_accepts_typed_context():
    parsed = ProcedureUpdate(procedure_context=endurance_context()).procedure_context
    assert type(parsed) is EnduranceContext
    assert parsed.test_code == ENDURANCE


def test_phase11_http_contract_accepts_typed_observation():
    row = endurance_observation()
    parsed = ObservationData(
        sequence_no=1, observation_type=ENDURANCE, payload_schema_version="v1", payload=row
    )
    assert type(parsed.payload) is EnduranceObservation


def test_phase11_observation_envelope_rejects_other_type():
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=1,
            observation_type="SPAN_STABILITY",
            payload_schema_version="v1",
            payload=endurance_observation(),
        )


def test_phase11_cycle_timestamps_must_be_paired():
    with pytest.raises(ValidationError, match="must be supplied together"):
        endurance_context(cycle_ended_at=None)


def test_phase11_cycle_end_cannot_precede_start():
    with pytest.raises(ValidationError, match="cannot precede"):
        endurance_context(
            cycle_started_at="2000-01-03T00:00:00Z", cycle_ended_at="2000-01-02T00:00:00Z"
        )


def test_phase11_observation_requires_initial_or_final_phase():
    with pytest.raises(ValidationError):
        endurance_observation(phase="CYCLING")
