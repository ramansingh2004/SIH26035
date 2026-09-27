"""Fix 10 contracts: exact executable review surface and assembly gate."""

import json

import pytest

from app.compliance.ruleset import load_ruleset
from app.compliance.suite import IMPLEMENTED_TEST_CODES, implemented_registry
from app.compliance.verified_blueprint import (
    CONSTRUCTION_ITEMS,
    INDIA_SUBSTITUTION_RULE,
    V1_ONLY_PROCEDURE_RULES,
    executable_review_rows,
    executable_rule_blueprint,
    verified_test_dependencies,
)
from scripts.assemble_phase25_verified_v1 import AssemblyError, assemble_verified_v1
from scripts.export_phase25_external_review import export_pack
from scripts.validate_phase25_external_review import validate_pack


def test_fix10_blueprint_contains_every_real_evaluator_dependency():
    candidate = load_ruleset()
    blueprint = {item.rule_key: item for item in executable_rule_blueprint(candidate)}
    dependencies = verified_test_dependencies(candidate)
    registry = implemented_registry()

    for code in IMPLEMENTED_TEST_CODES:
        required = set(registry.resolve(code).evaluator.required_rules())
        assert required <= blueprint.keys()
        assert set(dependencies[code]) == {f"APP_{code}", *required}

    assert INDIA_SUBSTITUTION_RULE in blueprint
    assert INDIA_SUBSTITUTION_RULE in blueprint["SECTION1_PROCEDURE"].required_dependencies
    assert "RETEST_SELECTION" in blueprint


def test_fix10_every_catalog_test_has_one_applicability_root():
    candidate = load_ruleset()
    blueprint = {item.rule_key for item in executable_rule_blueprint(candidate)}
    dependencies = verified_test_dependencies(candidate)

    for test in candidate.tests:
        app_key = f"APP_{test.code}"
        assert app_key in blueprint
        assert dependencies[test.code][0] == app_key
        assert sum(key.startswith("APP_") for key in dependencies[test.code]) == 1


def test_fix10_section16_has_structural_review_slots():
    candidate = load_ruleset()
    blueprint = {item.rule_key: item for item in executable_rule_blueprint(candidate)}

    expected = {f"SECTION16_{category}" for category, _ in CONSTRUCTION_ITEMS}
    assert expected <= blueprint.keys()
    for key in expected:
        assert blueprint[key].allowed_kinds == ("construction_item_v1",)
        assert blueprint[key].file_bucket == "checklist"


def test_fix10_does_not_offer_non_executable_v2_policy_kinds():
    candidate = load_ruleset()
    blueprint = {item.rule_key: item for item in executable_rule_blueprint(candidate)}

    for key in V1_ONLY_PROCEDURE_RULES:
        assert blueprint[key].allowed_kinds
        assert all(kind.endswith("_v1") for kind in blueprint[key].allowed_kinds)


def test_fix10_export_has_assembly_contract_and_remains_pending(tmp_path):
    output = tmp_path / "review"
    result = export_pack(output)

    assert result["executable_rules"] > 7
    assert (output / "07_executable_rule_review.csv").is_file()
    declaration = json.loads(
        (output / "08_final_regulatory_declaration.json").read_text()
    )
    assert declaration["regulatory_signoff"] is False
    assert declaration["independent_of_implementation"] is False

    validation = validate_pack(output)
    assert validation["valid"] is False
    assert any("EXEC_RULE" in item for item in validation["blockers"])
    assert "FINAL_REGULATORY_SIGNOFF_REQUIRED" in validation["blockers"]


def test_fix10_assembler_refuses_pending_pack_before_writing(tmp_path):
    review = tmp_path / "review"
    export_pack(review)
    evidence = tmp_path / "evidence.zip"
    evidence.write_bytes(b"not-a-signed-evidence-package")
    output = tmp_path / "verified"

    with pytest.raises(AssemblyError, match="not assembly-ready"):
        assemble_verified_v1(review, evidence, output)

    assert not output.exists()


def test_fix10_exported_rows_are_exact_blueprint():
    candidate = load_ruleset()
    rows = executable_review_rows(candidate)
    assert {row["rule_key"] for row in rows} == {
        item.rule_key for item in executable_rule_blueprint(candidate)
    }
    assert all(row["review_status"] == "PENDING" for row in rows)
    assert all(row["independent_of_implementation"] == "false" for row in rows)
