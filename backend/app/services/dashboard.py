"""Phase 17 scoped dashboard service."""

from app.compliance.domain import (
    ComplianceOutcome,
    EvaluationStatus,
    WorkflowStatus,
)
from app.core.errors import denied
from app.repositories.dashboard import DashboardRepository
from app.services.authorization import AuthorizationService


class DashboardService:
    def __init__(self, session, context):
        self.session = session
        self.context = context
        self.repo = DashboardRepository(session)
        self.authz = AuthorizationService(self.repo)

    async def summary(
        self,
        actor,
        page,
        size,
        laboratory_id=None,
    ):
        async with self.session.begin():
            _, grants = await self.authz.current(actor)
            labs = grants.labs_for("dashboard:read")
            if not labs:
                raise denied()
            if laboratory_id is not None and laboratory_id not in labs:
                raise denied()

            data = await self.repo.summary(
                labs,
                page,
                size,
                laboratory_id,
            )

            workflow = {item.value: 0 for item in WorkflowStatus}
            evaluation = {item.value: 0 for item in EvaluationStatus}
            outcome = {item.value: 0 for item in ComplianceOutcome}
            report_status = {
                "UNISSUED": 0,
                "ISSUED": 0,
                "SUPERSEDED": 0,
            }

            workflow.update({key: value for key, value in data["workflow_rows"]})
            evaluation.update({key: value for key, value in data["evaluation_rows"]})
            outcome.update({key: value for key, value in data["outcome_rows"]})
            report_status.update({key: value for key, value in data["report_rows"]})

            progress_states = {
                "DRAFT",
                "INSTRUMENT_CONFIGURATION",
                "APPLICABILITY_CONFIRMED",
                "TESTING",
                "EXAMINATION",
            }
            attention_states = {
                "INCOMPLETE",
                "STALE",
                "REVIEW_REQUIRED",
            }

            activity = []
            for row in data["activity_rows"]:
                activity.append(
                    {
                        "id": row.id,
                        "laboratory_id": row.laboratory_id,
                        "actor_id": row.actor_id,
                        "actor_type": row.actor_type,
                        "action": row.action,
                        "entity_type": row.entity_type,
                        "entity_id": row.entity_id,
                        "source_revision": row.source_revision,
                        "target_revision": row.target_revision,
                        "reason": row.reason,
                        "created_at": row.created_at,
                    }
                )

            return {
                "laboratory_ids": sorted(labs),
                "session_total": sum(workflow.values()),
                "workflow_counts": workflow,
                "evaluation_counts": evaluation,
                "outcome_counts": outcome,
                "work_in_progress_count": sum(workflow[state] for state in progress_states),
                "review_pending_count": workflow["UNDER_REVIEW"],
                "approved_unissued_count": workflow["APPROVED"],
                "issued_session_count": workflow["REPORT_ISSUED"],
                "evaluation_attention_count": sum(evaluation[state] for state in attention_states),
                "report_total": sum(report_status.values()),
                "report_status_counts": report_status,
                "recent_activity": {
                    "items": activity,
                    "page": page,
                    "page_size": size,
                    "total": data["activity_total"],
                },
            }
