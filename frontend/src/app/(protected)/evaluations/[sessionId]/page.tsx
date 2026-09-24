"use client";

import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApplicabilityPanel } from "@/components/evaluations/applicability-panel";
import { InstrumentSnapshotPanel } from "@/components/evaluations/instrument-snapshot";
import { SectionNavigator } from "@/components/evaluations/section-navigator";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
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

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Evaluation workspace"
        title={
          session.application_number ?? `Evaluation ${session.id.slice(0, 8)}`
        }
        description={`${session.evaluation_context} · session revision ${session.session_revision_no} · regulatory revision ${session.regulatory_revision}`}
      />

      <StatusAxes
        workflow={session.workflow_status}
        evaluation={session.evaluation_status}
        outcome={session.compliance_outcome}
      />

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

          <section className="evaluation-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Section readiness</p>
              <h2>Current section summary</h2>
            </div>
            <div className="section-summary-grid">
              {sections.map((section) => (
                <div className="section-summary-card" key={section.id}>
                  <strong>
                    {section.section_number}. {section.name}
                  </strong>
                  <span>{section.applicability_reason}</span>
                  <StatusAxes
                    workflow={session.workflow_status}
                    evaluation={section.evaluation_status}
                    outcome={section.compliance_outcome}
                  />
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
