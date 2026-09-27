"""Verify the Phase 25 engineering closeout handoff."""

from pathlib import Path

from app.compliance.ruleset import load_ruleset
from app.compliance.stage7_activation import inspect_verified_artifact
from app.compliance.stage8_acceptance import stage8_preflight

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def verify_closeout():
    candidate = load_ruleset()
    stage7 = inspect_verified_artifact()
    stage8 = stage8_preflight()

    required = (
        REPO / "docs" / "regulatory" / "PHASE25_ENGINEERING_CLOSEOUT.md",
        REPO / "docs" / "regulatory" / "PHASE25_REMAINING_WORK.md",
        BACKEND / "scripts" / "export_phase25_external_review.py",
        BACKEND / "scripts" / "validate_phase25_external_review.py",
        BACKEND / "tests" / "test_phase25_closeout.py",
    )
    for path in required:
        assert path.is_file(), path

    assert candidate.metadata.version == "candidate-v1"
    assert candidate.metadata.supported_test_codes == ()
    return {
        "engineering_status": "COMPLETE",
        "candidate_hash": candidate.configuration_hash,
        "independent_regulatory_verification": "PENDING",
        "verified_artifact_ready": stage7.ready,
        "stage8_authoritative_ready": stage8.authoritative_ready,
    }


def main():
    result = verify_closeout()
    print("Phase 25 engineering closeout verification passed.")
    print(f"Engineering status: {result['engineering_status']}")
    print(
        "Independent regulatory verification: "
        f"{result['independent_regulatory_verification']}"
    )
    print(f"Verified artifact ready: {result['verified_artifact_ready']}")
    print(f"Stage 8 authoritative ready: {result['stage8_authoritative_ready']}")
    print(f"Candidate configuration hash: {result['candidate_hash']}")


if __name__ == "__main__":
    main()
