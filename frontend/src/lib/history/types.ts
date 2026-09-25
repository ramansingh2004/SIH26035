import type {
  ComplianceOutcome,
  EvaluationStatus,
  SessionView,
  WorkflowStatus,
} from "@/lib/evaluations/types";
import type { Page } from "@/lib/master-data/types";
import type { ReportStatus } from "@/lib/reports/types";

export type ApprovalStage = "TECHNICAL_REVIEW" | "FINAL_APPROVAL";

export type ApprovalDecision =
  | "SUBMITTED"
  | "APPROVED"
  | "REJECTED"
  | "RETURNED_FOR_CORRECTION"
  | "INVALIDATED";

export type ApprovalActionView = {
  id: string;
  test_session_id: string;
  stage: ApprovalStage;
  decision: ApprovalDecision;
  actor_id: string;
  regulatory_revision: number;
  scope_json: Record<string, unknown>;
  referenced_action_id: string | null;
  comment: string | null;
  reason: string | null;
  created_at: string;
};

export type CorrectionRequestView = {
  id: string;
  test_session_id: string;
  approval_action_id: string;
  target_workflow_status: "TESTING" | "EXAMINATION";
  requested_scope_json: Record<string, unknown>;
  reason: string;
  requested_by: string;
  requested_at: string;
  correction_status: "OPEN" | "RESOLVED" | "CANCELLED";
  resolved_at: string | null;
  lock_version: number;
  created_at: string;
  updated_at: string;
};

export type InstrumentHistoryItem = {
  session_id: string;
  root_session_id: string;
  parent_session_id: string | null;
  session_revision_no: number;
  revision_reason: string | null;
  application_number: string | null;

  workflow_status: WorkflowStatus;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  regulatory_revision: number;
  session_created_at: string;

  run_count: number;
  retest_count: number;

  report_id: string | null;
  report_number: string | null;
  report_revision_no: number | null;
  report_status: ReportStatus | null;
  supersedes_report_id: string | null;
  report_issued_at: string | null;
};

export type SessionRevisionPage = Page<SessionView>;
export type InstrumentHistoryPage = Page<InstrumentHistoryItem>;
