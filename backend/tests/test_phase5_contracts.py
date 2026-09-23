"""Offline contracts; these checks do not substitute for PostgreSQL acceptance."""

import ast
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.compliance.canonical import content_hash, normalize
from app.compliance.ruleset import RuleSet, load_ruleset
from app.db.base import Base
from app.models import testing
from app.schemas.testing import (
    Configure,
    Confirmation,
    EnvironmentData,
    ObservationData,
    SessionPatch,
)
from domain_tests.fixtures.weighing import fixture_observations
from tests.phase5_fixtures import full_fixture_rules

TABLES = {
    "test_sessions",
    "test_session_sections",
    "session_test_requirements",
    "test_runs",
    "test_observations",
    "environment_readings",
    "test_run_equipment",
    "test_run_results",
    "evaluation_result_events",
    "test_run_selection_events",
}


def test_exact_phase5_tables_and_frozen_constraint_shapes():
    assert {
        m.__tablename__
        for m in vars(testing).values()
        if isinstance(m, type)
        and getattr(m, "__module__", None) == testing.__name__
        and hasattr(m, "__tablename__")
    } == TABLES
    assert TABLES <= Base.metadata.tables.keys()
    assert "payload_json" in Base.metadata.tables["test_observations"].c
    assert {"section_code", "section_name"} <= set(
        Base.metadata.tables["test_session_sections"].c.keys()
    )
    table = Base.metadata.tables["test_run_results"]
    uniques = {
        tuple(c.columns.keys())
        for c in table.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    }
    assert ("test_run_id", "evaluation_version") in uniques
    assert ("test_run_id",) not in uniques
    for table, constraint in (
        ("test_runs", "fk_run_current_result"),
        ("session_test_requirements", "fk_requirement_selection"),
        ("test_sessions", "fk_session_root_scope"),
    ):
        actual = next(c for c in Base.metadata.tables[table].constraints if c.name == constraint)
        assert actual.deferrable and actual.initially == "DEFERRED"
    for field in ("temperature_c", "relative_humidity_percent", "barometric_pressure_hpa"):
        assert Base.metadata.tables["environment_readings"].c[field].type.scale is None


def test_migration_static_append_only_guards_and_no_later_phase():
    source = Path("alembic/versions/0004_phase5.py").read_text()
    assert 'down_revision = "0003_phase3"' in source
    assert "import app.models" not in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "phase5_ownership_guard" in source
    for table in TABLES:
        assert f"CREATE TABLE {table}" in source
        assert f'op.drop_table("{table}")' in source
    for later_table in (
        "construction_examinations",
        "construction_items",
        "checklist_responses",
        "approvals",
        "reports",
    ):
        assert f"CREATE TABLE {later_table}" not in source
    assert {
        "construction_examinations",
        "construction_items",
        "checklist_responses",
    } <= Base.metadata.tables.keys()
    assert not {"approvals", "reports"} & Base.metadata.tables.keys()


@pytest.mark.parametrize("value", [0.1, "NaN", "Infinity", True])
def test_environment_has_no_float_or_nonfinite_metrology(value):
    with pytest.raises(ValidationError):
        EnvironmentData(measured_at="2000-01-01T00:00:00Z", temperature_c=value)


def test_unknown_fields_and_workflow_injection_rejected():
    with pytest.raises(ValidationError):
        SessionPatch(workflow_status="APPROVED")
    with pytest.raises(ValidationError):
        Confirmation(elections={}, waive_regulatory_validation=True)
    row = fixture_observations().rows[0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        ObservationData(
            sequence_no=1,
            observation_type="WEIGHING_PERFORMANCE",
            payload_schema_version="v1",
            payload=row | {"injected_mpe": "1"},
        )
    with pytest.raises(ValidationError):
        Configure(instrument_snapshot={"id": str(uuid4())})


def test_synthetic_catalog_is_explicit_full_and_never_normal_seed():
    fixture = full_fixture_rules()
    assert len(fixture.tests) == 28
    assert {t.section for t in fixture.tests if t.parent is None} == set(range(1, 18))
    assert all(t.source.identity.startswith("SYNTHETIC") for t in fixture.tests)
    candidate = load_ruleset()
    assert all(not t.implemented for t in candidate.tests)
    assert candidate.activation_blockers()
    assert "SYNTHETIC" not in candidate.metadata.version
    assert (
        candidate.configuration_hash
        == RuleSet.model_validate(candidate.snapshot()).configuration_hash
    )


def test_routes_contain_no_sql_or_calculation_and_sources_no_test_imports():
    for path in (Path("app/api/v1/testing.py"),):
        parsed = ast.parse(path.read_text())
        modules = [n.module or "" for n in ast.walk(parsed) if isinstance(n, ast.ImportFrom)]
        assert not any(
            m.startswith(("sqlalchemy", "app.compliance", "app.repositories", "app.models"))
            for m in modules
        )
    for path in Path("app").rglob("*.py"):
        modules = [
            n.module or ""
            for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, ast.ImportFrom)
        ]
        assert not any(m.startswith(("tests", "domain_tests")) for m in modules)


def test_section1_fresh_process_import_and_evaluation_without_frameworks():
    source = r"""
import importlib.abc
import sys
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fastapi','starlette','sqlalchemy','asyncpg','boto3'}:
            raise AssertionError(fullname)
sys.meta_path.insert(0,Deny())
from domain_tests.fixtures.weighing import evaluate
import builtins, io, socket
def blocked(*args, **kwargs):
    raise AssertionError('I/O forbidden during evaluation')
builtins.open = io.open = socket.socket = blocked
result = evaluate()
assert result.synthetic_fixture and result.compliance_outcome == 'NONCOMPLIANT'
assert result.calculations[0].corrected_error_g == 20
print('PURE_SECTION1_IMPORT_AND_IO_BOUNDARY_OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PURE_SECTION1_IMPORT_AND_IO_BOUNDARY_OK" in result.stdout


def test_input_snapshot_still_has_exactly_eight_semantic_keys():
    from app.compliance.canonical import evaluation_input_snapshot
    from domain_tests.fixtures.synthetic import instrument
    from domain_tests.fixtures.weighing import fixture_context, fixture_engine, fixture_rules

    snapshot = evaluation_input_snapshot(
        test_code="WEIGHING_PERFORMANCE",
        instrument_snapshot=instrument(),
        procedure_context=fixture_context(),
        observations=fixture_observations(),
        ruleset_configuration_hash=fixture_rules().configuration_hash,
        engine_version=fixture_engine().engine_version,
    )
    assert set(normalize(snapshot)) == {
        "hash_schema_version",
        "instrument_snapshot",
        "test_code",
        "procedure_context",
        "observations",
        "ruleset_configuration_hash",
        "observation_schema_version",
        "engine_version",
    }
    assert content_hash(normalize(snapshot)) == snapshot.input_hash
