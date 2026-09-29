"""Phase 26 Stage 5 synthetic Section 17 checklist data.

This module describes software-demonstration inputs only. It does not create
regulatory evidence and is accepted only for the V3 full-demo artifact.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.compliance.full_demo_execution import is_full_demo_execution_ruleset
from app.compliance.ruleset import RuleSet

EXPECTED_GROUP_COUNTS = {
    "GENERAL": 10,
    "DIRECT_SALES": 6,
    "ELECTRONIC": 7,
    "SOFTWARE_CONTROLLED": 4,
}

NOTICE = (
    "SYNTHETIC SIH26035 SECTION 17 DEMO ONLY — metadata-only software "
    "fixture; not regulatory evidence and not an OIML checklist conclusion"
)


@dataclass(frozen=True)
class FullDemoChecklistItem:
    requirement_key: str
    group_code: str
    response_result: str
    remarks: str
    evidence_required: bool
    evidence_file_name: str
    evidence_content_type: str
    evidence_size: int
    evidence_sha256: str


def full_demo_checklist_plan(
    ruleset: RuleSet,
) -> tuple[FullDemoChecklistItem, ...]:
    if not is_full_demo_execution_ruleset(ruleset):
        raise ValueError(
            "Section 17 synthetic completion is restricted to the V3 "
            "full-demo execution artifact"
        )

    rows = []
    for item in ruleset.checklist:
        if item.verification.status != "VERIFIED":
            raise ValueError(
                f"{item.key}: synthetic checklist item is not verified"
            )
        applicability = item.applicability
        if isinstance(applicability, str):
            raise ValueError(
                f"{item.key}: Stage 5 expects explicit synthetic applicability"
            )
        if (
            applicability.when_match != "REQUIRED"
            or applicability.when_not_match != "REQUIRED"
        ):
            raise ValueError(
                f"{item.key}: Stage 5 expects REQUIRED synthetic applicability"
            )
        if item.evidence_required is not True:
            raise ValueError(
                f"{item.key}: Stage 5 expects evidence on every V3 checklist row"
            )

        payload = (
            f"{NOTICE}\n"
            f"requirement_key={item.key}\n"
            f"group={item.group}\n"
            "response=PASS\n"
        ).encode()
        rows.append(
            FullDemoChecklistItem(
                requirement_key=item.key,
                group_code=item.group,
                response_result="PASS",
                remarks=NOTICE,
                evidence_required=True,
                evidence_file_name=f"{item.key.lower()}.txt",
                evidence_content_type="text/plain",
                evidence_size=len(payload),
                evidence_sha256=hashlib.sha256(payload).hexdigest(),
            )
        )

    rows.sort(key=lambda item: (item.group_code, item.requirement_key))
    if len(rows) != 27:
        raise ValueError("Stage 5 requires exactly 27 Section 17 demo rows")
    if len({item.requirement_key for item in rows}) != 27:
        raise ValueError("Stage 5 checklist keys must be unique")

    counts = {
        group: sum(item.group_code == group for item in rows)
        for group in EXPECTED_GROUP_COUNTS
    }
    if counts != EXPECTED_GROUP_COUNTS:
        raise ValueError("Stage 5 checklist group coverage is incomplete")
    return tuple(rows)
