"""Thin Phase 3 HTTP adapters."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import (
    Actor,
    Match,
    attachment_service,
    equipment_service,
    ruleset_service,
)
from app.api.v1.administration import versioned
from app.schemas.foundations import (
    CompleteRequest,
    EquipmentCreate,
    EquipmentPatch,
    EquipmentView,
    EvidenceTarget,
    RuleRegistration,
    UploadRequest,
)
from app.schemas.identity import Page
from app.schemas.master_data import ArchiveRequest
from app.services.attachments import AttachmentService
from app.services.equipment import EquipmentService
from app.services.rulesets import RulesetService

Equipment = Annotated[EquipmentService, Depends(equipment_service)]
Rulesets = Annotated[RulesetService, Depends(ruleset_service)]
Attachments = Annotated[AttachmentService, Depends(attachment_service)]
router = APIRouter(tags=["Phase 3 foundations"])


@router.get("/test-equipment", response_model=Page[EquipmentView])
async def equipment_list(
    service: Equipment,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    is_active: bool | None = None,
):
    return await service.listing(actor, page, page_size, laboratory_id, is_active)


@router.post("/test-equipment", status_code=201, response_model=EquipmentView)
async def equipment_create(
    data: EquipmentCreate, service: Equipment, actor: Actor, response: Response
):
    return versioned(response, await service.create(actor, data))


@router.get("/test-equipment/{identifier}", response_model=EquipmentView)
async def equipment_detail(identifier: UUID, service: Equipment, actor: Actor, response: Response):
    return versioned(response, await service.detail(actor, identifier))


@router.patch("/test-equipment/{identifier}", response_model=EquipmentView)
async def equipment_update(
    identifier: UUID,
    data: EquipmentPatch,
    service: Equipment,
    actor: Actor,
    response: Response,
    if_match: Match = None,
):
    return versioned(response, await service.mutate(actor, identifier, if_match, data=data))


@router.post("/test-equipment/{identifier}/archive", response_model=EquipmentView)
async def equipment_archive(
    identifier: UUID,
    data: ArchiveRequest,
    service: Equipment,
    actor: Actor,
    response: Response,
    if_match: Match = None,
):
    return versioned(
        response, await service.mutate(actor, identifier, if_match, reason=data.reason)
    )


@router.get("/rulesets")
async def rulesets_list(
    service: Rulesets,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.listing(actor, page, page_size)


@router.post("/rulesets", status_code=201)
async def rulesets_register(
    data: RuleRegistration, service: Rulesets, actor: Actor, response: Response
):
    return versioned(response, await service.register(actor, data.artifact))


@router.get("/rulesets/{identifier}")
async def rulesets_detail(identifier: UUID, service: Rulesets, actor: Actor, response: Response):
    return versioned(response, await service.detail(actor, identifier))


@router.get("/rulesets/{identifier}/tests")
async def rulesets_tests(identifier: UUID, service: Rulesets, actor: Actor):
    return await service.detail(actor, identifier, "tests")


@router.get("/rulesets/{identifier}/checklist")
async def rulesets_checklist(identifier: UUID, service: Rulesets, actor: Actor):
    return await service.detail(actor, identifier, "checklist")


@router.post("/rulesets/{identifier}/validate")
async def rulesets_validate(
    identifier: UUID, service: Rulesets, actor: Actor, response: Response, if_match: Match = None
):
    return versioned(response, await service.action(actor, identifier, "validate", if_match))


@router.post("/rulesets/{identifier}/activate")
async def rulesets_activate(
    identifier: UUID, service: Rulesets, actor: Actor, response: Response, if_match: Match = None
):
    return versioned(response, await service.action(actor, identifier, "activate", if_match))


@router.post("/rulesets/{identifier}/retire")
async def rulesets_retire(
    identifier: UUID, service: Rulesets, actor: Actor, response: Response, if_match: Match = None
):
    return versioned(response, await service.action(actor, identifier, "retire", if_match))


@router.post("/attachments/presign", status_code=201)
async def attachments_presign(
    data: UploadRequest, service: Attachments, actor: Actor, if_match: Match = None
):
    return await service.presign(actor, data, if_match)


@router.post("/attachments/complete", status_code=201)
async def attachments_complete(
    data: CompleteRequest,
    service: Attachments,
    actor: Actor,
    response: Response,
    if_match: Match = None,
):
    return versioned(response, await service.complete(actor, data.upload_id, if_match))


@router.post("/attachments/{identifier}/link", status_code=201)
async def attachments_link(
    identifier: UUID,
    data: EvidenceTarget,
    service: Attachments,
    actor: Actor,
    response: Response,
    if_match: Match = None,
):
    return versioned(response, await service.link(actor, identifier, data, if_match))


@router.delete("/attachments/{identifier}/links/{link_id}")
async def attachments_unlink(
    identifier: UUID,
    link_id: UUID,
    service: Attachments,
    actor: Actor,
    reason: str = Query(min_length=1, max_length=1000, pattern=r"\S"),
    if_match: Match = None,
):
    return await service.unlink(actor, identifier, link_id, if_match, reason)


@router.delete("/attachments/{identifier}", status_code=204)
async def attachments_archive(
    identifier: UUID,
    service: Attachments,
    actor: Actor,
    reason: str = Query(min_length=1, max_length=1000, pattern=r"\S"),
    if_match: Match = None,
):
    await service.archive(actor, identifier, if_match, reason)


@router.get("/attachments/{identifier}/download")
async def attachments_download(
    identifier: UUID, service: Attachments, actor: Actor, response: Response
):
    return versioned(response, await service.download(actor, identifier))
