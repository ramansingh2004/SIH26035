"use client";

import { useMemo, useState } from "react";

import { TypedField } from "./typed-field";
import {
  TEST_SPECS,
  coerceField,
  procedureIdentity,
} from "@/lib/evaluations/test-schemas";
import type {
  RequirementSlotSnapshot,
  TestCode,
} from "@/lib/evaluations/run-types";

function initialValues(
  current: Record<string, unknown>,
  fields: ReturnType<typeof procedureFields>,
) {
  const output: Record<string, unknown> = {};
  for (const field of fields) {
    output[field.key] = current[field.key] ?? defaultValue(field.kind);
  }
  return output;
}

function procedureFields(code: TestCode) {
  return TEST_SPECS[code]?.procedure ?? [];
}

function defaultValue(kind: string): unknown {
  if (
    kind === "enum-list" ||
    kind === "positions" ||
    kind === "tare-scenarios"
  ) {
    return [];
  }
  return "";
}

export function ProcedureForm({
  testCode,
  slot,
  evaluationContext,
  procedureSchemaVersion,
  current,
  disabled,
  saving,
  onSave,
}: {
  testCode: TestCode;
  slot: RequirementSlotSnapshot;
  evaluationContext: string;
  procedureSchemaVersion: string;
  current: Record<string, unknown>;
  disabled: boolean;
  saving: boolean;
  onSave: (context: Record<string, unknown>) => Promise<void>;
}) {
  const fields = useMemo(() => procedureFields(testCode), [testCode]);
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    initialValues(current, fields),
  );
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    try {
      const context = procedureIdentity(
        testCode,
        slot,
        evaluationContext,
        procedureSchemaVersion,
      );

      for (const field of fields) {
        const value = coerceField(field, values[field.key]);
        if (
          field.required &&
          (value === null ||
            value === "" ||
            (Array.isArray(value) && value.length === 0))
        ) {
          throw new Error(`${field.label} is required.`);
        }
        if (value !== null) context[field.key] = value;
      }

      await onSave(context);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The procedure context could not be saved.",
      );
    }
  }

  return (
    <form className="run-panel" onSubmit={submit}>
      <div className="panel-heading">
        <p className="page-eyebrow">Typed procedure</p>
        <h2>Procedure metadata</h2>
        <p>
          Range, scenario, variant, schema version and protocol are pinned to
          the backend requirement. Environment, equipment and evidence are
          attached through their dedicated controls below.
        </p>
      </div>

      <div className="form-grid">
        {fields.map((field) => (
          <TypedField
            key={field.key}
            field={field}
            value={values[field.key]}
            onChange={(value) =>
              setValues((currentValues) => ({
                ...currentValues,
                [field.key]: value,
              }))
            }
          />
        ))}
      </div>

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="form-actions">
        <button
          className="button button-primary"
          type="submit"
          disabled={disabled || saving}
        >
          {saving ? "Saving…" : "Save procedure metadata"}
        </button>
      </div>
    </form>
  );
}
