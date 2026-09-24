"""Phase 17 scoped dashboard API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import Actor, dashboard_service
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import DashboardService

router = APIRouter(tags=["Dashboard"])
Service = Annotated[DashboardService, Depends(dashboard_service)]


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummary,
)
async def dashboard_summary(
    service: Service,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
):
    return await service.summary(
        actor,
        page,
        page_size,
        laboratory_id,
    )
