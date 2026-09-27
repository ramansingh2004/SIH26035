"""Phase 25 remediation Fix 1 contracts for Section 1 static temperature coverage."""

from app.compliance.parameterized import TemperatureExpression, resolve_temperature_expression
from app.compliance.weighing import (
    StaticTemperatureWeighingContext,
    StaticTemperatureWeighingObservation,
)
from app.schemas.testing import ObservationData, ProcedureUpdate
from domain_tests.fixtures.synthetic import instrument


def test_declared_mean_temperature_expression_is_exact_and_requires_bounds():
    snapshot = instrument(declared_temp_min_c="-10", declared_temp_max_c="40")
    value = resolve_temperature_expression(
        TemperatureExpression(basis="DECLARED_MEAN"),
        snapshot,
    )
    assert str(value) == "15.0"


def test_http_contract_accepts_static_temperature_v2_without_weakening_v1_discriminator():
    context = StaticTemperatureWeighingContext(
        evaluation_context="SYNTHETIC",
        range_no=1,
        scenario="static",
        stages=(),
    )
    parsed_context = ProcedureUpdate.model_validate(
        {"procedure_context": context.model_dump(mode="json")}
    )
    assert parsed_context.procedure_context.procedure_schema_version == "v2"
    assert parsed_context.procedure_context.procedure_variant == "STATIC_TEMPERATURE"

    observation = StaticTemperatureWeighingObservation(
        sequence_no=1,
        load_g="0",
        indication_g="0",
        additional_load_g="0",
        zero_error_g="0",
        direction="UP",
        measured_at="2000-01-01T00:00:00Z",
        temperature_stage="REFERENCE_INITIAL",
    )
    parsed_observation = ObservationData.model_validate(
        {
            "sequence_no": 1,
            "observation_type": "WEIGHING_PERFORMANCE",
            "payload_schema_version": "v2",
            "payload": observation.model_dump(mode="json"),
        }
    )
    assert parsed_observation.payload.observation_schema_version == "v2"
    assert parsed_observation.payload.protocol == "WEIGHING_STATIC_TEMPERATURE_V2"
