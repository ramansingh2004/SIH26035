from pathlib import Path

from app.compliance.demo import (
    FULL_DEMO_EXECUTION_VERSION,
    is_demo_ruleset,
)
from app.compliance.full_demo_execution import (
    FULL_DEMO_EXECUTION_ARTIFACT,
    full_demo_execution_runtime_schema_map,
    is_full_demo_execution_ruleset,
)
from app.services.rulesets import (
    _runtime_schemas_for,
    _trusted_artifact,
    _trusted_snapshot,
    _validation_summary,
)

ROOT = Path(__file__).resolve().parents[2]


def test_stage3_v3_is_trusted_static_synthetic_artifact():
    ruleset, manifest = _trusted_artifact(FULL_DEMO_EXECUTION_ARTIFACT)

    assert manifest is None
    assert ruleset.metadata.version == FULL_DEMO_EXECUTION_VERSION
    assert is_demo_ruleset(ruleset)
    assert is_full_demo_execution_ruleset(ruleset)

    trusted, trusted_manifest = _trusted_snapshot(ruleset)
    assert trusted_manifest is None
    assert trusted.configuration_hash == ruleset.configuration_hash

    summary = _validation_summary(ruleset)
    assert summary["authoritative"] is False
    assert summary["synthetic_demo_only"] is True
    assert summary["blockers"] == ["SYNTHETIC_DEMO_ONLY"]


def test_stage3_registration_uses_generated_runtime_schema_map():
    ruleset, _ = _trusted_artifact(FULL_DEMO_EXECUTION_ARTIFACT)
    expected = full_demo_execution_runtime_schema_map()
    runtime = _runtime_schemas_for(ruleset, None)

    assert len(runtime) == 23
    assert set(runtime) == set(expected)
    for code in expected:
        assert runtime[code] == expected[code]


def test_stage3_runtime_loader_has_no_domain_test_dependency():
    source = (
        ROOT / "backend/app/compliance/full_demo_execution.py"
    ).read_text(encoding="utf-8")

    assert "domain_tests" not in source
    assert "phase26_full_demo_v3_ruleset.json" in source
    assert "phase26_full_demo_v3_data.json" in source
