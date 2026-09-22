"""Phase 5 HTTP parsing and serialization only; services own all policy."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import Actor, Match, no_body, testing_json, testing_service
from app.api.v1.administration import versioned
from app.schemas.identity import Page
from app.schemas.testing import (
    ApplicabilityView,
    Configure,
    Confirmation,
    Dashboard,
    EnvironmentData,
    EnvironmentView,
    EquipmentCertificate,
    EquipmentLink,
    EquipmentLinkView,
    ObservationData,
    ObservationView,
    ProcedureUpdate,
    ReasonRequest,
    RequirementView,
    ResultView,
    RunHistory,
    RunView,
    SectionView,
    SelectRun,
    SessionCreate,
    SessionPatch,
    SessionView,
)
from app.services.testing import TestingService

router = APIRouter(tags=["Testing"], dependencies=[Depends(testing_json)])
Service = Annotated[TestingService, Depends(testing_service)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]


@router.get("/test-sessions", response_model=Page[SessionView])
async def sessions(
    service: Service,
    actor: Actor,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    laboratory_id: UUID | None = None,
    instrument_id: UUID | None = None,
    workflow_status: str | None = None,
    compliance_outcome: str | None = None,
    application_number: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    return await service.listing(
        actor,
        page,
        page_size,
        laboratory_id=laboratory_id,
        instrument_id=instrument_id,
        workflow_status=workflow_status,
        compliance_outcome=compliance_outcome,
        application_number=application_number,
        created_from=created_from,
        created_to=created_to,
    )


@router.post("/test-sessions", status_code=201, response_model=SessionView)
async def create_session(
    data: SessionCreate, response: Response, service: Service, actor: Actor, key: Key = None
):
    return versioned(response, await service.create(actor, data, key))


@router.get("/test-sessions/{identifier}", response_model=SessionView)
async def get_session(identifier: UUID, response: Response, service: Service, actor: Actor):
    return versioned(response, await service.detail(actor, identifier))


@router.patch("/test-sessions/{identifier}", response_model=SessionView)
async def patch_session(
    identifier: UUID,
    data: SessionPatch,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.mutate_session(actor, identifier, if_match, "patch", data)
    )


@router.post("/test-sessions/{identifier}/applicability", response_model=ApplicabilityView)
async def applicability(identifier: UUID, service: Service, actor: Actor):
    return await service.applicability(actor, identifier)


@router.post("/test-sessions/{identifier}/confirm-applicability", response_model=SessionView)
async def confirm(
    identifier: UUID,
    data: Confirmation,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.confirm(actor, identifier, if_match, data))


@router.post("/test-sessions/{identifier}/revisions", response_model=SessionView, status_code=201)
async def revision(
    identifier: UUID,
    data: ReasonRequest,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    key: Key = None,
):
    return versioned(response, await service.revision(actor, identifier, if_match, key, data))


@router.get("/test-sessions/{identifier}/sections/{section_number}", response_model=SectionView)
async def section(
    identifier: UUID, section_number: int, response: Response, service: Service, actor: Actor
):
    return versioned(response, await service.section(actor, identifier, section_number))


@router.get("/test-runs/{identifier}", response_model=RunView)
async def get_run(identifier: UUID, response: Response, service: Service, actor: Actor):
    return versioned(response, await service.run_detail(actor, identifier))


@router.post(
    "/test-runs/{identifier}/evaluate", response_model=ResultView, dependencies=[Depends(no_body)]
)
async def evaluate(
    identifier: UUID, service: Service, actor: Actor, if_match: Match = None, key: Key = None
):
    return await service.evaluate(actor, identifier, if_match, key)


@router.post("/test-runs/{identifier}/retests", response_model=RunView, status_code=201)
async def retest(
    identifier: UUID,
    data: ReasonRequest,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
    key: Key = None,
):
    return versioned(response, await service.retest(actor, identifier, if_match, key, data))


@router.post("/test-requirements/{identifier}/select-run", response_model=RequirementView)
async def select_run(
    identifier: UUID,
    data: SelectRun,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(response, await service.select_run(actor, identifier, if_match, data))


@router.get("/test-runs/{identifier}/results/{result_id}", response_model=ResultView)
async def result(identifier: UUID, result_id: UUID, service: Service, actor: Actor):
    return await service.result_detail(actor, identifier, result_id)


@router.get("/test-runs/{identifier}/history", response_model=RunHistory)
async def history(identifier: UUID, service: Service, actor: Actor):
    return await service.history(actor, identifier)


@router.post(
    "/test-runs/{identifier}/equipment/{equipment_id}",
    response_model=EquipmentLinkView,
    status_code=201,
)
async def link_equipment(
    identifier: UUID,
    equipment_id: UUID,
    data: EquipmentCertificate,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.equipment(
            actor,
            identifier,
            if_match,
            EquipmentLink(
                equipment_id=equipment_id,
                calibration_attachment_id=data.calibration_attachment_id,
            ),
        ),
    )


@router.delete("/test-runs/{identifier}/equipment/{equipment_id}", status_code=204)
async def unlink_equipment(
    identifier: UUID, equipment_id: UUID, service: Service, actor: Actor, if_match: Match = None
):
    await service.equipment(actor, identifier, if_match, equipment_id=equipment_id)


@router.post("/test-sessions/{identifier}/configure", response_model=SessionView)
async def session_configure(
    identifier: UUID,
    data: Configure,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.mutate_session(actor, identifier, if_match, "configure", data)
    )


@router.post("/test-sessions/{identifier}/start-testing", response_model=SessionView)
async def session_start_testing(
    identifier: UUID, response: Response, service: Service, actor: Actor, if_match: Match = None
):
    return versioned(
        response, await service.mutate_session(actor, identifier, if_match, "start-testing")
    )


@router.post("/test-sessions/{identifier}/cancel", response_model=SessionView)
async def session_cancel(
    identifier: UUID,
    data: ReasonRequest,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.mutate_session(actor, identifier, if_match, "cancel", data)
    )


@router.get("/test-sessions/{identifier}/revisions", response_model=list[SessionView])
async def session_revisions(identifier: UUID, service: Service, actor: Actor):
    return await service.detail(actor, identifier, "revisions")


@router.get("/test-sessions/{identifier}/dashboard", response_model=Dashboard)
async def session_dashboard(identifier: UUID, service: Service, actor: Actor):
    return await service.detail(actor, identifier, "dashboard")


@router.get("/test-sessions/{identifier}/sections", response_model=list[SectionView])
async def session_sections(identifier: UUID, service: Service, actor: Actor):
    return await service.detail(actor, identifier, "sections")


@router.get("/test-sessions/{identifier}/requirements", response_model=list[RequirementView])
async def session_requirements(identifier: UUID, service: Service, actor: Actor):
    return await service.detail(actor, identifier, "requirements")


@router.post("/test-runs/{identifier}/start", response_model=RunView)
async def run_start(
    identifier: UUID, response: Response, service: Service, actor: Actor, if_match: Match = None
):
    return versioned(response, await service.mutate_run(actor, identifier, if_match, "start"))


@router.post("/test-runs/{identifier}/complete", response_model=RunView)
async def run_complete(
    identifier: UUID, response: Response, service: Service, actor: Actor, if_match: Match = None
):
    return versioned(response, await service.mutate_run(actor, identifier, if_match, "complete"))


@router.patch("/test-runs/{identifier}/procedure-context", response_model=RunView)
async def run_procedure_context(
    identifier: UUID,
    data: ProcedureUpdate,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.mutate_run(actor, identifier, if_match, "procedure-context", data)
    )


@router.get("/test-runs/{identifier}/observations", response_model=list[ObservationView])
async def run_observations(identifier: UUID, service: Service, actor: Actor):
    return await service.run_detail(actor, identifier, "observations")


@router.get("/test-runs/{identifier}/environment", response_model=list[EnvironmentView])
async def run_environment(identifier: UUID, service: Service, actor: Actor):
    return await service.run_detail(actor, identifier, "environment-readings")


@router.get("/test-runs/{identifier}/equipment", response_model=list[EquipmentLinkView])
async def run_equipment(identifier: UUID, service: Service, actor: Actor):
    return await service.run_detail(actor, identifier, "equipment")


@router.get("/test-runs/{identifier}/results", response_model=list[ResultView])
async def run_results(identifier: UUID, service: Service, actor: Actor):
    return await service.run_detail(actor, identifier, "results")


@router.post(
    "/test-runs/{identifier}/observations", response_model=ObservationView, status_code=201
)
async def create_observations(
    identifier: UUID,
    data: ObservationData,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.source(actor, identifier, if_match, "observations", data)
    )


@router.patch("/test-runs/{identifier}/observations/{source_id}", response_model=ObservationView)
async def update_observations(
    identifier: UUID,
    source_id: UUID,
    data: ObservationData,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.source(actor, identifier, if_match, "observations", data, source_id)
    )


@router.delete("/test-runs/{identifier}/observations/{source_id}", status_code=204)
async def delete_observations(
    identifier: UUID, source_id: UUID, service: Service, actor: Actor, if_match: Match = None
):
    await service.source(
        actor, identifier, if_match, "observations", identifier=source_id, delete=True
    )


@router.post("/test-runs/{identifier}/environment", response_model=EnvironmentView, status_code=201)
async def create_environment(
    identifier: UUID,
    data: EnvironmentData,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response, await service.source(actor, identifier, if_match, "environment-readings", data)
    )


@router.patch("/test-runs/{identifier}/environment/{source_id}", response_model=EnvironmentView)
async def update_environment(
    identifier: UUID,
    source_id: UUID,
    data: EnvironmentData,
    response: Response,
    service: Service,
    actor: Actor,
    if_match: Match = None,
):
    return versioned(
        response,
        await service.source(actor, identifier, if_match, "environment-readings", data, source_id),
    )


@router.delete("/test-runs/{identifier}/environment/{source_id}", status_code=204)
async def delete_environment(
    identifier: UUID, source_id: UUID, service: Service, actor: Actor, if_match: Match = None
):
    await service.source(
        actor, identifier, if_match, "environment-readings", identifier=source_id, delete=True
    )
