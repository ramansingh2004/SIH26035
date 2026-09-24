import type { Page } from "@/lib/master-data/types";

export type WorkflowStatus =
  | "DRAFT"
  | "INSTRUMENT_CONFIGURATION"
  | "APPLICABILITY_CONFIRMED"
  | "TESTING"
  | "EXAMINATION"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REPORT_ISSUED"
  | "REJECTED"
  | "CANCELLED";

export type EvaluationStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "INCOMPLETE"
  | "STALE"
  | "REVIEW_REQUIRED"
  | "COMPLETE";

export type ComplianceOutcome =
  "UNDETERMINED" | "COMPLIANT" | "NONCOMPLIANT" | "NOT_APPLICABLE";

export type Applicability =
  "REQUIRED" | "OPTIONAL" | "NOT_APPLICABLE" | "REQUIRES_REVIEW";

export type InstrumentRangeSnapshot = {
  range_no: number;
  min_capacity_g?: string | null;
  max_capacity_g: string;
  scale_interval_d_g: string;
  verification_interval_e_g: string;
};

export type InstrumentSnapshot = {
  min_capacity_g?: string | null;
  max_capacity_g: string;
  scale_interval_d_g: string;
  verification_interval_e_g: string;
  accuracy_class: "I" | "II" | "III" | "IIII";
  ranges: InstrumentRangeSnapshot[];
  range_type?: string | null;
  indication_type?: string | null;
  is_self_indicating?: boolean | null;
  is_electronic?: boolean | null;
  is_software_controlled?: boolean | null;
  is_portable?: boolean | null;
  is_mobile?: boolean | null;
  load_receptor_type?: string | null;
  support_point_count?: number | null;
  tare_type?: string | null;
  maximum_tare_g?: string | null;
  zero_setting_type?: string | null;
  zero_tracking_available?: boolean | null;
  level_indicator_available?: boolean | null;
  automatic_tilt_sensor?: boolean | null;
  power_supply_type?: string | null;
  nominal_voltage?: string | null;
  min_voltage?: string | null;
  max_voltage?: string | null;
  declared_temp_min_c?: string | null;
  declared_temp_max_c?: string | null;
  software_identifier?: string | null;
  is_direct_sales?: boolean | null;
  is_price_computing?: boolean | null;
  is_labeling?: boolean | null;
  data_storage_device_present?: boolean | null;
  battery_charging_during_operation?: boolean | null;
  vehicle_powered?: boolean | null;
  vehicle_power_details?: string | null;
  declared_operating_conditions?: string | null;
  declared_installation?: string | null;
  [key: string]: unknown;
};

export type SessionView = {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  laboratory_id: string;
  instrument_id: string;
  rule_set_id: string;
  application_number: string | null;
  evaluation_context: string;
  notes: string | null;
  workflow_status: WorkflowStatus;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  instrument_snapshot: InstrumentSnapshot;
  ruleset_snapshot: Record<string, unknown>;
  snapshot_schema_version: 1;
  regulatory_revision: number;
  root_session_id: string;
  parent_session_id: string | null;
  session_revision_no: number;
  revision_reason: string | null;
  started_by: string;
  started_at: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
};

export type SectionView = {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_session_id: string;
  section_number: number;
  code: string;
  name: string;
  applicability_status: Applicability;
  applicability_reason: string;
  rule_references: Array<Record<string, unknown>>;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  summary_schema_version: number;
  summary_json: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
};

export type RequirementView = {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  test_session_id: string;
  session_section_id: string;
  test_definition_id: string;
  requirement_key: string;
  applicability_status: Applicability;
  applicability_reason: string;
  rule_references: Array<Record<string, unknown>>;
  slot_snapshot: Record<string, unknown>;
  is_elected: boolean;
  selected_run_id: string | null;
};

export type EvaluationDashboard = {
  session: SessionView;
  sections: SectionView[];
  requirements: RequirementView[];
};

export type ApplicabilityDecision = {
  applicability: Applicability;
  reason: string;
  rule_references: Array<Record<string, unknown>>;
  unresolved_rule_ids: string[];
  feature?: string | null;
  range_no?: number | null;
  scenario?: string | null;
};

export type RequirementSlot = {
  section_number: number;
  test_code: string;
  parent_test_code?: string | null;
  range_no: number | null;
  scenario: string;
  procedure_variant: string;
  decision: ApplicabilityDecision;
  elected: boolean;
  // The current backend model defines slot_key as a Python property. If a
  // future API response serializes it, the UI can safely use it for elections.
  slot_key?: string;
};

export type ApplicabilityView = {
  session_id: string;
  regulatory_revision: number;
  plan: {
    slots: RequirementSlot[];
  };
  confirmable: boolean;
};

export type RuleSetRecord = {
  id: string;
  standard_code: string;
  standard_name: string;
  edition: string;
  version: string;
  ruleset_status: "DRAFT" | "ACTIVE" | "RETIRED";
  configuration_hash: string;
  validation_summary?: {
    authoritative?: boolean;
    blockers?: string[];
    structurally_valid?: boolean;
  };
  created_at?: string;
  updated_at?: string;
  lock_version?: number;
  [key: string]: unknown;
};

export type RulesetPage = Page<RuleSetRecord>;

export type SessionResource = {
  item: SessionView;
  etag: string | null;
};
