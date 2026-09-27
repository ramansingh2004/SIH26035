"""Phase 25 Stage 8 engineering and authoritative acceptance verifier."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.compliance.stage8_acceptance import (
    REQUIRED_HTTP_STEPS,
    RUN_RECORD_NAME,
    inspect_stage8_evidence,
    stage8_preflight,
)
from app.core.config import Settings
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
VERIFIED_ROOT = (
    BACKEND
    / "app"
    / "compliance"
    / "rules"
    / "oiml_r76_2006_verified"
)


def _route_blockers():
    schema = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url=None,
        )
    ).openapi()
    paths = schema["paths"]

    blockers = []
    for step in REQUIRED_HTTP_STEPS:
        operations = paths.get(step.path)
        if operations is None:
            blockers.append(f"STAGE8:ROUTE_MISSING:{step.method}:{step.path}")
            continue
        if step.method.lower() not in operations:
            blockers.append(f"STAGE8:METHOD_MISSING:{step.method}:{step.path}")
    return tuple(sorted(blockers))


def verify_stage8():
    preflight = stage8_preflight()
    evidence = inspect_stage8_evidence()
    route_blockers = _route_blockers()

    template_path = VERIFIED_ROOT / "stage8_authoritative_run.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    assert template["status"] == "PENDING_STAGE7_EXTERNAL_SIGNOFF"
    assert template["stage7_verified_artifact_ready"] is False
    assert template["ruleset_configuration_hash"] is None
    assert template["report_hash"] is None
    assert len(template["sections"]) == 17

    required_docs = (
        "PHASE25_STAGE8.md",
        "docs/regulatory/PHASE25_STAGE8_AUTHORITATIVE_RUNBOOK.md",
        "docs/regulatory/PHASE25_STAGE8_FINAL_ACCEPTANCE.md",
        "docs/regulatory/phase25_stage8_acceptance_matrix.csv",
        "docs/regulatory/phase25_stage8_external_acceptance_checklist.csv",
    )
    for relative in required_docs:
        assert (REPO / relative).is_file(), relative

    matrix_path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage8_acceptance_matrix.csv"
    )
    with matrix_path.open(encoding="utf-8", newline="") as handle:
        matrix = list(csv.DictReader(handle))
    assert len(matrix) == 13

    external_path = (
        REPO
        / "docs"
        / "regulatory"
        / "phase25_stage8_external_acceptance_checklist.csv"
    )
    with external_path.open(encoding="utf-8", newline="") as handle:
        external = list(csv.DictReader(handle))
    assert len(external) == 9

    assert not route_blockers

    if evidence.complete:
        authoritative_status = "COMPLETE"
        authoritative_gate = "ACCEPTED"
    elif preflight.authoritative_ready:
        authoritative_status = "READY_FOR_EXTERNAL_WALKTHROUGH"
        authoritative_gate = "READY"
    else:
        authoritative_status = "BLOCKED_STAGE7_EXTERNAL_SIGNOFF"
        authoritative_gate = "BLOCKED"

    return {
        "engineering_status": "COMPLETE",
        "authoritative_status": authoritative_status,
        "authoritative_gate": authoritative_gate,
        "stage7_authoritative_ready": preflight.authoritative_ready,
        "required_http_steps": len(REQUIRED_HTTP_STEPS),
        "route_blockers": route_blockers,
        "stage8_blockers": evidence.blockers,
        "candidate_hash": preflight.stage7_candidate_hash,
        "verified_hash": preflight.stage7_verified_hash,
        "manifest_hash": preflight.stage7_manifest_hash,
        "run_record_name": RUN_RECORD_NAME,
        "run_record_hash": evidence.record_hash,
        "external_acceptance_gates": len(external),
    }


def main():
    result = verify_stage8()

    print("Phase 25 Stage 8 engineering verification passed.")
    print(f"Engineering harness status: {result['engineering_status']}")
    print(f"Authoritative walkthrough status: {result['authoritative_status']}")
    print(f"Authoritative gate: {result['authoritative_gate']}")
    print(f"Stage 7 authoritative ready: {result['stage7_authoritative_ready']}")
    print(f"Required HTTP steps: {result['required_http_steps']}")
    print(f"Route blocker count: {len(result['route_blockers'])}")
    print(f"Acceptance blocker count: {len(result['stage8_blockers'])}")
    print(f"External acceptance gates: {result['external_acceptance_gates']}")
    print(f"Candidate configuration hash: {result['candidate_hash']}")
    if result["verified_hash"]:
        print(f"Verified configuration hash: {result['verified_hash']}")
    if result["manifest_hash"]:
        print(f"Stage 7 manifest hash: {result['manifest_hash']}")
    if result["run_record_hash"]:
        print(f"Stage 8 run record hash: {result['run_record_hash']}")


if __name__ == "__main__":
    main()
