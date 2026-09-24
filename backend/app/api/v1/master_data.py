"""HTTP parsing/serialization only; master services enforce policy."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import Actor, Instruments, Manufacturers, Match
from app.api.v1.administration import versioned
from app.core.concurrency import etag
from app.schemas.identity import Page
from app.schemas.master_data import (
    ArchiveRequest,
    ClassCode,
    ComponentData,
    ComponentPatch,
    ComponentView,
    ConfigurationRequest,
    InstrumentCreate,
    InstrumentPatch,
    InstrumentView,
    ManufacturerCreate,
    ManufacturerPatch,
    ManufacturerView,
    RangeData,
    RangePatch,
    RangeView,
)
from app.schemas.repository import InstrumentHistoryItem

router = APIRouter(tags=["Master data"])


@router.get("/manufacturers", response_model=Page[ManufacturerView])
async def manufacturers(
    service: Manufacturers,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    registration_no: str | None = Query(None, max_length=200),
    country: str | None = Query(None, max_length=200),
    is_active: bool | None = None,
    search: str | None = Query(None, max_length=200),
):
    return await service.listing(
        actor,
        page,
        page_size,
        laboratory_id=laboratory_id,
        registration_no=registration_no,
        country=country,
        is_active=is_active,
        search=search,
    )


@router.get("/instruments", response_model=Page[InstrumentView])
async def instruments(
    service: Instruments,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    manufacturer_id: UUID | None = None,
    accuracy_class: ClassCode | None = None,
    instrument_status: Literal["ACTIVE", "ARCHIVED"] | None = None,
    search: str | None = Query(None, max_length=200),
):
    return await service.listing(
        actor,
        page,
        page_size,
        laboratory_id=laboratory_id,
        manufacturer_id=manufacturer_id,
        accuracy_class=accuracy_class,
        instrument_status=instrument_status,
        search=search,
    )


@router.post("/instruments/validate-configuration")
async def configuration(data: ConfigurationRequest, service: Instruments, actor: Actor):
    return await service.configuration(actor, data)


@router.get("/manufacturers/{identifier}", response_model=ManufacturerView)
async def get_manufacturer(
    identifier: UUID, response: Response, service: Manufacturers, actor: Actor
):
    return versioned(response, await service.detail(actor, identifier))


@router.post("/manufacturers", status_code=201, response_model=ManufacturerView)
async def create_manufacturer(
    data: ManufacturerCreate, response: Response, service: Manufacturers, actor: Actor
):
    return versioned(response, await service.create(actor, data))


@router.patch("/manufacturers/{identifier}", response_model=ManufacturerView)
async def update_manufacturer(
    identifier: UUID,
    data: ManufacturerPatch,
    response: Response,
    service: Manufacturers,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.update(actor, identifier, data, if_match))


@router.post("/manufacturers/{identifier}/archive", response_model=ManufacturerView)
async def archive_manufacturer(
    identifier: UUID,
    data: ArchiveRequest,
    response: Response,
    service: Manufacturers,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.archive(actor, identifier, if_match, data.reason))


@router.get("/instruments/{identifier}", response_model=InstrumentView)
async def get_instrument(identifier: UUID, response: Response, service: Instruments, actor: Actor):
    return versioned(response, await service.detail(actor, identifier))


@router.post("/instruments", status_code=201, response_model=InstrumentView)
async def create_instrument(
    data: InstrumentCreate, response: Response, service: Instruments, actor: Actor
):
    return versioned(response, await service.create(actor, data))


@router.patch("/instruments/{identifier}", response_model=InstrumentView)
async def update_instrument(
    identifier: UUID,
    data: InstrumentPatch,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.update(actor, identifier, data, if_match))


@router.post("/instruments/{identifier}/archive", response_model=InstrumentView)
async def archive_instrument(
    identifier: UUID,
    data: ArchiveRequest,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.archive(actor, identifier, if_match, data.reason))


@router.get("/instruments/{identifier}/ranges", response_model=Page[RangeView])
async def list_ranges(
    identifier: UUID,
    response: Response,
    service: Instruments,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = False,
):
    result, parent_version = await service.list_children(
        actor, identifier, "ranges", page, page_size, include_archived
    )
    response.headers["ETag"] = etag(parent_version)
    return result


@router.post("/instruments/{identifier}/ranges", status_code=201, response_model=RangeView)
async def create_ranges(
    identifier: UUID,
    data: RangeData,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    result, parent_version = await service.mutate_child(
        actor, identifier, "ranges", if_match, data=data
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)
    return versioned(response, result)


@router.patch("/instruments/{identifier}/ranges/{child_id}", response_model=RangeView)
async def update_ranges(
    identifier: UUID,
    child_id: UUID,
    data: RangePatch,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    result, parent_version = await service.mutate_child(
        actor, identifier, "ranges", if_match, data=data, child_id=child_id
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)
    return versioned(response, result)


@router.delete("/instruments/{identifier}/ranges/{child_id}", status_code=204)
async def archive_ranges(
    identifier: UUID,
    child_id: UUID,
    response: Response,
    service: Instruments,
    actor: Actor,
    reason: str = Query(min_length=1, max_length=1000, pattern=r"\S"),
    if_match: Match = None,
):
    _, parent_version = await service.mutate_child(
        actor, identifier, "ranges", if_match, child_id=child_id, reason=reason
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)


@router.get("/instruments/{identifier}/components", response_model=Page[ComponentView])
async def list_components(
    identifier: UUID,
    response: Response,
    service: Instruments,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_archived: bool = False,
):
    result, parent_version = await service.list_children(
        actor, identifier, "components", page, page_size, include_archived
    )
    response.headers["ETag"] = etag(parent_version)
    return result


@router.post("/instruments/{identifier}/components", status_code=201, response_model=ComponentView)
async def create_components(
    identifier: UUID,
    data: ComponentData,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    result, parent_version = await service.mutate_child(
        actor, identifier, "components", if_match, data=data
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)
    return versioned(response, result)


@router.patch("/instruments/{identifier}/components/{child_id}", response_model=ComponentView)
async def update_components(
    identifier: UUID,
    child_id: UUID,
    data: ComponentPatch,
    response: Response,
    service: Instruments,
    actor: Actor,
    if_match: Match = None,
):
    result, parent_version = await service.mutate_child(
        actor, identifier, "components", if_match, data=data, child_id=child_id
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)
    return versioned(response, result)


@router.delete("/instruments/{identifier}/components/{child_id}", status_code=204)
async def archive_components(
    identifier: UUID,
    child_id: UUID,
    response: Response,
    service: Instruments,
    actor: Actor,
    reason: str = Query(min_length=1, max_length=1000, pattern=r"\S"),
    if_match: Match = None,
):
    _, parent_version = await service.mutate_child(
        actor, identifier, "components", if_match, child_id=child_id, reason=reason
    )
    response.headers["X-Instrument-ETag"] = etag(parent_version)


@router.get(
    "/instruments/{identifier}/history",
    response_model=Page[InstrumentHistoryItem],
)
async def history(
    identifier: UUID,
    service: Instruments,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await service.history(
        actor,
        identifier,
        page,
        page_size,
    )
