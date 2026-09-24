"use client";

import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { getDashboardSummary } from "@/lib/dashboard/queries";

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function CountPanel({
  title,
  counts,
}: {
  title: string;
  counts: Record<string, number>;
}) {
  const entries = Object.entries(counts).filter(([, count]) => count > 0);

  return (
    <section className="dashboard-panel">
      <div className="panel-heading">
        <h2>{title}</h2>
      </div>
      {entries.length ? (
        <div className="count-list">
          {entries.map(([label, count]) => (
            <div className="count-row" key={label}>
              <StatusBadge value={label} />
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted-copy">No records in this category.</p>
      )}
    </section>
  );
}

function formatAction(action: string): string {
  return action
    .split(".")
    .map((part) => part.replaceAll("_", " "))
    .join(" · ");
}

export default function DashboardPage() {
  const { selectedLaboratoryId, hasPermission, user } = useAuth();

  const canRead = hasPermission("dashboard:read");

  const dashboard = useQuery({
    queryKey: ["dashboard", selectedLaboratoryId],
    queryFn: () => getDashboardSummary(selectedLaboratoryId!),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Laboratory operations"
        title="Dashboard"
        description="Current testing, review and reporting activity for the selected laboratory scope."
      />

      {!selectedLaboratoryId ? (
        <EmptyState
          title="No laboratory scope selected"
          description={
            user?.global_roles.includes("ADMIN")
              ? "Global administration does not automatically grant access to laboratory regulatory records. Assign an authorized laboratory role to view laboratory activity."
              : "Your account does not currently have an accessible laboratory scope."
          }
        />
      ) : !canRead ? (
        <EmptyState
          title="Dashboard access unavailable"
          description="Your current laboratory assignment does not include dashboard:read."
        />
      ) : dashboard.isPending ? (
        <LoadingState label="Loading laboratory dashboard" />
      ) : dashboard.isError ? (
        <ErrorState
          error={dashboard.error}
          onRetry={() => void dashboard.refetch()}
        />
      ) : (
        <>
          <section className="metric-grid" aria-label="Operational summary">
            <MetricCard
              label="Testing in progress"
              value={dashboard.data.work_in_progress_count}
              detail={`${dashboard.data.session_total} total sessions`}
            />
            <MetricCard
              label="Pending review"
              value={dashboard.data.review_pending_count}
              detail="Under technical review"
            />
            <MetricCard
              label="Approved / unissued"
              value={dashboard.data.approved_unissued_count}
              detail="Ready for report workflow"
            />
            <MetricCard
              label="Issued sessions"
              value={dashboard.data.issued_session_count}
              detail={`${dashboard.data.report_total} repository reports`}
            />
          </section>

          {dashboard.data.evaluation_attention_count > 0 ? (
            <div className="attention-banner">
              <strong>
                {dashboard.data.evaluation_attention_count} evaluation
                {dashboard.data.evaluation_attention_count === 1
                  ? ""
                  : "s"}{" "}
                need attention
              </strong>
              <span>
                Includes incomplete, stale or review-required evaluation states.
              </span>
            </div>
          ) : null}

          <div className="dashboard-grid">
            <CountPanel
              title="Workflow status"
              counts={dashboard.data.workflow_counts}
            />
            <CountPanel
              title="Evaluation readiness"
              counts={dashboard.data.evaluation_counts}
            />
            <CountPanel
              title="Compliance outcomes"
              counts={dashboard.data.outcome_counts}
            />
            <CountPanel
              title="Report status"
              counts={dashboard.data.report_status_counts}
            />
          </div>

          <section className="dashboard-panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <p className="page-eyebrow">Traceability</p>
                <h2>Recent activity</h2>
              </div>
              <span className="record-count">
                {dashboard.data.recent_activity.total} recorded event
                {dashboard.data.recent_activity.total === 1 ? "" : "s"}
              </span>
            </div>

            {dashboard.data.recent_activity.items.length ? (
              <div className="activity-list">
                {dashboard.data.recent_activity.items.map((item) => (
                  <article className="activity-row" key={item.id}>
                    <div className="activity-mark" aria-hidden="true" />
                    <div>
                      <strong>{formatAction(item.action)}</strong>
                      <span>
                        {item.entity_type.replaceAll("_", " ")}
                        {item.reason ? ` · ${item.reason}` : ""}
                      </span>
                    </div>
                    <time dateTime={item.created_at}>
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(item.created_at))}
                    </time>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No recent activity"
                description="Audit events for this laboratory will appear here."
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}
