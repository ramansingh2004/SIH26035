"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDetail } from "@/lib/evaluations/api";
import {
  createReportRevision,
  downloadReport,
  instrumentHistory,
  issueReport,
  regenerateReport,
  reportDetail,
  reportGenerations,
  reportRevisions,
} from "@/lib/reports/api";
import type { ReportFormat } from "@/lib/reports/types";

function utcDate() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const queryClient = useQueryClient();
  const { user, hasPermission } = useAuth();
  const [plannedIssueDate, setPlannedIssueDate] = useState(utcDate());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [revisionSessionId, setRevisionSessionId] = useState("");
  const [revisionReason, setRevisionReason] = useState("");

  const report = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => reportDetail(reportId),
  });
  const generations = useQuery({
    queryKey: ["report-generations", reportId],
    queryFn: () => reportGenerations(reportId),
  });
  const revisions = useQuery({
    queryKey: ["report-revisions", reportId],
    queryFn: () => reportRevisions(reportId),
  });
  const sourceSession = useQuery({
    queryKey: ["evaluation", report.data?.item.test_session_id],
    queryFn: () => evaluationDetail(report.data!.item.test_session_id),
    enabled: Boolean(report.data?.item.test_session_id),
  });
  const history = useQuery({
    queryKey: ["instrument-history", sourceSession.data?.item.instrument_id],
    queryFn: () => instrumentHistory(sourceSession.data!.item.instrument_id),
    enabled: Boolean(sourceSession.data?.item.instrument_id),
  });

  const validRevisionSessions = useMemo(() => {
    if (!history.data || !report.data) return [];
    return history.data.items.filter(
      (item) =>
        item.session_id !== report.data!.item.test_session_id &&
        item.workflow_status === "APPROVED" &&
        item.evaluation_status === "COMPLETE" &&
        (item.compliance_outcome === "COMPLIANT" ||
          item.compliance_outcome === "NONCOMPLIANT") &&
        !item.report_id,
    );
  }, [history.data, report.data]);

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["report", reportId] }),
      queryClient.invalidateQueries({
        queryKey: ["report-generations", reportId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["report-revisions", reportId],
      }),
      queryClient.invalidateQueries({ queryKey: ["reports"] }),
      queryClient.invalidateQueries({
        queryKey: ["instrument-history", sourceSession.data?.item.instrument_id],
      }),
    ]);
  }

  async function action(key: string, work: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await work();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  if (report.isPending || generations.isPending || revisions.isPending) {
    return <LoadingState label="Loading report record" />;
  }
  if (report.isError) return <ErrorState error={report.error} />;
  if (generations.isError) return <ErrorState error={generations.error} />;
  if (revisions.isError) return <ErrorState error={revisions.error} />;

  const item = report.data.item;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Official report"
        title={`${item.report_number} · revision ${item.revision_no}`}
        description="Immutable report context, generation attempts, issue action and revision chain."
        actions={
          <Link className="button button-secondary" href="/reports">
            Back to repository
          </Link>
        }
      />
      {error ? <div className="form-alert">{error}</div> : null}

      <section className="report-overview-grid">
        <div className="report-metric-card">
          <span>Report status</span>
          <StatusBadge value={item.report_status} />
        </div>
        <div className="report-metric-card">
          <span>Revision</span>
          <strong>{item.revision_no}</strong>
        </div>
        <div className="report-metric-card">
          <span>Issued at</span>
          <strong>
            {item.issued_at
              ? new Date(item.issued_at).toLocaleString()
              : "Not issued"}
          </strong>
        </div>
        <div className="report-metric-card">
          <span>Report hash</span>
          <code>{item.report_hash ?? "Not selected"}</code>
        </div>
      </section>

      {item.report_status !== "UNISSUED" ? (
        <section className="report-repository-card report-download-card">
          <div className="panel-heading">
            <p className="page-eyebrow">Controlled download</p>
            <h2>Issued report files</h2>
            <p>
              PDF and DOCX are rendered from the same immutable selected generation.
              Download authorization is audited and the issued report hash remains
              unchanged.
            </p>
          </div>
          <div className="report-download-grid">
            {(["pdf", "docx"] as ReportFormat[]).map((format) => (
              <button
                className="button button-secondary"
                type="button"
                key={format}
                disabled={busy === `download-${format}`}
                onClick={() =>
                  void action(`download-${format}`, async () => {
                    await downloadReport(
                      reportId,
                      item.report_number,
                      item.revision_no,
                      format,
                    );
                  })
                }
              >
                Download {format.toUpperCase()}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <section className="report-repository-card">
        <div className="panel-heading-row">
          <div className="panel-heading">
            <p className="page-eyebrow">Generation</p>
            <h2>Immutable attempts</h2>
          </div>
          {hasPermission("report:generate") &&
          item.report_status === "UNISSUED" ? (
            <div className="report-inline-form">
              <label className="form-field">
                <span>Planned issue date (UTC)</span>
                <input
                  type="date"
                  value={plannedIssueDate}
                  onChange={(event) => setPlannedIssueDate(event.target.value)}
                />
              </label>
              <button
                className="button button-secondary"
                type="button"
                disabled={busy === "regenerate" || !user || !report.data.etag}
                onClick={() =>
                  void action("regenerate", async () => {
                    await regenerateReport(
                      reportId,
                      {
                        intended_issuer_id: user!.id,
                        planned_issue_date: plannedIssueDate,
                      },
                      report.data.etag!,
                    );
                    await refresh();
                  })
                }
              >
                Regenerate
              </button>
            </div>
          ) : null}
        </div>

        <div className="report-generation-list">
          {generations.data
            .slice()
            .sort((a, b) => b.attempt_no - a.attempt_no)
            .map((generation) => {
              const issuerMatches = generation.intended_issuer_id === user?.id;
              const dateMatches = generation.planned_issue_date === utcDate();
              return (
                <div className="report-generation-row" key={generation.id}>
                  <div>
                    <strong>Attempt #{generation.attempt_no}</strong>
                    <span>
                      Revision {generation.source_regulatory_revision} · planned{" "}
                      {generation.planned_issue_date}
                    </span>
                    <code>{generation.context_hash}</code>
                  </div>
                  <div className="report-generation-actions">
                    <StatusBadge value={generation.generation_status} />
                    {item.report_status === "UNISSUED" &&
                    generation.generation_status === "READY" &&
                    hasPermission("report:issue") ? (
                      <button
                        className="button button-primary button-compact"
                        type="button"
                        disabled={
                          !issuerMatches ||
                          !dateMatches ||
                          !report.data.etag ||
                          busy === `issue-${generation.id}`
                        }
                        onClick={() =>
                          void action(`issue-${generation.id}`, async () => {
                            await issueReport(
                              reportId,
                              generation.id,
                              item.supersedes_report_id,
                              report.data.etag!,
                            );
                            await refresh();
                          })
                        }
                      >
                        Issue report
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
        </div>

        {item.report_status === "UNISSUED" &&
        generations.data.some(
          (generation) =>
            generation.generation_status === "READY" &&
            (generation.intended_issuer_id !== user?.id ||
              generation.planned_issue_date !== utcDate()),
        ) ? (
          <div className="regulatory-blocker">
            <strong>Issue reservation no longer matches.</strong>
            <span>
              The issuer and current UTC date must match the values captured in
              the READY generation. Regenerate a new immutable attempt before issue.
            </span>
          </div>
        ) : null}
      </section>

      <section className="report-repository-card">
        <div className="panel-heading">
          <p className="page-eyebrow">Revision chain</p>
          <h2>Reports in this series</h2>
        </div>
        {revisions.data.items.map((revision) => (
          <div className="report-revision-row" key={revision.id}>
            <div>
              <strong>
                {revision.report_number} · revision {revision.revision_no}
              </strong>
              <span>{revision.revision_reason ?? "Original issue"}</span>
            </div>
            <div className="run-actions">
              <StatusBadge value={revision.report_status} />
              <Link
                className="button button-secondary button-compact"
                href={`/reports/${revision.id}`}
              >
                Open
              </Link>
            </div>
          </div>
        ))}
      </section>

      {item.report_status === "ISSUED" && hasPermission("report:generate") ? (
        <section className="report-repository-card">
          <div className="panel-heading">
            <p className="page-eyebrow">Controlled correction</p>
            <h2>Create report revision from an approved child session</h2>
          </div>
          {history.isPending || sourceSession.isPending ? (
            <LoadingState label="Loading evaluation revision history" />
          ) : history.isError ? (
            <ErrorState error={history.error} />
          ) : sourceSession.isError ? (
            <ErrorState error={sourceSession.error} />
          ) : (
            <div className="report-revision-form">
              <label className="form-field">
                <span>Approved child session</span>
                <select
                  value={revisionSessionId}
                  onChange={(event) => setRevisionSessionId(event.target.value)}
                >
                  <option value="">Select approved session revision</option>
                  {validRevisionSessions.map((session) => (
                    <option value={session.session_id} key={session.session_id}>
                      Session revision {session.session_revision_no} ·{" "}
                      {session.compliance_outcome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-field">
                <span>Revision reason</span>
                <textarea
                  rows={3}
                  value={revisionReason}
                  onChange={(event) => setRevisionReason(event.target.value)}
                />
              </label>
              <label className="form-field">
                <span>Planned issue date (UTC)</span>
                <input
                  type="date"
                  value={plannedIssueDate}
                  onChange={(event) => setPlannedIssueDate(event.target.value)}
                />
              </label>
              <button
                className="button button-primary"
                type="button"
                disabled={
                  !revisionSessionId ||
                  !revisionReason.trim() ||
                  !user ||
                  !report.data.etag ||
                  busy === "revision"
                }
                onClick={() =>
                  void action("revision", async () => {
                    await createReportRevision(
                      reportId,
                      {
                        test_session_id: revisionSessionId,
                        revision_reason: revisionReason.trim(),
                        intended_issuer_id: user!.id,
                        planned_issue_date: plannedIssueDate,
                      },
                      report.data.etag!,
                    );
                    await refresh();
                  })
                }
              >
                Generate new report revision
              </button>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
