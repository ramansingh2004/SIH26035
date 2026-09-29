"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApplicabilityPanel } from "@/components/evaluations/applicability-panel";
import { EvaluationHistoryPanel } from "@/components/evaluations/evaluation-history-panel";
import { InstrumentSnapshotPanel } from "@/components/evaluations/instrument-snapshot";
import { SectionNavigator } from "@/components/evaluations/section-navigator";
import { EvaluationProgressOverview } from "@/components/polish/evaluation-progress-overview";
import { ReportSessionPanel } from "@/components/reports/report-session-panel";
import { ReviewLifecyclePanel } from "@/components/review/review-lifecycle-panel";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError, friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import {
  configureEvaluation,
  evaluationDashboard,
  evaluationDetail,
  startTesting,
} from "@/lib/evaluations/api";
import { useState } from "react";

export default function EvaluationWorkspacePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const detail = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });

  const dashboard = useQuery({
    queryKey: ["evaluation-dashboard", sessionId],
    queryFn: () => evaluationDashboard(sessionId),
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      }),
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
    setActionError(friendlyApiMessage(cause));
  }

  const configure = useMutation({
    mutationFn: async () => {
      if (!detail.data?.etag) {
        throw new Error("Reload the evaluation before configuration.");
      }
      return configureEvaluation(
        sessionId,
        detail.data.item.instrument_snapshot,
        detail.data.etag,
      );
    },
    onSuccess: async () => {
      setConflict(false);
      setActionError(null);
      await refresh();
    },
    onError: captureError,
  });

  const start = useMutation({
    mutationFn: async () => {
      if (!detail.data?.etag) {
        throw new Error("Reload the evaluation before starting testing.");
      }
      return startTesting(sessionId, detail.data.etag);
    },
    onSuccess: async () => {
      setConflict(false);
      setActionError(null);
      await refresh();
    },
    onError: captureError,
  });

  if (detail.isPending || dashboard.isPending) {
    return <LoadingState label="Loading evaluation workspace" />;
  }

  if (detail.isError) return <ErrorState error={detail.error} />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} />;

  const session = detail.data.item;
  const sections = dashboard.data.sections;
  const canUpdate = hasPermission("session:update");
  const canExecute = hasPermission("test:execute");

  const requiredSections = sections.filter(
    (section) => section.applicability_status === "REQUIRED",
  );
  const attentionSections = sections.filter(
    (section) =>
      section.applicability_status === "REQUIRES_REVIEW" ||
      ["INCOMPLETE", "STALE", "REVIEW_REQUIRED"].includes(
        section.evaluation_status,
      ),
  );
  const notApplicableCount = sections.filter(
    (section) => section.applicability_status === "NOT_APPLICABLE",
  ).length;

  return (
    <div className="page-stack">
      <header className="evaluation-record-header">
        <div className="evaluation-record-heading">
          <p className="record-kicker">Evaluation record</p>
          <div className="evaluation-record-title-row">
            <h1>
              {session.application_number ??
                `Evaluation ${session.id.slice(0, 8)}`}
            </h1>
            <StatusBadge value={session.compliance_outcome} />
          </div>
          <p>
            {session.evaluation_context.replaceAll("_", " ")}
            {" · "}session revision {session.session_revision_no}
            {" · "}regulatory revision {session.regulatory_revision}
          </p>
        </div>

        <dl className="evaluation-record-meta">
          <div>
            <dt>Workflow</dt>
            <dd>{session.workflow_status.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Evaluation</dt>
            <dd>{session.evaluation_status.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Regulatory revision</dt>
            <dd>{session.regulatory_revision}</dd>
          </div>
          <div>
            <dt>Sections</dt>
            <dd>{sections.length}</dd>
          </div>
        </dl>
      </header>

      <EvaluationProgressOverview session={session} sections={sections} />

      <nav className="evaluation-jump-nav" aria-label="Evaluation workspace">
        <span>Jump to</span>
        <a href="#overview">Overview</a>
        <a href="#governance">Governance</a>
        <a href="#readiness">Readiness</a>
        <a href="#reporting">Reporting</a>
        <a href="#history">History</a>
      </nav>

      {conflict ? (
        <div className="conflict-banner">
          <strong>This evaluation changed on the server.</strong>
          <span>
            Reload the current record before attempting another write. A 412
            conflict is never overwritten automatically.
          </span>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() => {
              setConflict(false);
              setActionError(null);
              void refresh();
            }}
          >
            Reload current version
          </button>
        </div>
      ) : null}

      {actionError ? (
        <div className="form-alert" role="alert">
          {actionError}
        </div>
      ) : null}

      <div className="evaluation-workspace-grid">
        <aside className="evaluation-sections-panel">
          <div className="panel-heading">
            <p className="page-eyebrow">OIML R76</p>
            <h2>17 sections</h2>
          </div>
          <SectionNavigator sessionId={sessionId} sections={sections} />
        </aside>

        <div className="evaluation-main-column">
          <section className="evaluation-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Lifecycle</p>
              <h2>Evaluation setup</h2>
            </div>

            <div className="workflow-steps">
              <div
                className={`workflow-step ${
                  session.workflow_status !== "DRAFT" ? "is-complete" : ""
                }`}
              >
                <strong>1. Instrument snapshot</strong>
                <span>
                  Confirm the frozen session snapshot before applicability.
                </span>
                {session.workflow_status === "DRAFT" && canUpdate ? (
                  <button
                    className="button button-primary button-compact"
                    type="button"
                    disabled={configure.isPending}
                    onClick={() => configure.mutate()}
                  >
                    {configure.isPending
                      ? "Confirming…"
                      : "Confirm instrument snapshot"}
                  </button>
                ) : null}
              </div>

              <div
                className={`workflow-step ${
                  !["DRAFT", "INSTRUMENT_CONFIGURATION"].includes(
                    session.workflow_status,
                  )
                    ? "is-complete"
                    : ""
                }`}
              >
                <strong>2. Applicability</strong>
                <span>
                  Backend rules determine required, optional, N/A or
                  review-required slots.
                </span>
              </div>

              <div
                className={`workflow-step ${
                  [
                    "TESTING",
                    "EXAMINATION",
                    "UNDER_REVIEW",
                    "APPROVED",
                    "REPORT_ISSUED",
                  ].includes(session.workflow_status)
                    ? "is-complete"
                    : ""
                }`}
              >
                <strong>3. Start testing</strong>
                <span>
                  Testing can start only after authoritative applicability
                  confirmation.
                </span>
                {session.workflow_status === "APPLICABILITY_CONFIRMED" &&
                canExecute ? (
                  <button
                    className="button button-primary button-compact"
                    type="button"
                    disabled={start.isPending}
                    onClick={() => start.mutate()}
                  >
                    {start.isPending ? "Starting…" : "Start testing"}
                  </button>
                ) : null}
              </div>
            </div>
          </section>

          <InstrumentSnapshotPanel snapshot={session.instrument_snapshot} />

          <ReviewLifecyclePanel
            session={session}
            sessionEtag={detail.data.etag}
            onChanged={refresh}
          />

          {["INSTRUMENT_CONFIGURATION", "APPLICABILITY_CONFIRMED"].includes(
            session.workflow_status,
          ) ? (
            <ApplicabilityPanel
              sessionId={sessionId}
              etag={detail.data.etag}
              canExecute={canExecute}
              workflowStatus={session.workflow_status}
              onChanged={refresh}
            />
          ) : null}

          <section
            className="evaluation-card section-readiness-panel"
            id="readiness"
          >
            <div className="panel-heading">
              <p className="page-eyebrow">Section readiness</p>
              <h2>Readiness and exceptions</h2>
              <p>
                The left index is the complete 17-section navigation. This panel
                surfaces only sections that require execution or attention.
              </p>
            </div>

            <div className="readiness-summary">
              <div className="readiness-stat">
                <span>Required</span>
                <strong>{requiredSections.length}</strong>
                <small>Sections requiring deterministic execution.</small>
              </div>
              <div className="readiness-stat">
                <span>Not applicable</span>
                <strong>{notApplicableCount}</strong>
                <small>Explicitly excluded by persisted applicability.</small>
              </div>
              <div className="readiness-stat">
                <span>Attention</span>
                <strong>{attentionSections.length}</strong>
                <small>Review-required, stale or incomplete sections.</small>
              </div>
            </div>

            {requiredSections.length > 0 ? (
              <div className="readiness-list">
                <div className="readiness-list-heading">
                  <span>Required section</span>
                  <span>Evaluation</span>
                  <span>Outcome</span>
                  <span />
                </div>

                {requiredSections.map((section) => (
                  <Link
                    className="readiness-row"
                    href={`/evaluations/${sessionId}/sections/${section.section_number}`}
                    key={section.id}
                  >
                    <span className="readiness-section">
                      <strong>
                        {String(section.section_number).padStart(2, "0")} ·{" "}
                        {section.name}
                      </strong>
                      <small>{section.code.replaceAll("_", " ")}</small>
                    </span>
                    <span>
                      {section.evaluation_status.replaceAll("_", " ")}
                    </span>
                    <span>
                      <StatusBadge value={section.compliance_outcome} />
                    </span>
                    <span className="readiness-open" aria-hidden="true">
                      Open →
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="readiness-empty">
                <strong>No required section is currently open.</strong>
                <span>
                  Applicability and completion state remain available in the
                  17-section index.
                </span>
              </div>
            )}

            {attentionSections.length > 0 ? (
              <div className="attention-summary">
                <strong>Needs attention</strong>
                {attentionSections.map((section) => (
                  <Link
                    href={`/evaluations/${sessionId}/sections/${section.section_number}`}
                    key={section.id}
                  >
                    {String(section.section_number).padStart(2, "0")} ·{" "}
                    {section.name}
                  </Link>
                ))}
              </div>
            ) : (
              <div className="readiness-clear">
                <strong>No section-level attention flags.</strong>
                <span>
                  No persisted section is stale, incomplete or review-required.
                </span>
              </div>
            )}
          </section>
        </div>
      </div>
      <ReportSessionPanel sessionId={sessionId} />

      <EvaluationHistoryPanel sessionId={sessionId} />
    </div>
  );
}
