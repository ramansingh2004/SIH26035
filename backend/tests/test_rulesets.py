"""Pure configuration tests. Synthetic evidence never enters the production registry."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.compliance.catalog import CHECKLIST_DOMAINS, FAMILIES, SECTIONS
from app.compliance.ruleset import ROOT, Parameter, RuleSet, RuleSetRegistry, load_ruleset


def test_complete_candidate_catalog_and_gate():
    rules = load_ruleset()
    assert {t.code for t in rules.tests if not t.parent} == set(SECTIONS)
    assert {t.section for t in rules.tests if not t.parent} == set(range(1, 18))
    assert {t.code for t in rules.tests if t.parent} == {
        code for values in FAMILIES.values() for code in values
    }
    assert len(rules.tests) == 28
    assert {c.group for c in rules.checklist} == set(CHECKLIST_DOMAINS)
    assert len(rules.checklist) == 27
    assert all(
        not t.implemented and t.verification.status == "TODO_REGULATORY_VALIDATION"
        for t in rules.tests
    )
    assert "NO_SUPPORTED_TESTS" in rules.activation_blockers()
    registry = RuleSetRegistry()
    registry.register(rules)
    m = rules.metadata
    assert registry.get(m.standard_code, m.edition, m.version) == rules
    with pytest.raises(ValueError, match="RULESET_NOT_VERIFIED"):
        registry.get(m.standard_code, m.edition, m.version, authoritative=True)
    with pytest.raises(KeyError):
        registry.get(m.standard_code, m.edition, "unknown-version")


def test_hash_is_semantic_and_immutable():
    rules = load_ruleset()
    value = rules.model_dump(mode="json")
    value["rules"].reverse()
    value["tests"].reverse()
    value["metadata"]["standard_parts"].reverse()
    rebuilt = RuleSet.model_validate(value)
    assert rebuilt.configuration_hash == rules.configuration_hash
    assert RuleSet.model_validate(rules.snapshot()).configuration_hash == rules.configuration_hash
    with pytest.raises(ValidationError):
        rules.metadata.version = "changed"
    value["rules"][0]["description"] += " changed"
    changed = RuleSet.model_validate(value)
    assert changed.configuration_hash != rules.configuration_hash
    registry = RuleSetRegistry()
    registry.register(rules)
    with pytest.raises(ValueError, match="different content"):
        registry.register(changed)


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "unknown_field",
        "duplicate_rule",
        "duplicate_test",
        "unknown_dependency",
        "cycle",
        "bad_parent",
        "verified_without_evidence",
        "undeclared_source",
        "float_parameter",
        "unknown_supported",
    ],
)
def test_invalid_configuration_rejected(change):
    value = load_ruleset().model_dump(mode="json")
    if change == "schema":
        value["metadata"]["schema_version"] = 999
    elif change == "unknown_field":
        value["metadata"]["authoritative"] = True
    elif change == "duplicate_rule":
        value["rules"].append(copy.deepcopy(value["rules"][0]))
    elif change == "duplicate_test":
        value["tests"].append(copy.deepcopy(value["tests"][0]))
    elif change == "unknown_dependency":
        value["rules"][0]["dependencies"] = ["UNKNOWN"]
    elif change == "cycle":
        value["rules"][0]["dependencies"] = [value["rules"][0]["key"]]
    elif change == "bad_parent":
        value["tests"][0]["parent"] = "UNKNOWN"
    elif change == "verified_without_evidence":
        value["rules"][0]["verification"]["status"] = "VERIFIED"
    elif change == "undeclared_source":
        value["rules"][0]["source"]["edition"] = "invented"
    elif change == "float_parameter":
        value["rules"][0]["parameters"][0]["value"] = 0.5
    else:
        value["metadata"]["supported_test_codes"] = ["UNKNOWN"]
    with pytest.raises((ValueError, ValidationError)):
        RuleSet.model_validate(value)


def test_supported_declaration_does_not_verify_or_implement():
    value = load_ruleset().model_dump(mode="json")
    value["metadata"]["supported_test_codes"] = ["WEIGHING_PERFORMANCE"]
    rule = RuleSet.model_validate(value)
    blockers = rule.activation_blockers()
    assert "WEIGHING_PERFORMANCE:NOT_IMPLEMENTED" in blockers
    assert any("REG-16" in b for b in blockers)
    assert any("TODO_REGULATORY_VALIDATION" in b for b in blockers)


def test_decimal_normalization_without_rounding():
    a = Parameter(name="EXAMPLE", numeric=True, value="1.00000000000000000000001")
    assert a.value == "1.00000000000000000000001"
    assert Parameter(name="EXAMPLE", numeric=True, value="1.00").value == "1"
    assert Parameter(name="EXAMPLE", numeric=True, value="-0").value == "0"
    with pytest.raises(ValueError):
        Parameter(name="EXAMPLE", numeric=True, value="NaN")


def test_yaml_duplicate_key_and_unknown_version(tmp_path):
    for source in ROOT.glob("*.yaml"):
        (tmp_path / source.name).write_text(source.read_text())
    metadata = tmp_path / "metadata.yaml"
    metadata.write_text("schema_version: 1\nschema_version: 1\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_ruleset(tmp_path)
    metadata.write_text(json.dumps({"schema_version": 2}))
    with pytest.raises(ValueError):
        load_ruleset(tmp_path)


def test_engine_package_has_no_framework_or_evaluator():
    for path in Path("app/compliance").rglob("*.py"):
        source = path.read_text()
        assert "import sqlalchemy" not in source
        assert "from fastapi" not in source
        assert "def evaluate(" not in source
