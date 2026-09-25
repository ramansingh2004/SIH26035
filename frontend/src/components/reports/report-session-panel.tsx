"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatusAxes } from "@/components/evaluations/status-axes";
import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDetail } from "@/lib/evaluations/api";
import {
  createReportPreview,
  downloadPreview,
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
  const [generated, setGenerated] =
    useState<ReportGenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadBusy, setDownloadBusy] = useState<string | null>(null);

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

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!session.data?.etag) {
        throw new Error("Reload the evaluation before creating a preview.");
      }
      return createReportPreview(sessionId, session.data.etag);
    },
    onSuccess: setPreview,
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

  if (!session.data) return null;
  const item = session.data.item;

  return (
    <section className="report-session-panel">
      <div className="panel-heading-row">
        <div className="panel-heading">
          <p className="page-eyebrow">Reporting</p>
          <h2>Preview and official report</h2>
          <p>
            Preview is non-authoritative. Official generation reads the frozen
            approval snapshot and never recalculates regulatory decisions.
          </p>
        </div>
        <StatusAxes
          workflow={item.workflow_status}
          evaluation={item.evaluation_status}
          outcome={item.compliance_outcome}
        />
      </div>

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="report-action-grid">
        <div className="report-action-card">
          <span className="report-kicker">Unofficial</span>
          <h3>Watermarked preview</h3>
          <p>
            Captures the current working revision, including incomplete,
            stale and regulatory-review state.
          </p>
          {hasPermission("report:preview") ? (
            <button
              className="button button-secondary"
              type="button"
              disabled={previewMutation.isPending}
              onClick={() => previewMutation.mutate()}
            >
              {previewMutation.isPending
                ? "Creating preview…"
                : "Create unofficial preview"}
            </button>
          ) : null}
          {preview ? (
            <div className="report-result-box">
              <div className="report-result-heading">
                <strong>Preview {preview.id.slice(0, 8)}</strong>
                <StatusBadge value={preview.preview_status} />
              </div>
              {preview.preview_status === "READY" ? (
                <div className="run-actions">
                  {(["pdf", "docx"] as ReportFormat[]).map((format) => (
                    <button
                      className="button button-secondary button-compact"
                      type="button"
                      key={format}
                      disabled={downloadBusy === format}
                      onClick={() => void download(format)}
                    >
                      Download {format.toUpperCase()}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="report-action-card">
          <span className="report-kicker">Official</span>
          <h3>Generate immutable report bytes</h3>
          <p>
            Requires APPROVED + COMPLETE and a determined outcome. Generation
            does not issue the report.
          </p>
          <div className="report-gate-row">
            <span>Official generation gate</span>
            <strong>{officialGate ? "OPEN" : "BLOCKED"}</strong>
          </div>
          <label className="form-field">
            <span>Planned issue date (UTC)</span>
            <input
              type="date"
              value={plannedIssueDate}
              onChange={(event) => setPlannedIssueDate(event.target.value)}
            />
          </label>
          <div className="report-issuer-note">
            Intended issuer: <strong>{user?.full_name ?? "Current user"}</strong>
          </div>
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
          {generated ? (
            <div className="report-result-box">
              <div className="report-result-heading">
                <strong>
                  {generated.report.report_number} · revision{" "}
                  {generated.report.revision_no}
                </strong>
                <StatusBadge value={generated.generation.generation_status} />
              </div>
              <Link
                className="button button-secondary button-compact"
                href={`/reports/${generated.report.id}`}
              >
                Open report record
              </Link>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
