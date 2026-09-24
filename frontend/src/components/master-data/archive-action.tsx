"use client";

import { useState } from "react";

import { friendlyApiMessage } from "@/lib/api/errors";

export function ArchiveAction({
  label,
  disabled = false,
  onArchive,
}: {
  label: string;
  disabled?: boolean;
  onArchive: (reason: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!reason.trim()) return;
    setPending(true);
    setError(null);
    try {
      await onArchive(reason.trim());
      setExpanded(false);
      setReason("");
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setPending(false);
    }
  }

  if (!expanded) {
    return (
      <button
        className="button button-danger"
        type="button"
        disabled={disabled}
        onClick={() => setExpanded(true)}
      >
        Archive
      </button>
    );
  }

  return (
    <div className="archive-panel">
      <strong>Archive {label}?</strong>
      <p>
        Historical records remain preserved. Archived master data becomes
        read-only.
      </p>
      <label className="form-field">
        <span>Reason *</span>
        <textarea
          rows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      {error ? <div className="form-alert">{error}</div> : null}
      <div className="archive-actions">
        <button
          className="button button-secondary"
          type="button"
          disabled={pending}
          onClick={() => setExpanded(false)}
        >
          Cancel
        </button>
        <button
          className="button button-danger"
          type="button"
          disabled={pending || !reason.trim()}
          onClick={() => void submit()}
        >
          {pending ? "Archiving…" : "Confirm archive"}
        </button>
      </div>
    </div>
  );
}
