"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CorrectionScopeBuilder } from "@/components/review/correction-scope-builder";
import { ReviewHistory } from "@/components/review/review-history";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError, friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import {
  evaluationDashboard,
  evaluationDetail,
} from "@/lib/evaluations/api";
import {
  checklistRows,
  constructionDetail,
  constructionItems,
} from "@/lib/evaluations/special-api";
import { correctionTargetOptions } from "@/lib/review/correction-targets";
import {
  correctionHistory,
  finalApprove,
  finalReject,
  returnForCorrection,
  reviewHistory,
  technicalReview,
} from "@/lib/review/api";
import type { ReturnForCorrectionInput } from "@/lib/review/types";

function currentTechnicalApproval(
  actions: Awaited<ReturnType<typeof reviewHistory>>,
  revision: number,
) {
  const invalidated = new Set(
    actions
      .filter(
        (action) =>
          action.stage === "TECHNICAL_REVIEW" &&
          action.decision === "INVALIDATED" &&
          action.referenced_action_id,
      )
      .map((action) => action.referenced_action_id as string),
  );

  return (
    actions.find(
      (action) =>
        action.stage === "TECHNICAL_REVIEW" &&
        action.decision === "APPROVED" &&
        action.regulatory_revision === revision &&
        !invalidated.has(action.id),
    ) ?? null
  );
}

