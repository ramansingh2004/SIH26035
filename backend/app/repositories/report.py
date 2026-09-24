"""Phase 16/17 reporting queries, numbering, search and lock ownership."""

from sqlalchemy import func, or_, select, text

from app.models.foundations import Attachment
from app.models.master_data import Instrument, Manufacturer
from app.models.report import (
    Report,
    ReportFile,
    ReportGeneration,
    ReportPreview,
)
from app.models.review import SessionApprovalSnapshot
from app.models.testing import TestSession
from app.repositories.foundations import FoundationRepository


def _escaped_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ReportRepository(FoundationRepository):
    async def test_session(self, identifier, *, lock=False):
        statement = (
            select(TestSession)
            .where(TestSession.id == identifier)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def preview(self, identifier, *, lock=False):
        statement = (
            select(ReportPreview)
            .where(ReportPreview.id == identifier)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def report(self, identifier, *, lock=False):
        statement = (
            select(Report).where(Report.id == identifier).execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def report_for_session(self, session_id):
        return await self.session.scalar(select(Report).where(Report.test_session_id == session_id))

    async def generation(self, identifier, *, lock=False):
        statement = (
            select(ReportGeneration)
            .where(ReportGeneration.id == identifier)
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def generations(self, report_id):
        return list(
            (
                await self.session.scalars(
                    select(ReportGeneration)
                    .where(ReportGeneration.report_id == report_id)
                    .order_by(
                        ReportGeneration.attempt_no,
                        ReportGeneration.id,
                    )
                )
            ).all()
        )

    async def files(self, generation_id):
        return list(
            (
                await self.session.scalars(
                    select(ReportFile)
                    .where(ReportFile.report_generation_id == generation_id)
                    .order_by(ReportFile.format, ReportFile.id)
                )
            ).all()
        )

    async def attachment(self, identifier):
        return await self.session.get(Attachment, identifier)

    async def approval_snapshot(self, session_id):
        return await self.session.scalar(
            select(SessionApprovalSnapshot).where(
                SessionApprovalSnapshot.test_session_id == session_id
            )
        )

    async def next_number(self, year):
        sequence = await self.session.scalar(
            text(
                """
                INSERT INTO report_number_counters (
                    year,
                    next_sequence,
                    lock_version
                )
                VALUES (:year, 2, 1)
                ON CONFLICT (year) DO UPDATE
                SET
                    next_sequence = report_number_counters.next_sequence + 1,
                    lock_version = report_number_counters.lock_version + 1
                RETURNING next_sequence - 1
                """
            ),
            {"year": year},
        )
        return f"R76-{year}-{sequence}"

    async def next_attempt(self, report_id):
        return await self.session.scalar(
            select(
                func.coalesce(
                    func.max(ReportGeneration.attempt_no),
                    0,
                )
                + 1
            ).where(ReportGeneration.report_id == report_id)
        )

    async def series_lock(self, report_number):
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": "report-series:" + report_number},
        )

    async def current_issued(self, report_number):
        return await self.session.scalar(
            select(Report)
            .where(
                Report.report_number == report_number,
                Report.report_status == "ISSUED",
            )
            .with_for_update()
        )

    async def revisions(self, report_number):
        return list(
            (
                await self.session.scalars(
                    select(Report)
                    .where(Report.report_number == report_number)
                    .order_by(Report.revision_no, Report.id)
                )
            ).all()
        )

    async def revisions_page(self, report_number, page, size):
        statement = (
            select(Report)
            .where(Report.report_number == report_number)
            .order_by(
                Report.revision_no,
                Report.created_at,
                Report.id,
            )
        )
        return await self.page(statement, page, size)

    async def search(self, labs, page, size, filters):
        query = (
            select(
                Report,
                TestSession,
                Instrument,
                Manufacturer,
            )
            .join(
                TestSession,
                TestSession.id == Report.test_session_id,
            )
            .join(
                Instrument,
                Instrument.id == TestSession.instrument_id,
            )
            .join(
                Manufacturer,
                Manufacturer.id == Instrument.manufacturer_id,
            )
            .where(TestSession.laboratory_id.in_(labs))
        )

        exact = {
            "laboratory_id": TestSession.laboratory_id,
            "manufacturer_id": Instrument.manufacturer_id,
            "instrument_id": TestSession.instrument_id,
            "report_number": Report.report_number,
            "workflow_status": TestSession.workflow_status,
            "evaluation_status": TestSession.evaluation_status,
            "compliance_outcome": TestSession.compliance_outcome,
            "report_status": Report.report_status,
        }
        for key, column in exact.items():
            value = filters.get(key)
            if value is not None:
                query = query.where(column == value)

        created_from = filters.get("created_from")
        if created_from is not None:
            query = query.where(Report.created_at >= created_from)
        created_to = filters.get("created_to")
        if created_to is not None:
            query = query.where(Report.created_at <= created_to)

        search = filters.get("search")
        if search:
            escaped = _escaped_search(search)
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    Report.report_number.ilike(pattern, escape="\\"),
                    TestSession.application_number.ilike(pattern, escape="\\"),
                    Manufacturer.name.ilike(pattern, escape="\\"),
                    Instrument.model_name.ilike(pattern, escape="\\"),
                    Instrument.serial_number.ilike(pattern, escape="\\"),
                    Instrument.type_designation.ilike(pattern, escape="\\"),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        rows = (
            await self.session.execute(
                query.order_by(
                    Report.created_at.desc(),
                    Report.report_number.desc(),
                    Report.revision_no.desc(),
                    Report.id,
                )
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
        return rows, total
