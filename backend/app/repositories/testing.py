"""Session SQL and consistent parent-first row locking."""

from sqlalchemy import func, select

from app.models import Attachment, AttachmentLink, InstrumentComponent, InstrumentRange
from app.models.testing import (
    SessionTestRequirement,
    TestRun,
    TestRunResult,
    TestSession,
    TestSessionSection,
)
from app.repositories.foundations import FoundationRepository


class TestingRepository(FoundationRepository):
    async def rows(self, model, **filters):
        statement = select(model).filter_by(**filters).order_by(model.id)
        return list((await self.session.scalars(statement)).all())

    async def sessions(self, labs, page, size, filters):
        query = select(TestSession).where(TestSession.laboratory_id.in_(labs))
        for field, value in filters.items():
            if value is None:
                continue
            if field == "created_from":
                query = query.where(TestSession.created_at >= value)
            elif field == "created_to":
                query = query.where(TestSession.created_at <= value)
            else:
                query = query.where(getattr(TestSession, field) == value)
        return await self.page(
            query.order_by(TestSession.created_at.desc(), TestSession.id), page, size
        )

    async def instrument_children(self, instrument_id):
        return (
            await self.rows(InstrumentRange, instrument_id=instrument_id, is_active=True),
            await self.rows(InstrumentComponent, instrument_id=instrument_id, is_active=True),
        )

    async def sections(self, identifier):
        return sorted(
            await self.rows(TestSessionSection, test_session_id=identifier),
            key=lambda r: r.section_number,
        )

    async def requirements(self, identifier):
        return await self.rows(SessionTestRequirement, test_session_id=identifier)

    async def runs(self, identifier):
        return await self.rows(TestRun, test_session_id=identifier)

    async def results(self, identifier):
        return sorted(
            await self.rows(TestRunResult, test_run_id=identifier),
            key=lambda r: r.evaluation_version,
        )

    async def next_revision(self, root):
        return 1 + (
            await self.session.scalar(
                select(func.max(TestSession.session_revision_no)).where(
                    TestSession.root_session_id == root
                )
            )
        )

    async def evidence(self, targets):
        from sqlalchemy import or_

        query = (
            select(Attachment, AttachmentLink)
            .join(AttachmentLink, AttachmentLink.attachment_id == Attachment.id)
            .where(
                AttachmentLink.unlinked_at.is_(None),
                Attachment.archived_at.is_(None),
                or_(
                    *(
                        (AttachmentLink.entity_type == kind)
                        & (AttachmentLink.entity_id == identifier)
                        for kind, identifier in targets
                    )
                ),
            )
        )
        return list((await self.session.execute(query.order_by(Attachment.id))).all())

    async def delete(self, row):
        await self.session.delete(row)
