"""Pure Phase 16 report-context composition and integrity manifests."""

from importlib.metadata import PackageNotFoundError, version

from app.compliance.canonical import content_hash, normalize

CONTEXT_SCHEMA_VERSION = 1
TEMPLATE_VERSION = "r76-report-v1"
FULL_DEMO_TEMPLATE_VERSION = "r76-full-demo-v1"


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def renderer_manifest() -> dict:
    return {
        "schema_version": 1,
        "pdf": {
            "renderer": "reportlab",
            "version": _package_version("reportlab"),
        },
        "docx": {
            "renderer": "python-docx",
            "version": _package_version("python-docx"),
        },
        "template_version": TEMPLATE_VERSION,
    }


def preview_context(
    regulatory_record: dict,
    *,
    requested_by: str,
    source_regulatory_revision: int,
) -> dict:
    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "document_kind": "UNOFFICIAL_PREVIEW",
        "document_control": {
            "report_number": None,
            "revision_no": None,
            "report_status": "UNOFFICIAL_PREVIEW",
            "planned_issue_date": None,
            "intended_issuer_id": None,
            "source_regulatory_revision": source_regulatory_revision,
            "requested_by": requested_by,
        },
        "template_version": TEMPLATE_VERSION,
        "renderer_manifest": renderer_manifest(),
        "regulatory_record": regulatory_record,
    }
    return normalize(context)


def simulated_approved_context(
    regulatory_record: dict,
    *,
    requested_by: str,
    source_regulatory_revision: int,
) -> dict:
    """Compose a permanently non-authoritative SIH demonstration report."""
    session = regulatory_record.get("session", {})
    actual_outcome = session.get("compliance_outcome")
    target_outcome = (
        actual_outcome if actual_outcome in {"COMPLIANT", "NONCOMPLIANT"} else "COMPLIANT"
    )
    session_id = str(session.get("id") or "DEMO")
    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "document_kind": "SIMULATED_APPROVED_REPORT",
        "document_control": {
            "report_number": f"SIM-DEMO-{session_id[:8].upper()}",
            "revision_no": 1,
            "report_status": "SIMULATED_APPROVED",
            "planned_issue_date": None,
            "intended_issuer_id": None,
            "source_regulatory_revision": source_regulatory_revision,
            "requested_by": requested_by,
        },
        "simulation": {
            "demo_only": True,
            "not_for_regulatory_use": True,
            "target_workflow_status": "APPROVED",
            "target_evaluation_status": "COMPLETE",
            "target_compliance_outcome": target_outcome,
            "actual_workflow_status": session.get("workflow_status"),
            "actual_evaluation_status": session.get("evaluation_status"),
            "actual_compliance_outcome": actual_outcome,
        },
        "template_version": TEMPLATE_VERSION,
        "renderer_manifest": renderer_manifest(),
        "regulatory_record": regulatory_record,
    }
    return normalize(context)


def full_demo_report_context(
    regulatory_record: dict,
    *,
    requested_by: str,
    source_regulatory_revision: int,
) -> dict:
    """Compose the complete, permanently non-official Stage 7 demo report."""
    session = regulatory_record.get("session", {})
    session_id = str(session.get("id") or "DEMO")
    record = dict(regulatory_record)
    ruleset = record.get("ruleset_record") or {}

    # Keep the human-readable demo report reproducible without dumping the
    # complete internal ruleset payload into the document.
    record["ruleset_snapshot"] = {
        "human_readable_demo_omission": True,
        "configuration_hash": ruleset.get("configuration_hash"),
        "source_reference": ruleset.get("source_reference"),
        "version": ruleset.get("version"),
    }

    manifest = renderer_manifest()
    manifest["template_version"] = FULL_DEMO_TEMPLATE_VERSION

    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "document_kind": "FULL_DEMO_REPORT",
        "document_control": {
            "report_number": f"SIM-DEMO-{session_id[:8].upper()}",
            "revision_no": 1,
            "report_status": "DEMONSTRATION_ONLY",
            "planned_issue_date": None,
            "intended_issuer_id": None,
            "source_regulatory_revision": source_regulatory_revision,
            "requested_by": requested_by,
        },
        "demonstration": {
            "demo_only": True,
            "not_for_regulatory_use": True,
            "not_an_official_oiml_certificate": True,
            "full_evidence_report": True,
            "actual_workflow_status": session.get("workflow_status"),
            "actual_evaluation_status": session.get("evaluation_status"),
            "actual_compliance_outcome": session.get("compliance_outcome"),
            "target_workflow_status": session.get("workflow_status"),
            "target_evaluation_status": session.get("evaluation_status"),
            "target_compliance_outcome": session.get("compliance_outcome"),
        },
        "template_version": FULL_DEMO_TEMPLATE_VERSION,
        "renderer_manifest": manifest,
        "regulatory_record": record,
    }
    return normalize(context)


def official_context(
    approved_snapshot: dict,
    *,
    report_number: str,
    revision_no: int,
    intended_issuer_id: str,
    planned_issue_date: str,
    source_regulatory_revision: int,
) -> dict:
    context = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "document_kind": "OFFICIAL_REPORT",
        "document_control": {
            "report_number": report_number,
            "revision_no": revision_no,
            "report_status": "UNISSUED",
            "planned_issue_date": planned_issue_date,
            "intended_issuer_id": intended_issuer_id,
            "source_regulatory_revision": source_regulatory_revision,
        },
        "template_version": TEMPLATE_VERSION,
        "renderer_manifest": renderer_manifest(),
        "regulatory_record": approved_snapshot,
    }
    return normalize(context)


def context_hash(context: dict) -> str:
    return content_hash(context)


def report_hash(context_digest: str, file_hashes: dict[str, str]) -> str:
    return content_hash(
        {
            "schema_version": 1,
            "context_hash": context_digest,
            "files": {key.upper(): file_hashes[key] for key in sorted(file_hashes)},
        }
    )


def issuance_manifest(
    *,
    report_id: str,
    report_number: str,
    revision_no: int,
    generation_id: str,
    context_digest: str,
    file_hashes: dict[str, str],
    final_report_hash: str,
    issued_by: str,
    issued_at: str,
    predecessor_id: str | None,
) -> dict:
    return normalize(
        {
            "schema_version": 1,
            "report_id": report_id,
            "report_number": report_number,
            "revision_no": revision_no,
            "generation_id": generation_id,
            "context_hash": context_digest,
            "file_hashes": {key.upper(): file_hashes[key] for key in sorted(file_hashes)},
            "report_hash": final_report_hash,
            "issued_by": issued_by,
            "issued_at": issued_at,
            "predecessor_id": predecessor_id,
        }
    )
