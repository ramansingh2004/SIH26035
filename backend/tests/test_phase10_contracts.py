"""Phase 10 Stage 1 typed-contract and registry wiring tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.compliance.phase10 import (
    DISTURBANCE_CODES,
    DISTURBANCE_VEHICLE_SUPPLY,
    BurstContext,
    BurstObservation,
    DisturbanceSeverity,
    VehicleSupplyContext,
)
from app.compliance.suite import (
    IMPLEMENTED_TEST_CODES,
    implemented_registry,
)
from app.schemas.testing import ObservationData, ProcedureUpdate

NOW = datetime(2000, 1, 1, tzinfo=UTC).isoformat()


def severity(identifier="s1"):
    return DisturbanceSeverity(
        severity_id=identifier,
        case="SYNTHETIC_CONTRACT",
        waveform_reference="SYNTHETIC_REFERENCE",
    )


def burst_context():
    return BurstContext.model_validate(
        dict(
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            test_load_g="1000",
            warm_up_completed=True,
            environment_stabilized=True,
            peripherals_connected=True,
            no_load_deviation_g="0",
            severity_cases=[severity().model_dump(mode="json")],
        )
    )


def burst_observation():
    return BurstObservation.model_validate(
        dict(
            sequence_no=1,
            severity_id="s1",
            repetition_no=1,
            reference_indication_g="1000",
            disturbed_indication_g="1000",
            fault_detected=False,
            state_before="NORMAL",
            state_during="NORMAL",
            state_after="NORMAL",
            measured_at=NOW,
        )
    )


def test_phase10_registry_adds_all_seven_disturbance_families():
    registry = implemented_registry()
    codes = tuple(item.test_code for item in registry.registrations)
    assert codes == IMPLEMENTED_TEST_CODES
    assert set(DISTURBANCE_CODES) <= set(codes)


def test_phase10_http_contract_accepts_typed_context():
    context = burst_context()
    parsed = ProcedureUpdate(procedure_context=context).procedure_context
    assert type(parsed) is BurstContext
    assert parsed.test_code == "DISTURBANCE_BURST"


def test_phase10_http_contract_accepts_typed_observation():
    row = burst_observation()
    parsed = ObservationData(
        sequence_no=1,
        observation_type="DISTURBANCE_BURST",
        payload_schema_version="v1",
        payload=row,
    )
    assert type(parsed.payload) is BurstObservation


def test_phase10_observation_envelope_rejects_cross_family_payload():
    row = burst_observation()
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=1,
            observation_type="DISTURBANCE_SURGE",
            payload_schema_version="v1",
            payload=row,
        )


def test_phase10_context_rejects_duplicate_severity_identifier():
    item = severity().model_dump(mode="json")
    with pytest.raises(
        ValidationError,
        match="Duplicate disturbance severity identifier",
    ):
        BurstContext.model_validate(
            dict(
                evaluation_context="SYNTHETIC",
                range_no=1,
                scenario="fixture",
                test_load_g="1000",
                warm_up_completed=True,
                environment_stabilized=True,
                peripherals_connected=True,
                no_load_deviation_g="0",
                severity_cases=[item, item],
            )
        )


def test_phase10_fault_response_data_requires_detected_fault():
    payload = burst_observation().model_dump(mode="python")
    payload["fault_response"] = "SYNTHETIC_RESPONSE"
    with pytest.raises(
        ValidationError,
        match="requires fault_detected=true",
    ):
        BurstObservation.model_validate(payload)


@pytest.mark.parametrize(
    "variant",
    [
        "SUPPLY_LINE_CONDUCTION",
        "NON_SUPPLY_LINE_COUPLING",
    ],
)
def test_phase10_vehicle_subvariants_are_registered(variant):
    context = VehicleSupplyContext.model_validate(
        dict(
            procedure_variant=variant,
            evaluation_context="SYNTHETIC",
            range_no=1,
            scenario="fixture",
            test_load_g="1000",
            warm_up_completed=True,
            environment_stabilized=True,
            peripherals_connected=True,
            no_load_deviation_g="0",
            severity_cases=[severity().model_dump(mode="json")],
        )
    )
    registration = implemented_registry().resolve(DISTURBANCE_VEHICLE_SUPPLY)
    validated = registration.contexts.validate(context)
    assert validated.procedure_variant == variant
