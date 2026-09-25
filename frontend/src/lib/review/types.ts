import type { WorkflowStatus } from "@/lib/evaluations/types";

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

export type CorrectionEntityType =
  | "test_sessions"
  | "session_test_requirements"
  | "test_runs"
  | "construction_examinations"
  | "construction_items"
  | "checklist_responses";

export type CorrectionTarget = {
  entity_type: CorrectionEntityType;
  entity_id: string;
  field_paths: string[];
};

export type CorrectionScope = {
  targets: CorrectionTarget[];
};

export type CorrectionRequestView = {
  id: string;
  test_session_id: string;
  approval_action_id: string;
  target_workflow_status: Extract<WorkflowStatus, "TESTING" | "EXAMINATION">;
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

export type CorrectionTargetOption = {
  entity_type: CorrectionEntityType;
  entity_id: string;
  label: string;
  description: string;
  allowed_fields: Array<{
    value: string;
    label: string;
  }>;
};

export type TechnicalReviewInput = {
  decision: "APPROVED" | "REJECTED";
  comment: string | null;
  reviewed_regulatory_revision: number;
};

export type ReturnForCorrectionInput = {
  target_workflow_status: "TESTING" | "EXAMINATION";
  requested_scope: CorrectionScope;
  reason: string;
};
