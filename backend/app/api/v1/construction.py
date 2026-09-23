"""Phase 12 construction-examination HTTP surface."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import Actor, Match, construction_service, no_body, testing_json
from app.api.v1.administration import versioned
from app.schemas.construction import (
    ConstructionExaminationPatch,
    ConstructionExaminationView,
    ConstructionItemPatch,
    ConstructionItemView,
)
from app.schemas.testing import SessionView
from app.services.construction import ConstructionService

router = APIRouter(
    tags=["Construction"],
    dependencies=[Depends(testing_json)],
)
Service = Annotated[ConstructionService, Depends(construction_service)]


@router.post(
    "/test-sessions/{identifier}/start-examination",
    response_model=SessionView,
    dependencies=[Depends(no_body)],
)
async def start_examination(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.start_examination(actor, identifier, if_match),
    )


@router.get(
    "/test-sessions/{identifier}/construction",
    response_model=ConstructionExaminationView,
)
async def construction(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
):
    return versioned(
        response,
        await service.detail(actor, identifier),
    )


@router.get(
    "/test-sessions/{identifier}/construction/items",
    response_model=list[ConstructionItemView],
)
async def construction_items(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.detail(actor, identifier, items=True)


@router.patch(
    "/test-sessions/{identifier}/construction",
    response_model=ConstructionExaminationView,
)
async def update_construction(
    identifier: UUID,
    data: ConstructionExaminationPatch,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.patch_examination(
            actor,
            identifier,
            if_match,
            data,
        ),
    )


@router.patch(
    "/test-sessions/{identifier}/construction/items/{item_id}",
    response_model=ConstructionItemView,
)
async def update_construction_item(
    identifier: UUID,
    item_id: UUID,
    data: ConstructionItemPatch,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.patch_item(
            actor,
            identifier,
            item_id,
            if_match,
            data,
        ),
    )


@router.post(
    "/test-sessions/{identifier}/construction/complete",
    response_model=ConstructionExaminationView,
    dependencies=[Depends(no_body)],
)
async def complete_construction(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.complete(actor, identifier, if_match),
    )
