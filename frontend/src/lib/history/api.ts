import { apiRequest } from "@/lib/api/client";

import type {
  ApprovalActionView,
  CorrectionRequestView,
  InstrumentHistoryPage,
  SessionRevisionPage,
} from "./types";

export async function sessionRevisionHistory(
  sessionId: string,
): Promise<SessionRevisionPage> {
  return (
    await apiRequest<SessionRevisionPage>(
      `/api/v1/test-sessions/${sessionId}/revisions?page=1&page_size=100`,
    )
  ).data;
}

export async function approvalHistory(
  sessionId: string,
): Promise<ApprovalActionView[]> {
  return (
    await apiRequest<ApprovalActionView[]>(
      `/api/v1/test-sessions/${sessionId}/reviews`,
    )
  ).data;
}

export async function correctionHistory(
  sessionId: string,
): Promise<CorrectionRequestView[]> {
  return (
    await apiRequest<CorrectionRequestView[]>(
      `/api/v1/test-sessions/${sessionId}/corrections`,
    )
  ).data;
}

export async function instrumentEvaluationHistory(
  instrumentId: string,
): Promise<InstrumentHistoryPage> {
  return (
    await apiRequest<InstrumentHistoryPage>(
      `/api/v1/instruments/${instrumentId}/history?page=1&page_size=100`,
    )
  ).data;
}
