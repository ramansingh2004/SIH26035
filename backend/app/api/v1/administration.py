from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime

from app.api.dependencies import Actor, Admin, Match
from app.core.concurrency import etag
from app.schemas.identity import (
    AssignmentCreate,
    AssignmentView,
    LaboratoryCreate,
    LaboratoryPatch,
    LaboratoryView,
    Page,
    PasswordReset,
    UserCreate,
    UserPatch,
    UserView,
)

router = APIRouter(tags=["Administration"])


def versioned(response: Response, result: dict):
    response.headers["ETag"] = etag(result["lock_version"])
    return result


@router.get("/laboratories", response_model=Page[LaboratoryView])
async def labs(
    service: Admin,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.laboratories(actor, page, page_size)


@router.get("/laboratories/{lab_id}", response_model=LaboratoryView)
async def lab(lab_id: UUID, response: Response, service: Admin, actor: Actor):
    return versioned(response, await service.laboratory(actor, lab_id))


@router.post("/laboratories", status_code=201, response_model=LaboratoryView)
async def create_lab(data: LaboratoryCreate, response: Response, service: Admin, actor: Actor):
    return versioned(response, await service.create_lab(actor, data))


@router.patch("/laboratories/{lab_id}", response_model=LaboratoryView)
async def update_lab(
    lab_id: UUID,
    data: LaboratoryPatch,
    response: Response,
    service: Admin,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.update_lab(actor, lab_id, data, if_match))


@router.get("/users", response_model=Page[UserView])
async def users(
    service: Admin,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    role: str | None = Query(None, max_length=40),
    active: bool | None = None,
    search: str | None = Query(None, max_length=200),
):
    return await service.users(
        actor, page, page_size, laboratory_id=laboratory_id, role=role, active=active, search=search
    )


@router.post("/users", status_code=201, response_model=UserView)
async def create_user(data: UserCreate, response: Response, service: Admin, actor: Actor):
    return versioned(response, await service.create_user(actor, data))


@router.patch("/users/{user_id}", response_model=UserView)
async def update_user(
    user_id: UUID,
    data: UserPatch,
    response: Response,
    service: Admin,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.update_user(actor, user_id, data, if_match))


@router.post("/users/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: UUID, data: PasswordReset, service: Admin, actor: Actor, if_match: Match = None
):
    await service.reset_password(actor, user_id, data.new_password.get_secret_value(), if_match)


@router.get("/roles")
async def roles(
    service: Admin,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.roles(actor, page, page_size)


@router.get("/users/{user_id}/role-assignments", response_model=Page[AssignmentView])
async def assignments(
    user_id: UUID,
    service: Admin,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.assignments(actor, user_id, page, page_size)


@router.post("/users/{user_id}/role-assignments", status_code=201, response_model=AssignmentView)
async def grant(
    user_id: UUID,
    data: AssignmentCreate,
    response: Response,
    service: Admin,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.grant(actor, user_id, data, if_match))


@router.delete("/users/{user_id}/role-assignments/{assignment_id}", status_code=204)
async def revoke(
    user_id: UUID,
    assignment_id: UUID,
    service: Admin,
    actor: Actor,
    reason: str = Query(min_length=1, max_length=500),
    if_match: Match = None,
):
    await service.revoke_assignment(actor, user_id, assignment_id, if_match, reason)


@router.get("/audit-events")
async def audits(
    service: Admin,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    entity_type: str | None = Query(None, max_length=80),
    entity_id: UUID | None = None,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
):
    return await service.audits(
        actor,
        page,
        page_size,
        laboratory_id=laboratory_id,
        entity_type=entity_type,
        entity_id=entity_id,
        since=since,
        until=until,
    )
