import type {
  ChecklistRow,
  ConstructionExamination,
  ConstructionItem,
} from "@/lib/evaluations/special-types";
import type { EvaluationDashboard } from "@/lib/evaluations/types";

import type {
  CorrectionEntityType,
  CorrectionTargetOption,
} from "./types";

const FIELD_LABELS: Record<CorrectionEntityType, Array<[string, string]>> = {
  test_sessions: [
    ["application_number", "Application number"],
    ["notes", "Session notes"],
    ["evidence", "Session evidence"],
  ],
  session_test_requirements: [["selected_run_id", "Selected run"]],
  test_runs: [
    ["procedure_context", "Procedure metadata"],
    ["observations", "Observations"],
    ["environment", "Environment readings"],
    ["equipment", "Test equipment"],
    ["evidence", "Run evidence"],
    ["retest", "Retest"],
    ["start", "Run start"],
    ["evaluate", "Evaluation action"],
    ["complete", "Run completion"],
  ],
  construction_examinations: [["overall_notes", "Construction dossier notes"]],
  construction_items: [
    ["value_schema_version", "Value schema"],
    ["value_json", "Construction values"],
    ["examination_state", "Examination state"],
    ["conformance_result", "Conformance result"],
    ["remarks", "Remarks"],
    ["evidence", "Construction evidence"],
  ],
  checklist_responses: [
    ["response_result", "Checklist response"],
    ["remarks", "Remarks"],
    ["evidence", "Checklist evidence"],
  ],
};

function fields(type: CorrectionEntityType) {
  return FIELD_LABELS[type].map(([value, label]) => ({ value, label }));
}

export function correctionTargetOptions(input: {
  dashboard: EvaluationDashboard;
  construction?: ConstructionExamination | null;
  constructionItems?: ConstructionItem[];
  checklist?: ChecklistRow[];
}): CorrectionTargetOption[] {
  const output: CorrectionTargetOption[] = [
    {
      entity_type: "test_sessions",
      entity_id: input.dashboard.session.id,
      label: "Evaluation session",
      description:
        input.dashboard.session.application_number ??
        `Session ${input.dashboard.session.id.slice(0, 8)}`,
      allowed_fields: fields("test_sessions"),
    },
  ];

  for (const requirement of input.dashboard.requirements) {
    output.push({
      entity_type: "session_test_requirements",
      entity_id: requirement.id,
      label: `Requirement · ${requirement.requirement_key}`,
      description: "Selected-run governance",
      allowed_fields: fields("session_test_requirements"),
    });

    if (requirement.selected_run_id) {
      output.push({
        entity_type: "test_runs",
        entity_id: requirement.selected_run_id,
        label: `Selected run · ${requirement.requirement_key}`,
        description:
          typeof requirement.slot_snapshot.test_code === "string"
            ? requirement.slot_snapshot.test_code.replaceAll("_", " ")
            : "Confirmed test run",
        allowed_fields: fields("test_runs"),
      });
    }
  }

  if (input.construction) {
    output.push({
      entity_type: "construction_examinations",
      entity_id: input.construction.id,
      label: "Section 16 · Construction dossier",
      description: "Overall construction examination",
      allowed_fields: fields("construction_examinations"),
    });
  }

  for (const item of input.constructionItems ?? []) {
    output.push({
      entity_type: "construction_items",
      entity_id: item.id,
      label: `Construction · ${item.item_key}`,
      description: item.description_snapshot,
      allowed_fields: fields("construction_items"),
    });
  }

  for (const row of input.checklist ?? []) {
    output.push({
      entity_type: "checklist_responses",
      entity_id: row.id,
      label: `Checklist · ${row.requirement_key}`,
      description: row.display_text,
      allowed_fields: fields("checklist_responses"),
    });
  }

  return output;
}
