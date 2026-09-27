"""Phase 25 Stage 3A source-mapping contracts for Sections 6–10."""

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs" / "regulatory"
EXTRACTION = DOCS / "phase25_stage3a_source_extraction.csv"
GAPS = DOCS / "phase25_stage3a_engine_gap_matrix.csv"
TRANSCRIPT = DOCS / "PHASE25_STAGE3A_SOURCE_TRANSCRIPT.md"


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stage3a_source_extraction_covers_sections_6_to_10():
    rows = _rows(EXTRACTION)

    assert {row["section"] for row in rows} == {
        "6.1",
        "6.2",
        "7",
        "8",
        "9",
        "10",
    }
    assert {row["test_code"] for row in rows} == {
        "ZERO_RETURN",
        "CREEP",
        "STABILITY_EQUILIBRIUM",
        "TILTING",
        "TARE",
        "WARM_UP",
    }


def test_stage3a_register_ownership_matches_stage1_freeze():
    rows = _rows(EXTRACTION)
    by_code = {row["test_code"]: row["register_id"] for row in rows}

    assert by_code["ZERO_RETURN"] == "REG-09"
    assert by_code["CREEP"] == "REG-09"
    assert by_code["STABILITY_EQUILIBRIUM"] == "REG-10"
    assert by_code["TILTING"] == "REG-11"
    assert by_code["TARE"] == "REG-12"
    assert by_code["WARM_UP"] == "REG-12"


def test_stage3a_every_extraction_remains_unverified_and_nonactivatable():
    rows = _rows(EXTRACTION)

    assert all(
        row["verification_status"] == "SOURCE_MAPPED_NOT_VERIFIED"
        for row in rows
    )
    assert all(row["activation_allowed"] == "false" for row in rows)


def test_stage3a_gap_matrix_is_explicit_for_every_runtime_evaluator():
    rows = _rows(GAPS)
    by_code = {row["test_code"]: row for row in rows}

    assert set(by_code) == {
        "ZERO_RETURN",
        "CREEP",
        "STABILITY_EQUILIBRIUM",
        "TILTING",
        "TARE",
        "WARM_UP",
    }
    assert all(row["next_stage"] == "3B" for row in rows)
    assert all(row["gap_status"] for row in rows)


def test_stage3a_transcript_keeps_independent_verification_boundary_visible():
    text = TRANSCRIPT.read_text(encoding="utf-8")

    assert "not independent regulatory verification" in text
    assert "SOURCE_MAPPED_NOT_VERIFIED" in text
    assert "independent verification remains mandatory" in text


def test_stage3a_does_not_promote_candidate_runtime_ruleset():
    root = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006"
    )
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["parameters"][0]["value"] is None
