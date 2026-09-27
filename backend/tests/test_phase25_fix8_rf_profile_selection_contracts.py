"""Phase 25 Fix 8 structural contracts."""

from pathlib import Path

from app.compliance.domain import InstrumentSnapshot
from app.compliance.parameterized import PolicySelector
from app.compliance.phase10 import disturbance_registrations
from app.schemas.master_data import InstrumentMetadata

REPO = Path(__file__).resolve().parents[2]


def test_fix8_raw_fact_exists_in_metadata_and_immutable_snapshot():
    assert "conducted_rf_path_available" in InstrumentMetadata.model_fields
    assert "conducted_rf_path_available" in InstrumentSnapshot.model_fields
    assert "conducted_rf_path_available" in PolicySelector.model_fields


def test_fix8_requires_no_database_migration():
    versions = REPO / "backend" / "alembic" / "versions"
    assert not any("phase25_fix8" in item.name for item in versions.iterdir())


def test_fix8_section12_identity_is_bumped():
    assert {
        item.implementation_version for item in disturbance_registrations()
    } == {"section12-v3"}


def test_fix8_does_not_hardcode_r76_rf_frequency_branch_in_runtime():
    runtime = (
        REPO / "backend" / "app" / "compliance" / "phase10.py"
    ).read_text(encoding="utf-8")
    assert "26 mhz" not in runtime.lower()
    assert "80 mhz" not in runtime.lower()


def test_fix8_frontend_contract_exposes_raw_metadata_fact():
    source = (
        REPO / "frontend" / "src" / "lib" / "master-data" / "types.ts"
    ).read_text(encoding="utf-8")
    assert "conducted_rf_path_available?: boolean | null;" in source
