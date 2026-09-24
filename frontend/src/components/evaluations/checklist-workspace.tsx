"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { EvidenceUploader } from "@/components/evidence/evidence-uploader";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDetail } from "@/lib/evaluations/api";
import {
  checklistRows,
  checklistSummary,
  completeChecklist,
  patchChecklistRow,
} from "@/lib/evaluations/special-api";
import type {
  ChecklistResult,
  ChecklistRow,
} from "@/lib/evaluations/special-types";
import { etagFromVersion } from "@/lib/master-data/types";

function RowEditor({
  sessionId,
  laboratoryId,
  row,
  editable,
  onChanged,
}: {
  sessionId: string;
  laboratoryId: string;
  row: ChecklistRow;
  editable: boolean;
  onChanged: () => Promise<void>;
}) {
  const { hasPermission } = useAuth();
  const [result, setResult] = useState<ChecklistResult>(row.response_result);
  const [remarks, setRemarks] = useState(row.remarks ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const canEdit = editable && row.applicability_status === "REQUIRED";

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await patchChecklistRow(
        sessionId,
        row.checklist_rule_id,
        {
          response_result:
            result === "NOT_APPLICABLE" ? "NOT_EXAMINED" : result,
          remarks: remarks.trim() || null,
        },
        etagFromVersion(row.lock_version),
      );
      await onChanged();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="checklist-row-card">
      <div className="checklist-row-heading">
        <div>
          <span>
            {row.group_code.replaceAll("_", " ")}
            {row.clause_reference ? ` · ${row.clause_reference}` : ""}
          </span>
          <h3>{row.requirement_key}</h3>
          <p>{row.display_text}</p>
        </div>
        <div className="construction-badges">
          <StatusBadge value={row.validation_status} />
          <StatusBadge value={row.applicability_status} />
          <StatusBadge value={row.response_result} />
        </div>
      </div>

      {row.validation_status !== "VERIFIED" ||
      row.applicability_status === "REQUIRES_REVIEW" ? (
        <RegulatoryBlocker
          ruleIds={[
            `${row.requirement_key}:${
              row.validation_status !== "VERIFIED"
                ? "TODO_REGULATORY_VALIDATION"
                : "REQUIRES_REVIEW"
            }`,
          ]}
        />
      ) : null}

      {canEdit ? (
        <div className="construction-editor">
          <label className="form-field">
            <span>Response</span>
            <select
              value={result}
              onChange={(event) =>
                setResult(event.target.value as ChecklistResult)
              }
            >
              <option value="NOT_EXAMINED">Not examined</option>
              <option value="PASS">Pass</option>
              <option value="FAIL">Fail</option>
            </select>
          </label>
          <label className="form-field form-span-2">
            <span>Remarks</span>
            <textarea
              rows={3}
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
            />
          </label>
          {error ? <div className="form-alert form-span-2">{error}</div> : null}
          <div className="form-actions form-span-2">
            <button
              className="button button-primary"
              type="button"
              disabled={saving}
              onClick={() => void save()}
            >
              {saving ? "Saving…" : "Save checklist response"}
            </button>
          </div>
        </div>
      ) : (
        <p className="detail-note">{row.applicability_reason}</p>
      )}

      {canEdit &&
      row.evidence_required &&
      hasPermission("attachment:create") ? (
        <EvidenceUploader
          key={`${row.id}-${row.lock_version}`}
          laboratoryId={laboratoryId}
          entityType="checklist_responses"
          entityId={row.id}
          targetEtag={etagFromVersion(row.lock_version)}
          defaultPurpose="checklist_evidence"
          onTargetChanged={onChanged}
        />
      ) : null}
    </article>
  );
}

export function ChecklistWorkspace({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const session = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });
  const rows = useQuery({
    queryKey: ["checklist", sessionId],
    queryFn: () => checklistRows(sessionId),
  });
  const summary = useQuery({
    queryKey: ["checklist-summary", sessionId],
    queryFn: () => checklistSummary(sessionId),
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      }),
      queryClient.invalidateQueries({ queryKey: ["checklist", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["checklist-summary", sessionId],
      }),
    ]);
  }

  if (session.isPending || rows.isPending || summary.isPending) {
    return <LoadingState label="Loading Section 17 checklist" />;
  }
  if (session.isError) return <ErrorState error={session.error} />;
  if (rows.isError) return <ErrorState error={rows.error} />;
  if (summary.isError) return <ErrorState error={summary.error} />;

  const mutable = session.data.item.workflow_status === "EXAMINATION";
  const editable = mutable && hasPermission("checklist:update");
  const summaryEtag = summary.data.etag;

  async function complete() {
    if (!summaryEtag) return;
    setError(null);
    try {
      await completeChecklist(sessionId, summaryEtag);
      await refresh();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  return (
    <div className="special-workspace-stack">
      <section className="run-panel">
        <div className="panel-heading-row">
          <div className="panel-heading">
            <p className="page-eyebrow">Section 17</p>
            <h2>Conformity checklist</h2>
          </div>
          <StatusAxes
            workflow={session.data.item.workflow_status}
            evaluation={summary.data.item.evaluation_status}
            outcome={summary.data.item.compliance_outcome}
          />
        </div>

        <div className="checklist-summary-grid">
          {[
            ["Catalog", summary.data.item.catalog_total],
            ["Applicable", summary.data.item.applicable],
            ["Passed", summary.data.item.passed],
            ["Failed", summary.data.item.failed],
            ["Not examined", summary.data.item.not_examined],
            ["N/A", summary.data.item.not_applicable],
            ["Review required", summary.data.item.review_required],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>

        {summary.data.item.blockers.length > 0 ? (
          <RegulatoryBlocker ruleIds={summary.data.item.blockers} />
        ) : null}
      </section>

      <div className="checklist-list">
        {rows.data
          .slice()
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((row) => (
            <RowEditor
              key={`${row.id}-${row.lock_version}`}
              sessionId={sessionId}
              laboratoryId={session.data.item.laboratory_id}
              row={row}
              editable={editable}
              onChanged={refresh}
            />
          ))}
      </div>

      {error ? <div className="form-alert">{error}</div> : null}
      {mutable && hasPermission("checklist:complete") ? (
        <div className="completion-bar">
          <div>
            <strong>Complete Section 17</strong>
            <span>
              PASS and FAIL are both examined states. Missing evidence or
              unresolved regulatory rows remain backend blockers.
            </span>
          </div>
          <button
            className="button button-primary"
            type="button"
            onClick={() => void complete()}
          >
            Complete checklist
          </button>
        </div>
      ) : null}
    </div>
  );
}
