import type { TestFormSpec } from "./test-schemas";
import type { TestCode } from "./run-types";

const procedure = [
  {
    key: "test_load_g",
    label: "Test load (g)",
    kind: "decimal",
    required: true,
  },
  {
    key: "warm_up_completed",
    label: "Warm-up completed",
    kind: "boolean",
    required: true,
  },
  {
    key: "environment_stabilized",
    label: "Environment stabilized",
    kind: "boolean",
    required: true,
  },
  {
    key: "peripherals_connected",
    label: "Applicable peripherals connected",
    kind: "boolean",
    required: true,
  },
  {
    key: "no_load_deviation_g",
    label: "No-load deviation (g)",
    kind: "decimal",
  },
  {
    key: "severity_cases",
    label: "Disturbance severity cases",
    kind: "severity-cases",
    required: true,
  },
] satisfies TestFormSpec["procedure"];

const observation = [
  { key: "severity_id", label: "Severity ID", kind: "text", required: true },
  {
    key: "repetition_no",
    label: "Repetition number",
    kind: "integer",
    required: true,
  },
  {
    key: "reference_indication_g",
    label: "Reference indication (g)",
    kind: "decimal",
    required: true,
  },
  {
    key: "disturbed_indication_g",
    label: "Disturbed indication (g)",
    kind: "decimal",
    required: true,
  },
  {
    key: "fault_detected",
    label: "Fault detected",
    kind: "boolean",
    required: true,
  },
  { key: "fault_response", label: "Fault response", kind: "text" },
  {
    key: "fault_response_evidence_hash",
    label: "Fault-response evidence SHA-256",
    kind: "text",
  },
  { key: "state_before", label: "State before", kind: "text" },
  { key: "state_during", label: "State during", kind: "text" },
  { key: "state_after", label: "State after", kind: "text" },
  {
    key: "measured_at",
    label: "Measured at",
    kind: "datetime",
    required: true,
  },
] satisfies TestFormSpec["observation"];

function spec(label: string): TestFormSpec {
  return { label, protocol: "DISTURBANCE_V1", procedure, observation };
}

export const DISTURBANCE_SPECS: Partial<Record<TestCode, TestFormSpec>> = {
  DISTURBANCE_VOLTAGE_DIP: spec("Voltage dips and interruptions"),
  DISTURBANCE_BURST: spec("Electrical fast transient / burst"),
  DISTURBANCE_SURGE: spec("Surge"),
  DISTURBANCE_ESD: spec("Electrostatic discharge"),
  DISTURBANCE_RADIATED_RF: spec("Radiated RF electromagnetic fields"),
  DISTURBANCE_CONDUCTED_RF: spec("Conducted RF disturbances"),
  DISTURBANCE_VEHICLE_SUPPLY: spec("Vehicle supply disturbances"),
};
