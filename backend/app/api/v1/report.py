"""Phase 16 report preview, official generation, repository and issue API."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
    Actor,
    Match,
    no_body,
    report_service,
)
from app.compliance.domain import (
    ComplianceOutcome,
    EvaluationStatus,
    WorkflowStatus,
)
from app.core.concurrency import etag
from app.schemas.identity import Page
from app.schemas.report import (
    ReportFileView,
    ReportGenerateRequest,
    ReportGenerationResponse,
    ReportGenerationView,
    ReportIssueRequest,
    ReportPreviewView,
    ReportRegenerateRequest,
    ReportRevisionRequest,
    ReportView,
)
from app.schemas.repository import ReportRepositoryItem
from app.services.report import ReportService

router = APIRouter(tags=["Reports"])
Service = Annotated[ReportService, Depends(report_service)]
IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key"),
]


@router.post(
    "/test-sessions/{identifier}/report-previews",
    response_model=ReportPreviewView,
    status_code=201,
    dependencies=[Depends(no_body)],
)
async def create_preview(
    identifier: UUID,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return await service.create_preview(
        actor,
        identifier,
        if_match,
    )


@router.get(
    "/report-previews/{identifier}",
    response_model=ReportPreviewView,
)
async def get_preview(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.preview_detail(actor, identifier)


@router.get("/report-previews/{identifier}/download")
async def download_preview(
    identifier: UUID,
    service: Service,
    actor: Actor,
    format: Literal["pdf", "docx"] = Query(...),
):
    return await service.preview_download(
        actor,
        identifier,
        format,
    )


@router.post(
    "/test-sessions/{identifier}/reports",
    response_model=ReportGenerationResponse,
    status_code=201,
)
async def generate_report(
    identifier: UUID,
    data: ReportGenerateRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    idempotency_key: IdempotencyKey = None,
):
    return await service.generate(
        actor,
        identifier,
        if_match,
        idempotency_key,
        data,
    )


@router.post(
    "/reports/{identifier}/regenerate",
    response_model=ReportGenerationResponse,
    status_code=201,
)
async def regenerate_report(
    identifier: UUID,
    data: ReportRegenerateRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    idempotency_key: IdempotencyKey = None,
):
    return await service.regenerate(
        actor,
        identifier,
        if_match,
        idempotency_key,
        data,
    )


@router.get(
    "/reports",
    response_model=Page[ReportRepositoryItem],
)
async def list_reports(
    service: Service,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    manufacturer_id: UUID | None = None,
    instrument_id: UUID | None = None,
    report_number: str | None = Query(None, max_length=80),
    workflow_status: WorkflowStatus | None = None,
    evaluation_status: EvaluationStatus | None = None,
    compliance_outcome: ComplianceOutcome | None = None,
    report_status: Literal["UNISSUED", "ISSUED", "SUPERSEDED"] | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    search: str | None = Query(None, max_length=200),
):
    return await service.listing(
        actor,
        page,
        page_size,
        laboratory_id=laboratory_id,
        manufacturer_id=manufacturer_id,
        instrument_id=instrument_id,
        report_number=report_number,
        workflow_status=workflow_status,
        evaluation_status=evaluation_status,
        compliance_outcome=compliance_outcome,
        report_status=report_status,
        created_from=created_from,
        created_to=created_to,
        search=search,
    )


@router.get(
    "/reports/{identifier}",
    response_model=ReportView,
)
async def get_report(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
):
    result = await service.detail(actor, identifier)
    response.headers["ETag"] = etag(result["lock_version"])
    return result


@router.get(
    "/reports/{identifier}/generations",
    response_model=list[ReportGenerationView],
)
async def get_report_generations(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.generations(actor, identifier)


@router.get(
    "/reports/{identifier}/files",
    response_model=list[ReportFileView],
)
async def get_report_files(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.files(actor, identifier)


@router.get("/reports/{identifier}/download")
async def download_report(
    identifier: UUID,
    service: Service,
    actor: Actor,
    format: Literal["pdf", "docx"] = Query(...),
):
    return await service.download(
        actor,
        identifier,
        format,
    )


@router.post(
    "/reports/{identifier}/issue",
    response_model=ReportView,
)
async def issue_report(
    identifier: UUID,
    data: ReportIssueRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    idempotency_key: IdempotencyKey = None,
):
    return await service.issue(
        actor,
        identifier,
        if_match,
        idempotency_key,
        data,
    )


@router.post(
    "/reports/{identifier}/revisions",
    response_model=ReportGenerationResponse,
    status_code=201,
)
async def create_report_revision(
    identifier: UUID,
    data: ReportRevisionRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    idempotency_key: IdempotencyKey = None,
):
    return await service.create_revision(
        actor,
        identifier,
        if_match,
        idempotency_key,
        data,
    )


@router.get(
    "/reports/{identifier}/revisions",
    response_model=Page[ReportView],
)
async def get_report_revisions(
    identifier: UUID,
    service: Service,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.revisions(
        actor,
        identifier,
        page,
        page_size,
    )
