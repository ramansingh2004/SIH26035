import type {
  ComplianceOutcome,
  EvaluationStatus,
  WorkflowStatus,
} from "@/lib/evaluations/types";
import type { Page } from "@/lib/master-data/types";

export type ReportStatus = "UNISSUED" | "ISSUED" | "SUPERSEDED";
export type GenerationStatus = "GENERATING" | "READY" | "FAILED";
export type PreviewStatus = "GENERATING" | "READY" | "FAILED";
export type ReportFormat = "pdf" | "docx";

export type ReportView = {
  id: string;
  test_session_id: string;
  report_number: string;
  revision_no: number;
  root_report_id: string;
  supersedes_report_id: string | null;
  revision_reason: string | null;
  report_status: ReportStatus;
  selected_generation_id: string | null;
  issued_at: string | null;
  issued_by: string | null;
  issuance_manifest: Record<string, unknown> | null;
  report_hash: string | null;
  created_at: string;
  created_by: string;
  lock_version: number;
};

export type ReportGenerationView = {
  id: string;
  report_id: string;
  attempt_no: number;
  generation_status: GenerationStatus;
  report_context_snapshot: Record<string, unknown>;
  context_schema_version: 1;
  context_hash: string;
  source_regulatory_revision: number;
  intended_issuer_id: string;
  planned_issue_date: string;
  template_version: string;
  renderer_manifest: Record<string, unknown>;
  report_hash: string | null;
  error_code: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ReportPreviewView = {
  id: string;
  test_session_id: string;
  source_regulatory_revision: number;
  preview_context_snapshot: Record<string, unknown>;
  preview_status: PreviewStatus;
  requested_by: string;
  requested_at: string;
  expires_at: string;
  context_hash: string;
  file_attachment_ids: Record<string, unknown>;
  error_code: string | null;
};

export type ReportGenerationResponse = {
  report: ReportView;
  generation: ReportGenerationView;
  files: Array<{
    id: string;
    report_generation_id: string;
    format: "PDF" | "DOCX";
    attachment_id: string;
    file_hash: string;
    generated_at: string;
  }>;
};

export type ReportRepositoryItem = {
  id: string;
  test_session_id: string;
  laboratory_id: string;
  instrument_id: string;
  manufacturer_id: string;
  manufacturer_name: string;
  instrument_model_name: string;
  instrument_serial_number: string | null;
  application_number: string | null;
  workflow_status: WorkflowStatus;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  report_number: string;
  revision_no: number;
  root_report_id: string;
  supersedes_report_id: string | null;
  revision_reason: string | null;
  report_status: ReportStatus;
  issued_at: string | null;
  report_hash: string | null;
  created_at: string;
  is_current_issued: boolean;
  is_superseded: boolean;
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

export type ReportPage = Page<ReportRepositoryItem>;
export type ReportRevisionPage = Page<ReportView>;

export type VersionedReport = {
  item: ReportView;
  etag: string | null;
};
