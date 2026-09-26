from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REG = REPO / "docs" / "regulatory"
GAPS = REG / "phase25_stage2_engine_gap_matrix.csv"
EXTRACT = REG / "phase25_stage2_source_extraction.csv"
TRANSCRIPT = REG / "PHASE25_STAGE2_SOURCE_TRANSCRIPT.md"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stage2a_covers_common_and_sections_1_to_5_rule_families():
    values = {row["area"] for row in rows(GAPS)}
    assert values == {
        "COMMON_CLASSIFICATION",
        "COMMON_MPE",
        "WEIGHING_PERFORMANCE",
        "TEMPERATURE_ZERO",
        "ECCENTRICITY",
        "DISCRIMINATION",
        "SENSITIVITY",
        "REPEATABILITY",
    }


def test_stage2a_all_engine_gaps_block_authoritative_encoding():
    assert all(row["stage2c_status"] == "BLOCKS_STAGE2C" for row in rows(GAPS))


def test_stage2a_source_extraction_requires_independent_signoff():
    extracted = rows(EXTRACT)
    assert extracted
    assert all(
        row["verification_status"] == "SOURCE_MAPPED_PENDING_INDEPENDENT_SIGNOFF"
        for row in extracted
    )


def test_stage2a_source_transcript_pins_exact_oiml_editions():
    text = TRANSCRIPT.read_text(encoding="utf-8")
    assert "OIML R 76-1:2006" in text
    assert "OIML R 76-2:2007" in text
    assert "Table 6" in text
    assert "A.4.4" in text
    assert "A.5.3.2" in text
    assert "A.4.7" in text
    assert "A.4.8" in text
    assert "A.4.9" in text
    assert "A.4.10" in text


def test_stage2a_does_not_promote_candidate_ruleset():
    root = REPO / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    metadata = json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))
    mpe = json.loads((root / "mpe.yaml").read_text(encoding="utf-8"))

    assert metadata["version"] == "candidate-v1"
    assert metadata["supported_test_codes"] == []
    assert mpe["rules"][0]["key"] == "MPE_PENDING"
    assert mpe["rules"][0]["verification"]["status"] == "TODO_REGULATORY_VALIDATION" \
        if "verification" in mpe["rules"][0] else True
    assert mpe["rules"][0]["parameters"][0]["value"] is None


def test_stage2a_does_not_modify_runtime_rule_files_by_contract():
    # Stage 2A is documentation/contracts only. The runtime candidate must still
    # contain unresolved placeholder configuration.
    root = REPO / "backend" / "app" / "compliance" / "rules" / "oiml_r76_2006"
    files = [
        "metadata.yaml",
        "classes.yaml",
        "mpe.yaml",
        "applicability.yaml",
        "voltage.yaml",
        "disturbances.yaml",
        "endurance.yaml",
        "checklist.yaml",
        "report_sections.yaml",
    ]
    for name in files:
        assert (root / name).exists()
    assert json.loads((root / "metadata.yaml").read_text(encoding="utf-8"))[
        "version"
    ] == "candidate-v1"
