"""Phase 16 report preview, official generation, repository and issue API."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
    Actor,
    Match,
    no_body,
    report_service,
)
from app.core.concurrency import etag
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
    response_model=list[ReportView],
)
async def get_report_revisions(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.revisions(actor, identifier)
