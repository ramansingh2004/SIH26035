"""Pure Phase 16 report-context composition and integrity manifests."""

from importlib.metadata import PackageNotFoundError, version

from app.compliance.canonical import content_hash, normalize

CONTEXT_SCHEMA_VERSION = 1
TEMPLATE_VERSION = "r76-report-v1"


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
