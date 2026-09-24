import { apiRequest } from "@/lib/api/client";

import type { SessionView } from "./types";
import type {
  ChecklistRow,
  ChecklistSummary,
  ConformanceResult,
  ConstructionExamination,
  ConstructionItem,
  ExaminationState,
  Versioned,
} from "./special-types";

export async function startExamination(
  sessionId: string,
  etag: string,
): Promise<Versioned<SessionView>> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${sessionId}/start-examination`,
    { method: "POST", etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function constructionDetail(
  sessionId: string,
): Promise<Versioned<ConstructionExamination>> {
  const response = await apiRequest<ConstructionExamination>(
    `/api/v1/test-sessions/${sessionId}/construction`,
  );
  return { item: response.data, etag: response.etag };
}

export async function constructionItems(
  sessionId: string,
): Promise<ConstructionItem[]> {
  return (
    await apiRequest<ConstructionItem[]>(
      `/api/v1/test-sessions/${sessionId}/construction/items`,
    )
  ).data;
}

export async function patchConstruction(
  sessionId: string,
  overallNotes: string | null,
  etag: string,
): Promise<Versioned<ConstructionExamination>> {
  const response = await apiRequest<ConstructionExamination>(
    `/api/v1/test-sessions/${sessionId}/construction`,
    { method: "PATCH", body: { overall_notes: overallNotes }, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function patchConstructionItem(
  sessionId: string,
  itemId: string,
  data: {
    value_schema_version: 1;
    value_json: Record<string, unknown>;
    examination_state: ExaminationState;
    conformance_result: ConformanceResult;
    remarks: string | null;
  },
  etag: string,
): Promise<Versioned<ConstructionItem>> {
  const response = await apiRequest<ConstructionItem>(
    `/api/v1/test-sessions/${sessionId}/construction/items/${itemId}`,
    { method: "PATCH", body: data, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function completeConstruction(
  sessionId: string,
  etag: string,
): Promise<Versioned<ConstructionExamination>> {
  const response = await apiRequest<ConstructionExamination>(
    `/api/v1/test-sessions/${sessionId}/construction/complete`,
    { method: "POST", etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function checklistRows(
  sessionId: string,
): Promise<ChecklistRow[]> {
  return (
    await apiRequest<ChecklistRow[]>(
      `/api/v1/test-sessions/${sessionId}/checklist`,
    )
  ).data;
}

export async function checklistSummary(
  sessionId: string,
): Promise<Versioned<ChecklistSummary>> {
  const response = await apiRequest<ChecklistSummary>(
    `/api/v1/test-sessions/${sessionId}/checklist/summary`,
  );
  return { item: response.data, etag: response.etag };
}

export async function patchChecklistRow(
  sessionId: string,
  ruleId: string,
  data: {
    response_result: "PASS" | "FAIL" | "NOT_EXAMINED";
    remarks: string | null;
  },
  etag: string,
): Promise<Versioned<ChecklistRow>> {
  const response = await apiRequest<ChecklistRow>(
    `/api/v1/test-sessions/${sessionId}/checklist/${ruleId}`,
    { method: "PATCH", body: data, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function completeChecklist(
  sessionId: string,
  etag: string,
): Promise<Versioned<ChecklistSummary>> {
  const response = await apiRequest<ChecklistSummary>(
    `/api/v1/test-sessions/${sessionId}/checklist/complete`,
    { method: "POST", etag },
  );
  return { item: response.data, etag: response.etag };
}
