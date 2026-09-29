"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDetail } from "@/lib/evaluations/api";
import {
  createFullDemoReport,
  createReportPreview,
  createSimulatedApprovedReport,
  downloadPreview,
  downloadSimulation,
  generateReport,
} from "@/lib/reports/api";
import type {
  ReportFormat,
  ReportGenerationResponse,
  ReportPreviewView,
} from "@/lib/reports/types";

function utcDate() {
  return new Date().toISOString().slice(0, 10);
}

export function ReportSessionPanel({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();
  const { user, hasPermission } = useAuth();
  const [plannedIssueDate, setPlannedIssueDate] = useState(utcDate());
  const [preview, setPreview] = useState<ReportPreviewView | null>(null);
  const [simulation, setSimulation] = useState<ReportPreviewView | null>(null);
  const [generated, setGenerated] = useState<ReportGenerationResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [downloadBusy, setDownloadBusy] = useState<string | null>(null);
  const [simulationDownloadBusy, setSimulationDownloadBusy] = useState<
    string | null
  >(null);

  const session = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });

  const officialGate = useMemo(() => {
    if (!session.data) return false;
    const item = session.data.item;
    return (
      item.workflow_status === "APPROVED" &&
      item.evaluation_status === "COMPLETE" &&
      (item.compliance_outcome === "COMPLIANT" ||
        item.compliance_outcome === "NONCOMPLIANT")
    );
  }, [session.data]);

  const officialGateReason = useMemo(() => {
    if (!session.data) return "Reload the evaluation.";
    const item = session.data.item;

    if (item.workflow_status !== "APPROVED") {
      return `workflow is ${item.workflow_status.replaceAll("_", " ")}, not APPROVED`;
    }

    if (item.evaluation_status !== "COMPLETE") {
      return `evaluation status is ${item.evaluation_status.replaceAll("_", " ")}, not COMPLETE`;
    }

    if (
      item.compliance_outcome !== "COMPLIANT" &&
      item.compliance_outcome !== "NONCOMPLIANT"
    ) {
      return `outcome is ${item.compliance_outcome.replaceAll("_", " ")}, not determined`;
    }

    return null;
  }, [session.data]);

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!session.data?.etag) {
        throw new Error("Reload the evaluation before creating a preview.");
      }
      return createReportPreview(sessionId, session.data.etag);
    },
    onSuccess: (value) => {
      setError(null);
      setPreview(value);
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  const simulationMutation = useMutation({
    mutationFn: async () => {
      if (!session.data?.etag) {
        throw new Error(
          "Reload the evaluation before creating a simulated report.",
        );
      }
      const item = session.data.item;
      const metadata = item.ruleset_snapshot.metadata;
      const fullDemoReady =
        Boolean(metadata) &&
        typeof metadata === "object" &&
        (metadata as Record<string, unknown>).version ===
          "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3" &&
        item.workflow_status === "EXAMINATION" &&
        item.evaluation_status === "COMPLETE" &&
        item.compliance_outcome === "COMPLIANT";

      return fullDemoReady
        ? createFullDemoReport(sessionId, session.data.etag)
        : createSimulatedApprovedReport(sessionId, session.data.etag);
    },
    onSuccess: (value) => {
      setError(null);
      setSimulation(value);
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!session.data?.etag || !user) {
        throw new Error("Reload the evaluation before report generation.");
      }

      return generateReport(
        sessionId,
        {
          intended_issuer_id: user.id,
          planned_issue_date: plannedIssueDate,
        },
        session.data.etag,
      );
    },
    onSuccess: async (value) => {
      setError(null);
      setGenerated(value);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  async function download(format: ReportFormat) {
    if (!preview) return;

    setDownloadBusy(format);
    try {
      await downloadPreview(preview.id, format);
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setDownloadBusy(null);
    }
  }

  async function downloadSimulationFile(format: ReportFormat) {
    if (!simulation) return;

    setSimulationDownloadBusy(format);
    try {
      await downloadSimulation(simulation.id, format);
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setSimulationDownloadBusy(null);
    }
  }

  if (!session.data) return null;
  const item = session.data.item;
  const metadata = item.ruleset_snapshot.metadata;
  const fullDemoReady =
    Boolean(metadata) &&
    typeof metadata === "object" &&
    (metadata as Record<string, unknown>).version ===
      "SYNTHETIC_TEST_SIH26035_FULL_FLOW_V3" &&
    item.workflow_status === "EXAMINATION" &&
    item.evaluation_status === "COMPLETE" &&
    item.compliance_outcome === "COMPLIANT";

  return (
    <section
      className="report-session-panel report-workflow-panel"
      id="reporting"
      tabIndex={-1}
    >
      <div className="report-workflow-header">
        <div className="panel-heading">
          <p className="page-eyebrow">Reporting</p>
          <h2>Report workflow</h2>
          <p>
            Working previews, SIH demonstration files and official report
            generation remain separate controlled paths.
          </p>
        </div>

        <div
          className="report-stored-state"
          aria-label="Stored evaluation state"
        >
          <div>
            <span>Workflow</span>
            <strong>{item.workflow_status.replaceAll("_", " ")}</strong>
          </div>
          <div>
            <span>Evaluation</span>
            <strong>{item.evaluation_status.replaceAll("_", " ")}</strong>
          </div>
          <div>
            <span>Outcome</span>
            <StatusBadge value={item.compliance_outcome} />
          </div>
        </div>
      </div>

      {error ? (
        <div className="form-alert" role="alert">
          {error}
        </div>
      ) : null}

      <div className="report-workflow-list">
        <article className="report-workflow-step">
          <div className="report-step-number">01</div>

          <div className="report-step-copy">
            <span className="report-kicker">Working copy</span>
            <h3>Unofficial preview</h3>
            <p>
              Preview files are unofficial. Captures the current persisted
              revision for internal review. It is watermarked and is never an
              issued regulatory report.
            </p>

            {preview ? (
              <div className="report-output-row">
                <div>
                  <strong>Preview {preview.id.slice(0, 8)}</strong>
                  <span>
                    Regulatory revision {preview.source_regulatory_revision}
                    {" · "}
                    expires {new Date(preview.expires_at).toLocaleString()}
                  </span>
                </div>

                <StatusBadge value={preview.preview_status} />

                {preview.preview_status === "READY" ? (
                  <div className="report-output-actions">
                    {(["pdf", "docx"] as ReportFormat[]).map((format) => (
                      <button
                        className="button button-secondary button-compact"
                        type="button"
                        key={format}
                        disabled={downloadBusy === format}
                        onClick={() => void download(format)}
                      >
                        {downloadBusy === format
                          ? "Preparing…"
                          : format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="report-step-action">
            <span className="report-step-state">Non-authoritative</span>
            {hasPermission("report:preview") ? (
              <button
                className="button button-secondary"
                type="button"
                disabled={previewMutation.isPending}
                onClick={() => previewMutation.mutate()}
              >
                {previewMutation.isPending ? "Creating…" : "Create preview"}
              </button>
            ) : null}
          </div>
        </article>

        <article className="report-workflow-step is-demo">
          <div className="report-step-number">02</div>

          <div className="report-step-copy">
            <div className="report-step-title-row">
              <div>
                <span className="report-kicker">SIH demonstration</span>
                <h3>
                  {fullDemoReady
                    ? "Complete 17-section demonstration report"
                    : "Simulated approved report"}
                </h3>
              </div>
              <span className="demo-only-label">DEMONSTRATION ONLY</span>
            </div>

            <p>
              {fullDemoReady
                ? "Renders the completed V3 evaluation into one evidence-rich PDF/DOCX pair: 17 sections, 23 typed runs, Sections 16 and 17, 60 unique synthetic evidence files, and 85 immutable evidence links."
                : "Demonstrates the final approved-report experience without changing the stored workflow, approval state or regulatory decision."}
            </p>

            <div className="report-demo-notice">
              {fullDemoReady
                ? "SIMULATED / DEMONSTRATION REPORT - NOT AN OFFICIAL OIML CERTIFICATE"
                : "Watermarked PDF/DOCX · not a regulatory approval, certificate or issued report."}
            </div>

            {simulation ? (
              <div className="report-output-row">
                <div>
                  <strong>Simulation {simulation.id.slice(0, 8)}</strong>
                  <span>
                    Regulatory revision {simulation.source_regulatory_revision}
                    {" · "}
                    expires {new Date(simulation.expires_at).toLocaleString()}
                  </span>
                </div>

                <StatusBadge value={simulation.preview_status} />

                {simulation.preview_status === "READY" ? (
                  <div className="report-output-actions">
                    {(["pdf", "docx"] as ReportFormat[]).map((format) => (
                      <button
                        className="button button-secondary button-compact"
                        type="button"
                        key={format}
                        disabled={simulationDownloadBusy === format}
                        onClick={() => void downloadSimulationFile(format)}
                      >
                        {simulationDownloadBusy === format
                          ? "Preparing…"
                          : format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="report-step-action">
            <span className="report-step-state">Demonstration path</span>
            {hasPermission("report:preview") ? (
              <button
                className="button button-primary"
                type="button"
                disabled={simulationMutation.isPending}
                onClick={() => simulationMutation.mutate()}
              >
                {simulationMutation.isPending
                  ? "Generating…"
                  : fullDemoReady
                    ? "Generate complete 17-section demo report"
                    : "Generate simulated approved report"}
              </button>
            ) : null}
          </div>
        </article>

        <article className="report-workflow-step is-official">
          <div className="report-step-number">03</div>

          <div className="report-step-copy">
            <div className="report-step-title-row">
              <div>
                <span className="report-kicker">Controlled output</span>
                <h3>Official report generation</h3>
              </div>
              <span
                aria-label="Official generation gate"
                className={`official-gate-label ${
                  officialGate ? "is-open" : "is-blocked"
                }`}
              >
                {officialGate ? "GATE OPEN" : "GATE BLOCKED"}
              </span>
            </div>

            <p>
              Reads the frozen approval snapshot. Generation does not issue the
              report and never recalculates the compliance outcome.
            </p>

            {!officialGate && officialGateReason ? (
              <div className="official-gate-reason">
                <strong>Official generation is blocked because:</strong>
                <span>{officialGateReason}.</span>
              </div>
            ) : null}

            <div className="official-report-fields">
              <label className="form-field">
                <span>Planned issue date (UTC)</span>
                <input
                  type="date"
                  value={plannedIssueDate}
                  disabled={!officialGate}
                  onChange={(event) => setPlannedIssueDate(event.target.value)}
                />
              </label>

              <div className="official-issuer-field">
                <span>Intended issuer</span>
                <strong>{user?.full_name ?? "Current user"}</strong>
              </div>
            </div>

            {generated ? (
              <div className="report-output-row">
                <div>
                  <strong>
                    {generated.report.report_number} · revision{" "}
                    {generated.report.revision_no}
                  </strong>
                  <span>
                    Immutable report generation record created successfully.
                  </span>
                </div>

                <StatusBadge value={generated.generation.generation_status} />

                <Link
                  className="button button-secondary button-compact"
                  href={`/reports/${generated.report.id}`}
                >
                  Open record
                </Link>
              </div>
            ) : null}
          </div>

          <div className="report-step-action">
            <span className="report-step-state">
              {officialGate ? "Authorized state" : "Requires approval"}
            </span>
            {hasPermission("report:generate") ? (
              <button
                className="button button-primary"
                type="button"
                disabled={!officialGate || generateMutation.isPending || !user}
                onClick={() => generateMutation.mutate()}
              >
                {generateMutation.isPending
                  ? "Generating…"
                  : "Generate official report"}
              </button>
            ) : null}
          </div>
        </article>
      </div>
    </section>
  );
}
