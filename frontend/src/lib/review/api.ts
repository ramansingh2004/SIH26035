import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";
import type {
  SessionResource,
  SessionView,
} from "@/lib/evaluations/types";

import type {
  ApprovalActionView,
  CorrectionRequestView,
  ReturnForCorrectionInput,
  TechnicalReviewInput,
} from "./types";

export async function reviewHistory(
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

export async function submitForReview(
  sessionId: string,
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${sessionId}/submit-for-review`,
    { method: "POST", etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function technicalReview(
  sessionId: string,
  data: TechnicalReviewInput,
  etag: string,
): Promise<ApprovalActionView> {
  return (
    await apiRequest<ApprovalActionView>(
      `/api/v1/test-sessions/${sessionId}/reviews`,
      { method: "POST", body: data, etag },
    )
  ).data;
}

export async function returnForCorrection(
  sessionId: string,
  data: ReturnForCorrectionInput,
  etag: string,
): Promise<CorrectionRequestView> {
  return (
    await apiRequest<CorrectionRequestView>(
      `/api/v1/test-sessions/${sessionId}/return-for-correction`,
      { method: "POST", body: data, etag },
    )
  ).data;
}

export async function resolveCorrection(
  sessionId: string,
  requestId: string,
  resolutionNote: string,
  correctionEtag: string,
): Promise<CorrectionRequestView> {
  return (
    await apiRequest<CorrectionRequestView>(
      `/api/v1/test-sessions/${sessionId}/corrections/${requestId}/resolve`,
      {
        method: "POST",
        body: { resolution_note: resolutionNote },
        etag: correctionEtag,
      },
    )
  ).data;
}

export async function finalApprove(
  sessionId: string,
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${sessionId}/approve`,
    {
      method: "POST",
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function finalReject(
  sessionId: string,
  reason: string,
  etag: string,
): Promise<SessionResource> {
  const response = await apiRequest<SessionView>(
    `/api/v1/test-sessions/${sessionId}/reject`,
    { method: "POST", body: { reason }, etag },
  );
  return { item: response.data, etag: response.etag };
}
