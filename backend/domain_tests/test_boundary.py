import ast
import subprocess
import sys
from pathlib import Path


def test_static_import_boundary_all_compliance_modules():
    forbidden = (
        "fastapi",
        "starlette",
        "sqlalchemy",
        "asyncpg",
        "httpx",
        "requests",
        "boto3",
        "botocore",
        "minio",
        "app.api",
        "app.core",
        "app.db",
        "app.models",
        "app.repositories",
        "app.services",
        "app.storage",
        "app.schemas",
        "app.main",
    )
    for path in Path("app/compliance").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n == f or n.startswith(f + ".") for n in names for f in forbidden), path


def test_fresh_process_without_frameworks_network_or_io_during_evaluation():
    script = r"""
import importlib.abc
import sys
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = {'fastapi','starlette','sqlalchemy','asyncpg','httpx',
                     'requests','boto3','botocore','minio'}
        application = ('app.api','app.db','app.models','app.services','app.storage','app.main')
        if fullname.split('.')[0] in forbidden or fullname.startswith(application):
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, Deny())
from app.compliance.engine import R76Engine
from app.compliance.ruleset import load_ruleset
from app.compliance.planning import RequirementPlanner
from domain_tests.fixtures.synthetic import engine, instrument, context, observations, ruleset, CODE
candidate = load_ruleset()
fixture = ruleset()
domain_engine = engine()
args = dict(test_code=CODE, instrument_snapshot=instrument(),
            procedure_context=context(), observations=observations())
import builtins
import io
import socket
def forbidden(*args, **kwargs):
    raise AssertionError('I/O during evaluation')
builtins.open = io.open = socket.socket = forbidden
result = domain_engine.evaluate(**args, ruleset=fixture)
assert result.evaluation_status == 'COMPLETE' and result.synthetic_fixture
assert result.calculations[-1].value == 20
assert R76Engine().evaluate(**args, ruleset=candidate).issue_code == 'TODO_REGULATORY_VALIDATION'
plan = RequirementPlanner().plan(instrument_snapshot=args['instrument_snapshot'], ruleset=candidate)
assert len(plan.slots) == 28
assert not {'fastapi','sqlalchemy','starlette','asyncpg','boto3'} & set(sys.modules)
print('PURE_IMPORT_AND_EVALUATION_OK: frameworks blocked; evaluation file/network I/O blocked')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PURE_IMPORT_AND_EVALUATION_OK" in result.stdout


def test_no_phase5_tables_routes_or_production_evaluators_introduced():
    migrations = {p.stem for p in Path("alembic/versions").glob("*.py")}
    assert migrations == {"0001_phase1", "0002_phase2", "0003_phase3"}
    from app.compliance.evaluators import EvaluatorRegistry

    assert EvaluatorRegistry().registrations == ()
    for path in Path("app/api").rglob("*.py"):
        assert "R76Engine" not in path.read_text()
