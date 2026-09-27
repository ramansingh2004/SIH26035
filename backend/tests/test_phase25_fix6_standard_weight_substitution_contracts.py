"""Phase 25 Fix 6 structural contracts."""

from pathlib import Path

from app.compliance.parameterized import RationalFractionV2, StandardWeightSubstitutionProcedureV2
from app.compliance.ruleset import load_ruleset
from app.compliance.weighing import section1_registration

REPO = Path(__file__).resolve().parents[2]


def test_fix6_keeps_regulatory_constants_out_of_production_code():
    parameterized = (REPO / "backend/app/compliance/parameterized.py").read_text(encoding="utf-8")
    weighing = (REPO / "backend/app/compliance/weighing.py").read_text(encoding="utf-8")
    combined = parameterized + weighing
    for forbidden in ("0.3e", "0.2e", "one third", "one fifth"):
        assert forbidden not in combined.lower()


def test_fix6_fraction_is_exact_rational_not_decimal_approximation():
    one_third = RationalFractionV2(numerator=1, denominator=3)
    assert one_third.numerator == 1
    assert one_third.denominator == 3


def test_fix6_policy_has_no_regulatory_defaults():
    field = StandardWeightSubstitutionProcedureV2.model_fields[
        "base_minimum_standard_weight_fraction"
    ]
    assert field.is_required()
    assert StandardWeightSubstitutionProcedureV2.model_fields[
        "repeatability_reductions"
    ].default == ()


def test_fix6_bumps_section1_implementation_identity():
    assert section1_registration().implementation_version == "section1-v3"


def test_fix6_candidate_ruleset_remains_unpromoted():
    ruleset = load_ruleset()
    assert ruleset.metadata.version == "candidate-v1"
    assert ruleset.metadata.supported_test_codes == ()
    assert ruleset.activation_blockers()
