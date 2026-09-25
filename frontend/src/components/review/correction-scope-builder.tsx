"use client";

import { useMemo, useState } from "react";

import type {
  CorrectionTarget,
  CorrectionTargetOption,
  ReturnForCorrectionInput,
} from "@/lib/review/types";

type Selection = Record<string, Set<string>>;

function identity(option: CorrectionTargetOption) {
  return `${option.entity_type}:${option.entity_id}`;
}

function selectedTargets(
  options: CorrectionTargetOption[],
  selection: Selection,
): CorrectionTarget[] {
  const byIdentity = new Map(
    options.map((option) => [identity(option), option]),
  );

  return Object.entries(selection)
    .filter(([, fieldSet]) => fieldSet.size > 0)
    .map(([key, fieldSet]) => {
      const option = byIdentity.get(key);
      if (!option) {
        throw new Error("Correction target is no longer available.");
      }
      return {
        entity_type: option.entity_type,
        entity_id: option.entity_id,
        field_paths: Array.from(fieldSet).sort(),
      };
    });
}

export function CorrectionScopeBuilder({
  options,
  submitting,
  onSubmit,
}: {
  options: CorrectionTargetOption[];
  submitting: boolean;
  onSubmit: (data: ReturnForCorrectionInput) => Promise<void>;
}) {
  const [workflow, setWorkflow] = useState<"TESTING" | "EXAMINATION">(
    "TESTING",
  );
  const [reason, setReason] = useState("");
  const [selection, setSelection] = useState<Selection>({});
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return options;
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(value) ||
        option.description.toLowerCase().includes(value),
    );
  }, [options, search]);

  function toggleTarget(option: CorrectionTargetOption, checked: boolean) {
    const key = identity(option);
    setSelection((current) => {
      const next = { ...current };
      if (checked) next[key] = new Set();
      else delete next[key];
      return next;
    });

    if (
      checked &&
      (option.entity_type === "construction_examinations" ||
        option.entity_type === "construction_items" ||
        option.entity_type === "checklist_responses")
    ) {
      setWorkflow("EXAMINATION");
    }
  }

  function toggleField(
    option: CorrectionTargetOption,
    field: string,
    checked: boolean,
  ) {
    const key = identity(option);
    setSelection((current) => {
      const next = { ...current };
      const values = new Set(next[key] ?? []);
      if (checked) values.add(field);
      else values.delete(field);
      next[key] = values;
      return next;
    });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    try {
      const targets = selectedTargets(options, selection);
      if (targets.length === 0) {
        throw new Error(
          "Choose at least one real session target and one permitted field.",
        );
      }
      if (!reason.trim()) throw new Error("Correction reason is required.");

      await onSubmit({
        target_workflow_status: workflow,
        requested_scope: { targets },
        reason: reason.trim(),
      });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The correction request could not be created.",
      );
    }
  }

  return (
    <form className="correction-builder" onSubmit={submit}>
      <div className="correction-builder-head">
        <div>
          <strong>Bounded correction scope</strong>
          <span>
            Only backend-supported fields on records that belong to this
            evaluation can be requested.
          </span>
        </div>
        <label className="form-field">
          <span>Return workflow *</span>
          <select
            value={workflow}
            onChange={(event) =>
              setWorkflow(event.target.value as "TESTING" | "EXAMINATION")
            }
          >
            <option value="TESTING">Testing</option>
            <option value="EXAMINATION">Examination</option>
          </select>
        </label>
      </div>

      <label className="form-field">
        <span>Find target</span>
        <input
          value={search}
          placeholder="Requirement, run, construction or checklist…"
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>

      <div className="correction-target-list">
        {filtered.map((option) => {
          const key = identity(option);
          const selected = selection[key];
          return (
            <div className="correction-target-card" key={key}>
              <label className="correction-target-heading">
                <input
                  type="checkbox"
                  checked={selected !== undefined}
                  onChange={(event) =>
                    toggleTarget(option, event.target.checked)
                  }
                />
                <span>
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
              </label>

              {selected !== undefined ? (
                <div className="correction-field-grid">
                  {option.allowed_fields.map((field) => (
                    <label key={field.value}>
                      <input
                        type="checkbox"
                        checked={selected.has(field.value)}
                        onChange={(event) =>
                          toggleField(
                            option,
                            field.value,
                            event.target.checked,
                          )
                        }
                      />
                      <span>{field.label}</span>
                    </label>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <label className="form-field">
        <span>Reason *</span>
        <textarea
          rows={4}
          maxLength={4000}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="form-actions">
        <button
          className="button button-secondary"
          type="submit"
          disabled={submitting}
        >
          {submitting ? "Returning…" : "Return for scoped correction"}
        </button>
      </div>
    </form>
  );
}
