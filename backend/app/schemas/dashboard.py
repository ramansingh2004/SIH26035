"""Phase 17 scoped dashboard projections."""

from datetime import datetime
from uuid import UUID

from app.schemas.identity import Page, Schema


class DashboardActivityItem(Schema):
    id: UUID
    laboratory_id: UUID
    actor_id: UUID | None
    actor_type: str
    action: str
    entity_type: str
    entity_id: UUID | None
    source_revision: int | None
    target_revision: int | None
    reason: str | None
    created_at: datetime


class DashboardSummary(Schema):
    laboratory_ids: list[UUID]

    session_total: int
    workflow_counts: dict[str, int]
    evaluation_counts: dict[str, int]
    outcome_counts: dict[str, int]

    work_in_progress_count: int
    review_pending_count: int
    approved_unissued_count: int
    issued_session_count: int
    evaluation_attention_count: int

    report_total: int
    report_status_counts: dict[str, int]

    recent_activity: Page[DashboardActivityItem]
