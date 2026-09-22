"""Pure Section 5 tests; determined outcomes use synthetic verified policies only."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compliance.engine import R76Engine
from app.compliance.evaluators import EvaluatorRegistry
from app.compliance.repeatability import (
    CODE,
    RepeatabilityContext,
    RepeatabilityObservation,
    RepeatabilitySeriesResult,
    section5_registration,
)
from app.compliance.ruleset import load_ruleset
from domain_tests.fixtures.core_reusable import (
    _unverify,
    evaluate_repeatability,
    repeatability_context,
    repeatability_observations,
    repeatability_rules,
)
from domain_tests.fixtures.synthetic import instrument


def _series(result, code):
    return next(
        item
        for item in result.calculations
        if isinstance(item, RepeatabilitySeriesResult) and item.series_code == code
    )


def test_repeatability_complete_synthetic_series_and_range_calculation():
    result = evaluate_repeatability()
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "COMPLIANT"
    mid = _series(result, "MID")
    high = _series(result, "HIGH")
    assert (mid.minimum_error_g, mid.maximum_error_g, mid.repeatability_range_g) == (
        Decimal("0"),
        Decimal("10"),
        Decimal("10"),
    )
    assert mid.allowed_range_g == Decimal("10")
    assert high.repeatability_range_g == Decimal("10")
    assert high.allowed_range_g == Decimal("10")


def test_repeatability_range_failure_is_complete_noncompliant():
    result = evaluate_repeatability(ruleset=repeatability_rules(series=[
        dict(
            series_code="MID",
            load_g="5000",
            minimum_repetitions=3,
            range_limit_basis="E",
            range_limit_multiplier="0.5",
            range_operator="<=",
            range_semantics="SIGNED",
        ),
        dict(
            series_code="HIGH",
            load_g="10000",
            minimum_repetitions=3,
            range_limit_basis="MPE",
            range_limit_multiplier="1",
            range_operator="<=",
            range_semantics="SIGNED",
        ),
    ]))
    assert result.evaluation_status == "COMPLETE"
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert any(f.code == "REPEATABILITY_RANGE_LIMIT_EXCEEDED" for f in result.failed_conditions)


def test_repeatability_individual_mpe_failure_is_complete_noncompliant():
    result = evaluate_repeatability(
        observations=repeatability_observations(mid_errors=("0", "5", "11"))
    )
    assert result.compliance_outcome == "NONCOMPLIANT"
    assert any(
        f.code == "REPEATABILITY_INDIVIDUAL_LIMIT_EXCEEDED"
        for f in result.failed_conditions
    )


@pytest.mark.parametrize(
    ("rules", "context", "observations"),
    [
        (
            repeatability_rules(),
            repeatability_context(stabilized=False),
            repeatability_observations(),
        ),
        (
            repeatability_rules(require_environment=True),
            repeatability_context(environment=[]),
            repeatability_observations(),
        ),
        (
            repeatability_rules(require_equipment=True),
            repeatability_context(equipment=[]),
            repeatability_observations(),
        ),
        (
            repeatability_rules(require_evidence=True),
            repeatability_context(evidence_hashes=[]),
            repeatability_observations(),
        ),
        (repeatability_rules(series=[dict(
            series_code="MID", load_g="5000", minimum_repetitions=4,
            range_limit_basis="E",
            range_limit_multiplier="1",
            range_operator="<=",
            range_semantics="SIGNED",
        ), dict(
            series_code="HIGH", load_g="10000", minimum_repetitions=3,
            range_limit_basis="MPE",
            range_limit_multiplier="1",
            range_operator="<=",
            range_semantics="SIGNED",
        )]), repeatability_context(), repeatability_observations()),
    ],
)
def test_repeatability_verified_procedure_requirements_block_incomplete_data(
    rules, context, observations
):
    result = evaluate_repeatability(
        ruleset=rules, procedure_context=context, observations=observations
    )
    assert result.evaluation_status == "INCOMPLETE"
    assert result.compliance_outcome == "UNDETERMINED"


def test_repeatability_duplicate_repetition_number_is_domain_incomplete_not_schema_guess():
    batch = repeatability_observations()
    rows = [row.model_dump(mode="python") for row in batch.rows]
    rows[1]["repetition_no"] = rows[0]["repetition_no"]
    parsed = section5_registration().observations.parse(
        test_code=CODE, protocol="REPEATABILITY_V1", version="v1", rows=rows
    )
    result = evaluate_repeatability(observations=parsed)
    assert result.evaluation_status == "INCOMPLETE"
    assert any(issue.category == "COUNT" for issue in result.procedure_issues)


def test_repeatability_candidate_rules_remain_review_required():
    result = R76Engine(EvaluatorRegistry((section5_registration(),))).evaluate(
        test_code=CODE,
        instrument_snapshot=instrument(indication_type="DIGITAL"),
        procedure_context=repeatability_context(),
        observations=repeatability_observations(),
        ruleset=load_ruleset(),
    )
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert result.compliance_outcome == "UNDETERMINED"


@pytest.mark.parametrize(
    "rule_id", ["SECTION5_PROCEDURE", "SECTION5_MPE", "SECTION5_CLASSIFICATION"]
)
def test_repeatability_unverified_dependency_blocks(rule_id):
    result = evaluate_repeatability(ruleset=_unverify(repeatability_rules(), rule_id))
    assert result.evaluation_status == "REVIEW_REQUIRED"
    assert rule_id in result.unresolved_rule_ids


@pytest.mark.parametrize("value", [1.25, "NaN", "Infinity", "-Infinity"])
def test_repeatability_float_and_nonfinite_rejected(value):
    row = repeatability_observations().rows[0].model_dump()
    row["indication_g"] = value
    with pytest.raises(ValueError):
        RepeatabilityObservation.model_validate(row)


def test_repeatability_context_closed_frozen_and_hash_deterministic():
    context = repeatability_context()
    with pytest.raises(ValidationError):
        context.stabilized = False
    with pytest.raises(ValidationError):
        RepeatabilityContext.model_validate(context.model_dump() | {"unknown": "x"})
    first = evaluate_repeatability()
    second = evaluate_repeatability()
    changed = evaluate_repeatability(
        observations=repeatability_observations(high_errors=("0", "-4", "5"))
    )
    assert first.input_hash == second.input_hash
    assert first.result_hash == second.result_hash
    assert changed.input_hash != first.input_hash
    assert changed.result_hash != first.result_hash


def test_repeatability_error_basis_is_explicitly_rule_controlled():
    batch = repeatability_observations()
    rows = [row.model_dump(mode="python") for row in batch.rows]
    for row in rows:
        row["zero_error_g"] = "5"
    parsed = section5_registration().observations.parse(
        test_code=CODE, protocol="REPEATABILITY_V1", version="v1", rows=rows
    )
    corrected = evaluate_repeatability(observations=parsed)
    raw = evaluate_repeatability(
        observations=parsed,
        ruleset=repeatability_rules(error_basis="RAW"),
    )
    corrected_point = next(
        item for item in corrected.calculations if hasattr(item, "selected_error_g")
    )
    raw_point = next(item for item in raw.calculations if hasattr(item, "selected_error_g"))
    assert corrected_point.error_g == Decimal("0")
    assert corrected_point.corrected_error_g == Decimal("-5")
    assert corrected_point.selected_error_g == Decimal("-5")
    assert raw_point.selected_error_g == Decimal("0")
