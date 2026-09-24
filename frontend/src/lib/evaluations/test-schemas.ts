import type {
  ObservationData,
  RequirementSlotSnapshot,
  TestCode,
} from "./run-types";

import { DISTURBANCE_SPECS } from "./disturbance-schemas";

export type FieldKind =
  | "text"
  | "decimal"
  | "integer"
  | "datetime"
  | "boolean"
  | "tri"
  | "select"
  | "decimal-list"
  | "string-list"
  | "enum-list"
  | "positions"
  | "tare-scenarios"
  | "severity-cases";

export type FieldSpec = {
  key: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  options?: string[];
  help?: string;
};

export type TestFormSpec = {
  label: string;
  protocol: string;
  procedure: FieldSpec[];
  observation: FieldSpec[];
};

const measuredAt: FieldSpec = {
  key: "measured_at",
  label: "Measured at",
  kind: "datetime",
  required: true,
};

const stabilized: FieldSpec = {
  key: "stabilized",
  label: "Stabilized",
  kind: "tri",
};

const weighingFields: FieldSpec[] = [
  { key: "load_g", label: "Load (g)", kind: "decimal", required: true },
  {
    key: "indication_g",
    label: "Indication (g)",
    kind: "decimal",
    required: true,
  },
  {
    key: "additional_load_g",
    label: "Additional load (g)",
    kind: "decimal",
    required: true,
  },
  {
    key: "zero_error_g",
    label: "Zero error (g)",
    kind: "decimal",
    required: true,
  },
];

