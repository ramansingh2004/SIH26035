"""Immutable Phase 15 final-approval snapshot construction."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.inspection import inspect as sa_inspect

from app.compliance.canonical import normalize
from app.core.errors import AppError
from app.models.checklist import ChecklistResponse
from app.models.construction import ConstructionExamination, ConstructionItem
from app.models.foundations import (
    Attachment,
    AttachmentLink,
    ChecklistRule,
    RuleDefinition,
    RuleSetRecord,
)
from app.models.identity import Laboratory, Role, User, UserRoleAssignment
from app.models.master_data import (
    Instrument,
    InstrumentComponent,
    InstrumentRange,
    Manufacturer,
)
from app.models.review import ApprovalAction
from app.models.testing import (
    EnvironmentReading,
    EvaluationResultEvent,
    SessionTestRequirement,
    TestObservation,
    TestRun,
    TestRunEquipment,
    TestRunResult,
    TestRunSelectionEvent,
    TestSessionSection,
)


def _primitive(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_primitive(item) for item in value]
    return normalize(value)


def row_payload(row):
    return {
        attribute.key: _primitive(getattr(row, attribute.key))
        for attribute in sa_inspect(type(row)).column_attrs
    }


def user_payload(row):
    return {
        "id": str(row.id),
        "full_name": row.full_name,
        "email": str(row.email),
        "is_active": row.is_active,
    }


class ApprovalSnapshotBuilder:
    """Build one canonical, self-contained approved regulatory record."""

    def __init__(self, session):
        self.session = session

    async def _all(self, model, *criteria, order_by=()):
        statement = select(model)
        if criteria:
            statement = statement.where(*criteria)
        if order_by:
            statement = statement.order_by(*order_by)
        return list((await self.session.scalars(statement)).all())

    async def build(self, test_session):
        laboratory = await self.session.get(
            Laboratory,
            test_session.laboratory_id,
        )
        instrument = await self.session.get(
            Instrument,
            test_session.instrument_id,
        )
        ruleset = await self.session.get(
            RuleSetRecord,
            test_session.rule_set_id,
        )
        if laboratory is None or instrument is None or ruleset is None:
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Approval source identity is incomplete",
            )

        manufacturer = await self.session.get(
            Manufacturer,
            instrument.manufacturer_id,
        )
        if manufacturer is None:
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Approval manufacturer identity is unavailable",
            )

        ranges = await self._all(
            InstrumentRange,
            InstrumentRange.instrument_id == instrument.id,
            order_by=(InstrumentRange.range_no, InstrumentRange.id),
        )
        components = await self._all(
            InstrumentComponent,
            InstrumentComponent.instrument_id == instrument.id,
            order_by=(InstrumentComponent.id,),
        )
        sections = await self._all(
            TestSessionSection,
            TestSessionSection.test_session_id == test_session.id,
            order_by=(TestSessionSection.section_number,),
        )
        requirements = await self._all(
            SessionTestRequirement,
            SessionTestRequirement.test_session_id == test_session.id,
            order_by=(SessionTestRequirement.requirement_key, SessionTestRequirement.id),
        )
        runs = await self._all(
            TestRun,
            TestRun.test_session_id == test_session.id,
            order_by=(TestRun.requirement_id, TestRun.run_no, TestRun.id),
        )
        run_ids = [row.id for row in runs]
        requirement_ids = [row.id for row in requirements]

        observations = (
            await self._all(
                TestObservation,
                TestObservation.test_run_id.in_(run_ids),
                order_by=(
                    TestObservation.test_run_id,
                    TestObservation.sequence_no,
                    TestObservation.id,
                ),
            )
            if run_ids
            else []
        )
        environments = (
            await self._all(
                EnvironmentReading,
                EnvironmentReading.test_run_id.in_(run_ids),
                order_by=(
                    EnvironmentReading.test_run_id,
                    EnvironmentReading.measured_at,
                    EnvironmentReading.phase,
                    EnvironmentReading.id,
                ),
            )
            if run_ids
            else []
        )
        equipment = (
            await self._all(
                TestRunEquipment,
                TestRunEquipment.test_run_id.in_(run_ids),
                order_by=(
                    TestRunEquipment.test_run_id,
                    TestRunEquipment.equipment_id,
                    TestRunEquipment.id,
                ),
            )
            if run_ids
            else []
        )
        results = (
            await self._all(
                TestRunResult,
                TestRunResult.test_run_id.in_(run_ids),
                order_by=(
                    TestRunResult.test_run_id,
                    TestRunResult.evaluation_version,
                    TestRunResult.id,
                ),
            )
            if run_ids
            else []
        )
        result_ids = [row.id for row in results]
        result_events = (
            await self._all(
                EvaluationResultEvent,
                EvaluationResultEvent.result_id.in_(result_ids),
                order_by=(
                    EvaluationResultEvent.created_at,
                    EvaluationResultEvent.id,
                ),
            )
            if result_ids
            else []
        )
        selection_events = (
            await self._all(
                TestRunSelectionEvent,
                TestRunSelectionEvent.requirement_id.in_(requirement_ids),
                order_by=(
                    TestRunSelectionEvent.regulatory_revision,
                    TestRunSelectionEvent.created_at,
                    TestRunSelectionEvent.id,
                ),
            )
            if requirement_ids
            else []
        )

        examination = await self.session.scalar(
            select(ConstructionExamination).where(
                ConstructionExamination.test_session_id == test_session.id
            )
        )
        construction_items = (
            await self._all(
                ConstructionItem,
                ConstructionItem.construction_examination_id == examination.id,
                order_by=(ConstructionItem.sort_order, ConstructionItem.id),
            )
            if examination is not None
            else []
        )
        construction_rule_ids = {row.requirement_rule_id for row in construction_items}
        construction_rules = (
            await self._all(
                RuleDefinition,
                RuleDefinition.id.in_(construction_rule_ids),
                order_by=(RuleDefinition.id,),
            )
            if construction_rule_ids
            else []
        )

        checklist_responses = await self._all(
            ChecklistResponse,
            ChecklistResponse.test_session_id == test_session.id,
            order_by=(ChecklistResponse.id,),
        )
        checklist_rule_ids = {row.checklist_rule_id for row in checklist_responses}
        checklist_rules = (
            await self._all(
                ChecklistRule,
                ChecklistRule.id.in_(checklist_rule_ids),
                order_by=(ChecklistRule.sort_order, ChecklistRule.id),
            )
            if checklist_rule_ids
            else []
        )

        approval_actions = await self._all(
            ApprovalAction,
            ApprovalAction.test_session_id == test_session.id,
            order_by=(ApprovalAction.created_at, ApprovalAction.id),
        )

        targets = [("test_sessions", test_session.id)]
        targets.extend(("test_runs", row.id) for row in runs)
        targets.extend(("test_observations", row.id) for row in observations)
        targets.extend(("test_run_equipment", row.id) for row in equipment)
        targets.extend(("test_run_results", row.id) for row in results)
        targets.extend(("construction_items", row.id) for row in construction_items)
        targets.extend(("checklist_responses", row.id) for row in checklist_responses)

        conditions = [
            (AttachmentLink.entity_type == entity_type) & (AttachmentLink.entity_id == entity_id)
            for entity_type, entity_id in targets
        ]
        evidence_rows = list(
            (
                await self.session.execute(
                    select(AttachmentLink, Attachment)
                    .join(
                        Attachment,
                        Attachment.id == AttachmentLink.attachment_id,
                    )
                    .where(
                        AttachmentLink.unlinked_at.is_(None),
                        Attachment.archived_at.is_(None),
                        or_(*conditions),
                    )
                    .order_by(
                        AttachmentLink.entity_type,
                        AttachmentLink.entity_id,
                        AttachmentLink.purpose,
                        AttachmentLink.id,
                    )
                )
            ).all()
        )
        if any(
            attachment.laboratory_id != test_session.laboratory_id
            for _, attachment in evidence_rows
        ):
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Approved evidence crosses laboratory scope",
            )

        actor_ids = {
            test_session.started_by,
            *(row.recorded_by for row in observations),
            *(row.recorded_by for row in environments),
            *(row.linked_by for row in equipment),
            *(row.initiated_by for row in results),
            *(row.actor_id for row in result_events),
            *(row.actor_id for row in selection_events),
            *(row.actor_id for row in approval_actions),
            *(row.examined_by for row in checklist_responses if row.examined_by),
            *(
                [examination.examined_by]
                if examination is not None and examination.examined_by
                else []
            ),
            *(link.linked_by for link, _ in evidence_rows),
            *(attachment.uploaded_by for _, attachment in evidence_rows),
        }
        actor_ids.discard(None)

        users = (
            await self._all(
                User,
                User.id.in_(actor_ids),
                order_by=(User.id,),
            )
            if actor_ids
            else []
        )
        assignments = []
        if actor_ids:
            assignments = list(
                (
                    await self.session.execute(
                        select(UserRoleAssignment, Role.code)
                        .join(
                            Role,
                            Role.id == UserRoleAssignment.role_id,
                        )
                        .where(
                            UserRoleAssignment.user_id.in_(actor_ids),
                            or_(
                                UserRoleAssignment.scope_type == "GLOBAL",
                                UserRoleAssignment.laboratory_id == test_session.laboratory_id,
                            ),
                        )
                        .order_by(
                            UserRoleAssignment.user_id,
                            UserRoleAssignment.assigned_at,
                            UserRoleAssignment.id,
                        )
                    )
                ).all()
            )

        checklist_rule_map = {rule.id: rule for rule in checklist_rules}
        if checklist_rule_ids != set(checklist_rule_map):
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Approved checklist rule snapshot is incomplete",
            )

        raw = {
            "schema_version": 1,
            "session": row_payload(test_session),
            "laboratory": row_payload(laboratory),
            "manufacturer": row_payload(manufacturer),
            "instrument_master_at_approval": row_payload(instrument),
            "instrument_ranges_at_approval": [row_payload(row) for row in ranges],
            "instrument_components_at_approval": [row_payload(row) for row in components],
            "evaluation_instrument_snapshot": _primitive(test_session.instrument_snapshot),
            "ruleset_record": row_payload(ruleset),
            "ruleset_snapshot": _primitive(test_session.ruleset_snapshot),
            "sections": [row_payload(row) for row in sections],
            "requirements": [row_payload(row) for row in requirements],
            "runs": [row_payload(row) for row in runs],
            "observations": [row_payload(row) for row in observations],
            "environment_readings": [row_payload(row) for row in environments],
            "equipment_links": [row_payload(row) for row in equipment],
            "results": [row_payload(row) for row in results],
            "result_events": [row_payload(row) for row in result_events],
            "selection_events": [row_payload(row) for row in selection_events],
            "construction": {
                "examination": (row_payload(examination) if examination is not None else None),
                "items": [row_payload(row) for row in construction_items],
                "rules": [row_payload(row) for row in construction_rules],
            },
            "checklist": [
                {
                    "response": row_payload(response),
                    "rule": row_payload(checklist_rule_map[response.checklist_rule_id]),
                }
                for response in checklist_responses
            ],
            "evidence": [
                {
                    "link": row_payload(link),
                    "attachment": row_payload(attachment),
                }
                for link, attachment in evidence_rows
            ],
            "approval_actions": [row_payload(row) for row in approval_actions],
            "actors": [
                {
                    "user": user_payload(user),
                    "role_assignments": [
                        row_payload(assignment) | {"role_code": role_code}
                        for assignment, role_code in assignments
                        if assignment.user_id == user.id
                    ],
                }
                for user in users
            ],
        }
        try:
            return normalize(raw)
        except ValueError as exc:
            raise AppError(
                409,
                "SESSION_NOT_READY_FOR_APPROVAL",
                "Approved record cannot be represented canonically",
                {"reason": str(exc)},
            ) from exc
