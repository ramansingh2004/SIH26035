"""Phase 7 Stage 1 typed-contract and registry wiring tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.compliance.phase7 import (
    CREEP,
    DISCRIMINATION,
    SENSITIVITY,
    STABILITY_EQUILIBRIUM,
    ZERO_RETURN,
    CreepContext,
    DiscriminationContext,
    SensitivityContext,
    StabilityContext,
    ZeroReturnContext,
)
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.schemas.testing import ObservationData, ProcedureUpdate

NOW = datetime(2000, 1, 1, tzinfo=UTC).isoformat()


def _ctx(cls, **values):
    base = dict(evaluation_context="SYNTHETIC", range_no=1, scenario="fixture")
    base.update(values)
    return cls.model_validate(base)


@pytest.mark.parametrize(
    "context",
    [
        _ctx(
            DiscriminationContext,
            procedure_variant="DIGITAL",
            indication_mode="DIGITAL",
        ),
        _ctx(SensitivityContext),
        _ctx(
            ZeroReturnContext,
            test_load_g="10000",
            hold_seconds="60",
        ),
        _ctx(
            CreepContext,
            procedure_variant="SHORT",
            test_load_g="10000",
            planned_duration_s="1800",
        ),
        _ctx(
            StabilityContext,
            functions_under_test=["PRINTING", "STORAGE", "ZERO", "TARE"],
        ),
    ],
)
def test_phase7_http_contract_accepts_typed_context(context):
    parsed = ProcedureUpdate(procedure_context=context).procedure_context
    assert type(parsed) is type(context)


def test_phase7_registry_extends_phase6_without_group_evaluators():
    registry = implemented_registry()
    codes = tuple(item.test_code for item in registry.registrations)
    assert codes == IMPLEMENTED_TEST_CODES
    for code in (
        DISCRIMINATION,
        SENSITIVITY,
        ZERO_RETURN,
        CREEP,
        STABILITY_EQUILIBRIUM,
    ):
        assert code in codes
    assert "DISCRIMINATION_SENSITIVITY" not in codes
    assert "TIME_DEPENDENCE" not in codes


def test_phase7_observation_envelope_rejects_disagreement():
    from app.compliance.phase7 import DiscriminationObservation

    row = DiscriminationObservation.model_validate(
        dict(
            sequence_no=1,
            load_g="5000",
            extra_load_g="10",
            indication_before_g="5000",
            indication_after_g="5010",
            measured_at=NOW,
        )
    )
    with pytest.raises(ValidationError, match="envelope"):
        ObservationData(
            sequence_no=1,
            observation_type=ZERO_RETURN,
            payload_schema_version="v1",
            payload=row,
        )