export const TEST_SPECS: Partial<Record<TestCode, TestFormSpec>> = {
  ...DISTURBANCE_SPECS,
  WEIGHING_PERFORMANCE: {
    label: "Weighing performance",
    protocol: "WEIGHING_V1",
    procedure: [
      {
        key: "stages",
        label: "Loading stages",
        kind: "enum-list",
        options: ["UP", "DOWN"],
        required: true,
      },
      { key: "preloaded", label: "Preloaded", kind: "tri" },
      {
        key: "warmed_up_seconds",
        label: "Warm-up duration (s)",
        kind: "decimal",
      },
      stabilized,
      { key: "zero_condition", label: "Zero condition", kind: "text" },
    ],
    observation: [
      ...weighingFields,
      {
        key: "direction",
        label: "Direction",
        kind: "select",
        options: ["UP", "DOWN"],
        required: true,
      },
      measuredAt,
    ],
  },
  TEMPERATURE_ZERO: {
    label: "Temperature effect on zero",
    protocol: "TEMPERATURE_ZERO_V1",
    procedure: [
      {
        key: "temperature_sequence_c",
        label: "Temperature sequence (°C)",
        kind: "decimal-list",
        required: true,
        help: "Comma-separated ordered temperature points.",
      },
      {
        key: "zero_tracking_disabled",
        label: "Zero tracking disabled",
        kind: "tri",
      },
    ],
    observation: [
      {
        key: "temperature_c",
        label: "Temperature (°C)",
        kind: "decimal",
        required: true,
      },
      {
        key: "indication_g",
        label: "Indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "additional_load_g",
        label: "Additional load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "stabilized",
        label: "Stabilized",
        kind: "boolean",
        required: true,
      },
      {
        key: "zero_tracking_active",
        label: "Zero tracking active",
        kind: "tri",
      },
      measuredAt,
    ],
  },
  ECCENTRICITY: {
    label: "Eccentricity",
    protocol: "ECCENTRICITY_V1",
    procedure: [
      {
        key: "load_receptor_type",
        label: "Load receptor type",
        kind: "text",
        required: true,
      },
      {
        key: "support_count",
        label: "Support count",
        kind: "integer",
      },
      {
        key: "display_location",
        label: "Display location",
        kind: "text",
      },
      {
        key: "positions",
        label: "Test positions",
        kind: "positions",
        required: true,
      },
    ],
    observation: [
      {
        key: "position_code",
        label: "Position code",
        kind: "text",
        required: true,
      },
      {
        key: "rolling_direction",
        label: "Rolling direction",
        kind: "select",
        options: ["", "FORWARD", "REVERSE"],
      },
      ...weighingFields,
      measuredAt,
    ],
  },
  REPEATABILITY: {
    label: "Repeatability",
    protocol: "REPEATABILITY_V1",
    procedure: [stabilized],
    observation: [
      {
        key: "series_code",
        label: "Series code",
        kind: "text",
        required: true,
      },
      {
        key: "repetition_no",
        label: "Repetition number",
        kind: "integer",
        required: true,
      },
      ...weighingFields,
      {
        key: "zero_reset_performed",
        label: "Zero reset performed",
        kind: "tri",
      },
      measuredAt,
    ],
  },
  DISCRIMINATION: {
    label: "Discrimination",
    protocol: "DISCRIMINATION_V1",
    procedure: [
      stabilized,
      {
        key: "indication_mode",
        label: "Indication mode",
        kind: "select",
        options: ["DIGITAL", "ANALOG"],
        required: true,
      },
    ],
    observation: [
      { key: "load_g", label: "Load (g)", kind: "decimal", required: true },
      {
        key: "extra_load_g",
        label: "Extra load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "indication_before_g",
        label: "Indication before (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "indication_after_g",
        label: "Indication after (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "displacement_mm",
        label: "Displacement (mm)",
        kind: "decimal",
      },
      measuredAt,
    ],
  },
  SENSITIVITY: {
    label: "Sensitivity",
    protocol: "SENSITIVITY_V1",
    procedure: [stabilized],
    observation: [
      { key: "load_g", label: "Load (g)", kind: "decimal", required: true },
      {
        key: "extra_load_g",
        label: "Extra load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "permanent_displacement_mm",
        label: "Permanent displacement (mm)",
        kind: "decimal",
        required: true,
      },
      measuredAt,
    ],
  },
  ZERO_RETURN: {
    label: "Zero return",
    protocol: "ZERO_RETURN_V1",
    procedure: [
      stabilized,
      {
        key: "test_load_g",
        label: "Test load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "hold_seconds",
        label: "Hold duration (s)",
        kind: "decimal",
        required: true,
      },
    ],
    observation: [
      {
        key: "zero_before_g",
        label: "Zero before (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_after_g",
        label: "Zero after (g)",
        kind: "decimal",
        required: true,
      },
      measuredAt,
    ],
  },
  CREEP: {
    label: "Creep",
    protocol: "CREEP_V1",
    procedure: [
      stabilized,
      {
        key: "test_load_g",
        label: "Test load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "planned_duration_s",
        label: "Planned duration (s)",
        kind: "decimal",
        required: true,
      },
    ],
    observation: [
      {
        key: "elapsed_s",
        label: "Elapsed time (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "indication_g",
        label: "Indication (g)",
        kind: "decimal",
        required: true,
      },
      measuredAt,
    ],
  },
  STABILITY_EQUILIBRIUM: {
    label: "Equilibrium stability",
    protocol: "STABILITY_EQUILIBRIUM_V1",
    procedure: [
      stabilized,
      {
        key: "functions_under_test",
        label: "Functions under test",
        kind: "enum-list",
        options: ["PRINTING", "STORAGE", "ZERO", "TARE"],
        required: true,
      },
    ],
    observation: [
      {
        key: "function",
        label: "Function",
        kind: "select",
        options: ["PRINTING", "STORAGE", "ZERO", "TARE"],
        required: true,
      },
      {
        key: "trial_no",
        label: "Trial number",
        kind: "integer",
        required: true,
      },
      {
        key: "equilibrium_stable",
        label: "Equilibrium stable",
        kind: "boolean",
        required: true,
      },
      {
        key: "operation_performed",
        label: "Operation performed",
        kind: "boolean",
        required: true,
      },
      {
        key: "adjacent_values_consistent",
        label: "Adjacent values consistent",
        kind: "tri",
      },
      measuredAt,
    ],
  },
  TILTING: {
    label: "Tilting",
    protocol: "TILTING_V1",
    procedure: [
      {
        key: "reference_tilt_value",
        label: "Reference tilt",
        kind: "decimal",
        required: true,
      },
      {
        key: "test_tilt_value",
        label: "Test tilt",
        kind: "decimal",
        required: true,
      },
      {
        key: "directions",
        label: "Directions",
        kind: "enum-list",
        options: ["FORWARD", "BACKWARD", "LEFT", "RIGHT"],
        required: true,
      },
      {
        key: "reference_position_confirmed",
        label: "Reference position confirmed",
        kind: "boolean",
        required: true,
      },
      {
        key: "protection_behavior_checked",
        label: "Protection behavior checked",
        kind: "tri",
      },
    ],
    observation: [
      {
        key: "direction",
        label: "Direction",
        kind: "select",
        options: ["FORWARD", "BACKWARD", "LEFT", "RIGHT"],
        required: true,
      },
      {
        key: "stage",
        label: "Stage",
        kind: "select",
        options: ["REFERENCE", "TILTED"],
        required: true,
      },
      {
        key: "tilt_value",
        label: "Tilt value",
        kind: "decimal",
        required: true,
      },
      ...weighingFields,
      { key: "warning_generated", label: "Warning generated", kind: "tri" },
      { key: "display_operational", label: "Display operational", kind: "tri" },
      { key: "printing_inhibited", label: "Printing inhibited", kind: "tri" },
      {
        key: "transmission_inhibited",
        label: "Transmission inhibited",
        kind: "tri",
      },
      measuredAt,
    ],
  },
  TARE: {
    label: "Tare",
    protocol: "TARE_V1",
    procedure: [
      {
        key: "stages",
        label: "Loading stages",
        kind: "enum-list",
        options: ["UP", "DOWN"],
        required: true,
      },
      {
        key: "tare_scenarios",
        label: "Tare scenarios",
        kind: "tare-scenarios",
        required: true,
      },
      stabilized,
    ],
    observation: [
      {
        key: "tare_scenario_code",
        label: "Tare scenario code",
        kind: "text",
        required: true,
      },
      {
        key: "tare_type",
        label: "Tare type",
        kind: "text",
        required: true,
      },
      {
        key: "tare_value_g",
        label: "Tare value (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "net_load_g",
        label: "Net load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "gross_load_g",
        label: "Gross load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "indication_g",
        label: "Indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "additional_load_g",
        label: "Additional load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_error_g",
        label: "Zero error (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "direction",
        label: "Direction",
        kind: "select",
        options: ["UP", "DOWN"],
        required: true,
      },
      measuredAt,
    ],
  },
  WARM_UP: {
    label: "Warm-up",
    protocol: "WARM_UP_V1",
    procedure: [
      {
        key: "power_off_seconds",
        label: "Power-off duration (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "test_load_g",
        label: "Test load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "first_stable_indication_observed",
        label: "First stable indication observed",
        kind: "boolean",
        required: true,
      },
      {
        key: "zero_set_after_power_on",
        label: "Zero set after power-on",
        kind: "boolean",
        required: true,
      },
    ],
    observation: [
      {
        key: "elapsed_s",
        label: "Elapsed time (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_indication_g",
        label: "Zero indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_additional_load_g",
        label: "Zero additional load (g)",
        kind: "decimal",
        required: true,
      },
      { key: "load_g", label: "Load (g)", kind: "decimal", required: true },
      {
        key: "loaded_indication_g",
        label: "Loaded indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "loaded_additional_load_g",
        label: "Loaded additional load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "temperature_c",
        label: "Temperature (°C)",
        kind: "decimal",
      },
      {
        key: "stabilized",
        label: "Stabilized",
        kind: "boolean",
        required: true,
      },
      measuredAt,
    ],
  },
  VOLTAGE_VARIATION: {
    label: "Voltage variation",
    protocol: "VOLTAGE_VARIATION_V1",
    procedure: [
      {
        key: "reference_voltage_v",
        label: "Reference voltage (V)",
        kind: "decimal",
        required: true,
      },
      {
        key: "protection_behavior_checked",
        label: "Protection behavior checked",
        kind: "boolean",
        required: true,
      },
    ],
    observation: [
      {
        key: "applied_voltage_v",
        label: "Applied voltage (V)",
        kind: "decimal",
        required: true,
      },
      { key: "load_g", label: "Load (g)", kind: "decimal", required: true },
      {
        key: "operational_state",
        label: "Operational state",
        kind: "select",
        options: ["INDICATING", "SWITCHED_OFF"],
        required: true,
      },
      {
        key: "functions_operational",
        label: "Functions operational",
        kind: "boolean",
        required: true,
      },
      { key: "indication_g", label: "Indication (g)", kind: "decimal" },
      {
        key: "additional_load_g",
        label: "Additional load (g)",
        kind: "decimal",
      },
      { key: "zero_error_g", label: "Zero error (g)", kind: "decimal" },
      measuredAt,
    ],
  },
  DAMP_HEAT: {
    label: "Damp heat",
    protocol: "DAMP_HEAT_V1",
    procedure: [
      {
        key: "stages",
        label: "Stages",
        kind: "enum-list",
        options: ["INITIAL", "HIGH_HUMIDITY", "FINAL"],
        required: true,
      },
      {
        key: "loads_g",
        label: "Test loads (g)",
        kind: "decimal-list",
        required: true,
      },
      {
        key: "same_reference_weights_confirmed",
        label: "Same reference weights confirmed",
        kind: "boolean",
        required: true,
      },
    ],
    observation: [
      {
        key: "stage",
        label: "Stage",
        kind: "select",
        options: ["INITIAL", "HIGH_HUMIDITY", "FINAL"],
        required: true,
      },
      ...weighingFields,
      {
        key: "temperature_c",
        label: "Temperature (°C)",
        kind: "decimal",
        required: true,
      },
      {
        key: "relative_humidity_percent",
        label: "Relative humidity (%)",
        kind: "decimal",
        required: true,
      },
      {
        key: "stage_elapsed_s",
        label: "Stage elapsed (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "exposure_elapsed_s",
        label: "Exposure elapsed (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "stabilized",
        label: "Stabilized",
        kind: "boolean",
        required: true,
      },
      {
        key: "functions_operational",
        label: "Functions operational",
        kind: "boolean",
        required: true,
      },
      measuredAt,
    ],
  },
  SPAN_STABILITY: {
    label: "Span stability",
    protocol: "SPAN_STABILITY_V1",
    procedure: [
      {
        key: "test_load_g",
        label: "Test load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "planned_duration_s",
        label: "Planned duration (s)",
        kind: "decimal",
        required: true,
      },
      {
        key: "same_reference_weights_confirmed",
        label: "Same reference weights confirmed",
        kind: "boolean",
        required: true,
      },
      {
        key: "extension_completed",
        label: "Extension completed",
        kind: "boolean",
        required: true,
      },
    ],
    observation: [
      {
        key: "measurement_no",
        label: "Measurement number",
        kind: "integer",
        required: true,
      },
      {
        key: "elapsed_s",
        label: "Elapsed time (s)",
        kind: "decimal",
        required: true,
      },
      { key: "location", label: "Location", kind: "text", required: true },
      {
        key: "temperature_c",
        label: "Temperature (°C)",
        kind: "decimal",
        required: true,
      },
      {
        key: "relative_humidity_percent",
        label: "Relative humidity (%)",
        kind: "decimal",
        required: true,
      },
      {
        key: "barometric_pressure_hpa",
        label: "Barometric pressure (hPa)",
        kind: "decimal",
        required: true,
      },
      {
        key: "event_since_previous_measurement",
        label: "Event since previous measurement",
        kind: "text",
      },
      {
        key: "power_disconnection_event",
        label: "Power disconnection event",
        kind: "boolean",
        required: true,
      },
      {
        key: "power_disconnection_duration_s",
        label: "Power disconnection duration (s)",
        kind: "decimal",
      },
      {
        key: "temperature_test_event",
        label: "Temperature test event",
        kind: "boolean",
        required: true,
      },
      {
        key: "damp_heat_event",
        label: "Damp heat event",
        kind: "boolean",
        required: true,
      },
      {
        key: "extension_measurement",
        label: "Extension measurement",
        kind: "boolean",
        required: true,
      },
      {
        key: "load_g",
        label: "Load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_indication_g",
        label: "Zero indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "zero_additional_load_g",
        label: "Zero additional load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "loaded_indication_g",
        label: "Loaded indication (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "loaded_additional_load_g",
        label: "Loaded additional load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "influence_correction_g",
        label: "Influence correction (g)",
        kind: "decimal",
      },
      measuredAt,
    ],
  },
  ENDURANCE: {
    label: "Endurance",
    protocol: "ENDURANCE_V1",
    procedure: [
      {
        key: "cycling_target_load_g",
        label: "Cycling target load (g)",
        kind: "decimal",
        required: true,
      },
      {
        key: "planned_cycles",
        label: "Planned cycles",
        kind: "integer",
        required: true,
      },
      {
        key: "completed_cycles",
        label: "Completed cycles",
        kind: "integer",
        required: true,
      },
      {
        key: "cycle_started_at",
        label: "Cycle started at",
        kind: "datetime",
      },
      {
        key: "cycle_ended_at",
        label: "Cycle ended at",
        kind: "datetime",
      },
      {
        key: "same_reference_weights_confirmed",
        label: "Same reference weights confirmed",
        kind: "boolean",
        required: true,
      },
      {
        key: "abnormal_events",
        label: "Abnormal events",
        kind: "string-list",
      },
      {
        key: "abnormal_events_resolved",
        label: "Abnormal events resolved",
        kind: "boolean",
        required: true,
      },
    ],
    observation: [
      {
        key: "phase",
        label: "Phase",
        kind: "select",
        options: ["INITIAL", "FINAL"],
        required: true,
      },
      { key: "point_id", label: "Point ID", kind: "text", required: true },
      ...weighingFields,
      measuredAt,
    ],
  },
};

