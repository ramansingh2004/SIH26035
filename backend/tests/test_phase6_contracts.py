"""Phase 6 service/schema wiring contracts; PostgreSQL behavior is covered in Stage 3."""

import pytest
from pydantic import ValidationError

from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.schemas.testing import ObservationData, ProcedureUpdate
from domain_tests.fixtures.core_reusable import (
    eccentricity_context,
    eccentricity_observations,
    repeatability_context,
    repeatability_observations,
    tare_context,
    tare_observations,
)
from domain_tests.fixtures.weighing import fixture_context, fixture_observations


def test_phase6_registry_contains_only_implemented_mechanics():
    registry = implemented_registry()
    assert tuple(item.test_code for item in registry.registrations) == IMPLEMENTED_TEST_CODES
    assert {item.implementation_version for item in registry.registrations} == {
        "section1-v1",
        "section3-v1",
        "section5-v1",
        "section9-v1",
    }


@pytest.mark.parametrize(
    ("context", "batch"),
    [
        (fixture_context(), fixture_observations()),
        (eccentricity_context(), eccentricity_observations()),
        (repeatability_context(), repeatability_observations()),
        (tare_context(), tare_observations()),
    ],
)
def test_phase6_http_contracts_accept_typed_context_and_observations(context, batch):
    parsed_context = ProcedureUpdate(procedure_context=context).procedure_context
    assert type(parsed_context) is type(context)
    row = batch.rows[0]
    parsed = ObservationData(
        sequence_no=row.sequence_no,
        observation_type=row.test_code,
        payload_schema_version=row.observation_schema_version,
        payload=row,
    )
    assert type(parsed.payload) is type(row)


def test_observation_envelope_cannot_disagree_with_typed_payload():
    row = eccentricity_observations().rows[0]
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=row.sequence_no,
            observation_type="TARE",
            payload_schema_version="v1",
            payload=row,
        )


def test_procedure_discriminator_rejects_unknown_phase6_test_code():
    payload = eccentricity_context().model_dump(mode="json")
    payload["test_code"] = "UNKNOWN_TEST"
    with pytest.raises(ValidationError):
        ProcedureUpdate(procedure_context=payload)
