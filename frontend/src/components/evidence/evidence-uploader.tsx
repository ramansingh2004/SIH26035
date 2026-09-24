"use client";

import { useState } from "react";

import { friendlyApiMessage } from "@/lib/api/errors";
import { downloadEvidence, uploadEvidence } from "@/lib/evidence/api";
import type {
  CompletedAttachment,
  EvidenceTargetType,
} from "@/lib/evidence/types";

type UploadState =
  "idle" | "hashing" | "uploading" | "verifying" | "complete" | "failed";

export function EvidenceUploader({
  laboratoryId,
  entityType,
  entityId,
  targetEtag,
  defaultPurpose = "supporting_document",
  onTargetChanged,
}: {
  laboratoryId: string;
  entityType: EvidenceTargetType;
  entityId: string;
  targetEtag: string | null;
  defaultPurpose?: string;
  onTargetChanged?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState(defaultPurpose);
  const [status, setStatus] = useState<UploadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<CompletedAttachment[]>([]);
  const [currentEtag, setCurrentEtag] = useState<string | null>(targetEtag);

  async function upload() {
    if (!file || !currentEtag) return;
    setError(null);

    try {
      setStatus("hashing");
      // uploadEvidence performs the SHA-256 step first, then presign/PUT/finalize.
      setStatus("uploading");
      const attachment = await uploadEvidence({
        file,
        laboratoryId,
        entityType,
        entityId,
        purpose: purpose.trim(),
        targetEtag: currentEtag,
      });
      setStatus("verifying");
      setRecent((items) => [attachment, ...items]);
      setCurrentEtag(attachment.target_etag);
      setFile(null);
      setStatus("complete");
      onTargetChanged?.();
    } catch (cause) {
      setStatus("failed");
      setError(friendlyApiMessage(cause));
      if (cause instanceof Error && cause.message) {
        setError(cause.message);
      }
    }
  }

  async function download(attachmentId: string) {
    setError(null);
    try {
      const result = await downloadEvidence(attachmentId);
      window.open(result.download_url, "_blank", "noopener,noreferrer");
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  const busy =
    status === "hashing" || status === "uploading" || status === "verifying";

  return (
    <section className="evidence-card">
      <div className="form-section-heading">
        <h2>Evidence & supporting documents</h2>
        <p>
          Files are uploaded to private object storage and finalized only after
          the backend verifies size, MIME type, SHA-256 hash, ownership and
          target version.
        </p>
      </div>

      {!currentEtag ? (
        <div className="form-alert">
          Reload this record before uploading evidence so its current ETag is
          available.
        </div>
      ) : (
        <div className="evidence-upload-grid">
          <label className="form-field">
            <span>Purpose</span>
            <input
              value={purpose}
              pattern="^[a-z0-9][a-z0-9_.-]*$"
              onChange={(event) => setPurpose(event.target.value.toLowerCase())}
            />
          </label>
          <label className="form-field">
            <span>File</span>
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setStatus("idle");
                setError(null);
              }}
            />
            <small>PDF, PNG or JPEG · maximum 25 MiB</small>
          </label>
          <button
            className="button button-primary"
            type="button"
            disabled={
              busy ||
              !file ||
              !purpose.trim() ||
              !/^[a-z0-9][a-z0-9_.-]*$/.test(purpose)
            }
            onClick={() => void upload()}
          >
            {busy ? "Uploading & verifying…" : "Upload evidence"}
          </button>
        </div>
      )}

      {status !== "idle" ? (
        <div className={`upload-status upload-status-${status}`} role="status">
          <strong>
            {status === "hashing"
              ? "Calculating SHA-256"
              : status === "uploading"
                ? "Uploading to private storage"
                : status === "verifying"
                  ? "Backend verification"
                  : status === "complete"
                    ? "Upload completed"
                    : "Upload failed"}
          </strong>
          <span>
            {status === "complete"
              ? "The backend finalized and linked the immutable evidence object."
              : "No evidence is accepted until backend finalization succeeds."}
          </span>
        </div>
      ) : null}

      {error ? (
        <div className="form-alert" role="alert">
          {error}
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div className="recent-evidence">
          <h3>Recently uploaded in this view</h3>
          {recent.map((attachment) => (
            <div className="evidence-row" key={attachment.id}>
              <div>
                <strong>{attachment.file_name}</strong>
                <span>
                  {attachment.content_type} ·{" "}
                  {Math.ceil(attachment.file_size / 1024)} KiB
                </span>
                <code>{attachment.sha256}</code>
              </div>
              <button
                className="button button-secondary button-compact"
                type="button"
                onClick={() => void download(attachment.id)}
              >
                Download
              </button>
            </div>
          ))}
          <p className="detail-note">
            The current API exposes secure upload/finalization/download but no
            target-scoped evidence-list endpoint. This panel therefore shows
            uploads completed during the current view only.
          </p>
        </div>
      ) : null}
    </section>
  );
}
