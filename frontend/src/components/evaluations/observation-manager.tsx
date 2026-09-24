"use client";

import { useMemo, useState } from "react";

import { TypedField } from "./typed-field";
import { TEST_SPECS, buildObservation } from "@/lib/evaluations/test-schemas";
import type {
  ObservationData,
  ObservationView,
  TestCode,
} from "@/lib/evaluations/run-types";

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function initialObservationValues(
  row: ObservationView | null,
): Record<string, unknown> {
  if (!row) return {};
  const output = { ...row.payload };
  delete output.test_code;
  delete output.protocol;
  delete output.observation_schema_version;
  delete output.sequence_no;
  return output;
}

export function ObservationManager({
  testCode,
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
  testCode: TestCode;
  rows: ObservationView[];
  runEtag: string | null;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  busy: boolean;
  onCreate: (data: ObservationData, runEtag: string) => Promise<void>;
  onUpdate: (row: ObservationView, data: ObservationData) => Promise<void>;
  onDelete: (row: ObservationView) => Promise<void>;
}) {
  const spec = TEST_SPECS[testCode]!;
  const [editing, setEditing] = useState<ObservationView | null>(null);
  const [sequence, setSequence] = useState(
    rows.length ? Math.max(...rows.map((row) => row.sequence_no)) + 1 : 1,
  );
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);

  const fields = useMemo(() => spec.observation, [spec.observation]);

  function beginEdit(row: ObservationView) {
    setEditing(row);
    setSequence(row.sequence_no);
    setValues(initialObservationValues(row));
    setError(null);
  }

  function reset() {
    setEditing(null);
    setValues({});
    setSequence(
      rows.length ? Math.max(...rows.map((row) => row.sequence_no)) + 1 : 1,
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const data = buildObservation(testCode, sequence, values);
      if (editing) {
        await onUpdate(editing, data);
      } else {
        if (!runEtag) {
          throw new Error("Reload the run before recording an observation.");
        }
        await onCreate(data, runEtag);
      }
      reset();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The observation could not be saved.",
      );
    }
  }

  return (
    <section className="run-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Typed observations</p>
        <h2>{spec.label} observations</h2>
        <p>
          Metrological values remain decimal strings until the backend
          deterministic engine evaluates the captured input.
        </p>
      </div>

      {(editing ? canUpdate : canCreate) ? (
        <form className="observation-editor" onSubmit={submit}>
          <label className="form-field">
            <span>Sequence number *</span>
            <input
              type="number"
              min="1"
              required
              disabled={Boolean(editing)}
              value={sequence}
              onChange={(event) =>
                setSequence(Number.parseInt(event.target.value || "1", 10))
              }
            />
          </label>

          {fields.map((field) => (
            <TypedField
              key={field.key}
              field={field}
              value={values[field.key]}
              onChange={(value) =>
                setValues((current) => ({
                  ...current,
                  [field.key]: value,
                }))
              }
            />
          ))}

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
              {busy
                ? "Saving…"
                : editing
                  ? "Update observation"
                  : "Add observation"}
            </button>
          </div>
        </form>
      ) : null}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Seq.</th>
              {fields.slice(0, 4).map((field) => (
                <th key={field.key}>{field.label}</th>
              ))}
              <th>Recorded</th>
              <th>State</th>
              {canUpdate || canDelete ? <th>Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.sequence_no}</td>
                {fields.slice(0, 4).map((field) => (
                  <td key={field.key}>
                    {displayValue(row.payload[field.key])}
                  </td>
                ))}
                <td>{new Date(row.recorded_at).toLocaleString()}</td>
                <td>{row.is_locked ? "Locked" : "Editable"}</td>
                {canUpdate || canDelete ? (
                  <td>
                    <div className="table-actions">
                      {canUpdate ? (
                        <button
                          className="button button-secondary button-compact"
                          type="button"
                          disabled={row.is_locked}
                          onClick={() => beginEdit(row)}
                        >
                          Edit
                        </button>
                      ) : null}
                      {canDelete ? (
                        <button
                          className="button button-secondary button-compact"
                          type="button"
                          disabled={row.is_locked}
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
                <td
                  colSpan={
                    3 +
                    Math.min(4, fields.length) +
                    (canUpdate || canDelete ? 1 : 0)
                  }
                >
                  No observations recorded.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
