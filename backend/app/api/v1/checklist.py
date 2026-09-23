"""Phase 13 checklist HTTP surface."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import Actor, Match, checklist_service, no_body, testing_json
from app.api.v1.administration import versioned
from app.schemas.checklist import (
    ChecklistResponsePatch,
    ChecklistRowView,
    ChecklistSummary,
)
from app.services.checklist import ChecklistService

router = APIRouter(
    tags=["Checklist"],
    dependencies=[Depends(testing_json)],
)
Service = Annotated[ChecklistService, Depends(checklist_service)]


@router.get(
    "/test-sessions/{identifier}/checklist",
    response_model=list[ChecklistRowView],
)
async def checklist(
    identifier: UUID,
    service: Service,
    actor: Actor,
    group: Literal[
        "GENERAL",
        "DIRECT_SALES",
        "ELECTRONIC",
        "SOFTWARE_CONTROLLED",
    ]
    | None = Query(None),
    response_result: Literal[
        "PASS",
        "FAIL",
        "NOT_APPLICABLE",
        "NOT_EXAMINED",
    ]
    | None = Query(None),
):
    return await service.rows(
        actor,
        identifier,
        group=group,
        response_result=response_result,
    )


@router.get(
    "/test-sessions/{identifier}/checklist/summary",
    response_model=ChecklistSummary,
)
async def checklist_summary(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
):
    return versioned(
        response,
        await service.summary(actor, identifier),
    )


@router.patch(
    "/test-sessions/{identifier}/checklist/{rule_id}",
    response_model=ChecklistRowView,
)
async def update_checklist(
    identifier: UUID,
    rule_id: UUID,
    data: ChecklistResponsePatch,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.patch(
            actor,
            identifier,
            rule_id,
            if_match,
            data,
        ),
    )


@router.post(
    "/test-sessions/{identifier}/checklist/complete",
    response_model=ChecklistSummary,
    dependencies=[Depends(no_body)],
)
async def complete_checklist(
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
