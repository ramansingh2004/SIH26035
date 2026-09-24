"use client";

import { useState } from "react";

import type {
  EnvironmentData,
  EnvironmentView,
} from "@/lib/evaluations/run-types";

function localDateTime(iso: string): string {
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function emptyValues() {
  return {
    measured_at: "",
    temperature_c: "",
    relative_humidity_percent: "",
    barometric_pressure_hpa: "",
    phase: "",
    notes: "",
  };
}

export function EnvironmentManager({
  rows,
  runEtag,
  canCreate,
  canUpdate,
  canDelete,
  busy,
  onCreate,
  onUpdate,
  onDelete,
}: {
  rows: EnvironmentView[];
  runEtag: string | null;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  busy: boolean;
  onCreate: (data: EnvironmentData, runEtag: string) => Promise<void>;
  onUpdate: (row: EnvironmentView, data: EnvironmentData) => Promise<void>;
  onDelete: (row: EnvironmentView) => Promise<void>;
}) {
  const [editing, setEditing] = useState<EnvironmentView | null>(null);
  const [values, setValues] = useState(emptyValues());
  const [error, setError] = useState<string | null>(null);

  function beginEdit(row: EnvironmentView) {
    setEditing(row);
    setValues({
      measured_at: localDateTime(row.measured_at),
      temperature_c: row.temperature_c ?? "",
      relative_humidity_percent: row.relative_humidity_percent ?? "",
      barometric_pressure_hpa: row.barometric_pressure_hpa ?? "",
      phase: row.phase ?? "",
      notes: row.notes ?? "",
    });
  }

  function reset() {
    setEditing(null);
    setValues(emptyValues());
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const hasMeasurement = Boolean(
        values.temperature_c ||
        values.relative_humidity_percent ||
        values.barometric_pressure_hpa,
      );
      if (!hasMeasurement) {
        throw new Error("Record at least one measured environmental quantity.");
      }
      const measured = new Date(values.measured_at);
      if (Number.isNaN(measured.getTime())) {
        throw new Error("Measured-at time is required.");
      }

      const data: EnvironmentData = {
        measured_at: measured.toISOString(),
        temperature_c: values.temperature_c || null,
        relative_humidity_percent: values.relative_humidity_percent || null,
        barometric_pressure_hpa: values.barometric_pressure_hpa || null,
        phase: values.phase.trim() || null,
        notes: values.notes.trim() || null,
      };

      if (editing) {
        await onUpdate(editing, data);
      } else {
        if (!runEtag)
          throw new Error("Reload the run before recording environment.");
        await onCreate(data, runEtag);
      }
      reset();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The environment reading could not be saved.",
      );
    }
  }

  return (
    <section className="run-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Traceability</p>
        <h2>Environment readings</h2>
      </div>

      {(editing ? canUpdate : canCreate) ? (
        <form className="environment-editor" onSubmit={submit}>
          <label className="form-field">
            <span>Measured at *</span>
            <input
              type="datetime-local"
              required
              value={values.measured_at}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  measured_at: event.target.value,
                }))
              }
            />
          </label>
          <label className="form-field">
            <span>Temperature (°C)</span>
            <input
              inputMode="decimal"
              value={values.temperature_c}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  temperature_c: event.target.value,
                }))
              }
            />
          </label>
          <label className="form-field">
            <span>Relative humidity (%)</span>
            <input
              inputMode="decimal"
              value={values.relative_humidity_percent}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  relative_humidity_percent: event.target.value,
                }))
              }
            />
          </label>
          <label className="form-field">
            <span>Pressure (hPa)</span>
            <input
              inputMode="decimal"
              value={values.barometric_pressure_hpa}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  barometric_pressure_hpa: event.target.value,
                }))
              }
            />
          </label>
          <label className="form-field">
            <span>Phase</span>
            <input
              value={values.phase}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  phase: event.target.value,
                }))
              }
            />
          </label>
          <label className="form-field form-span-2">
            <span>Notes</span>
            <textarea
              rows={3}
              value={values.notes}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
            />
          </label>
          {error ? <div className="form-alert form-span-2">{error}</div> : null}
          <div className="form-actions form-span-2">
            {editing ? (
              <button
                className="button button-secondary"
                type="button"
                onClick={reset}
              >
                Cancel edit
              </button>
            ) : null}
            <button
              className="button button-primary"
              type="submit"
              disabled={busy}
            >
              {busy ? "Saving…" : editing ? "Update reading" : "Add reading"}
            </button>
          </div>
        </form>
      ) : null}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Measured</th>
              <th>Temperature</th>
              <th>RH</th>
              <th>Pressure</th>
              <th>Phase</th>
              {canUpdate || canDelete ? <th>Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.measured_at).toLocaleString()}</td>
                <td>{row.temperature_c ? `${row.temperature_c} °C` : "—"}</td>
                <td>
                  {row.relative_humidity_percent
                    ? `${row.relative_humidity_percent}%`
                    : "—"}
                </td>
                <td>
                  {row.barometric_pressure_hpa
                    ? `${row.barometric_pressure_hpa} hPa`
                    : "—"}
                </td>
                <td>{row.phase ?? "—"}</td>
                {canUpdate || canDelete ? (
                  <td>
                    <div className="table-actions">
                      {canUpdate ? (
                        <button
                          className="button button-secondary button-compact"
                          type="button"
                          onClick={() => beginEdit(row)}
                        >
                          Edit
                        </button>
                      ) : null}
                      {canDelete ? (
                        <button
                          className="button button-secondary button-compact"
                          type="button"
                          onClick={() => void onDelete(row)}
                        >
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={canUpdate || canDelete ? 6 : 5}>
                  No environment readings recorded.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
