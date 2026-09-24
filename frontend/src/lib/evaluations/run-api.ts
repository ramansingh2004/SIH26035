import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";

import type {
  EnvironmentData,
  EnvironmentView,
  EquipmentLinkView,
  ObservationData,
  ObservationView,
  ResultView,
  RunResource,
  RunView,
} from "./run-types";

export async function runDetail(id: string): Promise<RunResource> {
  const response = await apiRequest<RunView>(`/api/v1/test-runs/${id}`);
  return { item: response.data, etag: response.etag };
}

export async function startRun(id: string, etag: string): Promise<RunResource> {
  const response = await apiRequest<RunView>(`/api/v1/test-runs/${id}/start`, {
    method: "POST",
    etag,
  });
  return { item: response.data, etag: response.etag };
}

export async function saveProcedureContext(
  id: string,
  procedureContext: Record<string, unknown>,
  etag: string,
): Promise<RunResource> {
  const response = await apiRequest<RunView>(
    `/api/v1/test-runs/${id}/procedure-context`,
    {
      method: "PATCH",
      body: { procedure_context: procedureContext },
      etag,
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function completeRun(
  id: string,
  etag: string,
): Promise<RunResource> {
  const response = await apiRequest<RunView>(
    `/api/v1/test-runs/${id}/complete`,
    {
      method: "POST",
      etag,
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function evaluateRun(
  id: string,
  etag: string,
): Promise<ResultView> {
  return (
    await apiRequest<ResultView>(`/api/v1/test-runs/${id}/evaluate`, {
      method: "POST",
      etag,
      idempotencyKey: createIdempotencyKey(),
    })
  ).data;
}

export async function observations(id: string): Promise<ObservationView[]> {
  return (
    await apiRequest<ObservationView[]>(`/api/v1/test-runs/${id}/observations`)
  ).data;
}

export async function createObservation(
  id: string,
  data: ObservationData,
  runEtag: string,
): Promise<ObservationView> {
  return (
    await apiRequest<ObservationView>(`/api/v1/test-runs/${id}/observations`, {
      method: "POST",
      body: data,
      etag: runEtag,
    })
  ).data;
}

export async function updateObservation(
  runId: string,
  observationId: string,
  data: ObservationData,
  childEtag: string,
): Promise<ObservationView> {
  return (
    await apiRequest<ObservationView>(
      `/api/v1/test-runs/${runId}/observations/${observationId}`,
      {
        method: "PATCH",
        body: data,
        etag: childEtag,
      },
    )
  ).data;
}

export async function deleteObservation(
  runId: string,
  observationId: string,
  childEtag: string,
): Promise<void> {
  await apiRequest<void>(
    `/api/v1/test-runs/${runId}/observations/${observationId}`,
    {
      method: "DELETE",
      etag: childEtag,
    },
  );
}

export async function environmentReadings(
  id: string,
): Promise<EnvironmentView[]> {
  return (
    await apiRequest<EnvironmentView[]>(`/api/v1/test-runs/${id}/environment`)
  ).data;
}

export async function createEnvironment(
  id: string,
  data: EnvironmentData,
  runEtag: string,
): Promise<EnvironmentView> {
  return (
    await apiRequest<EnvironmentView>(`/api/v1/test-runs/${id}/environment`, {
      method: "POST",
      body: data,
      etag: runEtag,
    })
  ).data;
}

export async function updateEnvironment(
  runId: string,
  readingId: string,
  data: EnvironmentData,
  childEtag: string,
): Promise<EnvironmentView> {
  return (
    await apiRequest<EnvironmentView>(
      `/api/v1/test-runs/${runId}/environment/${readingId}`,
      {
        method: "PATCH",
        body: data,
        etag: childEtag,
      },
    )
  ).data;
}

export async function deleteEnvironment(
  runId: string,
  readingId: string,
  childEtag: string,
): Promise<void> {
  await apiRequest<void>(
    `/api/v1/test-runs/${runId}/environment/${readingId}`,
    {
      method: "DELETE",
      etag: childEtag,
    },
  );
}

export async function linkedEquipment(
  id: string,
): Promise<EquipmentLinkView[]> {
  return (
    await apiRequest<EquipmentLinkView[]>(`/api/v1/test-runs/${id}/equipment`)
  ).data;
}

export async function linkEquipment(
  runId: string,
  equipmentId: string,
  calibrationAttachmentId: string | null,
  runEtag: string,
): Promise<EquipmentLinkView> {
  return (
    await apiRequest<EquipmentLinkView>(
      `/api/v1/test-runs/${runId}/equipment/${equipmentId}`,
      {
        method: "POST",
        body: {
          calibration_attachment_id: calibrationAttachmentId,
        },
        etag: runEtag,
      },
    )
  ).data;
}

export async function unlinkEquipment(
  runId: string,
  equipmentId: string,
  childEtag: string,
): Promise<void> {
  await apiRequest<void>(
    `/api/v1/test-runs/${runId}/equipment/${equipmentId}`,
    {
      method: "DELETE",
      etag: childEtag,
    },
  );
}

export async function runResults(id: string): Promise<ResultView[]> {
  return (await apiRequest<ResultView[]>(`/api/v1/test-runs/${id}/results`))
    .data;
}

export async function runHistory(
  id: string,
  page = 1,
  pageSize = 20,
): Promise<import("./run-types").RunHistory> {
  return (
    await apiRequest<import("./run-types").RunHistory>(
      `/api/v1/test-runs/${id}/history?page=${page}&page_size=${pageSize}`,
    )
  ).data;
}

export async function createRetest(
  id: string,
  reason: string,
  etag: string,
): Promise<RunResource> {
  const response = await apiRequest<RunView>(
    `/api/v1/test-runs/${id}/retests`,
    {
      method: "POST",
      body: { reason },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function selectRun(
  requirementId: string,
  runId: string,
  reason: string,
  etag: string,
): Promise<import("./types").RequirementView> {
  return (
    await apiRequest<import("./types").RequirementView>(
      `/api/v1/test-requirements/${requirementId}/select-run`,
      {
        method: "POST",
        body: { run_id: runId, reason },
        etag,
      },
    )
  ).data;
}
