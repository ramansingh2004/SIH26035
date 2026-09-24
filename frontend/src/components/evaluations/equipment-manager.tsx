"use client";

import { useState } from "react";

import type { EquipmentView } from "@/lib/master-data/types";
import type { EquipmentLinkView } from "@/lib/evaluations/run-types";

function snapshotLabel(snapshot: Record<string, unknown>) {
  const reference = snapshot.reference_number;
  const serial = snapshot.serial_number;
  const model = snapshot.model;
  return (
    [reference, model, serial]
      .filter(
        (value): value is string => typeof value === "string" && Boolean(value),
      )
      .join(" · ") || "Equipment snapshot"
  );
}

export function EquipmentManager({
  available,
  linked,
  runEtag,
  canLink,
  canUnlink,
  busy,
  onLink,
  onUnlink,
}: {
  available: EquipmentView[];
  linked: EquipmentLinkView[];
  runEtag: string | null;
  canLink: boolean;
  canUnlink: boolean;
  busy: boolean;
  onLink: (
    equipment: EquipmentView,
    calibrationFile: File | null,
    runEtag: string,
  ) => Promise<void>;
  onUnlink: (row: EquipmentLinkView) => Promise<void>;
}) {
  const [equipmentId, setEquipmentId] = useState("");
  const [certificate, setCertificate] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = available.find((item) => item.id === equipmentId);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      if (!selected) throw new Error("Select equipment.");
      if (!runEtag) throw new Error("Reload the run before linking equipment.");
      await onLink(selected, certificate, runEtag);
      setEquipmentId("");
      setCertificate(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Equipment could not be linked.",
      );
    }
  }

  return (
    <section className="run-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Traceability</p>
        <h2>Test equipment</h2>
        <p>
          The backend captures an immutable calibration snapshot when equipment
          is linked. A certificate file may be uploaded and bound before the
          link is created.
        </p>
      </div>

      {canLink ? (
        <form className="equipment-link-form" onSubmit={submit}>
          <label className="form-field">
            <span>Equipment *</span>
            <select
              required
              value={equipmentId}
              onChange={(event) => setEquipmentId(event.target.value)}
            >
              <option value="">Select active equipment</option>
              {available.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.reference_number ??
                    item.serial_number ??
                    item.model ??
                    item.category}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Calibration certificate</span>
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              onChange={(event) =>
                setCertificate(event.target.files?.[0] ?? null)
              }
            />
            <small>Optional. PDF, PNG or JPEG.</small>
          </label>

          <button
            className="button button-primary"
            type="submit"
            disabled={busy || !selected}
          >
            {busy ? "Linking…" : "Link equipment"}
          </button>
        </form>
      ) : null}

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="equipment-link-list">
        {linked.map((row) => (
          <div className="equipment-link-row" key={row.id}>
            <div>
              <strong>{snapshotLabel(row.equipment_snapshot)}</strong>
              <span>
                Calibration evidence:{" "}
                {row.calibration_attachment_id ? "linked" : "not linked"}
              </span>
            </div>
            {canUnlink ? (
              <button
                className="button button-secondary button-compact"
                type="button"
                onClick={() => void onUnlink(row)}
              >
                Unlink
              </button>
            ) : null}
          </div>
        ))}
        {linked.length === 0 ? (
          <p className="muted-copy">No equipment linked to this run.</p>
        ) : null}
      </div>
    </section>
  );
}
