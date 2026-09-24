"""Phase 15 technical review and bounded correction HTTP surface."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from app.api.dependencies import (
    Actor,
    Match,
    no_body,
    review_service,
    testing_json,
)
from app.api.v1.administration import versioned
from app.schemas.review import (
    ApprovalActionView,
    CorrectionRequestView,
    CorrectionResolveRequest,
    FinalRejectRequest,
    ReturnForCorrectionRequest,
    TechnicalReviewRequest,
)
from app.schemas.testing import SessionView
from app.services.review import ReviewService

router = APIRouter(
    tags=["Review"],
    dependencies=[Depends(testing_json)],
)
Service = Annotated[ReviewService, Depends(review_service)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]


@router.post(
    "/test-sessions/{identifier}/submit-for-review",
    response_model=SessionView,
    dependencies=[Depends(no_body)],
)
async def submit_for_review(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.submit(actor, identifier, if_match),
    )


@router.get(
    "/test-sessions/{identifier}/reviews",
    response_model=list[ApprovalActionView],
)
async def review_history(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.history(actor, identifier)


@router.post(
    "/test-sessions/{identifier}/reviews",
    response_model=ApprovalActionView,
)
async def technical_review(
    identifier: UUID,
    data: TechnicalReviewRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return await service.technical_review(
        actor,
        identifier,
        if_match,
        data,
    )


@router.post(
    "/test-sessions/{identifier}/return-for-correction",
    response_model=CorrectionRequestView,
)
async def return_for_correction(
    identifier: UUID,
    data: ReturnForCorrectionRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return await service.return_for_correction(
        actor,
        identifier,
        if_match,
        data,
    )


@router.post(
    "/test-sessions/{identifier}/reopen",
    response_model=SessionView,
    dependencies=[Depends(no_body)],
)
async def reopen(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.reopen(actor, identifier, if_match),
    )


@router.get(
    "/test-sessions/{identifier}/corrections",
    response_model=list[CorrectionRequestView],
)
async def corrections(
    identifier: UUID,
    service: Service,
    actor: Actor,
):
    return await service.corrections(actor, identifier)


@router.post(
    "/test-sessions/{identifier}/corrections/{request_id}/resolve",
    response_model=CorrectionRequestView,
)
async def resolve_correction(
    identifier: UUID,
    request_id: UUID,
    data: CorrectionResolveRequest,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return await service.resolve_correction(
        actor,
        identifier,
        request_id,
        if_match,
        data,
    )


@router.post(
    "/test-sessions/{identifier}/approve",
    response_model=SessionView,
    dependencies=[Depends(no_body)],
)
async def final_approve(
    identifier: UUID,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    key: Key = None,
):
    return versioned(
        response,
        await service.approve(
            actor,
            identifier,
            if_match,
            key,
        ),
    )


@router.post(
    "/test-sessions/{identifier}/reject",
    response_model=SessionView,
)
async def final_reject(
    identifier: UUID,
    data: FinalRejectRequest,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.reject_final(
            actor,
            identifier,
            if_match,
            data,
        ),
    )
