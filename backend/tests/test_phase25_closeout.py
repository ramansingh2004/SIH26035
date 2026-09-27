"""Phase 25 engineering closeout / external-review handoff tests."""

from pathlib import Path

from scripts.export_phase25_external_review import export_pack
from scripts.validate_phase25_external_review import validate_pack

REPO = Path(__file__).resolve().parents[2]


def test_closeout_export_is_candidate_only(tmp_path):
    output = tmp_path / "review-pack"
    result = export_pack(output)

    assert result["registers"] == 17
    assert result["sources"] == 5
    assert result["rules"] > 0
    assert result["tests"] > 0
    assert result["checklist"] == 27
    assert result["runtime_schemas"] > 0

    summary = (output / "00_summary.json").read_text(encoding="utf-8")
    assert "candidate-v1" in summary
    assert "not regulatory verification" in summary


def test_fresh_export_cannot_pass_as_completed_review(tmp_path):
    output = tmp_path / "review-pack"
    export_pack(output)

    result = validate_pack(output)

    assert result["valid"] is False
    assert result["blockers"]
    assert any("NOT_VERIFIED" in blocker for blocker in result["blockers"])


def test_closeout_does_not_mutate_verified_intake_directory(tmp_path):
    verified = (
        REPO
        / "backend"
        / "app"
        / "compliance"
        / "rules"
        / "oiml_r76_2006_verified"
    )
    before = {path.name for path in verified.iterdir()}

    export_pack(tmp_path / "review-pack")

    after = {path.name for path in verified.iterdir()}
    assert before == after


def test_closeout_docs_keep_external_boundary():
    text = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_ENGINEERING_CLOSEOUT.md"
    ).read_text(encoding="utf-8")

    assert "Phase 25 engineering: **COMPLETE**" in text
    assert "Independent regulatory verification: **PENDING**" in text
    assert "does **not**" in text


def test_remaining_work_register_forbids_automated_promotion():
    text = (
        REPO
        / "docs"
        / "regulatory"
        / "PHASE25_REMAINING_WORK.md"
    ).read_text(encoding="utf-8")

    assert "No automated tool may convert" in text
    assert "VERIFIED" in text
