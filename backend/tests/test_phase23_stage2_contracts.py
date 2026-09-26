"""Phase 23 Stage 2 pure/source contracts."""

from pathlib import Path

from app.compliance.demo import (
    DEMO_ARTIFACT,
    DEMO_LAB_CODE,
    demo_registry,
    is_demo_ruleset,
    load_demo_ruleset,
)
from app.compliance.domain import InstrumentSnapshot, ObservationBatch
from app.compliance.engine import R76Engine
from app.compliance.planning import RequirementPlanner
from app.compliance.weighing import WeighingContext, WeighingObservation

ROOT = Path(__file__).resolve().parents[2]


def instrument() -> InstrumentSnapshot:
    capacity = {
        "min_capacity_g": "200",
        "max_capacity_g": "30000",
        "scale_interval_d_g": "10",
        "verification_interval_e_g": "10",
        "verification_intervals_n": "3000",
    }
    return InstrumentSnapshot.model_validate(
        {
            **capacity,
            "accuracy_class": "III",
            "range_type": "SINGLE",
            "indication_type": "DIGITAL",
            "is_electronic": True,
            "ranges": [{**capacity, "range_no": 1}],
        }
    )


def context() -> WeighingContext:
    return WeighingContext.model_validate(
        {
            "range_no": 1,
            "scenario": "demo",
            "evaluation_context": "SIH_DEMO",
            "stages": ["UP", "DOWN"],
            "preloaded": False,
            "warmed_up_seconds": "0",
            "stabilized": False,
            "zero_condition": "DEMO_ZERO",
            "environment": [],
            "equipment": [],
            "evidence_hashes": [],
        }
    )


def observations(*, failing: bool) -> ObservationBatch:
    rows = [
        (1, "UP", "200", "200", "2000-01-01T00:00:01Z"),
        (
            2,
            "UP",
            "30000",
            "30030" if failing else "30000",
            "2000-01-01T00:00:02Z",
        ),
        (3, "DOWN", "30000", "30000", "2000-01-01T00:00:03Z"),
        (4, "DOWN", "200", "200", "2000-01-01T00:00:04Z"),
    ]
    values = tuple(
        WeighingObservation.model_validate(
            {
                "sequence_no": sequence,
                "load_g": load,
                "indication_g": indication,
                "additional_load_g": "5",
                "zero_error_g": "0",
                "direction": direction,
                "measured_at": measured_at,
            }
        )
        for sequence, direction, load, indication, measured_at in rows
    )
    return ObservationBatch(
        test_code="WEIGHING_PERFORMANCE",
        protocol="WEIGHING_V1",
        observation_schema_version="v1",
        rows=values,
    )


def test_demo_identity_is_closed_and_explicit() -> None:
    rules = load_demo_ruleset()
    assert DEMO_ARTIFACT == "sih26035_demo_v1"
    assert DEMO_LAB_CODE == "SIH26035-DEMO"
    assert is_demo_ruleset(rules)
    assert rules.metadata.version == "SYNTHETIC_TEST_SIH26035_DEMO_V1"
    assert rules.metadata.source_reference == "SYNTHETIC TEST FIXTURE ONLY"


def test_demo_ruleset_exposes_exactly_17_top_level_sections() -> None:
    rules = load_demo_ruleset()
    assert len(rules.tests) == 17
    assert {test.section for test in rules.tests} == set(range(1, 18))
    assert all(test.parent is None for test in rules.tests)


def test_demo_applicability_has_one_required_and_16_explicit_na() -> None:
    plan = RequirementPlanner().plan(
        instrument_snapshot=instrument(),
        ruleset=load_demo_ruleset(),
    )
    assert plan.applicability_confirmable is True
    required = [
        slot for slot in plan.slots if slot.decision.applicability == "REQUIRED"
    ]
    excluded = [
        slot
        for slot in plan.slots
        if slot.decision.applicability == "NOT_APPLICABLE"
    ]
    assert len(required) == 1
    assert required[0].test_code == "WEIGHING_PERFORMANCE"
    assert len(excluded) == 16


def test_demo_positive_is_deterministically_compliant_but_synthetic() -> None:
    result = R76Engine(demo_registry()).evaluate(
        test_code="WEIGHING_PERFORMANCE",
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(failing=False),
        ruleset=load_demo_ruleset(),
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    assert result.synthetic_fixture is True
    assert not result.failed_conditions
    assert "SYNTHETIC SIH DEMO ONLY" in result.reasons[0]


def test_demo_negative_is_deterministically_noncompliant_but_synthetic() -> None:
    result = R76Engine(demo_registry()).evaluate(
        test_code="WEIGHING_PERFORMANCE",
        instrument_snapshot=instrument(),
        procedure_context=context(),
        observations=observations(failing=True),
        ruleset=load_demo_ruleset(),
    )
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert result.synthetic_fixture is True
    assert result.failed_conditions
    assert result.failed_conditions[0].code == "WEIGHING_LIMIT_EXCEEDED"


def test_application_source_has_non_activation_and_official_guards() -> None:
    rulesets = (ROOT / "backend/app/services/rulesets.py").read_text(encoding="utf-8")
    testing = (ROOT / "backend/app/services/testing.py").read_text(encoding="utf-8")
    review = (ROOT / "backend/app/services/review.py").read_text(encoding="utf-8")
    report = (ROOT / "backend/app/services/report.py").read_text(encoding="utf-8")

    assert "SYNTHETIC_DEMO_ACTIVATION_FORBIDDEN" in rulesets
    assert "DEMO_LAB_CODE" in testing
    assert "demo_registry()" in testing
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in review
    assert "SYNTHETIC_DEMO_OFFICIAL_FORBIDDEN" in report
