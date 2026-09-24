"use client";

import type { FieldSpec } from "@/lib/evaluations/test-schemas";

type Position = {
  position_code: string;
  x_mm?: string | null;
  y_mm?: string | null;
  description?: string | null;
};

type TareScenario = {
  scenario_code: string;
  tare_type: string;
  tare_value_g: string;
};

export function TypedField({
  field,
  value,
  onChange,
}: {
  field: FieldSpec;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (field.kind === "boolean" || field.kind === "tri") {
    const normalized = value === true ? "true" : value === false ? "false" : "";
    return (
      <label className="form-field">
        <span>
          {field.label}
          {field.required ? " *" : ""}
        </span>
        <select
          required={field.required}
          value={normalized}
          onChange={(event) => onChange(event.target.value)}
        >
          {!field.required || field.kind === "tri" ? (
            <option value="">Unknown / not recorded</option>
          ) : (
            <option value="">Choose…</option>
          )}
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
        {field.help ? <small>{field.help}</small> : null}
      </label>
    );
  }

  if (field.kind === "select") {
    return (
      <label className="form-field">
        <span>
          {field.label}
          {field.required ? " *" : ""}
        </span>
        <select
          required={field.required}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {!field.required ? <option value="">Not recorded</option> : null}
          {field.required ? <option value="">Choose…</option> : null}
          {(field.options ?? []).map((option) => (
            <option key={option || "none"} value={option}>
              {option || "Not applicable"}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (field.kind === "enum-list") {
    const selected = new Set(Array.isArray(value) ? value.map(String) : []);
    return (
      <fieldset className="typed-checklist">
        <legend>
          {field.label}
          {field.required ? " *" : ""}
        </legend>
        {(field.options ?? []).map((option) => (
          <label key={option}>
            <input
              type="checkbox"
              checked={selected.has(option)}
              onChange={(event) => {
                const next = new Set(selected);
                if (event.target.checked) next.add(option);
                else next.delete(option);
                onChange(Array.from(next));
              }}
            />
            <span>{option.replaceAll("_", " ")}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (field.kind === "severity-cases") {
    const rows = (Array.isArray(value) ? value : []) as Array<
      Record<string, string | null>
    >;
    const fields = [
      ["severity_id", "Severity ID", true],
      ["case", "Case", false],
      ["line_type", "Line type", false],
      ["port", "Port", false],
      ["polarity", "Polarity", false],
      ["coupling_mode", "Coupling mode", false],
      ["application_type", "Application type", false],
      ["discharge_mode", "Discharge mode", false],
      ["location", "Location", false],
      ["pulse", "Pulse", false],
      ["reduction_percent", "Reduction (%)", false],
      ["cycles", "Cycles", false],
      ["amplitude_v", "Amplitude (V)", false],
      ["duration_s", "Duration (s)", false],
      ["phase_angle_deg", "Phase angle (deg)", false],
      ["frequency_hz", "Frequency (Hz)", false],
      ["field_strength_v_per_m", "Field strength (V/m)", false],
      ["modulation_percent", "Modulation (%)", false],
      ["modulation_frequency_hz", "Modulation frequency (Hz)", false],
      ["voltage_kv", "Voltage (kV)", false],
      ["battery_voltage_v", "Battery voltage (V)", false],
      ["conducted_voltage_v", "Conducted voltage (V)", false],
      ["waveform_reference", "Waveform reference", false],
      ["standard_profile_reference", "Standard profile reference", false],
    ] as const;

    const numericKeys = new Set([
      "reduction_percent",
      "cycles",
      "amplitude_v",
      "duration_s",
      "phase_angle_deg",
      "frequency_hz",
      "field_strength_v_per_m",
      "modulation_percent",
      "modulation_frequency_hz",
      "voltage_kv",
      "battery_voltage_v",
      "conducted_voltage_v",
    ]);

    return (
      <div className="typed-repeater form-span-2">
        <div className="typed-repeater-heading">
          <strong>{field.label} *</strong>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() => onChange([...rows, { severity_id: "" }])}
          >
            Add severity case
          </button>
        </div>

        {rows.map((row, index) => (
          <div className="severity-repeater-row" key={index}>
            {fields.map(([key, label, required]) => (
              <label
                className={
                  key === "waveform_reference" ||
                  key === "standard_profile_reference"
                    ? "severity-wide"
                    : undefined
                }
                key={key}
              >
                <span>
                  {label}
                  {required ? " *" : ""}
                </span>
                <input
                  required={required}
                  inputMode={numericKeys.has(key) ? "decimal" : undefined}
                  value={row[key] ?? ""}
                  onChange={(event) => {
                    const next = [...rows];
                    next[index] = {
                      ...row,
                      [key]: event.target.value || null,
                    };
                    onChange(next);
                  }}
                />
              </label>
            ))}

            <button
              className="button button-secondary button-compact"
              type="button"
              onClick={() =>
                onChange(rows.filter((_, itemIndex) => itemIndex !== index))
              }
            >
              Remove severity
            </button>
          </div>
        ))}
      </div>
    );
  }

  if (field.kind === "positions") {
    const rows = (Array.isArray(value) ? value : []) as Position[];
    return (
      <div className="typed-repeater form-span-2">
        <div className="typed-repeater-heading">
          <strong>{field.label} *</strong>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() =>
              onChange([
                ...rows,
                {
                  position_code: "",
                  x_mm: null,
                  y_mm: null,
                  description: null,
                },
              ])
            }
          >
            Add position
          </button>
        </div>
        {rows.map((row, index) => (
          <div className="typed-repeater-row" key={index}>
            <label>
              <span>Position code</span>
              <input
                required
                value={row.position_code}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    position_code: event.target.value,
                  };
                  onChange(next);
                }}
              />
            </label>
            <label>
              <span>X (mm)</span>
              <input
                inputMode="decimal"
                value={row.x_mm ?? ""}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    x_mm: event.target.value || null,
                  };
                  onChange(next);
                }}
              />
            </label>
            <label>
              <span>Y (mm)</span>
              <input
                inputMode="decimal"
                value={row.y_mm ?? ""}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    y_mm: event.target.value || null,
                  };
                  onChange(next);
                }}
              />
            </label>
            <label>
              <span>Description</span>
              <input
                value={row.description ?? ""}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    description: event.target.value || null,
                  };
                  onChange(next);
                }}
              />
            </label>
            <button
              className="button button-secondary button-compact"
              type="button"
              onClick={() =>
                onChange(rows.filter((_, itemIndex) => itemIndex !== index))
              }
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    );
  }

  if (field.kind === "tare-scenarios") {
    const rows = (Array.isArray(value) ? value : []) as TareScenario[];
    return (
      <div className="typed-repeater form-span-2">
        <div className="typed-repeater-heading">
          <strong>{field.label} *</strong>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() =>
              onChange([
                ...rows,
                { scenario_code: "", tare_type: "", tare_value_g: "" },
              ])
            }
          >
            Add scenario
          </button>
        </div>
        {rows.map((row, index) => (
          <div className="typed-repeater-row tare-repeater-row" key={index}>
            <label>
              <span>Scenario code</span>
              <input
                required
                value={row.scenario_code}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    scenario_code: event.target.value,
                  };
                  onChange(next);
                }}
              />
            </label>
            <label>
              <span>Tare type</span>
              <input
                required
                value={row.tare_type}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    tare_type: event.target.value,
                  };
                  onChange(next);
                }}
              />
            </label>
            <label>
              <span>Tare value (g)</span>
              <input
                required
                inputMode="decimal"
                value={row.tare_value_g}
                onChange={(event) => {
                  const next = [...rows];
                  next[index] = {
                    ...row,
                    tare_value_g: event.target.value,
                  };
                  onChange(next);
                }}
              />
            </label>
            <button
              className="button button-secondary button-compact"
              type="button"
              onClick={() =>
                onChange(rows.filter((_, itemIndex) => itemIndex !== index))
              }
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    );
  }

  if (field.kind === "decimal-list" || field.kind === "string-list") {
    const text = Array.isArray(value)
      ? value.join(field.kind === "decimal-list" ? ", " : "\n")
      : String(value ?? "");
    return (
      <label className="form-field form-span-2">
        <span>
          {field.label}
          {field.required ? " *" : ""}
        </span>
        {field.kind === "string-list" ? (
          <textarea
            rows={4}
            required={field.required}
            value={text}
            onChange={(event) => onChange(event.target.value)}
          />
        ) : (
          <input
            required={field.required}
            inputMode="decimal"
            value={text}
            onChange={(event) => onChange(event.target.value)}
          />
        )}
        {field.help ? <small>{field.help}</small> : null}
      </label>
    );
  }

  const type =
    field.kind === "datetime"
      ? "datetime-local"
      : field.kind === "integer"
        ? "number"
        : "text";

  return (
    <label className="form-field">
      <span>
        {field.label}
        {field.required ? " *" : ""}
      </span>
      <input
        type={type}
        inputMode={field.kind === "decimal" ? "decimal" : undefined}
        required={field.required}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
      />
      {field.help ? <small>{field.help}</small> : null}
    </label>
  );
}
