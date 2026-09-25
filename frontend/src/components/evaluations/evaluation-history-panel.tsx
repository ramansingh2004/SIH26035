"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { StatusAxes } from "@/components/evaluations/status-axes";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import {
  approvalHistory,
  correctionHistory,
  sessionRevisionHistory,
} from "@/lib/history/api";

function scopeCount(scope: Record<string, unknown>): number {
  const targets = scope.targets;
  return Array.isArray(targets) ? targets.length : 0;
}

export function EvaluationHistoryPanel({
  sessionId,
}: {
  sessionId: string;
}) {
  const { hasPermission } = useAuth();
  const canReadApprovals = hasPermission("approval:read");

  const revisions = useQuery({
    queryKey: ["session-revision-history", sessionId],
    queryFn: () => sessionRevisionHistory(sessionId),
  });

  const approvals = useQuery({
    queryKey: ["approval-history", sessionId],
    queryFn: () => approvalHistory(sessionId),
    enabled: canReadApprovals,
  });

  const corrections = useQuery({
    queryKey: ["correction-history", sessionId],
    queryFn: () => correctionHistory(sessionId),
    enabled: canReadApprovals,
  });

  return (
    <section className="traceability-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Traceability</p>
        <h2>Evaluation lifecycle history</h2>
        <p>
          Session revisions, review actions and bounded correction requests are
          append-only history. Earlier approved or rejected states are not
          overwritten.
        </p>
      </div>

      <div className="traceability-grid">
        <div className="traceability-column">
          <h3>Session revision chain</h3>
          {revisions.isPending ? (
            <LoadingState label="Loading session revisions" />
          ) : revisions.isError ? (
            <ErrorState error={revisions.error} />
          ) : revisions.data.items.length === 0 ? (
            <p className="detail-note">No session revisions recorded.</p>
          ) : (
            <div className="traceability-list">
              {revisions.data.items
                .slice()
                .sort(
                  (left, right) =>
                    right.session_revision_no - left.session_revision_no,
                )
                .map((revision) => (
                  <article
                    className="traceability-row"
                    key={revision.id}
                  >
                    <div>
                      <strong>
                        Session revision {revision.session_revision_no}
                      </strong>
                      <span>
                        Regulatory revision {revision.regulatory_revision}
                        {" · "}
                        {new Date(revision.created_at).toLocaleString()}
                      </span>
                      <small>
                        {revision.revision_reason ?? "Original evaluation"}
                      </small>
                    </div>
                    <div className="traceability-actions">
                      <StatusAxes
                        workflow={revision.workflow_status}
                        evaluation={revision.evaluation_status}
                        outcome={revision.compliance_outcome}
                      />
                      <Link
                        className="button button-secondary button-compact"
                        href={`/evaluations/${revision.id}`}
                      >
                        Open
                      </Link>
                    </div>
                  </article>
                ))}
            </div>
          )}
        </div>

        <div className="traceability-column">
          <h3>Review and approval events</h3>
          {!canReadApprovals ? (
            <p className="detail-note">
              Review history requires approval:read permission.
            </p>
          ) : approvals.isPending ? (
            <LoadingState label="Loading review history" />
          ) : approvals.isError ? (
            <ErrorState error={approvals.error} />
          ) : approvals.data.length === 0 ? (
            <p className="detail-note">No review actions recorded.</p>
          ) : (
            <div className="traceability-list">
              {approvals.data
                .slice()
                .sort(
                  (left, right) =>
                    new Date(right.created_at).getTime() -
                    new Date(left.created_at).getTime(),
                )
                .map((action) => (
                  <article className="traceability-row" key={action.id}>
                    <div>
                      <strong>
                        {action.stage.replaceAll("_", " ")}
                      </strong>
                      <span>
                        Regulatory revision {action.regulatory_revision}
                        {" · "}
                        {new Date(action.created_at).toLocaleString()}
                      </span>
                      {action.comment || action.reason ? (
                        <small>{action.comment ?? action.reason}</small>
                      ) : null}
                    </div>
                    <StatusBadge value={action.decision} />
                  </article>
                ))}
            </div>
          )}
        </div>
      </div>

      {canReadApprovals ? (
        <div className="traceability-corrections">
          <h3>Bounded corrections</h3>
          {corrections.isPending ? (
            <LoadingState label="Loading correction history" />
          ) : corrections.isError ? (
            <ErrorState error={corrections.error} />
          ) : corrections.data.length === 0 ? (
            <p className="detail-note">No correction requests recorded.</p>
          ) : (
            <div className="traceability-list">
              {corrections.data
                .slice()
                .sort(
                  (left, right) =>
                    new Date(right.requested_at).getTime() -
                    new Date(left.requested_at).getTime(),
                )
                .map((request) => (
                  <article className="traceability-row" key={request.id}>
                    <div>
                      <strong>{request.reason}</strong>
                      <span>
                        Return to {request.target_workflow_status.replaceAll("_", " ")}
                        {" · "}
                        {scopeCount(request.requested_scope_json)} scoped target(s)
                      </span>
                      <small>
                        Requested {new Date(request.requested_at).toLocaleString()}
                        {request.resolved_at
                          ? ` · resolved ${new Date(
                              request.resolved_at,
                            ).toLocaleString()}`
                          : ""}
                      </small>
                    </div>
                    <StatusBadge value={request.correction_status} />
                  </article>
                ))}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
