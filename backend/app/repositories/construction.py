"""Phase 12 construction-examination queries and stable locks."""

from sqlalchemy import func, select

from app.models import Attachment, AttachmentLink, RuleDefinition
from app.models.construction import ConstructionExamination, ConstructionItem
from app.models.testing import TestSession
from app.repositories.testing import TestingRepository

PREAPPROVAL_WORKFLOWS = (
    "DRAFT",
    "INSTRUMENT_CONFIGURATION",
    "APPLICABILITY_CONFIRMED",
    "TESTING",
    "EXAMINATION",
)


class ConstructionRepository(TestingRepository):
    async def examination(self, session_id, *, lock=False):
        statement = (
            select(ConstructionExamination)
            .where(ConstructionExamination.test_session_id == session_id)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def items(self, examination_id, *, lock=False):
        statement = (
            select(ConstructionItem)
            .where(ConstructionItem.construction_examination_id == examination_id)
            .order_by(
                ConstructionItem.sort_order,
                ConstructionItem.id,
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def construction_rules(self, rule_set_id):
        statement = (
            select(RuleDefinition)
            .where(
                RuleDefinition.rule_set_id == rule_set_id,
                RuleDefinition.section_no == 16,
                RuleDefinition.rule_type == "construction_item_v1",
            )
            .order_by(RuleDefinition.rule_key, RuleDefinition.id)
        )
        return list((await self.session.scalars(statement)).all())

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

    async def evidence_counts(self, item_ids):
        if not item_ids:
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
                AttachmentLink.entity_type == "construction_items",
                AttachmentLink.entity_id.in_(item_ids),
                AttachmentLink.unlinked_at.is_(None),
                Attachment.archived_at.is_(None),
            )
            .group_by(AttachmentLink.entity_id)
        )
        return {
            entity_id: count for entity_id, count in (await self.session.execute(statement)).all()
        }
