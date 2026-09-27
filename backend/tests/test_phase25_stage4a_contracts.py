"""Phase 25 Stage 4A source-mapping and gap-analysis contracts."""

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs" / "regulatory"


def _rows(name):
    with (DOCS / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stage4a_source_extraction_covers_sections_11_to_15():
    rows = _rows("phase25_stage4a_source_extraction.csv")

    assert {row["section"].split(".", 1)[0] for row in rows} == {
        "11",
        "12",
        "13",
        "14",
        "15",
    }
    assert {
        row["evaluator_code"]
        for row in rows
        if row["section"].startswith("12.")
    } == {
        "DISTURBANCE_VOLTAGE_DIP",
        "DISTURBANCE_BURST",
        "DISTURBANCE_SURGE",
        "DISTURBANCE_ESD",
        "DISTURBANCE_RADIATED_RF",
        "DISTURBANCE_CONDUCTED_RF",
        "DISTURBANCE_VEHICLE_SUPPLY",
    }


def test_stage4a_only_maps_reg12_reg13_reg14_and_never_activates():
    rows = _rows("phase25_stage4a_source_extraction.csv")

    assert {row["register_id"] for row in rows} == {
        "REG-12",
        "REG-13",
        "REG-14",
    }
    assert all(
        row["verification_status"] == "SOURCE_MAPPED_NOT_VERIFIED"
        for row in rows
    )
    assert all(row["activation_allowed"] == "false" for row in rows)


def test_stage4a_gap_matrix_covers_five_top_level_sections_and_points_to_4b():
    rows = _rows("phase25_stage4a_engine_gap_matrix.csv")

    assert {row["section"] for row in rows} == {
        "11",
        "12",
        "13",
        "14",
        "15",
    }
    assert all(row["next_step"] == "4B" for row in rows)


def test_stage4a_verification_register_keeps_stage4_regulatory_gates_open():
    rows = _rows("phase25_verification_register.csv")
    by_id = {row["register_id"]: row for row in rows}

    assert "Stage 3 + Stage 4" in by_id["REG-12"]["target_stage"]
    assert by_id["REG-13"]["target_stage"] == "Stage 4"
    assert by_id["REG-14"]["target_stage"] == "Stage 4"
    assert by_id["REG-12"]["status"].startswith("OPEN")
    assert by_id["REG-13"]["status"].startswith("OPEN")
    assert by_id["REG-14"]["status"].startswith("OPEN")


def test_stage4a_transcript_preserves_independent_verification_boundary():
    text = (
        DOCS / "PHASE25_STAGE4A_SOURCE_TRANSCRIPT.md"
    ).read_text(encoding="utf-8")

    assert "source-mapped, not independently verified" in text
    assert "Controlled source acquisition" in text
    assert "Stage 4B" in text
    assert "does not change evaluator runtime behavior" in (
        REPO / "PHASE25_STAGE4.md"
    ).read_text(encoding="utf-8")


def test_stage4a_runtime_candidate_remains_unpromoted():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert not (root / "phase25_stage4_candidate.json").exists()
