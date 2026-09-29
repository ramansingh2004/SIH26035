from types import SimpleNamespace

from app.compliance.full_demo import (
    FULL_DEMO_RUN_ARTIFACT,
    FULL_DEMO_RUN_VERSION,
    full_demo_runtime_schema_map,
    is_full_demo_run_ruleset,
    load_full_demo_run_ruleset,
)
from app.services.rulesets import (
    _runtime_schemas_for,
    _trusted_artifact,
    _trusted_snapshot,
    _validation_summary,
)
from app.services.testing import TestingService


def test_stage2_run_ready_artifact_is_trusted_but_never_authoritative():
    ruleset, manifest = _trusted_artifact(FULL_DEMO_RUN_ARTIFACT)

    assert manifest is None
    assert ruleset.metadata.version == FULL_DEMO_RUN_VERSION
    assert is_full_demo_run_ruleset(ruleset)

    trusted, trusted_manifest = _trusted_snapshot(ruleset)
    assert trusted_manifest is None
    assert trusted.configuration_hash == ruleset.configuration_hash

    summary = _validation_summary(ruleset)
    assert summary["synthetic_demo_only"] is True
    assert summary["authoritative"] is False
    assert summary["blockers"] == ["SYNTHETIC_DEMO_ONLY"]


def test_stage2_ruleset_registration_uses_pinned_runtime_schemas():
    ruleset = load_full_demo_run_ruleset()
    runtime = _runtime_schemas_for(ruleset, None)
    expected = full_demo_runtime_schema_map()

    assert set(runtime) == set(expected)
    for code, binding in expected.items():
        assert runtime[code].procedure_schema_version == (
            binding.procedure_schema_version
        )
        assert runtime[code].observation_schema_version == (
            binding.observation_schema_version
        )


def test_stage2_testing_service_routes_v2_to_full_synthetic_registry():
    ruleset = load_full_demo_run_ruleset()
    service = object.__new__(TestingService)
    session = SimpleNamespace(ruleset_snapshot=ruleset.snapshot())

    engine = TestingService.engine_for(service, session)
    expected = set(full_demo_runtime_schema_map())

    assert {item.test_code for item in engine.registry.registrations} == expected
    assert all(item.synthetic_fixture for item in engine.registry.registrations)