export function isStage2Test(code: string): code is TestCode {
  return Object.hasOwn(TEST_SPECS, code);
}

export function procedureIdentity(
  code: TestCode,
  slot: RequirementSlotSnapshot,
  evaluationContext: string,
  procedureSchemaVersion: string,
): Record<string, unknown> {
  const spec = TEST_SPECS[code];
  if (!spec) throw new Error("Typed procedure schema is not available.");

  if (
    slot.range_no === null ||
    slot.range_no === undefined ||
    !slot.scenario ||
    !slot.procedure_variant
  ) {
    throw new Error(
      "The backend requirement slot does not contain the range/scenario/variant identity required by this evaluator.",
    );
  }

  const identity: Record<string, unknown> = {
    test_code: code,
    procedure_variant: slot.procedure_variant,
    procedure_schema_version: procedureSchemaVersion,
    evaluation_context: evaluationContext,
    protocol: spec.protocol,
    range_no: slot.range_no,
    scenario: slot.scenario,
    environment: [],
    equipment: [],
    evidence_hashes: [],
  };

  if (code === "TILTING") {
    identity.tilt_mode = slot.procedure_variant;
  } else if (code === "VOLTAGE_VARIATION") {
    identity.power_supply_profile = slot.procedure_variant;
  } else if (code === "DISCRIMINATION") {
    identity.indication_mode = slot.procedure_variant;
  }

  return identity;
}

