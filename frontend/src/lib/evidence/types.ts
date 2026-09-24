export type EvidenceTargetType =
  | "laboratories"
  | "manufacturers"
  | "instruments"
  | "instrument_ranges"
  | "instrument_components"
  | "test_equipment"
  | "test_sessions"
  | "test_runs"
  | "test_observations"
  | "test_run_equipment"
  | "test_run_results"
  | "construction_items"
  | "checklist_responses";

export type EvidenceMimeType = "application/pdf" | "image/png" | "image/jpeg";

export type PresignResponse = {
  upload_id: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_at: string;
  target_etag: string | null;
  lock_version: number;
};

export type AttachmentView = {
  id: string;
  laboratory_id: string;
  file_name: string;
  content_type: string;
  file_size: number;
  sha256: string;
  lock_version: number;
  archived_at: string | null;
};

export type CompletedAttachment = AttachmentView & {
  link_id: string;
  target_etag: string;
};

export type AttachmentDownload = AttachmentView & {
  download_url: string;
  expires_in: number;
};
