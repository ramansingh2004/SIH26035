export type DashboardActivityItem = {
  id: string;
  laboratory_id: string;
  actor_id: string | null;
  actor_type: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  source_revision: number | null;
  target_revision: number | null;
  reason: string | null;
  created_at: string;
};

export type DashboardSummary = {
  laboratory_ids: string[];
  session_total: number;
  workflow_counts: Record<string, number>;
  evaluation_counts: Record<string, number>;
  outcome_counts: Record<string, number>;
  work_in_progress_count: number;
  review_pending_count: number;
  approved_unissued_count: number;
  issued_session_count: number;
  evaluation_attention_count: number;
  report_total: number;
  report_status_counts: Record<string, number>;
  recent_activity: {
    items: DashboardActivityItem[];
    page: number;
    page_size: number;
    total: number;
  };
};
