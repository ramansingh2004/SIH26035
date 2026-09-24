"""Phase 17 bounded aggregate and recent-activity queries."""

from sqlalchemy import func, select

from app.models import AuditEvent
from app.models.report import Report
from app.models.testing import TestSession
from app.repositories.identity import IdentityRepository


class DashboardRepository(IdentityRepository):
    async def summary(self, labs, page, size, laboratory_id=None):
        scope = {laboratory_id} if laboratory_id is not None else set(labs)

        session_scope = TestSession.laboratory_id.in_(scope)
        report_scope = select(TestSession.id).where(TestSession.laboratory_id.in_(scope)).subquery()

        workflow_rows = (
            await self.session.execute(
                select(
                    TestSession.workflow_status,
                    func.count(TestSession.id),
                )
                .where(session_scope)
                .group_by(TestSession.workflow_status)
            )
        ).all()

        evaluation_rows = (
            await self.session.execute(
                select(
                    TestSession.evaluation_status,
                    func.count(TestSession.id),
                )
                .where(session_scope)
                .group_by(TestSession.evaluation_status)
            )
        ).all()

        outcome_rows = (
            await self.session.execute(
                select(
                    TestSession.compliance_outcome,
                    func.count(TestSession.id),
                )
                .where(session_scope)
                .group_by(TestSession.compliance_outcome)
            )
        ).all()

        report_rows = (
            await self.session.execute(
                select(
                    Report.report_status,
                    func.count(Report.id),
                )
                .where(Report.test_session_id.in_(select(report_scope.c.id)))
                .group_by(Report.report_status)
            )
        ).all()

        activity_base = select(AuditEvent).where(AuditEvent.laboratory_id.in_(scope))
        activity_total = await self.session.scalar(
            select(func.count()).select_from(activity_base.order_by(None).subquery())
        )
        activity_rows = list(
            (
                await self.session.scalars(
                    activity_base.order_by(
                        AuditEvent.created_at.desc(),
                        AuditEvent.id.desc(),
                    )
                    .offset((page - 1) * size)
                    .limit(size)
                )
            ).all()
        )

        return {
            "workflow_rows": workflow_rows,
            "evaluation_rows": evaluation_rows,
            "outcome_rows": outcome_rows,
            "report_rows": report_rows,
            "activity_rows": activity_rows,
            "activity_total": activity_total,
        }
