"""Phase 13 checklist queries and stable locks."""

from sqlalchemy import func, select

from app.models import Attachment, AttachmentLink, ChecklistRule
from app.models.checklist import ChecklistResponse
from app.models.testing import TestSession
from app.repositories.testing import TestingRepository

PREAPPROVAL_WORKFLOWS = (
    "DRAFT",
    "INSTRUMENT_CONFIGURATION",
    "APPLICABILITY_CONFIRMED",
    "TESTING",
    "EXAMINATION",
)


class ChecklistRepository(TestingRepository):
    async def checklist_rules(self, rule_set_id):
        statement = (
            select(ChecklistRule)
            .where(ChecklistRule.rule_set_id == rule_set_id)
            .order_by(ChecklistRule.sort_order, ChecklistRule.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def responses(self, session_id, *, lock=False):
        statement = (
            select(ChecklistResponse)
            .where(ChecklistResponse.test_session_id == session_id)
            .order_by(ChecklistResponse.created_at, ChecklistResponse.id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def response(self, session_id, rule_id, *, lock=False):
        statement = (
            select(ChecklistResponse)
            .where(
                ChecklistResponse.test_session_id == session_id,
                ChecklistResponse.checklist_rule_id == rule_id,
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def preapproval_sessions(self, labs):
        statement = (
            select(TestSession)
            .where(
                TestSession.laboratory_id.in_(labs),
                TestSession.workflow_status.in_(PREAPPROVAL_WORKFLOWS),
            )
            .order_by(TestSession.created_at, TestSession.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def evidence_counts(self, response_ids):
        if not response_ids:
            return {}
        statement = (
            select(
                AttachmentLink.entity_id,
                func.count(AttachmentLink.id),
            )
            .join(
                Attachment,
                Attachment.id == AttachmentLink.attachment_id,
            )
            .where(
                AttachmentLink.entity_type == "checklist_responses",
                AttachmentLink.entity_id.in_(response_ids),
                AttachmentLink.unlinked_at.is_(None),
                Attachment.archived_at.is_(None),
            )
            .group_by(AttachmentLink.entity_id)
        )
        return {
            entity_id: count for entity_id, count in (await self.session.execute(statement)).all()
        }