export function ReviewCase({
  sessionId,
  mode,
}: {
  sessionId: string;
  mode: "technical" | "approval";
}) {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [comment, setComment] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const detail = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });
  const dashboard = useQuery({
    queryKey: ["evaluation-dashboard", sessionId],
    queryFn: () => evaluationDashboard(sessionId),
  });
  const history = useQuery({
    queryKey: ["review-history", sessionId],
    queryFn: () => reviewHistory(sessionId),
  });
  const corrections = useQuery({
    queryKey: ["corrections", sessionId],
    queryFn: () => correctionHistory(sessionId),
  });

  const construction = useQuery({
    queryKey: ["review-construction", sessionId],
    queryFn: async () => {
      try {
        return (await constructionDetail(sessionId)).item;
      } catch {
        return null;
      }
    },
    enabled: mode === "technical",
    retry: false,
  });
  const constructionRows = useQuery({
    queryKey: ["review-construction-items", sessionId],
    queryFn: async () => {
      try {
        return await constructionItems(sessionId);
      } catch {
        return [];
      }
    },
    enabled: mode === "technical",
    retry: false,
  });
  const checklist = useQuery({
    queryKey: ["review-checklist", sessionId],
    queryFn: async () => {
      try {
        return await checklistRows(sessionId);
      } catch {
        return [];
      }
    },
    enabled: mode === "technical",
    retry: false,
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["review-history", sessionId],
      }),
      queryClient.invalidateQueries({ queryKey: ["corrections", sessionId] }),
      queryClient.invalidateQueries({ queryKey: ["evaluations"] }),
    ]);
  }

  function captureError(cause: unknown) {
    if (
      cause instanceof ApiError &&
      (cause.status === 412 || cause.code === "VERSION_CONFLICT")
    ) {
      setConflict(true);
    }
    setError(
      cause instanceof Error && !(cause instanceof ApiError)
        ? cause.message
        : friendlyApiMessage(cause),
    );
  }

  const technical = useMutation({
    mutationFn: async (decision: "APPROVED" | "REJECTED") => {
      if (!detail.data?.etag) throw new Error("Reload before review.");
      if (decision === "REJECTED" && !comment.trim()) {
        throw new Error("A rejection comment is required.");
      }
      return technicalReview(
        sessionId,
        {
          decision,
          comment: comment.trim() || null,
          reviewed_regulatory_revision:
            detail.data.item.regulatory_revision,
        },
        detail.data.etag,
      );
    },
    onSuccess: async () => {
      setComment("");
      setError(null);
      setConflict(false);
      await refresh();
    },
    onError: captureError,
  });

  const correction = useMutation({
    mutationFn: async (data: ReturnForCorrectionInput) => {
      if (!detail.data?.etag) {
        throw new Error("Reload before returning for correction.");
      }
      return returnForCorrection(sessionId, data, detail.data.etag);
    },
    onSuccess: async () => {
      setError(null);
      setConflict(false);
      await refresh();
    },
    onError: captureError,
  });

  const approve = useMutation({
    mutationFn: async () => {
      if (!detail.data?.etag) {
        throw new Error("Reload before final approval.");
      }
      return finalApprove(sessionId, detail.data.etag);
    },
    onSuccess: async () => {
      setError(null);
      setConflict(false);
      await refresh();
    },
    onError: captureError,
  });

  const reject = useMutation({
    mutationFn: async () => {
      if (!detail.data?.etag) {
        throw new Error("Reload before final rejection.");
      }
      if (!rejectReason.trim()) {
        throw new Error("Rejection reason is required.");
      }
      return finalReject(
        sessionId,
        rejectReason.trim(),
        detail.data.etag,
      );
    },
    onSuccess: async () => {
      setRejectReason("");
      setError(null);
      setConflict(false);
      await refresh();
    },
    onError: captureError,
  });

  if (
    detail.isPending ||
    dashboard.isPending ||
    history.isPending ||
    corrections.isPending
  ) {
    return <LoadingState label="Loading review case" />;
  }

  if (detail.isError) return <ErrorState error={detail.error} />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} />;
  if (history.isError) return <ErrorState error={history.error} />;
  if (corrections.isError) return <ErrorState error={corrections.error} />;

  const session = detail.data.item;
  const technicalApproval = currentTechnicalApproval(
    history.data,
    session.regulatory_revision,
  );

  const scopeOptions = correctionTargetOptions({
    dashboard: dashboard.data,
    construction: construction.data ?? null,
    constructionItems: constructionRows.data ?? [],
    checklist: checklist.data ?? [],
  });

  const openCorrection = corrections.data.find(
    (item) => item.correction_status === "OPEN",
  );

  const canTechnical =
    mode === "technical" &&
    hasPermission("review:perform") &&
    session.workflow_status === "UNDER_REVIEW";

  const canReturn =
    mode === "technical" &&
    hasPermission("review:return_correction") &&
    session.workflow_status === "UNDER_REVIEW" &&
    !openCorrection;

  const canFinalize =
    mode === "approval" &&
    hasPermission("approval:finalize") &&
    session.workflow_status === "UNDER_REVIEW";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={
          mode === "technical" ? "Technical review" : "Final approval"
        }
        title={
          session.application_number ??
          `Evaluation ${session.id.slice(0, 8)}`
        }
        description={`Session revision ${session.session_revision_no} · regulatory revision ${session.regulatory_revision}`}
        actions={
          <Link
            className="button button-secondary"
            href={`/evaluations/${sessionId}`}
          >
            Open evaluation
          </Link>
        }
      />

      <StatusAxes
        workflow={session.workflow_status}
        evaluation={session.evaluation_status}
        outcome={session.compliance_outcome}
      />

      {mode === "approval" ? (
        <div className="governance-banner">
          <strong>Approval and compliance are separate.</strong>
          <span>
            Final approval confirms the reviewed, complete regulatory record.
            A COMPLETE + NONCOMPLIANT evaluation can be validly approved and
            reported as NONCOMPLIANT.
          </span>
        </div>
      ) : null}

      {conflict ? (
        <div className="conflict-banner">
          <strong>The review source changed.</strong>
          <span>Reload before another governance mutation.</span>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() => {
              setConflict(false);
              setError(null);
              void refresh();
            }}
          >
            Reload current revision
          </button>
        </div>
      ) : null}

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="review-layout">
        <div className="review-main">
          <section className="review-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Record readiness</p>
              <h2>Current evaluation</h2>
            </div>
            <div className="review-facts">
              <div>
                <span>Regulatory revision</span>
                <strong>{session.regulatory_revision}</strong>
              </div>
              <div>
                <span>Sections</span>
                <strong>{dashboard.data.sections.length} / 17</strong>
              </div>
              <div>
                <span>Open correction</span>
                <strong>{openCorrection ? "Yes" : "No"}</strong>
              </div>
              <div>
                <span>Current technical approval</span>
                <strong>
                  {technicalApproval ? "Recorded" : "Not recorded"}
                </strong>
              </div>
            </div>
          </section>

          {mode === "technical" ? (
            <>
              <section className="review-card">
                <div className="panel-heading">
                  <p className="page-eyebrow">Reviewer decision</p>
                  <h2>Technical review</h2>
                  <p>
                    The backend enforces reviewer independence and requires the
                    decision to reference the current regulatory revision.
                  </p>
                </div>

                <label className="form-field">
                  <span>
                    Comment <small>(required when rejecting)</small>
                  </span>
                  <textarea
                    rows={4}
                    maxLength={4000}
                    value={comment}
                    disabled={!canTechnical}
                    onChange={(event) => setComment(event.target.value)}
                  />
                </label>

                {canTechnical ? (
                  <div className="form-actions">
                    <button
                      className="button button-secondary"
                      type="button"
                      disabled={technical.isPending || !comment.trim()}
                      onClick={() => technical.mutate("REJECTED")}
                    >
                      Reject technical review
                    </button>
                    <button
                      className="button button-primary"
                      type="button"
                      disabled={technical.isPending}
                      onClick={() => technical.mutate("APPROVED")}
                    >
                      Approve technical review
                    </button>
                  </div>
                ) : null}
              </section>

              {canReturn ? (
                <section className="review-card">
                  <div className="panel-heading">
                    <p className="page-eyebrow">Bounded correction</p>
                    <h2>Return specific source data</h2>
                    <p>
                      Scope is generated from this session’s real records and
                      the backend’s frozen correction field allow-list.
                    </p>
                  </div>
                  <CorrectionScopeBuilder
                    options={scopeOptions}
                    submitting={correction.isPending}
                    onSubmit={async (data) => {
                      await correction.mutateAsync(data);
                    }}
                  />
                </section>
              ) : null}
            </>
          ) : (
            <section className="review-card">
              <div className="panel-heading">
                <p className="page-eyebrow">Independent officer decision</p>
                <h2>Final approval</h2>
                <p>
                  The backend requires a valid current technical approval and
                  independently checks the approving officer against the
                  session starter and all raw-observation authors.
                </p>
              </div>

              <div className="approval-readiness">
                <span>Technical approval</span>
                <StatusBadge
                  value={
                    technicalApproval ? "APPROVED" : "REVIEW_REQUIRED"
                  }
                />
              </div>

              <label className="form-field">
                <span>Final rejection reason</span>
                <textarea
                  rows={4}
                  maxLength={4000}
                  value={rejectReason}
                  disabled={!canFinalize}
                  onChange={(event) => setRejectReason(event.target.value)}
                />
              </label>

              {canFinalize ? (
                <div className="form-actions">
                  <button
                    className="button button-secondary"
                    type="button"
                    disabled={reject.isPending || !rejectReason.trim()}
                    onClick={() => reject.mutate()}
                  >
                    Reject record
                  </button>
                  <button
                    className="button button-primary"
                    type="button"
                    disabled={approve.isPending}
                    onClick={() => approve.mutate()}
                  >
                    {approve.isPending
                      ? "Approving…"
                      : "Grant final approval"}
                  </button>
                </div>
              ) : null}
            </section>
          )}
        </div>

        <aside className="review-side">
          <section className="review-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Immutable governance history</p>
              <h2>Review & approval actions</h2>
            </div>
            <ReviewHistory
              actions={history.data}
              regulatoryRevision={session.regulatory_revision}
            />
          </section>

          <section className="review-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Correction history</p>
              <h2>Bounded requests</h2>
            </div>
            {corrections.data.length === 0 ? (
              <p className="muted-copy">No correction requests recorded.</p>
            ) : (
              <div className="correction-history-list">
                {corrections.data.map((item) => (
                  <div key={item.id}>
                    <div>
                      <StatusBadge value={item.correction_status} />
                      <span>{item.target_workflow_status}</span>
                    </div>
                    <strong>{item.reason}</strong>
                    <small>
                      {new Date(item.requested_at).toLocaleString()}
                    </small>
                  </div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