function dateValue(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export function coerceField(field: FieldSpec, value: unknown): unknown {
  if (field.kind === "integer") {
    if (value === "" || value === null || value === undefined) return null;
    return Number.parseInt(String(value), 10);
  }

  if (field.kind === "boolean") {
    if (value === true || value === "true") return true;
    if (value === false || value === "false") return false;
    return null;
  }

  if (field.kind === "tri") {
    if (value === true || value === "true") return true;
    if (value === false || value === "false") return false;
    return null;
  }

  if (field.kind === "datetime") return dateValue(value);

  if (field.kind === "decimal-list") {
    if (Array.isArray(value)) return value.map(String);
    return String(value ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  if (field.kind === "string-list") {
    if (Array.isArray(value)) return value.map(String);
    return String(value ?? "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  if (field.kind === "enum-list") {
    return Array.isArray(value) ? value.map(String) : [];
  }

  if (field.kind === "positions" || field.kind === "tare-scenarios") {
    return Array.isArray(value) ? value : [];
  }

  if (field.kind === "severity-cases") {
    if (!Array.isArray(value)) return [];
    return value.map((row) => {
      if (!row || typeof row !== "object") return {};
      return Object.fromEntries(
        Object.entries(row as Record<string, unknown>).filter(
          ([, item]) => item !== "" && item !== null && item !== undefined,
        ),
      );
    });
  }

  if (value === "" || value === undefined) return null;
  return value;
}

export function buildObservation(
  code: TestCode,
  sequenceNo: number,
  values: Record<string, unknown>,
): ObservationData {
  const spec = TEST_SPECS[code];
  if (!spec) throw new Error("Typed observation schema is not available.");

  const payload: Record<string, unknown> = {
    test_code: code,
    protocol: spec.protocol,
    observation_schema_version: "v1",
    sequence_no: sequenceNo,
  };

  for (const field of spec.observation) {
    const value = coerceField(field, values[field.key]);
    if (field.required && (value === null || value === "")) {
      throw new Error(`${field.label} is required.`);
    }
    if (value !== null) payload[field.key] = value;
  }

  return {
    sequence_no: sequenceNo,
    observation_type: code,
    payload_schema_version: "v1",
    payload,
  };
}
