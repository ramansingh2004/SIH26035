"""Offline schema and HTTP boundaries; these do not substitute for Alembic check."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app


def test_phase3_tables_preserved_while_later_phases_extend_metadata():
    expected = {
        "rule_sets",
        "rule_definitions",
        "test_definitions",
        "checklist_rules",
        "test_equipment",
        "attachment_uploads",
        "attachments",
        "attachment_links",
    }
    assert expected <= Base.metadata.tables.keys()
    assert {
        "construction_examinations",
        "construction_items",
        "checklist_responses",
    } <= Base.metadata.tables.keys()
    assert not {"approvals", "reports"} & Base.metadata.tables.keys()
    assert "uq_ruleset_active" in {i.name for i in Base.metadata.tables["rule_sets"].indexes}
    assert "fk_test_parent_scope" in {
        c.name for c in Base.metadata.tables["test_definitions"].constraints
    }
    assert "fk_upload_attachment_lab" in {
        c.name for c in Base.metadata.tables["attachment_uploads"].constraints
    }
    assert "uq_attachment_link" in {
        c.name for c in Base.metadata.tables["attachment_links"].constraints
    }


def test_migration_is_static_and_downgrade_is_phase3_only():
    source = Path("alembic/versions/0003_phase3.py").read_text()
    assert 'down_revision = "0002_phase2"' in source
    assert "import app.models" not in source
    assert "phase3_attachment_guard" in source and "phase3_catalog_guard" in source
    assert 'op.drop_table("users")' not in source
    assert "DROP TABLE users" not in source


def test_development_docs_and_test_environment_visibility():
    with TestClient(
        create_app(Settings(_env_file=None, environment="development", database_url=None))
    ) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 200
    with TestClient(
        create_app(Settings(_env_file=None, environment="test", database_url=None))
    ) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
