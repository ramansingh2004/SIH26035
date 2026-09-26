"""Phase 5 transaction owner. Engine invocation is outside database transactions."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from app.compliance.aggregation import (
    AggregationChild,
    AggregationInput,
    SectionResultAggregator,
    SessionComplianceAggregator,
)
from app.compliance.canonical import canonical_bytes, evaluation_input_snapshot, normalize
from app.compliance.demo import DEMO_LAB_CODE, demo_registry, is_demo_ruleset
from app.compliance.domain import InstrumentSnapshot
from app.compliance.engine import R76Engine, synthetic_artifact
from app.compliance.planning import RequirementPlanner
from app.compliance.ruleset import RuleSet
from app.compliance.suite import implemented_registry
from app.compliance.weighing import CODE as WEIGHING_CODE
from app.compliance.weighing import WeighingContext
from app.core.concurrency import etag, require_match
from app.core.errors import AppError, denied, missing
from app.models import (
    Attachment,
    AttachmentLink,
    Instrument,
    RuleSetRecord,
    TestDefinitionRecord,
    TestEquipment,
)
from app.models.testing import (
    EnvironmentReading,
    EvaluationResultEvent,
    SessionTestRequirement,
    TestObservation,
    TestRun,
    TestRunEquipment,
    TestRunResult,
    TestRunSelectionEvent,
    TestSession,
    TestSessionSection,
)
from app.repositories.testing import TestingRepository
from app.schemas.foundations import EquipmentView
from app.schemas.testing import (
    EnvironmentView,
    EquipmentLinkView,
    ObservationView,
    RequirementView,
    ResultView,
    RunView,
    SectionView,
    SessionView,
)
from app.services.audit import AuditService
from app.services.authorization import AuthorizationService
from app.services.equipment import calibration_snapshot
from app.services.idempotency import IdempotencyService
from app.services.review_scope import (
    enforce_correction_scope,
    invalidate_technical_approvals,
)

EDITABLE = {"DRAFT", "INSTRUMENT_CONFIGURATION", "APPLICABILITY_CONFIRMED", "TESTING"}
VIEWS = {
    TestSession: SessionView,
    TestSessionSection: SectionView,
    SessionTestRequirement: RequirementView,
    TestRun: RunView,
    TestRunResult: ResultView,
    TestObservation: ObservationView,
    EnvironmentReading: EnvironmentView,
    TestRunEquipment: EquipmentLinkView,
}


def view(row):
    return VIEWS[type(row)].model_validate(row).model_dump(mode="json")


def reject(code, message, status=409, details=None):
    raise AppError(status, code, message, details or {})


class TestingService:
    def __init__(self, session, context):
        self.session = session
        self.repo = TestingRepository(session)
        self.authz = AuthorizationService(self.repo)
        self.audit = AuditService(self.repo, context)
        self.idempotency = IdempotencyService(session)
        self.engine = R76Engine(implemented_registry())

    def artifact_is_production(self, rules):
        """Production boundary; no HTTP/settings switch admits synthetic fixtures."""
        return not synthetic_artifact(rules)

    def require_production_output(self, synthetic):
        if synthetic:
            reject("SYNTHETIC_RESULT_FORBIDDEN", "Fixture results cannot be persisted or completed")

    def demo_ruleset(self, session):
        return is_demo_ruleset(RuleSet.model_validate(session.ruleset_snapshot))

    def engine_for(self, session):
        return R76Engine(demo_registry()) if self.demo_ruleset(session) else self.engine

    async def require_demo_scope(self, session):
        if not self.demo_ruleset(session):
            return False
        lab = await self.repo.lab(session.laboratory_id)
        if lab is None or lab.code != DEMO_LAB_CODE:
            reject(
                "SYNTHETIC_DEMO_SCOPE_FORBIDDEN",
                "Synthetic SIH demo data is restricted to the dedicated demo laboratory",
            )
        return True

    async def scoped(self, actor, identifier, permission, *, mutation=False):
        _, grants = await self.authz.current(actor, lock=mutation)
        labs = grants.labs_for(permission)
        if not labs:
            raise denied()
        row = await self.repo.get(TestSession, identifier)
        if row is None or row.laboratory_id not in labs:
            raise missing()
        if mutation:
            lab = await self.repo.lab(row.laboratory_id, lock=True)
            if not lab.is_active:
                reject("LABORATORY_INACTIVE", "Active laboratory required")
            row = await self.repo.get(TestSession, identifier, lock=True)
        return row

    async def scoped_run(self, actor, identifier, permission, *, mutation=False):
        # Resolve only parent identity before locking; no protected content is returned.
        run = await self.repo.get(TestRun, identifier)
        if run is None:
            raise missing()
        session = await self.scoped(actor, run.test_session_id, permission, mutation=mutation)
        if mutation:
            run = await self.repo.get(TestRun, identifier, lock=True)
        return session, run

    def editable(self, session, *, testing=False):
        if session.workflow_status not in ({"TESTING"} if testing else EDITABLE):
            reject("WORKFLOW_LOCKED", "Session does not permit this mutation")

    def source_editable(self, session, run):
        self.editable(session, testing=True)
        if run.completed_at:
            reject("TEST_ALREADY_LOCKED", "Completed runs require a retest")

    def event(self, actor, session, action, row, *, before=None, reason=None):
        self.audit.record(
            action,
            actor.user_id,
            row.__tablename__,
            row.id,
            lab=session.laboratory_id,
            before=before,
            after=view(row),
            target=getattr(row, "lock_version", None),
            reason=reason,
        )

    async def reserve(self, actor, lab, operation, key, payload, authorize):
        if not key:
            reject("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key required", 428)
        return await self.idempotency.reserve(
            actor.user_id, str(lab), operation, key, payload, authorize
        )

    async def finish(self, reservation, actor, lab, row, status=200):
        result = view(row)
        await self.idempotency.complete(
            reservation.id, actor.user_id, str(lab), status, result, {"id": str(row.id)}
        )
        return result

    async def instrument(self, actor, identifier):
        _, grants = await self.authz.current(actor, lock=True)
        labs = grants.labs_for("session:create")
        if not labs:
            raise denied()
        instrument = await self.repo.get(Instrument, identifier)
        if instrument is None or instrument.laboratory_id not in labs:
            raise missing()
        lab = await self.repo.lab(instrument.laboratory_id, lock=True)
        instrument = await self.repo.get(Instrument, identifier, lock=True)
        if not lab.is_active or instrument.instrument_status != "ACTIVE":
            reject("MASTER_INACTIVE", "Active laboratory and instrument required")
        return instrument

    async def instrument_snapshot(self, instrument):
        ranges, components = await self.repo.instrument_children(instrument.id)
        if not ranges:
            reject(
                "INSTRUMENT_RANGES_REQUIRED",
                "An explicit range is required even for single-range instruments",
                422,
            )
        data = {
            name: getattr(instrument, name)
            for name in InstrumentSnapshot.model_fields
            if hasattr(instrument, name)
        }
        data.update(instrument.metadata_json)
        data["ranges"] = [
            {
                name: getattr(row, name)
                for name in (
                    "range_no",
                    "min_capacity_g",
                    "max_capacity_g",
                    "scale_interval_d_g",
                    "verification_interval_e_g",
                )
            }
            for row in ranges
        ]
        # Components lack semantic designation in Phase 2. Use their declared
        # type/model/serial identity, never their storage UUID or record order.
        data["components"] = [
            dict(
                designation="|".join(filter(None, (r.component_type, r.model, r.serial_or_type))),
                component_type=r.component_type,
                manufacturer_name=r.manufacturer_name,
                model=r.model,
                serial_or_type=r.serial_or_type,
                certificate_reference=r.certificate_reference,
                notes=r.notes,
                **{k: v for k, v in r.technical_specifications.items() if k != "schema_version"},
            )
            for r in components
        ]
        try:
            return InstrumentSnapshot.model_validate(data)
        except ValueError as exc:
            reject("INVALID_INSTRUMENT_SNAPSHOT", str(exc), 422)

    async def initialize_sections(self, session):
        rules = RuleSet.model_validate(session.ruleset_snapshot)
        tops = [t for t in rules.tests if t.parent is None]
        if len(tops) != 17 or {t.section for t in tops} != set(range(1, 18)):
            reject("INCOMPLETE_CATALOG", "Pinned catalog must contain all 17 top-level sections")
        for test in tops:
            self.repo.add(
                TestSessionSection(
                    id=uuid4(),
                    test_session_id=session.id,
                    section_number=test.section,
                    code=test.code,
                    name=test.name,
                    applicability_status="REQUIRES_REVIEW",
                    applicability_reason="Applicability has not been confirmed",
                    rule_references=[],
                    summary_json={},
                )
            )
        await self.repo.flush()

    async def create(self, actor, data, key):
        async with self.session.begin():
            instrument = await self.instrument(actor, data.instrument_id)
            lab = instrument.laboratory_id

        async def authorize():
            await self.instrument(actor, data.instrument_id)

        reservation = await self.reserve(
            actor, lab, "session.create", key, data.model_dump(mode="json"), authorize
        )
        if reservation.replay:
            return reservation.response_body
        async with self.session.begin():
            instrument = await self.instrument(actor, data.instrument_id)
            artifact = await self.repo.get(RuleSetRecord, data.rule_set_id, lock=True)
            if artifact is None:
                raise missing()
            if artifact.ruleset_status == "RETIRED":
                reject("RULESET_RETIRED", "Retired ruleset cannot start a new session")
            rules = RuleSet.model_validate(artifact.configuration_snapshot)
            if rules.configuration_hash != artifact.configuration_hash:
                reject(
                    "RULESET_INVALID", "Only intact registered regulatory artifacts may be pinned"
                )
            if not self.artifact_is_production(rules):
                if not is_demo_ruleset(rules):
                    reject(
                        "RULESET_INVALID",
                        "Only intact registered regulatory artifacts may be pinned",
                    )
                demo_lab = await self.repo.lab(lab)
                if demo_lab is None or demo_lab.code != DEMO_LAB_CODE:
                    reject(
                        "SYNTHETIC_DEMO_SCOPE_FORBIDDEN",
                        "Synthetic SIH demo data is restricted to the dedicated demo laboratory",
                    )
            identifier = uuid4()
            row = TestSession(
                id=identifier,
                root_session_id=identifier,
                laboratory_id=lab,
                instrument_id=instrument.id,
                rule_set_id=artifact.id,
                application_number=data.application_number,
                evaluation_context=data.evaluation_context,
                notes=data.notes,
                started_by=actor.user_id,
                instrument_snapshot=normalize(await self.instrument_snapshot(instrument)),
                ruleset_snapshot=rules.snapshot(),
            )
            self.repo.add(row)
            await self.repo.flush()
            await self.initialize_sections(row)
            self.event(actor, row, "session.created", row)
            return await self.finish(reservation, actor, lab, row, 201)

    async def listing(self, actor, page, size, **filters):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = grants.labs_for("session:read")
            if not labs or filters.get("laboratory_id") and filters["laboratory_id"] not in labs:
                raise denied()
            rows, total = await self.repo.sessions(labs, page, size, filters)
            return dict(items=[view(r) for r in rows], total=total, page=page, page_size=size)

    async def revisions(self, actor, identifier, page, size):
        async with self.session.begin():
            row = await self.scoped(
                actor,
                identifier,
                "session:read",
            )
            rows, total = await self.repo.session_revisions(
                row.root_session_id,
                page,
                size,
            )
            return {
                "items": [view(item) for item in rows],
                "page": page,
                "page_size": size,
                "total": total,
            }

    async def detail(self, actor, identifier, part=None):
        async with self.session.begin():
            row = await self.scoped(actor, identifier, "session:read")
            if part == "sections":
                return [view(r) for r in await self.repo.sections(identifier)]
            if part == "requirements":
                return [view(r) for r in await self.repo.requirements(identifier)]
            if part == "revisions":
                return [
                    view(r)
                    for r in sorted(
                        await self.repo.rows(TestSession, root_session_id=row.root_session_id),
                        key=lambda r: r.session_revision_no,
                    )
                ]
            if part == "dashboard":
                return dict(
                    session=view(row),
                    sections=[view(r) for r in await self.repo.sections(identifier)],
                    requirements=[view(r) for r in await self.repo.requirements(identifier)],
                )
            return view(row)

    async def section(self, actor, identifier, number):
        rows = await self.detail(actor, identifier, "sections")
        for row in rows:
            if row["section_number"] == number:
                return row
        raise missing()

    async def mutate_session(self, actor, identifier, match, action, data=None):
        permission = {"cancel": "session:cancel", "start-testing": "test:execute"}.get(
            action, "session:update"
        )
        async with self.session.begin():
            row = await self.scoped(actor, identifier, permission, mutation=True)
            self.editable(row)
            require_match(match, etag(row.lock_version))
            before = view(row)
            if action == "configure":
                if row.workflow_status not in {"DRAFT", "INSTRUMENT_CONFIGURATION"}:
                    reject("WORKFLOW_LOCKED", "Configuration is already confirmed")
                row.instrument_snapshot = normalize(data.instrument_snapshot)
                row.workflow_status = "INSTRUMENT_CONFIGURATION"
                row.regulatory_revision += 1
            elif action == "start-testing":
                if row.workflow_status != "APPLICABILITY_CONFIRMED":
                    reject("INVALID_TRANSITION", "Confirm applicability first")
                row.workflow_status = "TESTING"
                row.started_at = datetime.now(UTC)
                row.regulatory_revision += 1
            elif action == "cancel":
                row.workflow_status = "CANCELLED"
                row.regulatory_revision += 1
            elif action == "patch":
                changes = data.model_dump(exclude_unset=True)
                await enforce_correction_scope(
                    self.repo,
                    row,
                    entity_type="test_sessions",
                    entity_id=row.id,
                    field_paths=tuple(changes),
                )
                for field, value in changes.items():
                    setattr(row, field, value)
            else:
                raise ValueError("Unknown lifecycle action")
            row.lock_version += 1
            await self.repo.flush()
            self.event(
                actor,
                row,
                "session." + action,
                row,
                before=before,
                reason=getattr(data, "reason", None),
            )
            return view(row)

    def plan(self, session, elections=()):
        return RequirementPlanner().plan(
            instrument_snapshot=InstrumentSnapshot.model_validate(session.instrument_snapshot),
            ruleset=RuleSet.model_validate(session.ruleset_snapshot),
            elected_slot_keys=tuple(elections),
        )

    async def applicability(self, actor, identifier):
        async with self.session.begin():
            row = await self.scoped(actor, identifier, "test:execute")
            plan = self.plan(row)
            artifact = await self.repo.get(RuleSetRecord, row.rule_set_id)
            demo_ready = (
                artifact.ruleset_status == "DRAFT"
                and await self.require_demo_scope(row)
            )
            production_ready = (
                artifact.ruleset_status == "ACTIVE"
                and self.artifact_is_production(
                    RuleSet.model_validate(row.ruleset_snapshot)
                )
            )
            return dict(
                session_id=row.id,
                regulatory_revision=row.regulatory_revision,
                plan=plan,
                confirmable=(demo_ready or production_ready)
                and plan.applicability_confirmable,
            )

    async def confirm(self, actor, identifier, match, data):
        async with self.session.begin():
            row = await self.scoped(actor, identifier, "test:execute", mutation=True)
            require_match(match, etag(row.lock_version))
            if row.workflow_status != "INSTRUMENT_CONFIGURATION":
                reject("INVALID_TRANSITION", "Configure the instrument before confirmation")
            artifact = await self.repo.get(RuleSetRecord, row.rule_set_id, lock=True)
            rules = RuleSet.model_validate(row.ruleset_snapshot)
            plan = self.plan(row)
            demo_ready = (
                artifact.ruleset_status == "DRAFT"
                and is_demo_ruleset(rules)
                and await self.require_demo_scope(row)
            )
            production_ready = (
                artifact.ruleset_status == "ACTIVE"
                and self.artifact_is_production(rules)
            )
            if (
                not (demo_ready or production_ready)
                or not plan.applicability_confirmable
            ):
                reject(
                    "TODO_REGULATORY_VALIDATION",
                    "Verified applicability and an ACTIVE ruleset required",
                    details={
                        "unresolved_rule_ids": sorted(
                            {r for slot in plan.slots for r in slot.decision.unresolved_rule_ids}
                        )
                    },
                )
            optional = {s.slot_key for s in plan.slots if s.decision.applicability == "OPTIONAL"}
            if set(data.elections) != optional:
                reject(
                    "OPTIONAL_ELECTIONS_REQUIRED",
                    "Supply an explicit election for every optional slot",
                    422,
                )
            plan = self.plan(row, [k for k, v in data.elections.items() if v])
            sections = {s.section_number: s for s in await self.repo.sections(row.id)}
            definitions = {
                t.code: t for t in await self.repo.catalog(TestDefinitionRecord, row.rule_set_id)
            }
            groups = {s.parent_test_code for s in plan.slots if s.parent_test_code}
            for slot in plan.slots:
                definition = definitions[slot.test_code]
                section = sections[slot.section_number]
                requirement = SessionTestRequirement(
                    id=uuid4(),
                    test_session_id=row.id,
                    session_section_id=section.id,
                    test_definition_id=definition.id,
                    requirement_key=slot.slot_key,
                    applicability_status=slot.decision.applicability,
                    applicability_reason=slot.decision.reason,
                    rule_references=normalize(slot.decision.rule_references),
                    slot_snapshot=normalize(slot),
                    is_elected=slot.elected,
                )
                self.repo.add(requirement)
                await self.repo.flush()
                if (
                    slot.required_for_completion
                    and slot.section_number <= 15
                    and slot.test_code not in groups
                ):
                    context = {}
                    if slot.test_code == WEIGHING_CODE:
                        if slot.range_no is None:
                            reject(
                                "INVALID_RANGE_PLAN",
                                "Section 1 requires an explicit selected range",
                                422,
                            )
                        context = normalize(
                            WeighingContext(
                                range_no=slot.range_no,
                                scenario=slot.scenario,
                                evaluation_context=row.evaluation_context,
                                stages=(),
                            )
                        )
                    registration = self.engine_for(row).registry.find(slot.test_code)
                    if registration is None:
                        observation_version = procedure_version = "UNIMPLEMENTED"
                    else:
                        contexts = [
                            item
                            for item in registration.contexts.registrations
                            if item.procedure_variant == slot.procedure_variant
                        ]
                        observation_versions = {
                            item.observation_schema_version
                            for item in registration.observations.registrations
                        }
                        if len(contexts) != 1 or len(observation_versions) != 1:
                            reject(
                                "EVALUATOR_SCHEMA_AMBIGUOUS",
                                "Implemented evaluator must resolve one schema version "
                                "for the slot",
                                500,
                            )
                        procedure_version = contexts[0].procedure_schema_version
                        observation_version = next(iter(observation_versions))
                    run = TestRun(
                        id=uuid4(),
                        test_session_id=row.id,
                        session_section_id=section.id,
                        requirement_id=requirement.id,
                        test_definition_id=definition.id,
                        run_no=1,
                        observation_schema_version=observation_version,
                        procedure_schema_version=procedure_version,
                        procedure_context=context,
                    )
                    self.repo.add(run)
                    await self.repo.flush()
                    requirement.selected_run_id = run.id
                    self.repo.add(
                        TestRunSelectionEvent(
                            requirement_id=requirement.id,
                            selected_run_id=run.id,
                            reason="Initial required/elected run",
                            regulatory_revision=row.regulatory_revision + 1,
                            actor_id=actor.user_id,
                        )
                    )
            row.workflow_status = "APPLICABILITY_CONFIRMED"
            row.lock_version += 1
            row.regulatory_revision += 1
            await self.repo.flush()
            await self.aggregate(row)
            self.event(actor, row, "session.applicability_confirmed", row)
            return view(row)

    async def aggregate(self, session):
        requirements = await self.repo.requirements(session.id)
        runs = {r.id: r for r in await self.repo.runs(session.id)}
        sections = await self.repo.sections(session.id)
        children = []
        groups = {
            r.slot_snapshot["parent_test_code"]
            for r in requirements
            if r.slot_snapshot["parent_test_code"]
        }
        for section in sections:
            items = []
            references = {}
            for req in requirements:
                if req.session_section_id != section.id or req.slot_snapshot["test_code"] in groups:
                    continue
                run = runs.get(req.selected_run_id)
                references.update({r["rule_id"]: r for r in req.rule_references})
                items.append(
                    AggregationChild(
                        semantic_key=req.requirement_key,
                        applicability=req.applicability_status,
                        elected=req.is_elected,
                        evaluation_status=run.evaluation_status if run else "NOT_STARTED",
                        compliance_outcome=run.compliance_outcome if run else "UNDETERMINED",
                    )
                )
            if not items:
                continue
            result = SectionResultAggregator.aggregate(AggregationInput(children=tuple(items)))
            section.evaluation_status, section.compliance_outcome = (
                result.evaluation_status,
                result.compliance_outcome,
            )
            section.summary_json = normalize(result)
            section.rule_references = [references[k] for k in sorted(references)]
            if all(c.applicability == "NOT_APPLICABLE" for c in items):
                section.applicability_status = "NOT_APPLICABLE"
            elif any(c.applicability == "REQUIRES_REVIEW" for c in items):
                section.applicability_status = "REQUIRES_REVIEW"
            elif any(c.applicability == "REQUIRED" or c.elected for c in items):
                section.applicability_status = "REQUIRED"
            else:
                section.applicability_status = "OPTIONAL"
            section.applicability_reason = (
                "Derived from explicit required/elected requirement slots"
            )
            section.lock_version += 1
            children.append(
                AggregationChild.from_aggregate(
                    semantic_key=section.code,
                    applicability=section.applicability_status,
                    result=result,
                )
            )
        if children:
            result = SessionComplianceAggregator.aggregate(
                AggregationInput(children=tuple(children))
            )
            session.evaluation_status, session.compliance_outcome = (
                result.evaluation_status,
                result.compliance_outcome,
            )
        await self.repo.flush()

    async def invalidate(self, actor, session, run, reason):
        # Called INSIDE the source mutation transaction, before publishing any audit.
        session.regulatory_revision += 1
        session.lock_version += 1
        await invalidate_technical_approvals(
            self.repo,
            actor,
            session,
            reason=reason,
            scope={
                "entity_type": "test_runs",
                "entity_id": str(run.id),
            },
            audit=self.audit,
        )
        if run.current_result_id:
            self.repo.add(
                EvaluationResultEvent(
                    result_id=run.current_result_id,
                    event_type="STALE",
                    actor_id=actor.user_id,
                    reason=reason,
                    regulatory_revision=session.regulatory_revision,
                )
            )
            run.current_result_id = None
            run.evaluation_status = "STALE"
        elif run.evaluation_status != "STALE":
            run.evaluation_status = "IN_PROGRESS" if run.started_at else "NOT_STARTED"
        run.compliance_outcome = "UNDETERMINED"
        run.input_revision += 1
        run.lock_version += 1
        await self.repo.flush()
        await self.aggregate(session)

    async def run_detail(self, actor, identifier, part=None):
        async with self.session.begin():
            permission = (
                "observation:read"
                if part in {"observations", "environment-readings"}
                else "equipment:read"
                if part == "equipment"
                else "test:read"
            )
            _, run = await self.scoped_run(actor, identifier, permission)
            models = {
                "observations": TestObservation,
                "environment-readings": EnvironmentReading,
                "equipment": TestRunEquipment,
                "results": TestRunResult,
            }
            if part in models:
                rows = await self.repo.rows(models[part], test_run_id=run.id)
                if part == "environment-readings":
                    rows = sorted(
                        rows,
                        key=lambda row: (
                            row.measured_at,
                            row.phase or "",
                            str(row.id),
                        ),
                    )
                else:
                    rows = sorted(
                        rows,
                        key=lambda row: getattr(
                            row,
                            "sequence_no",
                            getattr(row, "evaluation_version", str(row.id)),
                        ),
                    )
                return [view(row) for row in rows]
            return view(run)

    async def result_detail(self, actor, identifier, result_id):
        async with self.session.begin():
            _, run = await self.scoped_run(actor, identifier, "test:read")
            result = await self.repo.get(TestRunResult, result_id)
            if result is None or result.test_run_id != run.id:
                raise missing()
            return view(result)

    async def mutate_run(self, actor, identifier, match, action, data=None):
        async with self.session.begin():
            session, run = await self.scoped_run(
                actor,
                identifier,
                "test:complete" if action == "complete" else "test:execute",
                mutation=True,
            )
            self.source_editable(session, run)
            require_match(match, etag(run.lock_version))
            before = view(run)
            correction_field = {
                "procedure-context": "procedure_context",
                "start": "start",
                "complete": "complete",
            }[action]
            alternatives = (
                (
                    (
                        "test_runs",
                        run.retest_of_run_id,
                        ("retest",),
                    ),
                )
                if run.retest_of_run_id
                else ()
            )
            await enforce_correction_scope(
                self.repo,
                session,
                entity_type="test_runs",
                entity_id=run.id,
                field_paths=(correction_field,),
                alternatives=alternatives,
            )
            if action == "procedure-context":
                definition = await self.repo.get(TestDefinitionRecord, run.test_definition_id)
                context = data.procedure_context
                req = await self.repo.get(SessionTestRequirement, run.requirement_id)
                registration = self.engine_for(session).registry.find(definition.code)
                if (
                    registration is None
                    or context.test_code != definition.code
                    or context.procedure_schema_version != run.procedure_schema_version
                    or context.range_no != req.slot_snapshot["range_no"]
                    or context.scenario != req.slot_snapshot["scenario"]
                    or context.procedure_variant != req.slot_snapshot["procedure_variant"]
                    or context.evaluation_context != session.evaluation_context
                ):
                    reject(
                        "INCOMPATIBLE_PROCEDURE",
                        "Context must match the pinned requirement slot",
                        422,
                    )
                # Equipment/environment/evidence come from server-owned associations.
                if context.equipment or context.environment or context.evidence_hashes:
                    reject(
                        "SOURCE_ASSOCIATIONS_REQUIRED",
                        "Use equipment, environment and evidence endpoints",
                        422,
                    )
                run.procedure_context = normalize(context)
                await self.invalidate(actor, session, run, "Procedure context changed")
            elif action == "start":
                if run.started_at:
                    reject("INVALID_TRANSITION", "Run has already started")
                run.started_at, run.started_by = datetime.now(UTC), actor.user_id
                run.evaluation_status = "IN_PROGRESS"
                run.lock_version += 1
                session.lock_version += 1
                session.regulatory_revision += 1
                await invalidate_technical_approvals(
                    self.repo,
                    actor,
                    session,
                    reason="Run start changed reviewed regulatory content",
                    scope={
                        "entity_type": "test_runs",
                        "entity_id": str(run.id),
                        "field_paths": ["start"],
                    },
                    audit=self.audit,
                )
                await self.aggregate(session)
            elif action == "complete":
                result = (
                    await self.repo.get(TestRunResult, run.current_result_id)
                    if run.current_result_id
                    else None
                )
                if (
                    result is None
                    or result.source_input_revision != run.input_revision
                    or result.evaluation_status != "COMPLETE"
                ):
                    reject(
                        "CURRENT_RESULT_REQUIRED", "A complete current verified result is required"
                    )
                if result.deterministic_result["synthetic_fixture"]:
                    demo_output_allowed = await self.require_demo_scope(session)
                    if not demo_output_allowed:
                        self.require_production_output(True)
                run.completed_at = datetime.now(UTC)
                run.lock_version += 1
                session.lock_version += 1
                session.regulatory_revision += 1
                await invalidate_technical_approvals(
                    self.repo,
                    actor,
                    session,
                    reason="Run completion changed reviewed regulatory content",
                    scope={
                        "entity_type": "test_runs",
                        "entity_id": str(run.id),
                        "field_paths": ["complete"],
                    },
                    audit=self.audit,
                )
                for observation in await self.repo.rows(TestObservation, test_run_id=run.id):
                    observation.is_locked = True
                await self.aggregate(session)
            else:
                raise ValueError("Unknown run action")
            await self.repo.flush()
            self.event(actor, session, "test_run." + action, run, before=before)
            return view(run)

    async def source(self, actor, run_id, match, kind, data=None, identifier=None, delete=False):
        model = {"observations": TestObservation, "environment-readings": EnvironmentReading}[kind]
        permission = (
            "observation:delete"
            if delete
            else "observation:update"
            if identifier
            else "observation:create"
        )
        async with self.session.begin():
            session, run = await self.scoped_run(actor, run_id, permission, mutation=True)
            self.source_editable(session, run)
            row = await self.repo.get(model, identifier, lock=True) if identifier else None
            if identifier and (row is None or row.test_run_id != run.id):
                raise missing()
            require_match(match, etag(row.lock_version if row else run.lock_version))
            before = view(row) if row else None
            if row and getattr(row, "is_locked", False):
                reject("TEST_ALREADY_LOCKED", "Observation is locked")
            if delete:
                collection_field = "observations" if kind == "observations" else "environment"
                await enforce_correction_scope(
                    self.repo,
                    session,
                    entity_type=row.__tablename__,
                    entity_id=row.id,
                    field_paths=("__delete__",),
                    alternatives=(
                        (
                            "test_runs",
                            run.id,
                            (collection_field,),
                        ),
                        *(
                            (
                                (
                                    "test_runs",
                                    run.retest_of_run_id,
                                    ("retest",),
                                ),
                            )
                            if run.retest_of_run_id
                            else ()
                        ),
                    ),
                )
                links = await self.repo.evidence([(row.__tablename__, row.id)])
                if links:
                    reject(
                        "EVIDENCE_PROTECTED", "Unlink mutable evidence before deleting this source"
                    )
                await self.repo.delete(row)
            else:
                if kind == "observations":
                    definition = await self.repo.get(TestDefinitionRecord, run.test_definition_id)
                    registration = self.engine_for(session).registry.find(definition.code)
                    if (
                        registration is None
                        or data.observation_type != definition.code
                        or data.payload.test_code != definition.code
                        or data.sequence_no != data.payload.sequence_no
                        or data.payload_schema_version != run.observation_schema_version
                        or data.payload.observation_schema_version != run.observation_schema_version
                    ):
                        reject(
                            "INCOMPATIBLE_OBSERVATION",
                            "Observation must match the run and sequence",
                            422,
                        )
                    existing = await self.repo.rows(
                        TestObservation, test_run_id=run.id, sequence_no=data.sequence_no
                    )
                    if any(r.id != identifier for r in existing):
                        reject("DUPLICATE_SEQUENCE", "Observation sequence already exists")
                    values = data.model_dump(mode="python")
                    values["payload"] = normalize(data.payload)
                else:
                    values = data.model_dump()
                    values["test_session_id"] = session.id

                collection_field = "observations" if kind == "observations" else "environment"
                if row:
                    ignored = {"test_session_id"}
                    changed_fields = tuple(
                        name
                        for name, value in values.items()
                        if name not in ignored and getattr(row, name) != value
                    )
                    await enforce_correction_scope(
                        self.repo,
                        session,
                        entity_type=row.__tablename__,
                        entity_id=row.id,
                        field_paths=changed_fields,
                        alternatives=(
                            (
                                "test_runs",
                                run.id,
                                (collection_field,),
                            ),
                            *(
                                (
                                    (
                                        "test_runs",
                                        run.retest_of_run_id,
                                        ("retest",),
                                    ),
                                )
                                if run.retest_of_run_id
                                else ()
                            ),
                        ),
                    )
                else:
                    alternatives = (
                        (
                            (
                                "test_runs",
                                run.retest_of_run_id,
                                ("retest",),
                            ),
                        )
                        if run.retest_of_run_id
                        else ()
                    )
                    await enforce_correction_scope(
                        self.repo,
                        session,
                        entity_type="test_runs",
                        entity_id=run.id,
                        field_paths=(collection_field,),
                        alternatives=alternatives,
                    )
                if row:
                    for name, value in values.items():
                        setattr(row, name, value)
                    row.lock_version += 1
                else:
                    row = model(id=uuid4(), test_run_id=run.id, recorded_by=actor.user_id, **values)
                    self.repo.add(row)
            await self.invalidate(actor, session, run, kind + " changed")
            if delete:
                self.audit.record(
                    kind + ".deleted",
                    actor.user_id,
                    row.__tablename__,
                    row.id,
                    lab=session.laboratory_id,
                    before=before,
                )
                return None
            self.event(actor, session, kind + ".saved", row, before=before)
            return view(row)

    async def capture(self, session, run):
        definition = await self.repo.get(TestDefinitionRecord, run.test_definition_id)
        engine = self.engine_for(session)
        registration = engine.registry.find(definition.code)
        if registration is None:
            reject("TODO_REGULATORY_VALIDATION", "Evaluator not implemented in this phase")
        context = registration.contexts.parse(run.procedure_context)
        observations = await self.repo.rows(TestObservation, test_run_id=run.id)
        equipment = await self.repo.rows(TestRunEquipment, test_run_id=run.id)
        environment = sorted(
            await self.repo.rows(EnvironmentReading, test_run_id=run.id),
            key=lambda r: (
                r.measured_at,
                canonical_bytes(
                    (
                        r.phase,
                        r.temperature_c,
                        r.relative_humidity_percent,
                        r.barometric_pressure_hpa,
                    )
                ),
            ),
        )
        targets = (
            [("test_sessions", session.id), ("test_runs", run.id)]
            + [("test_observations", r.id) for r in observations]
            + [("test_run_equipment", r.id) for r in equipment]
        )
        links = await self.repo.evidence(targets)
        equipment_values = []
        for item in equipment:
            snap = item.equipment_snapshot
            certificate = (
                await self.repo.get(Attachment, item.calibration_attachment_id)
                if item.calibration_attachment_id
                else None
            )
            if item.calibration_attachment_id:
                calibration_links = [
                    (attachment, link)
                    for attachment, link in links
                    if (
                        attachment.id == item.calibration_attachment_id
                        and link.entity_type == "test_run_equipment"
                        and link.entity_id == item.id
                        and link.purpose == "calibration"
                    )
                ]
                frozen_identity = (
                    snap.get("calibration_attachment_id"),
                    snap.get("calibration_attachment_sha256"),
                    snap.get("calibration_attachment_object_version"),
                )
                live_identity = (
                    str(certificate.id) if certificate else None,
                    certificate.sha256 if certificate else None,
                    certificate.object_version if certificate else None,
                )
                if (
                    certificate is None
                    or certificate.laboratory_id != session.laboratory_id
                    or certificate.archived_at is not None
                    or len(calibration_links) != 1
                    or frozen_identity != live_identity
                ):
                    reject(
                        "EVIDENCE_INTEGRITY_ERROR",
                        "Calibration evidence mapping is "
                        "inconsistent with the frozen equipment snapshot",
                    )
            equipment_values.append(
                dict(
                    reference=snap.get("reference_number") or snap.get("serial_number") or "",
                    **{
                        k: snap.get(k)
                        for k in (
                            "category",
                            "manufacturer",
                            "model",
                            "serial_number",
                            "calibration_certificate_no",
                            "calibration_date",
                            "calibration_due_date",
                            "accuracy_or_class",
                            "nominal_mass_g",
                        )
                    },
                    certificate_content_hash=certificate.sha256 if certificate else None,
                )
            )
        context = type(context).model_validate(
            context.model_dump()
            | dict(
                equipment=equipment_values,
                environment=[
                    dict(
                        measured_at=r.measured_at,
                        temperature_c=r.temperature_c,
                        relative_humidity_percent=r.relative_humidity_percent,
                        pressure_hpa=r.barometric_pressure_hpa,
                        phase=r.phase,
                    )
                    for r in environment
                ],
                evidence_hashes=sorted({a.sha256 for a, _ in links}),
            )
        )
        batch = registration.observations.parse(
            test_code=definition.code,
            protocol=context.protocol,
            version=run.observation_schema_version,
            rows=[r.payload for r in observations],
        )
        rules = RuleSet.model_validate(session.ruleset_snapshot)
        arguments = dict(
            test_code=definition.code,
            instrument_snapshot=InstrumentSnapshot.model_validate(session.instrument_snapshot),
            procedure_context=context,
            observations=batch,
            ruleset=rules,
        )
        snapshot = evaluation_input_snapshot(
            **{k: v for k, v in arguments.items() if k != "ruleset"},
            ruleset_configuration_hash=rules.configuration_hash,
            engine_version=engine.engine_version,
        )
        return arguments, snapshot, [(a.id, link.purpose) for a, link in links]

    async def evaluate(self, actor, identifier, match, key):
        async with self.session.begin():
            parent, _ = await self.scoped_run(actor, identifier, "test:evaluate")
            lab = parent.laboratory_id

        async def authorize():
            await self.scoped_run(actor, identifier, "test:evaluate", mutation=True)

        reservation = await self.reserve(
            actor, lab, "test.evaluate", key, {"run_id": str(identifier)}, authorize
        )
        if reservation.replay:
            if reservation.response_status == 422:
                error = reservation.response_body["error"]
                reject(error["code"], error["message"], 422, {"issues": error["details"]})
            return reservation.response_body
        # Transaction A: authorize, lock, snapshot. No calculation while locked.
        async with self.session.begin():
            parent, run = await self.scoped_run(actor, identifier, "test:evaluate", mutation=True)
            self.source_editable(parent, run)
            alternatives = (
                (
                    (
                        "test_runs",
                        run.retest_of_run_id,
                        ("retest",),
                    ),
                )
                if run.retest_of_run_id
                else ()
            )
            await enforce_correction_scope(
                self.repo,
                parent,
                entity_type="test_runs",
                entity_id=run.id,
                field_paths=("evaluate",),
                alternatives=alternatives,
            )
            require_match(match, etag(run.lock_version))
            if not run.started_at:
                reject("RUN_NOT_STARTED", "Start the run before evaluation")
            requirement = await self.repo.get(SessionTestRequirement, run.requirement_id)
            if requirement.applicability_status == "NOT_APPLICABLE":
                reject("TEST_NOT_APPLICABLE", "Explicitly non-applicable runs cannot be evaluated")
            revision, regulatory_revision = run.input_revision, parent.regulatory_revision
            try:
                arguments, snapshot, links = await self.capture(parent, run)
                engine = self.engine_for(parent)
                demo_output_allowed = await self.require_demo_scope(parent)
            except (ValidationError, ValueError) as exc:
                reject("INVALID_EVALUATION_INPUT", str(exc), 422)
        result = await asyncio.to_thread(engine.evaluate, **arguments)
        if result.synthetic_fixture and not demo_output_allowed:
            self.require_production_output(result.synthetic_fixture)
        # Transaction B: reauthorize and reject source/workflow races before writing.
        async with self.session.begin():
            parent, run = await self.scoped_run(actor, identifier, "test:evaluate", mutation=True)
            if (
                parent.workflow_status != "TESTING"
                or run.completed_at is not None
                or run.input_revision != revision
                or parent.regulatory_revision != regulatory_revision
            ):
                reject(
                    "SOURCE_CHANGED_DURING_EVALUATION",
                    "Source changed during evaluation; retry against current revision",
                )
            if result.input_hash != snapshot.input_hash:
                reject(
                    "EVALUATION_IDENTITY_MISMATCH", "Engine identity does not match captured input"
                )
            current = (
                await self.repo.get(TestRunResult, run.current_result_id)
                if run.current_result_id
                else None
            )
            if current and current.input_hash == snapshot.input_hash:
                return await self.finish(reservation, actor, lab, current)
            if result.evaluation_status == "INCOMPLETE":
                run.evaluation_status, run.compliance_outcome = "INCOMPLETE", "UNDETERMINED"
                run.lock_version += 1
                parent.lock_version += 1
                await self.aggregate(parent)
                self.event(actor, parent, "test_run.procedure_incomplete", run)
                response = {
                    "error": {
                        "code": result.issue_code,
                        "message": "Procedure is incomplete",
                        "details": normalize(result.procedure_issues),
                    }
                }
                await self.idempotency.complete(
                    reservation.id, actor.user_id, str(lab), 422, response, {}
                )
            else:
                history = await self.repo.results(run.id)
                previous = history[-1] if history else None
                stored = TestRunResult(
                    id=uuid4(),
                    test_run_id=run.id,
                    rule_set_id=parent.rule_set_id,
                    evaluation_version=previous.evaluation_version + 1 if previous else 1,
                    supersedes_result_id=previous.id if previous else None,
                    source_input_revision=revision,
                    evaluation_input_snapshot=normalize(snapshot),
                    deterministic_result=normalize(result),
                    applicability_status=result.applicability.applicability,
                    applicability_reason=result.applicability.reason,
                    calculations_json=normalize(result.calculations),
                    acceptance_limits_json=normalize(result.acceptance_limits),
                    failed_conditions_json=normalize(result.failed_conditions),
                    rule_references_json=normalize(result.rule_references),
                    reason="; ".join(result.reasons),
                    issue_code=result.issue_code,
                    unresolved_rule_ids=list(result.unresolved_rule_ids),
                    hash_schema_version="v1",
                    observation_schema_version=run.observation_schema_version,
                    procedure_schema_version=run.procedure_schema_version,
                    engine_version=result.engine_version,
                    ruleset_version=result.ruleset_version,
                    ruleset_configuration_hash=result.ruleset_configuration_hash,
                    input_hash=result.input_hash,
                    result_hash=result.result_hash,
                    evaluation_status=result.evaluation_status,
                    compliance_outcome=result.compliance_outcome,
                    initiated_by=actor.user_id,
                )
                self.repo.add(stored)
                await self.repo.flush()
                parent.regulatory_revision += 1
                parent.lock_version += 1
                await invalidate_technical_approvals(
                    self.repo,
                    actor,
                    parent,
                    reason="Evaluation result changed after technical review",
                    scope={
                        "entity_type": "test_runs",
                        "entity_id": str(run.id),
                        "field_paths": ["evaluate"],
                    },
                    audit=self.audit,
                )
                run.lock_version += 1
                run.current_result_id = stored.id
                run.evaluation_status, run.compliance_outcome = (
                    result.evaluation_status,
                    result.compliance_outcome,
                )
                if previous:
                    self.repo.add(
                        EvaluationResultEvent(
                            result_id=previous.id,
                            replacement_result_id=stored.id,
                            event_type="SUPERSEDED",
                            regulatory_revision=parent.regulatory_revision,
                            actor_id=actor.user_id,
                            reason="New immutable evaluation version",
                        )
                    )
                self.repo.add(
                    EvaluationResultEvent(
                        result_id=stored.id,
                        event_type="CURRENT",
                        regulatory_revision=parent.regulatory_revision,
                        actor_id=actor.user_id,
                        reason="Current captured input revision",
                    )
                )
                for attachment_id, purpose in set(links):
                    self.repo.add(
                        AttachmentLink(
                            attachment_id=attachment_id,
                            entity_type="test_run_results",
                            entity_id=stored.id,
                            purpose=purpose,
                            linked_by=actor.user_id,
                        )
                    )
                await self.aggregate(parent)
                self.event(actor, parent, "test_run.evaluated", stored)
                return await self.finish(reservation, actor, lab, stored)
        reject(
            result.issue_code,
            "Procedure is incomplete",
            422,
            {"issues": normalize(result.procedure_issues)},
        )

    async def revision(self, actor, identifier, match, key, data):
        async with self.session.begin():
            parent = await self.scoped(actor, identifier, "session:create_revision")
            lab, root = parent.laboratory_id, parent.root_session_id

        async def authorize():
            await self.scoped(actor, identifier, "session:create_revision")

        reservation = await self.reserve(
            actor,
            lab,
            "session.revision",
            key,
            {"session_id": str(identifier), "reason": data.reason},
            authorize,
        )
        if reservation.replay:
            return reservation.response_body
        async with self.session.begin():
            await self.scoped(actor, root, "session:create_revision", mutation=True)
            parent = await self.scoped(actor, identifier, "session:create_revision", mutation=True)
            require_match(match, etag(parent.lock_version))
            number = await self.repo.next_revision(root)
            row = TestSession(
                id=uuid4(),
                laboratory_id=lab,
                instrument_id=parent.instrument_id,
                rule_set_id=parent.rule_set_id,
                application_number=parent.application_number,
                evaluation_context=parent.evaluation_context,
                instrument_snapshot=parent.instrument_snapshot,
                ruleset_snapshot=parent.ruleset_snapshot,
                root_session_id=root,
                parent_session_id=parent.id,
                session_revision_no=number,
                revision_reason=data.reason,
                started_by=actor.user_id,
                notes=parent.notes,
                workflow_status="INSTRUMENT_CONFIGURATION",
            )
            self.repo.add(row)
            await self.repo.flush()
            await self.initialize_sections(row)
            self.event(actor, row, "session.revision_created", row, reason=data.reason)
            return await self.finish(reservation, actor, lab, row, 201)

    async def retest(self, actor, identifier, match, key, data):
        async with self.session.begin():
            parent, _ = await self.scoped_run(actor, identifier, "test:retest")
            lab = parent.laboratory_id

        async def authorize():
            await self.scoped_run(actor, identifier, "test:retest")

        reservation = await self.reserve(
            actor,
            lab,
            "test.retest",
            key,
            {"run_id": str(identifier), "reason": data.reason},
            authorize,
        )
        if reservation.replay:
            return reservation.response_body
        async with self.session.begin():
            parent, original = await self.scoped_run(
                actor, identifier, "test:retest", mutation=True
            )
            self.editable(parent, testing=True)
            require_match(match, etag(original.lock_version))
            await enforce_correction_scope(
                self.repo,
                parent,
                entity_type="test_runs",
                entity_id=original.id,
                field_paths=("retest",),
            )
            siblings = await self.repo.rows(TestRun, requirement_id=original.requirement_id)
            run = TestRun(
                id=uuid4(),
                test_session_id=parent.id,
                session_section_id=original.session_section_id,
                requirement_id=original.requirement_id,
                test_definition_id=original.test_definition_id,
                run_no=max(r.run_no for r in siblings) + 1,
                retest_of_run_id=original.id,
                retest_reason=data.reason,
                procedure_context=original.procedure_context,
                procedure_schema_version=original.procedure_schema_version,
                observation_schema_version=original.observation_schema_version,
            )
            self.repo.add(run)
            parent.lock_version += 1
            parent.regulatory_revision += 1
            await invalidate_technical_approvals(
                self.repo,
                actor,
                parent,
                reason="Retest created after technical review",
                scope={
                    "entity_type": "test_runs",
                    "entity_id": str(original.id),
                    "field_paths": ["retest"],
                    "new_run_id": str(run.id),
                },
                audit=self.audit,
            )
            await self.repo.flush()
            self.event(actor, parent, "test_run.retest_created", run, reason=data.reason)
            return await self.finish(reservation, actor, lab, run, 201)

    async def select_run(self, actor, identifier, match, data):
        from app.compliance.regulatory import RegulatoryBlocked, rule_policy
        from app.compliance.selection import SelectionPolicy

        async with self.session.begin():
            req = await self.repo.get(SessionTestRequirement, identifier)
            if req is None:
                raise missing()
            parent = await self.scoped(actor, req.test_session_id, "test:select_run", mutation=True)
            self.editable(parent, testing=True)
            req = await self.repo.get(SessionTestRequirement, identifier, lock=True)
            require_match(match, etag(req.lock_version))
            await enforce_correction_scope(
                self.repo,
                parent,
                entity_type="session_test_requirements",
                entity_id=req.id,
                field_paths=("selected_run_id",),
            )
            run = await self.repo.get(TestRun, data.run_id, lock=True)
            if run is None or run.requirement_id != req.id:
                raise missing()
            if req.applicability_status not in {"REQUIRED", "OPTIONAL"} or (
                req.applicability_status == "OPTIONAL" and not req.is_elected
            ):
                reject("INVALID_RUN_SELECTION", "Only required/elected slots can select a run")
            rules = RuleSet.model_validate(parent.ruleset_snapshot)
            try:
                policy = rule_policy(rules, "RETEST_SELECTION", "run_selection_v1", SelectionPolicy)
            except RegulatoryBlocked as exc:
                reject(
                    "TODO_REGULATORY_VALIDATION",
                    "Retest selection requires verified REG-16 policy",
                    details={
                        "unresolved_rule_ids": sorted(
                            set(exc.resolution.unresolved_rule_ids) | {"REG-16"}
                        )
                    },
                )
            current = (
                await self.repo.get(TestRunResult, run.current_result_id)
                if run.current_result_id
                else None
            )
            old = await self.repo.get(TestRun, req.selected_run_id) if req.selected_run_id else None
            if not self.artifact_is_production(rules) or not policy.permits(
                run.evaluation_status,
                run.compliance_outcome,
                current=bool(current and current.source_input_revision == run.input_revision),
                replacing_negative=bool(old and old.compliance_outcome == "NONCOMPLIANT"),
            ):
                reject("INVALID_RUN_SELECTION", "Run does not meet verified selection policy")
            parent.regulatory_revision += 1
            parent.lock_version += 1
            await invalidate_technical_approvals(
                self.repo,
                actor,
                parent,
                reason="Authoritative run selection changed after technical review",
                scope={
                    "entity_type": "session_test_requirements",
                    "entity_id": str(req.id),
                    "field_paths": ["selected_run_id"],
                },
                audit=self.audit,
            )
            self.repo.add(
                TestRunSelectionEvent(
                    requirement_id=req.id,
                    previous_run_id=req.selected_run_id,
                    selected_run_id=run.id,
                    reason=data.reason,
                    regulatory_revision=parent.regulatory_revision,
                    actor_id=actor.user_id,
                )
            )
            req.selected_run_id = run.id
            req.lock_version += 1
            await self.repo.flush()
            await self.aggregate(parent)
            self.event(actor, parent, "test_run.selected", req, reason=data.reason)
            return view(req)

    async def equipment(self, actor, identifier, match, data=None, equipment_id=None):
        async with self.session.begin():
            parent, run = await self.scoped_run(actor, identifier, "test:execute", mutation=True)
            self.source_editable(parent, run)
            alternatives = (
                (
                    (
                        "test_runs",
                        run.retest_of_run_id,
                        ("retest",),
                    ),
                )
                if run.retest_of_run_id
                else ()
            )
            await enforce_correction_scope(
                self.repo,
                parent,
                entity_type="test_runs",
                entity_id=run.id,
                field_paths=("equipment",),
                alternatives=alternatives,
            )
            _, grants = await self.authz.current(actor)
            grants.require("equipment:read", parent.laboratory_id)
            if equipment_id:
                rows = await self.repo.rows(
                    TestRunEquipment, test_run_id=run.id, equipment_id=equipment_id
                )
                if not rows:
                    raise missing()
                row = await self.repo.get(TestRunEquipment, rows[0].id, lock=True)
                require_match(match, etag(row.lock_version))
                if await self.repo.evidence([("test_run_equipment", row.id)]):
                    reject(
                        "EVIDENCE_PROTECTED", "Unlink mutable evidence before removing equipment"
                    )
                before = view(row)
                await self.repo.delete(row)
                await self.invalidate(actor, parent, run, "Equipment removed")
                self.audit.record(
                    "test_run.equipment_removed",
                    actor.user_id,
                    "test_run_equipment",
                    row.id,
                    lab=parent.laboratory_id,
                    before=before,
                )
                return None
            require_match(match, etag(run.lock_version))
            equipment = await self.repo.get(TestEquipment, data.equipment_id, lock=True)
            if equipment is None or equipment.laboratory_id != parent.laboratory_id:
                raise missing()
            if not equipment.is_active:
                reject("EQUIPMENT_ARCHIVED", "Active equipment required")
            if await self.repo.rows(
                TestRunEquipment, test_run_id=run.id, equipment_id=equipment.id
            ):
                reject("EQUIPMENT_ALREADY_LINKED", "Equipment already linked")
            certificate = None
            if data.calibration_attachment_id:
                grants.require("attachment:read", parent.laboratory_id)
                certificate = await self.repo.get(
                    Attachment, data.calibration_attachment_id, lock=True
                )
                if (
                    certificate is None
                    or certificate.laboratory_id != parent.laboratory_id
                    or certificate.archived_at
                ):
                    raise missing()
            snapshot = calibration_snapshot(
                EquipmentView.model_validate(equipment),
                datetime.now(UTC),
                certificate=certificate,
            )
            row = TestRunEquipment(
                id=uuid4(),
                test_run_id=run.id,
                equipment_id=equipment.id,
                equipment_snapshot=snapshot.model_dump(mode="json"),
                calibration_attachment_id=data.calibration_attachment_id,
                linked_by=actor.user_id,
            )
            self.repo.add(row)
            await self.repo.flush()
            if certificate:
                self.repo.add(
                    AttachmentLink(
                        attachment_id=certificate.id,
                        entity_type="test_run_equipment",
                        entity_id=row.id,
                        purpose="calibration",
                        linked_by=actor.user_id,
                    )
                )
            await self.invalidate(actor, parent, run, "Equipment linked")
            self.event(actor, parent, "test_run.equipment_linked", row)
            return view(row)

    async def history(self, actor, identifier, page, size):
        from app.services.rulesets import serialize

        async with self.session.begin():
            _, run = await self.scoped_run(
                actor,
                identifier,
                "test:read",
            )
            sibling_runs, total = await self.repo.retest_runs(
                run.requirement_id,
                page,
                size,
            )
            requirement = await self.repo.get(
                SessionTestRequirement,
                run.requirement_id,
            )
            results = await self.repo.results(run.id)
            events = await self.repo.result_events([item.id for item in results])
            selection_events = await self.repo.rows(
                TestRunSelectionEvent,
                requirement_id=run.requirement_id,
            )

            selection_events.sort(
                key=lambda event: (
                    event.regulatory_revision,
                    event.created_at,
                    str(event.id),
                )
            )

            run_items = []
            for item in sibling_runs:
                run_items.append(
                    {
                        "id": item.id,
                        "run_no": item.run_no,
                        "retest_of_run_id": item.retest_of_run_id,
                        "retest_reason": item.retest_reason,
                        "evaluation_status": item.evaluation_status,
                        "compliance_outcome": item.compliance_outcome,
                        "input_revision": item.input_revision,
                        "current_result_id": item.current_result_id,
                        "started_at": item.started_at,
                        "completed_at": item.completed_at,
                        "is_selected": (
                            requirement is not None and requirement.selected_run_id == item.id
                        ),
                    }
                )

            return {
                "runs": {
                    "items": run_items,
                    "page": page,
                    "page_size": size,
                    "total": total,
                },
                "results": [view(item) for item in results],
                "events": [serialize(item) for item in events],
                "selections": [serialize(item) for item in selection_events],
            }

    async def evidence_target(self, actor, target, permission, match):
        models = {
            "test_sessions": TestSession,
            "test_runs": TestRun,
            "test_observations": TestObservation,
            "test_run_equipment": TestRunEquipment,
            "test_run_results": TestRunResult,
        }
        row = await self.repo.get(models[target.entity_type], target.entity_id)
        if row is None:
            raise missing()
        if isinstance(row, TestSession):
            parent = await self.scoped(actor, row.id, permission, mutation=True)
            self.editable(parent)
            row = parent
        else:
            run_id = row.id if isinstance(row, TestRun) else row.test_run_id
            parent, run = await self.scoped_run(actor, run_id, permission, mutation=True)
            self.source_editable(parent, run)
            if isinstance(row, TestRunResult):
                reject("EVIDENCE_PROTECTED", "Immutable result evidence cannot be changed")
            row = (
                run
                if isinstance(row, TestRun)
                else await self.repo.get(models[target.entity_type], row.id, lock=True)
            )
        alternatives = ()
        if not isinstance(row, TestSession):
            alternatives = (
                (
                    "test_runs",
                    run.id,
                    ("evidence",),
                ),
                *(
                    (
                        (
                            "test_runs",
                            run.retest_of_run_id,
                            ("retest",),
                        ),
                    )
                    if run.retest_of_run_id
                    else ()
                ),
            )
        await enforce_correction_scope(
            self.repo,
            parent,
            entity_type=row.__tablename__,
            entity_id=row.id,
            field_paths=("evidence",),
            alternatives=alternatives,
        )
        require_match(match, etag(row.lock_version))
        return row, parent, parent.laboratory_id

    async def evidence_changed(self, actor, row, parent):
        if isinstance(row, TestSession):
            runs = sorted(await self.repo.runs(parent.id), key=lambda r: str(r.id))
            if not runs:
                parent.lock_version += 1
                parent.regulatory_revision += 1
                await invalidate_technical_approvals(
                    self.repo,
                    actor,
                    parent,
                    reason="Session evidence changed after technical review",
                    scope={
                        "entity_type": "test_sessions",
                        "entity_id": str(parent.id),
                        "field_paths": ["evidence"],
                    },
                    audit=self.audit,
                )
            for run in runs:
                run = await self.repo.get(TestRun, run.id, lock=True)
                self.source_editable(parent, run)
                await self.invalidate(actor, parent, run, "Session evidence changed")
        else:
            run = (
                row
                if isinstance(row, TestRun)
                else await self.repo.get(TestRun, row.test_run_id, lock=True)
            )
            if row is not run:
                row.lock_version += 1
            await self.invalidate(actor, parent, run, "Run evidence changed")
        await self.repo.flush()
        self.event(actor, parent, "evidence.target_changed", row)
