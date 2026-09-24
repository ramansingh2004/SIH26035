import type { SessionView } from "./types";
import type { ComplianceOutcome, EvaluationStatus } from "./types";

export type ConstructionCategory =
  | "GENERAL"
  | "RECEPTOR_LOAD_CELLS"
  | "INDICATOR_DISPLAY"
  | "PRINTER_PERIPHERALS"
  | "POWER_INTERFACES"
  | "TILT_ZERO_TARE"
  | "SEALS_SECURITY_SOFTWARE"
  | "DOCUMENTS_PHOTOS";

export type ExaminationState = "NOT_EXAMINED" | "EXAMINED" | "REVIEW_REQUIRED";
export type ConformanceResult =
  "PASS" | "FAIL" | "NOT_APPLICABLE" | "UNDETERMINED";

export type ConstructionExamination = {
  id: string;
  test_session_id: string;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  overall_notes: string | null;
  examined_by: string | null;
  examined_at: string | null;
  summary_json: Record<string, unknown>;
  lock_version: number;
  created_at: string;
  updated_at: string;
};

export type ConstructionItem = {
  id: string;
  construction_examination_id: string;
  requirement_rule_id: string;
  category: ConstructionCategory;
  item_key: string;
  description_snapshot: string;
  value_schema_version: 1;
  value_json: Record<string, unknown>;
  examination_state: ExaminationState;
  conformance_result: ConformanceResult;
  remarks: string | null;
  sort_order: number;
  lock_version: number;
  created_at: string;
  updated_at: string;
};

export type ConstructionPolicy = {
  schema_version: "v1";
  category: ConstructionCategory;
  item_key: string;
  sort_order: number;
  required: boolean;
  evidence_required: boolean;
  allow_not_applicable: boolean;
  required_value_keys: string[];
};

export type ChecklistGroup =
  "GENERAL" | "DIRECT_SALES" | "ELECTRONIC" | "SOFTWARE_CONTROLLED";
export type ChecklistApplicability =
  "REQUIRED" | "NOT_APPLICABLE" | "REQUIRES_REVIEW";
export type ChecklistResult =
  "PASS" | "FAIL" | "NOT_APPLICABLE" | "NOT_EXAMINED";

export type ChecklistRow = {
  id: string;
  test_session_id: string;
  checklist_rule_id: string;
  applicability_status: ChecklistApplicability;
  applicability_reason: string;
  response_result: ChecklistResult;
  remarks: string | null;
  examined_by: string | null;
  examined_at: string | null;
  lock_version: number;
  created_at: string;
  updated_at: string;
  group_code: ChecklistGroup;
  requirement_key: string;
  clause_reference: string | null;
  display_text: string;
  evidence_required: boolean | null;
  validation_status: "TODO_REGULATORY_VALIDATION" | "VERIFIED";
  sort_order: number;
};

export type ChecklistSummary = {
  schema_version: 1;
  lock_version: number;
  catalog_total: number;
  applicable: number;
  passed: number;
  failed: number;
  not_examined: number;
  not_applicable: number;
  review_required: number;
  evaluation_status: EvaluationStatus;
  compliance_outcome: ComplianceOutcome;
  missing_rule_keys: string[];
  blockers: string[];
};

export type Versioned<T> = { item: T; etag: string | null };

function policyCandidate(value: unknown): ConstructionPolicy | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (
    item.schema_version !== "v1" ||
    typeof item.item_key !== "string" ||
    typeof item.category !== "string" ||
    typeof item.sort_order !== "number" ||
    typeof item.required !== "boolean" ||
    typeof item.evidence_required !== "boolean" ||
    typeof item.allow_not_applicable !== "boolean" ||
    !Array.isArray(item.required_value_keys) ||
    !item.required_value_keys.every((key) => typeof key === "string")
  ) {
    return null;
  }
  return item as unknown as ConstructionPolicy;
}

export function constructionPolicies(
  snapshot: SessionView["ruleset_snapshot"],
): Map<string, ConstructionPolicy> {
  const output = new Map<string, ConstructionPolicy>();
  const rules = snapshot.rules;
  if (!Array.isArray(rules)) return output;

  for (const rawRule of rules) {
    if (!rawRule || typeof rawRule !== "object") continue;
    const rule = rawRule as Record<string, unknown>;
    if (
      rule.kind !== "construction_item_v1" ||
      !Array.isArray(rule.parameters)
    ) {
      continue;
    }
    const parameter = rule.parameters.find(
      (raw) =>
        Boolean(raw) &&
        typeof raw === "object" &&
        (raw as Record<string, unknown>).name === "POLICY_JSON",
    );
    if (!parameter || typeof parameter !== "object") continue;
    const encoded = (parameter as Record<string, unknown>).value;
    if (typeof encoded !== "string") continue;

    try {
      const policy = policyCandidate(JSON.parse(encoded));
      if (policy) output.set(policy.item_key, policy);
    } catch {
      // Backend remains authoritative and will reject an invalid pinned policy.
    }
  }
  return output;
}
