"""Session SQL and consistent parent-first row locking."""

from sqlalchemy import func, or_, select

from app.models import (
    Attachment,
    AttachmentLink,
    Instrument,
    InstrumentComponent,
    InstrumentRange,
    Manufacturer,
)
from app.models.report import Report
from app.models.testing import (
    SessionTestRequirement,
    TestRun,
    TestRunResult,
    TestSession,
    TestSessionSection,
)
from app.repositories.foundations import FoundationRepository


def _escaped_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TestingRepository(FoundationRepository):
    async def rows(self, model, **filters):
        statement = select(model).filter_by(**filters).order_by(model.id)
        return list((await self.session.scalars(statement)).all())

    async def sessions(self, labs, page, size, filters):
        query = (
            select(TestSession)
            .join(
                Instrument,
                Instrument.id == TestSession.instrument_id,
            )
            .join(
                Manufacturer,
                Manufacturer.id == Instrument.manufacturer_id,
            )
            .outerjoin(
                Report,
                Report.test_session_id == TestSession.id,
            )
            .where(TestSession.laboratory_id.in_(labs))
        )

        for field, value in filters.items():
            if value is None or field in {"search", "report_number"}:
                continue
            if field == "created_from":
                query = query.where(TestSession.created_at >= value)
            elif field == "created_to":
                query = query.where(TestSession.created_at <= value)
            else:
                query = query.where(getattr(TestSession, field) == value)

        report_number = filters.get("report_number")
        if report_number is not None:
            query = query.where(Report.report_number == report_number)

        search = filters.get("search")
        if search:
            escaped = _escaped_search(search)
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    TestSession.application_number.ilike(pattern, escape="\\"),
                    Report.report_number.ilike(pattern, escape="\\"),
                    Instrument.model_name.ilike(pattern, escape="\\"),
                    Instrument.serial_number.ilike(pattern, escape="\\"),
                    Instrument.type_designation.ilike(pattern, escape="\\"),
                    Manufacturer.name.ilike(pattern, escape="\\"),
                )
            )

        return await self.page(
            query.order_by(TestSession.created_at.desc(), TestSession.id),
            page,
            size,
        )

    async def session_revisions(self, root_session_id, page, size):
        statement = (
            select(TestSession)
            .where(TestSession.root_session_id == root_session_id)
            .order_by(
                TestSession.session_revision_no,
                TestSession.created_at,
                TestSession.id,
            )
        )
        return await self.page(statement, page, size)

    async def retest_runs(self, requirement_id, page, size):
        statement = (
            select(TestRun)
            .where(TestRun.requirement_id == requirement_id)
            .order_by(
                TestRun.run_no,
                TestRun.created_at,
                TestRun.id,
            )
        )
        return await self.page(statement, page, size)

    async def result_events(self, result_ids):
        if not result_ids:
            return []
        from app.models.testing import EvaluationResultEvent

        return list(
            (
                await self.session.scalars(
                    select(EvaluationResultEvent)
                    .where(EvaluationResultEvent.result_id.in_(result_ids))
                    .order_by(
                        EvaluationResultEvent.created_at,
                        EvaluationResultEvent.id,
                    )
                )
            ).all()
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
