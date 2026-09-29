"use client";

import { useState } from "react";

import { friendlyApiMessage } from "@/lib/api/errors";
import {
  downloadEvidence,
  unlinkEvidence,
  uploadEvidence,
} from "@/lib/evidence/api";
import type {
  CompletedAttachment,
  EvidenceTargetType,
  LinkedEvidence,
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
  existing = [],
  canUpload = true,
  canUnlink = false,
}: {
  laboratoryId: string;
  entityType: EvidenceTargetType;
  entityId: string;
  targetEtag: string | null;
  defaultPurpose?: string;
  onTargetChanged?: () => void;
  existing?: LinkedEvidence[];
  canUpload?: boolean;
  canUnlink?: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState(defaultPurpose);
  const [status, setStatus] = useState<UploadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<CompletedAttachment[]>([]);
  const [removingLinkId, setRemovingLinkId] = useState<string | null>(null);

  async function upload() {
    if (!file || !targetEtag) return;
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
        targetEtag,
      });
      setStatus("verifying");
      setRecent((items) => [attachment, ...items]);
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

  async function unlink(attachment: LinkedEvidence) {
    if (!targetEtag) {
      setError("Reload this record before unlinking evidence.");
      return;
    }

    const reason = window.prompt(
      "Reason for unlinking this evidence:",
      "Duplicate evidence uploaded during manual UI test",
    );
    if (!reason?.trim()) return;

    setError(null);
    setRemovingLinkId(attachment.link_id);
    try {
      await unlinkEvidence({
        attachmentId: attachment.id,
        linkId: attachment.link_id,
        targetEtag,
        reason: reason.trim(),
      });
      setStatus("idle");
      setFile(null);
      setRecent((items) =>
        items.filter((item) => item.id !== attachment.id),
      );
      onTargetChanged?.();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setRemovingLinkId(null);
    }
  }

  const busy =
    status === "hashing" || status === "uploading" || status === "verifying";
  const existingIds = new Set(existing.map((item) => item.id));
  const recentOnly = recent.filter((item) => !existingIds.has(item.id));

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

      {canUpload ? (
        !targetEtag ? (
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
                onChange={(event) =>
                  setPurpose(event.target.value.toLowerCase())
                }
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
        )
      ) : null}

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

      {existing.length > 0 ? (
        <div className="recent-evidence">
          <h3>Linked evidence</h3>
          {existing.map((attachment) => (
            <div className="evidence-row" key={attachment.link_id}>
              <div>
                <strong>{attachment.file_name}</strong>
                <span>
                  {attachment.purpose} · {attachment.content_type} ·{" "}
                  {Math.ceil(attachment.file_size / 1024)} KiB
                </span>
                <code>{attachment.sha256}</code>
              </div>
              <div className="table-actions">
                <button
                  className="button button-secondary button-compact"
                  type="button"
                  onClick={() => void download(attachment.id)}
                >
                  Download
                </button>
                {canUnlink ? (
                  <button
                    className="button button-secondary button-compact"
                    type="button"
                    disabled={removingLinkId === attachment.link_id}
                    onClick={() => void unlink(attachment)}
                  >
                    {removingLinkId === attachment.link_id
                      ? "Unlinking…"
                      : "Unlink"}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="detail-note">No evidence is linked to this record.</p>
      )}

      {recentOnly.length > 0 ? (
        <div className="recent-evidence">
          <h3>Recently uploaded in this view</h3>
          {recentOnly.map((attachment) => (
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
        </div>
      ) : null}
    </section>
  );
}
