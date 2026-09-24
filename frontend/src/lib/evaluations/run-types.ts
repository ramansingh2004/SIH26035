import type {
  Applicability,
  ComplianceOutcome,
  EvaluationStatus,
} from "./types";

export type TestCode =
  | "WEIGHING_PERFORMANCE"
  | "TEMPERATURE_ZERO"
  | "ECCENTRICITY"
  | "REPEATABILITY"
  | "DISCRIMINATION"
  | "SENSITIVITY"
  | "ZERO_RETURN"
  | "CREEP"
  | "STABILITY_EQUILIBRIUM"
  | "TILTING"
  | "TARE"
  | "WARM_UP"
  | "VOLTAGE_VARIATION"
  | "DISTURBANCE_VOLTAGE_DIP"
  | "DISTURBANCE_BURST"
  | "DISTURBANCE_SURGE"
  | "DISTURBANCE_ESD"
  | "DISTURBANCE_RADIATED_RF"
  | "DISTURBANCE_CONDUCTED_RF"
  | "DISTURBANCE_VEHICLE_SUPPLY"
  | "DAMP_HEAT"
  | "SPAN_STABILITY"
  | "ENDURANCE";

export type RunView = {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_session_id: string;
  session_section_id: string;
  requirement_id: string;
  test_definition_id: string;
  run_no: number;
  retest_of_run_id: string | null;
  retest_reason: string | null;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  observation_schema_version: string;
  procedure_schema_version: string;
  procedure_context: Record<string, unknown>;
  input_revision: number;
  current_result_id: string | null;
  started_by: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type ObservationData = {
  sequence_no: number;
  observation_type: TestCode;
  payload_schema_version: "v1";
  payload: Record<string, unknown>;
};

export type ObservationView = ObservationData & {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_run_id: string;
  recorded_by: string;
  recorded_at: string;
  is_locked: boolean;
};

export type EnvironmentData = {
  measured_at: string;
  temperature_c: string | null;
  relative_humidity_percent: string | null;
  barometric_pressure_hpa: string | null;
  phase: string | null;
  notes: string | null;
};

export type EnvironmentView = EnvironmentData & {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_session_id: string;
  test_run_id: string;
  recorded_by: string;
};

export type EquipmentLinkView = {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_run_id: string;
  equipment_id: string;
  equipment_snapshot: Record<string, unknown>;
  calibration_attachment_id: string | null;
  linked_by: string;
  linked_at: string;
};

export type ResultView = {
  id: string;
  test_run_id: string;
  rule_set_id: string;
  evaluation_version: number;
  source_input_revision: number;
  supersedes_result_id: string | null;
  evaluation_input_snapshot: Record<string, unknown>;
  deterministic_result: Record<string, unknown>;
  applicability_status: Applicability;
  applicability_reason: string;
  calculations_json: Array<Record<string, unknown>>;
  acceptance_limits_json: Array<Record<string, unknown>>;
  failed_conditions_json: Array<Record<string, unknown>>;
  rule_references_json: Array<Record<string, unknown>>;
  reason: string;
  issue_code: string | null;
  unresolved_rule_ids: string[];
  hash_schema_version: "v1";
  observation_schema_version: string;
  procedure_schema_version: string;
  engine_version: string;
  ruleset_version: string;
  ruleset_configuration_hash: string;
  input_hash: string;
  result_hash: string;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  evaluated_at: string;
  initiated_by: string;
};

export type RunResource = {
  item: RunView;
  etag: string | null;
};

export type RequirementSlotSnapshot = {
  test_code?: TestCode;
  range_no?: number | null;
  scenario?: string;
  procedure_variant?: string;
  parent_test_code?: string | null;
};

export type RetestHistoryItem = {
  id: string;
  run_no: number;
  retest_of_run_id: string | null;
  retest_reason: string | null;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  input_revision: number;
  current_result_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  is_selected: boolean;
};

export type ResultEventView = {
  id: string;
  result_id: string;
  event_type: "CURRENT" | "STALE" | "SUPERSEDED";
  replacement_result_id: string | null;
  regulatory_revision: number;
  actor_id: string;
  reason: string;
  created_at: string;
};

export type SelectionEventView = {
  id: string;
  requirement_id: string;
  previous_run_id: string | null;
  selected_run_id: string;
  reason: string;
  regulatory_revision: number;
  actor_id: string;
  created_at: string;
};

export type RunHistory = {
  runs: {
    items: RetestHistoryItem[];
    page: number;
    page_size: number;
    total: number;
  };
  results: ResultView[];
  events: ResultEventView[];
  selections: SelectionEventView[];
};
