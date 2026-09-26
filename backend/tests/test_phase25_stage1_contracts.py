from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.catalog import SECTIONS
from app.compliance.suite import IMPLEMENTED_TEST_CODES

REPO = Path(__file__).resolve().parents[2]
REGULATORY = REPO / "docs" / "regulatory"
MATRIX = REGULATORY / "phase25_clause_engine_matrix.csv"
REGISTER = REGULATORY / "phase25_verification_register.csv"
INVENTORY = REGULATORY / "PHASE25_STAGE1_SOURCE_INVENTORY.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluator_codes(rows: list[dict[str, str]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        values.update(
            code for code in row["evaluator_codes"].split(";") if code
        )
    return values


def test_phase25_stage1_maps_all_seventeen_sections_exactly_once():
    rows = read_csv(MATRIX)

    assert len(rows) == 17
    assert [int(row["section_number"]) for row in rows] == list(range(1, 18))
    assert tuple(row["top_level_code"] for row in rows) == SECTIONS


def test_phase25_stage1_maps_every_registered_deterministic_evaluator():
    rows = read_csv(MATRIX)
    mapped = evaluator_codes(rows)

    assert set(IMPLEMENTED_TEST_CODES) <= mapped


def test_phase25_stage1_keeps_every_matrix_row_non_authoritative():
    rows = read_csv(MATRIX)

    assert all(
        row["verification_status"] == "SOURCE_MAPPED_NOT_VERIFIED"
        for row in rows
    )
    assert all(row["activation_allowed"] == "false" for row in rows)


def test_phase25_stage1_preserves_all_regulatory_register_items_open():
    rows = read_csv(REGISTER)

    assert [row["register_id"] for row in rows] == [
        f"REG-{number:02d}" for number in range(1, 18)
    ]
    assert all(
        row["status"].startswith("OPEN")
        for row in rows
    )


def test_phase25_stage1_inventory_pins_official_editions_and_revision_isolation():
    text = INVENTORY.read_text(encoding="utf-8")

    assert "OIML R 76-1 Edition 2006 (E)" in text
    assert "OIML R 76-2 Edition 2007 (E)" in text
    assert "r076-1-e06.pdf" in text
    assert "r076-2-e07.pdf" in text
    assert "TC9/SC1/p1" in text
    assert "CHANGE WATCH ONLY" in text
    assert text.count("PENDING_CONTROLLED_ACQUISITION") >= 2


def test_phase25_stage1_does_not_promote_candidate_ruleset():
    metadata_path = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
        / "metadata.yaml"
    )
    mpe_path = metadata_path.with_name("mpe.yaml")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    mpe = json.loads(mpe_path.read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []

    pending = mpe["rules"][0]
    assert pending["key"] == "MPE_PENDING"
    assert "REG-01:TODO_REGULATORY_VALIDATION" in pending["blockers"]
    assert pending["parameters"][0]["value"] is None


def test_phase25_stage1_keeps_sections_16_17_clause_mapping_explicitly_pending():
    rows = {
        int(row["section_number"]): row
        for row in read_csv(MATRIX)
    }

    assert rows[16]["r76_1_test_refs"] == "CLAUSE_LEVEL_EXAMINATION_PENDING"
    assert rows[17]["r76_1_test_refs"] == "CLAUSE_LEVEL_CHECKLIST_PENDING"
