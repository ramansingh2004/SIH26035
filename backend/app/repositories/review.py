"""Phase 15 review/correction queries and provenance helpers."""

from sqlalchemy import select

from app.models import AuditEvent
from app.models.checklist import ChecklistResponse
from app.models.construction import ConstructionExamination, ConstructionItem
from app.models.review import ApprovalAction, CorrectionRequest
from app.models.testing import (
    EnvironmentReading,
    SessionTestRequirement,
    TestObservation,
    TestRun,
    TestRunEquipment,
    TestSession,
)
from app.repositories.testing import TestingRepository


class ReviewRepository(TestingRepository):
    async def approval_actions(self, session_id):
        statement = (
            select(ApprovalAction)
            .where(ApprovalAction.test_session_id == session_id)
            .order_by(ApprovalAction.created_at, ApprovalAction.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def corrections(self, session_id, *, lock=False):
        statement = (
            select(CorrectionRequest)
            .where(CorrectionRequest.test_session_id == session_id)
            .order_by(CorrectionRequest.requested_at, CorrectionRequest.id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def open_corrections(self, session_id, *, lock=False):
        statement = (
            select(CorrectionRequest)
            .where(
                CorrectionRequest.test_session_id == session_id,
                CorrectionRequest.correction_status == "OPEN",
            )
            .order_by(CorrectionRequest.requested_at, CorrectionRequest.id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def current_submission(self, session_id, revision):
        rows = [
            action
            for action in await self.approval_actions(session_id)
            if action.stage == "TECHNICAL_REVIEW"
            and action.decision == "SUBMITTED"
            and action.regulatory_revision == revision
        ]
        return rows[-1] if rows else None

    async def current_technical_approval(self, session_id, revision):
        actions = await self.approval_actions(session_id)
        invalidated = {
            action.referenced_action_id
            for action in actions
            if action.stage == "TECHNICAL_REVIEW"
            and action.decision == "INVALIDATED"
            and action.referenced_action_id is not None
        }
        rows = [
            action
            for action in actions
            if action.stage == "TECHNICAL_REVIEW"
            and action.decision == "APPROVED"
            and action.regulatory_revision == revision
            and action.id not in invalidated
        ]
        return rows[-1] if rows else None

    async def observation_authors(self, session_id):
        run_ids = {
            row.id
            for row in await self.rows(
                TestRun,
                test_session_id=session_id,
            )
        }
        if not run_ids:
            return set()

        authors = set(
            (
                await self.session.scalars(
                    select(TestObservation.recorded_by)
                    .where(TestObservation.test_run_id.in_(run_ids))
                    .distinct()
                )
            ).all()
        )

        events = list(
            (
                await self.session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "test_observations",
                        AuditEvent.actor_id.is_not(None),
                        AuditEvent.action.in_(("observations.saved", "observations.deleted")),
                    )
                )
            ).all()
        )
        run_keys = {str(identifier) for identifier in run_ids}
        for event in events:
            for payload in (event.before_json, event.after_json):
                data = (payload or {}).get("data") or {}
                if str(data.get("test_run_id")) in run_keys:
                    authors.add(event.actor_id)
                    break
        return authors

    async def target_session_id(self, entity_type, identifier):
        if entity_type == "test_sessions":
            row = await self.get(TestSession, identifier)
            return row.id if row else None
        if entity_type == "session_test_requirements":
            row = await self.get(SessionTestRequirement, identifier)
            return row.test_session_id if row else None
        if entity_type == "test_runs":
            row = await self.get(TestRun, identifier)
            return row.test_session_id if row else None
        if entity_type == "test_observations":
            row = await self.get(TestObservation, identifier)
            if row is None:
                return None
            run = await self.get(TestRun, row.test_run_id)
            return run.test_session_id if run else None
        if entity_type == "environment_readings":
            row = await self.get(EnvironmentReading, identifier)
            return row.test_session_id if row else None
        if entity_type == "test_run_equipment":
            row = await self.get(TestRunEquipment, identifier)
            if row is None:
                return None
            run = await self.get(TestRun, row.test_run_id)
            return run.test_session_id if run else None
        if entity_type == "construction_examinations":
            row = await self.get(ConstructionExamination, identifier)
            return row.test_session_id if row else None
        if entity_type == "construction_items":
            row = await self.get(ConstructionItem, identifier)
            if row is None:
                return None
            examination = await self.get(
                ConstructionExamination,
                row.construction_examination_id,
            )
            return examination.test_session_id if examination else None
        if entity_type == "checklist_responses":
            row = await self.get(ChecklistResponse, identifier)
            return row.test_session_id if row else None
        return None
