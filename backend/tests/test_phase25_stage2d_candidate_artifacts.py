"""Phase 25 Stage 2D controlled candidate-artifact contracts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.candidate_stage2d import (
    ACQUISITION_PENDING,
    CANDIDATE_STATUS,
    load_stage2d_candidate,
)
from app.compliance.ruleset import FILES

REPO = Path(__file__).resolve().parents[2]
REGULATORY = REPO / "docs" / "regulatory"
LEDGER = REGULATORY / "phase25_stage2d_candidate_ledger.csv"
VECTORS = REGULATORY / "phase25_stage2d_vectors.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stage2d_bundle_is_candidate_only_and_covers_reg01_through_reg08():
    bundle = load_stage2d_candidate()

    assert bundle.verification_status == CANDIDATE_STATUS
    assert bundle.activation_allowed is False
    assert bundle.independent_verifier == "PENDING"

    covered = {
        register_id
        for fact in bundle.facts
        for register_id in fact.register_ids
    }
    assert {f"REG-{number:02d}" for number in range(1, 9)} <= covered
    assert len(bundle.candidate_hash) == 64


def test_stage2d_sources_keep_controlled_acquisition_and_verifier_pending():
    bundle = load_stage2d_candidate()

    assert {source.source_id for source in bundle.sources} == {
        "SRC-R76-1-2006-E",
        "SRC-R76-2-2007-E",
    }
    assert all(source.digest is None for source in bundle.sources)
    assert all(
        source.acquisition_status == ACQUISITION_PENDING
        for source in bundle.sources
    )


def test_stage2d_mpe_candidate_preserves_table6_boundaries_without_activation():
    fact = load_stage2d_candidate().fact("MPE")
    profiles = fact.details["initial_verification_profiles"]

    assert profiles["III"] == [
        {
            "lower_e": "0",
            "lower_inclusive": True,
            "upper_e": "500",
            "upper_inclusive": True,
            "multiplier_e": "0.5",
        },
        {
            "lower_e": "500",
            "lower_inclusive": False,
            "upper_e": "2000",
            "upper_inclusive": True,
            "multiplier_e": "1",
        },
        {
            "lower_e": "2000",
            "lower_inclusive": False,
            "upper_e": "10000",
            "upper_inclusive": True,
            "multiplier_e": "1.5",
        },
    ]
    assert fact.details["in_service_multiplier_of_initial"] == "2"
    assert fact.runtime_projection.status == "SCHEMA_READY_PENDING_SIGNOFF"
    assert fact.activation_allowed is False


def test_stage2d_sections_one_to_five_capture_source_facts_and_schema_gaps():
    bundle = load_stage2d_candidate()

    weighing = bundle.fact("WEIGHING")
    assert weighing.details["minimum_distinct_loads_initial_intrinsic"] == 10
    assert weighing.details["minimum_distinct_loads_other_weighing_tests"] == 5
    assert weighing.runtime_projection.status == "PARTIAL_SCHEMA_GAP"

    temperature = bundle.fact("TEMPERATURE_ZERO")
    assert temperature.details["default_working_range_c"] == {
        "minimum": "-10",
        "maximum": "40",
    }
    assert temperature.details["normalization_span_c_by_class"]["I"] == "1"
    assert temperature.details["normalization_span_c_by_class"]["III"] == "5"

    eccentricity = bundle.fact("ECCENTRICITY")
    assert eccentricity.runtime_projection.status == "SCHEMA_GAP"
    assert any(
        item["case"] == "MORE_THAN_FOUR_SUPPORTS"
        and item["formula"]
        == "(Max + maximum additive tare effect) / (n - 1)"
        for item in eccentricity.details["load_rules"]
    )

    discrimination = bundle.fact("DISCRIMINATION")
    digital = next(
        item
        for item in discrimination.details["cases"]
        if item["mode"] == "DIGITAL"
    )
    assert digital["extra_load"] == "1.4 * d"

    sensitivity = bundle.fact("SENSITIVITY")
    assert sensitivity.runtime_projection.status == "SCHEMA_GAP"
    assert sensitivity.details["minimum_distinct_test_loads"] == 2

    repeatability = bundle.fact("REPEATABILITY")
    assert repeatability.details["verification"]["repetitions_by_class"] == {
        "I": 6,
        "II": 6,
        "III": 3,
        "IIII": 3,
    }


def test_stage2d_ledger_and_vectors_remain_explicitly_non_authoritative():
    ledger = read_csv(LEDGER)
    vectors = read_csv(VECTORS)

    assert len(ledger) == 9
    assert all(
        row["verification_status"] == CANDIDATE_STATUS
        for row in ledger
    )
    assert all(row["activation_allowed"] == "false" for row in ledger)

    assert len(vectors) >= 15
    assert all(
        row["verification_status"]
        == "DEVELOPER_TRANSCRIBED_PENDING_INDEPENDENT_SIGNOFF"
        for row in vectors
    )
    assert all(row["authoritative"] == "false" for row in vectors)


def test_stage2d_candidate_file_is_not_loaded_by_runtime_ruleset():
    assert "phase25_stage2d_candidate" not in FILES

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
    assert pending["parameters"][0]["value"] is None
    assert any(
        "TODO_REGULATORY_VALIDATION" in blocker
        for blocker in pending["blockers"]
    )
