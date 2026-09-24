import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";

import type {
  ApplicabilityView,
  EvaluationDashboard,
  EvaluationStatus,
  ComplianceOutcome,
  RuleSetRecord,
  RulesetPage,
  SessionResource,
  SessionView,
  WorkflowStatus,
} from "./types";
import type { Page } from "@/lib/master-data/types";

function queryString(
  values: Record<string, string | number | boolean | null | undefined>,
) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export async function listEvaluations(input: {
  laboratoryId: string;
  page: number;
  pageSize?: number;
  search?: string;
  workflowStatus?: WorkflowStatus | "";
  evaluationStatus?: EvaluationStatus | "";
  complianceOutcome?: ComplianceOutcome | "";
}): Promise<Page<SessionView>> {
  const query = queryString({
    laboratory_id: input.laboratoryId,
    page: input.page,
    page_size: input.pageSize ?? 20,
    search: input.search,
    workflow_status: input.workflowStatus,
    evaluation_status: input.evaluationStatus,
    compliance_outcome: input.complianceOutcome,
  });

  return (await apiRequest<Page<SessionView>>(`/api/v1/test-sessions?${query}`))
    .data;
}

export async function createEvaluation(payload: {
  instrument_id: string;
  rule_set_id: string;
  evaluation_context: string;
  application_number: string | null;
  notes: string | null;
}): Promise<SessionResource> {
  const response = await apiRequest<SessionView>("/api/v1/test-sessions", {
    method: "POST",
    body: payload,
    idempotencyKey: createIdempotencyKey(),
  });
  return { item: response.data, etag: response.etag };
}

export async function evaluationDetail(id: string): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(`/api/v1/test-sessions/${id}`);
  return { item: response.data, etag: response.etag };
}

export async function evaluationDashboard(
  id: string,
): Promise<EvaluationDashboard> {
  return (
    await apiRequest<EvaluationDashboard>(
      `/api/v1/test-sessions/${id}/dashboard`,
    )
  ).data;
}

export async function configureEvaluation(
  id: string,
  instrumentSnapshot: SessionView["instrument_snapshot"],
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${id}/configure`,
    {
      method: "POST",
      body: { instrument_snapshot: instrumentSnapshot },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function calculateApplicability(
  id: string,
): Promise<ApplicabilityView> {
  return (
    await apiRequest<ApplicabilityView>(
      `/api/v1/test-sessions/${id}/applicability`,
      {
        method: "POST",
        idempotencyKey: createIdempotencyKey(),
      },
    )
  ).data;
}

export async function confirmApplicability(
  id: string,
  elections: Record<string, boolean>,
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${id}/confirm-applicability`,
    {
      method: "POST",
      body: { elections },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function startTesting(
  id: string,
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${id}/start-testing`,
    {
      method: "POST",
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function listRulesets(): Promise<RuleSetRecord[]> {
  const output: RuleSetRecord[] = [];
  let page = 1;

  while (true) {
    const response = await apiRequest<RulesetPage>(
      `/api/v1/rulesets?page=${page}&page_size=100`,
    );
    output.push(...response.data.items);
    if (page * response.data.page_size >= response.data.total) break;
    page += 1;
  }

  return output;
}
