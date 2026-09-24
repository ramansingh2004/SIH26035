"use client";

import { useMemo, useState } from "react";
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
  completeConstruction,
  constructionDetail,
  constructionItems,
  patchConstruction,
  patchConstructionItem,
} from "@/lib/evaluations/special-api";
import {
  constructionPolicies,
  type ConformanceResult,
  type ConstructionItem,
  type ConstructionPolicy,
  type ExaminationState,
} from "@/lib/evaluations/special-types";
import { etagFromVersion } from "@/lib/master-data/types";

function ItemEditor({
  sessionId,
  laboratoryId,
  item,
  policy,
  editable,
  onChanged,
}: {
  sessionId: string;
  laboratoryId: string;
  item: ConstructionItem;
  policy: ConstructionPolicy | null;
  editable: boolean;
  onChanged: () => Promise<void>;
}) {
  const { hasPermission } = useAuth();
  const [state, setState] = useState<ExaminationState>(item.examination_state);
  const [result, setResult] = useState<ConformanceResult>(
    item.conformance_result,
  );
  const [remarks, setRemarks] = useState(item.remarks ?? "");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (policy?.required_value_keys ?? []).map((key) => [
        key,
        item.value_json[key] === undefined ? "" : String(item.value_json[key]),
      ]),
    ),
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const valueJson: Record<string, unknown> = { ...item.value_json };
      for (const key of policy?.required_value_keys ?? []) {
        const value = values[key]?.trim() ?? "";
        if (!value) throw new Error(`${key} is required by the pinned policy.`);
        valueJson[key] = value;
      }
      await patchConstructionItem(
        sessionId,
        item.id,
        {
          value_schema_version: 1,
          value_json: valueJson,
          examination_state: state,
          conformance_result: state === "EXAMINED" ? result : "UNDETERMINED",
          remarks: remarks.trim() || null,
        },
        etagFromVersion(item.lock_version),
      );
      await onChanged();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : friendlyApiMessage(cause),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="construction-item-card">
      <div className="construction-item-heading">
        <div>
          <span>{item.category.replaceAll("_", " ")}</span>
          <h3>{item.item_key}</h3>
          <p>{item.description_snapshot}</p>
        </div>
        <div className="construction-badges">
          {policy?.required ? <span className="mini-tag">Required</span> : null}
          {policy?.evidence_required ? (
            <span className="mini-tag">Evidence required</span>
          ) : null}
          <StatusBadge value={item.examination_state} />
          <StatusBadge value={item.conformance_result} />
        </div>
      </div>

      {!policy ? (
        <RegulatoryBlocker
          ruleIds={[`${item.item_key}:INVALID_CONSTRUCTION_POLICY`]}
        />
      ) : null}

      {policy?.required_value_keys.length ? (
        <div className="construction-values">
          {policy.required_value_keys.map((key) => (
            <label className="form-field" key={key}>
              <span>{key.replaceAll("_", " ")} *</span>
              <input
                disabled={!editable}
                value={values[key] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({
                    ...current,
                    [key]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
        </div>
      ) : null}

      {editable ? (
        <div className="construction-editor">
          <label className="form-field">
            <span>Examination state</span>
            <select
              value={state}
              onChange={(event) => {
                const next = event.target.value as ExaminationState;
                setState(next);
                if (next !== "EXAMINED") setResult("UNDETERMINED");
                else if (result === "UNDETERMINED") setResult("PASS");
              }}
            >
              <option value="NOT_EXAMINED">Not examined</option>
              <option value="EXAMINED">Examined</option>
              <option value="REVIEW_REQUIRED">Review required</option>
            </select>
          </label>
          <label className="form-field">
            <span>Conformance</span>
            <select
              disabled={state !== "EXAMINED"}
              value={state === "EXAMINED" ? result : "UNDETERMINED"}
              onChange={(event) =>
                setResult(event.target.value as ConformanceResult)
              }
            >
              <option value="PASS">Pass</option>
              <option value="FAIL">Fail</option>
              {policy?.allow_not_applicable ? (
                <option value="NOT_APPLICABLE">Not applicable</option>
              ) : null}
              <option value="UNDETERMINED" disabled>
                Undetermined
              </option>
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
              {saving ? "Saving…" : "Save examination item"}
            </button>
          </div>
        </div>
      ) : null}

      {editable &&
      policy?.evidence_required &&
      hasPermission("attachment:create") ? (
        <EvidenceUploader
          key={`${item.id}-${item.lock_version}`}
          laboratoryId={laboratoryId}
          entityType="construction_items"
          entityId={item.id}
          targetEtag={etagFromVersion(item.lock_version)}
          defaultPurpose="construction_evidence"
          onTargetChanged={onChanged}
        />
      ) : null}
    </article>
  );
}

export function ConstructionWorkspace({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [notesDraft, setNotesDraft] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const session = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });
  const examination = useQuery({
    queryKey: ["construction", sessionId],
    queryFn: () => constructionDetail(sessionId),
  });
  const items = useQuery({
    queryKey: ["construction-items", sessionId],
    queryFn: () => constructionItems(sessionId),
  });

  const policies = useMemo(
    () =>
      session.data
        ? constructionPolicies(session.data.item.ruleset_snapshot)
        : new Map<string, ConstructionPolicy>(),
    [session.data],
  );

  async function refresh() {
    setNotesDraft(null);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      }),
      queryClient.invalidateQueries({ queryKey: ["construction", sessionId] }),
      queryClient.invalidateQueries({
        queryKey: ["construction-items", sessionId],
      }),
    ]);
  }

  if (session.isPending || examination.isPending || items.isPending) {
    return <LoadingState label="Loading construction examination" />;
  }
  if (session.isError) return <ErrorState error={session.error} />;
  if (examination.isError) return <ErrorState error={examination.error} />;
  if (items.isError) return <ErrorState error={items.error} />;

  const mutable = session.data.item.workflow_status === "EXAMINATION";
  const canUpdate = mutable && hasPermission("construction:update");
  const examinationData = examination.data;
  const examinationEtag = examinationData.etag;
  const notes = notesDraft ?? examinationData.item.overall_notes ?? "";
  const rawBlockers = examinationData.item.summary_json.blockers;
  const blockers = Array.isArray(rawBlockers)
    ? rawBlockers.filter((value): value is string => typeof value === "string")
    : [];

  async function saveNotes() {
    if (!examinationEtag) return;
    setError(null);
    try {
      await patchConstruction(sessionId, notes.trim() || null, examinationEtag);
      await refresh();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  async function complete() {
    if (!examinationEtag) return;
    setError(null);
    try {
      await completeConstruction(sessionId, examinationEtag);
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
            <p className="page-eyebrow">Section 16</p>
            <h2>Construction examination dossier</h2>
          </div>
          <StatusAxes
            workflow={session.data.item.workflow_status}
            evaluation={examination.data.item.evaluation_status}
            outcome={examination.data.item.compliance_outcome}
          />
        </div>

        <label className="form-field">
          <span>Overall notes</span>
          <textarea
            rows={4}
            disabled={!canUpdate}
            value={notes}
            onChange={(event) => setNotesDraft(event.target.value)}
          />
        </label>
        {canUpdate ? (
          <div className="form-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void saveNotes()}
            >
              Save dossier notes
            </button>
          </div>
        ) : null}
        {blockers.length > 0 ? <RegulatoryBlocker ruleIds={blockers} /> : null}
      </section>

      <div className="construction-item-list">
        {items.data
          .slice()
          .sort((left, right) => left.sort_order - right.sort_order)
          .map((item) => (
            <ItemEditor
              key={`${item.id}-${item.lock_version}`}
              sessionId={sessionId}
              laboratoryId={session.data.item.laboratory_id}
              item={item}
              policy={policies.get(item.item_key) ?? null}
              editable={canUpdate}
              onChanged={refresh}
            />
          ))}
      </div>

      {error ? <div className="form-alert">{error}</div> : null}
      {mutable && hasPermission("construction:complete") ? (
        <div className="completion-bar">
          <div>
            <strong>Complete Section 16</strong>
            <span>
              The backend verifies pinned policy, required values, evidence and
              conformance before accepting completion.
            </span>
          </div>
          <button
            className="button button-primary"
            type="button"
            onClick={() => void complete()}
          >
            Complete construction examination
          </button>
        </div>
      ) : null}
    </div>
  );
}
