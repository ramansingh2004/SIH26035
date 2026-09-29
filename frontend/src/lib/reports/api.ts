import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";
import type { Page } from "@/lib/master-data/types";

import type {
  InstrumentHistoryItem,
  ReportFormat,
  ReportGenerationResponse,
  ReportGenerationView,
  ReportPage,
  ReportPreviewView,
  ReportRevisionPage,
  ReportView,
  VersionedReport,
} from "./types";

function queryString(
  values: Record<string, string | number | null | undefined>,
) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export async function createReportPreview(
  sessionId: string,
  etag: string,
): Promise<ReportPreviewView> {
  return (
    await apiRequest<ReportPreviewView>(
      `/api/v1/test-sessions/${sessionId}/report-previews`,
      { method: "POST", etag },
    )
  ).data;
}

export async function createSimulatedApprovedReport(
  sessionId: string,
  etag: string,
): Promise<ReportPreviewView> {
  return (
    await apiRequest<ReportPreviewView>(
      `/api/v1/test-sessions/${sessionId}/report-simulations`,
      { method: "POST", etag },
    )
  ).data;
}

export async function createFullDemoReport(
  sessionId: string,
  etag: string,
): Promise<ReportPreviewView> {
  return (
    await apiRequest<ReportPreviewView>(
      `/api/v1/test-sessions/${sessionId}/full-demo-report-previews`,
      { method: "POST", etag },
    )
  ).data;
}

export async function generateReport(
  sessionId: string,
  data: { intended_issuer_id: string; planned_issue_date: string },
  etag: string,
): Promise<ReportGenerationResponse> {
  return (
    await apiRequest<ReportGenerationResponse>(
      `/api/v1/test-sessions/${sessionId}/reports`,
      {
        method: "POST",
        body: data,
        etag,
        idempotencyKey: createIdempotencyKey(),
      },
    )
  ).data;
}

export async function listReports(input: {
  laboratoryId: string;
  page: number;
  pageSize?: number;
  search?: string;
  reportStatus?: string;
}): Promise<ReportPage> {
  const query = queryString({
    laboratory_id: input.laboratoryId,
    page: input.page,
    page_size: input.pageSize ?? 20,
    search: input.search,
    report_status: input.reportStatus,
  });
  return (await apiRequest<ReportPage>(`/api/v1/reports?${query}`)).data;
}

export async function reportDetail(id: string): Promise<VersionedReport> {
  const response = await apiRequest<ReportView>(`/api/v1/reports/${id}`);
  return { item: response.data, etag: response.etag };
}

export async function reportGenerations(
  id: string,
): Promise<ReportGenerationView[]> {
  return (
    await apiRequest<ReportGenerationView[]>(
      `/api/v1/reports/${id}/generations`,
    )
  ).data;
}

export async function regenerateReport(
  reportId: string,
  data: { intended_issuer_id: string; planned_issue_date: string },
  etag: string,
): Promise<ReportGenerationResponse> {
  return (
    await apiRequest<ReportGenerationResponse>(
      `/api/v1/reports/${reportId}/regenerate`,
      {
        method: "POST",
        body: data,
        etag,
        idempotencyKey: createIdempotencyKey(),
      },
    )
  ).data;
}

export async function issueReport(
  reportId: string,
  generationId: string,
  predecessorId: string | null,
  etag: string,
): Promise<ReportView> {
  return (
    await apiRequest<ReportView>(`/api/v1/reports/${reportId}/issue`, {
      method: "POST",
      body: {
        generation_id: generationId,
        expected_predecessor_id: predecessorId,
      },
      etag,
      idempotencyKey: createIdempotencyKey(),
    })
  ).data;
}

export async function reportRevisions(
  reportId: string,
): Promise<ReportRevisionPage> {
  return (
    await apiRequest<ReportRevisionPage>(
      `/api/v1/reports/${reportId}/revisions?page=1&page_size=100`,
    )
  ).data;
}

export async function instrumentHistory(
  instrumentId: string,
): Promise<Page<InstrumentHistoryItem>> {
  return (
    await apiRequest<Page<InstrumentHistoryItem>>(
      `/api/v1/instruments/${instrumentId}/history?page=1&page_size=100`,
    )
  ).data;
}

export async function createReportRevision(
  reportId: string,
  data: {
    test_session_id: string;
    revision_reason: string;
    intended_issuer_id: string;
    planned_issue_date: string;
  },
  etag: string,
): Promise<ReportGenerationResponse> {
  return (
    await apiRequest<ReportGenerationResponse>(
      `/api/v1/reports/${reportId}/revisions`,
      {
        method: "POST",
        body: data,
        etag,
        idempotencyKey: createIdempotencyKey(),
      },
    )
  ).data;
}

type DownloadAuthorization = {
  download_url: string;
  file_name: string;
};

async function startAuthorizedDownload(path: string, fallbackName: string) {
  const authorization = (
    await apiRequest<DownloadAuthorization>(path, {
      method: "GET",
    })
  ).data;

  if (!authorization.download_url) {
    throw new Error("Download authorization did not include a download URL.");
  }

  const anchor = document.createElement("a");
  anchor.href = authorization.download_url;
  anchor.download = authorization.file_name || fallbackName;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export async function downloadPreview(previewId: string, format: ReportFormat) {
  await startAuthorizedDownload(
    `/api/v1/report-previews/${previewId}/download?format=${format}`,
    `UNOFFICIAL-PREVIEW-${previewId}.${format}`,
  );
}

export async function downloadSimulation(
  previewId: string,
  format: ReportFormat,
) {
  await startAuthorizedDownload(
    `/api/v1/report-previews/${previewId}/download?format=${format}`,
    `SIMULATED-APPROVED-DEMO-${previewId}.${format}`,
  );
}

export async function downloadReport(
  reportId: string,
  reportNumber: string,
  revisionNo: number,
  format: ReportFormat,
) {
  await startAuthorizedDownload(
    `/api/v1/reports/${reportId}/download?format=${format}`,
    `${reportNumber}-R${revisionNo}.${format}`,
  );
}
