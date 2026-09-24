"""Phase 16 reporting queries, numbering and lock ownership."""

from sqlalchemy import func, select, text

from app.models.foundations import Attachment
from app.models.report import (
    Report,
    ReportFile,
    ReportGeneration,
    ReportPreview,
)
from app.models.review import SessionApprovalSnapshot
from app.models.testing import TestSession
from app.repositories.foundations import FoundationRepository


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
