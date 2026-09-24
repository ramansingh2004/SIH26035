"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { EnvironmentManager } from "@/components/evaluations/environment-manager";
import { EquipmentManager } from "@/components/evaluations/equipment-manager";
import { ObservationManager } from "@/components/evaluations/observation-manager";
import { ProcedureForm } from "@/components/evaluations/procedure-form";
import { ResultPanel } from "@/components/evaluations/result-panel";
import { RunHistoryPanel } from "@/components/evaluations/run-history-panel";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { EvidenceUploader } from "@/components/evidence/evidence-uploader";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError, friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDashboard, evaluationDetail } from "@/lib/evaluations/api";
import {
  completeRun,
  createEnvironment,
  createObservation,
  deleteEnvironment,
  deleteObservation,
  environmentReadings,
  evaluateRun,
  linkEquipment,
  linkedEquipment,
  observations,
  runDetail,
  runResults,
  saveProcedureContext,
  startRun,
  unlinkEquipment,
  updateEnvironment,
  updateObservation,
} from "@/lib/evaluations/run-api";
import type {
  EnvironmentData,
  EnvironmentView,
  EquipmentLinkView,
  ObservationData,
  ObservationView,
  RequirementSlotSnapshot,
} from "@/lib/evaluations/run-types";
import { isStage2Test, TEST_SPECS } from "@/lib/evaluations/test-schemas";
import { equipmentDetail, listEquipment } from "@/lib/master-data/api";
import type { EquipmentView } from "@/lib/master-data/types";
import { etagFromVersion } from "@/lib/master-data/types";
import { uploadEvidence } from "@/lib/evidence/api";

function sourceError(cause: unknown) {
  if (cause instanceof Error && !(cause instanceof ApiError)) {
    return cause.message;
  }
  return friendlyApiMessage(cause);
}

export default function RunWorkspacePage() {
  const { sessionId, runId } = useParams<{
    sessionId: string;
    runId: string;
  }>();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const session = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });
  const dashboard = useQuery({
    queryKey: ["evaluation-dashboard", sessionId],
    queryFn: () => evaluationDashboard(sessionId),
  });
  const run = useQuery({
    queryKey: ["test-run", runId],
    queryFn: () => runDetail(runId),
  });
  const observationQuery = useQuery({
    queryKey: ["run-observations", runId],
    queryFn: () => observations(runId),
  });
  const environmentQuery = useQuery({
    queryKey: ["run-environment", runId],
    queryFn: () => environmentReadings(runId),
  });
  const equipmentQuery = useQuery({
    queryKey: ["run-equipment", runId],
    queryFn: () => linkedEquipment(runId),
  });
  const resultQuery = useQuery({
    queryKey: ["run-results", runId],
    queryFn: () => runResults(runId),
  });

  const availableEquipment = useQuery({
    queryKey: ["run-equipment-catalog", session.data?.item.laboratory_id],
    queryFn: async () => {
      const output = [];
      let page = 1;
      while (true) {
        const result = await listEquipment({
          laboratoryId: session.data!.item.laboratory_id,
          page,
          pageSize: 100,
          active: true,
        });
        output.push(...result.items);
        if (page * result.page_size >= result.total) break;
        page += 1;
      }
      return output;
    },
    enabled: Boolean(
      session.data?.item.laboratory_id && hasPermission("equipment:read"),
    ),
  });

  async function refreshRunSources() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["test-run", runId] }),
      queryClient.invalidateQueries({ queryKey: ["run-observations", runId] }),
      queryClient.invalidateQueries({ queryKey: ["run-environment", runId] }),
      queryClient.invalidateQueries({ queryKey: ["run-equipment", runId] }),
      queryClient.invalidateQueries({ queryKey: ["run-results", runId] }),
      queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      }),
      queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
      queryClient.invalidateQueries({ queryKey: ["evaluations"] }),
    ]);
  }

  function handleError(cause: unknown) {
    if (
      cause instanceof ApiError &&
      (cause.status === 412 || cause.code === "VERSION_CONFLICT")
    ) {
      setConflict(true);
    }
    setActionError(sourceError(cause));
  }

  const lifecycle = useMutation({
    mutationFn: async (action: "start" | "evaluate" | "complete") => {
      if (!run.data?.etag) throw new Error("Reload the run before continuing.");
      if (action === "start") return startRun(runId, run.data.etag);
      if (action === "complete") return completeRun(runId, run.data.etag);
      return evaluateRun(runId, run.data.etag);
    },
    onSuccess: async () => {
      setActionError(null);
      setConflict(false);
      await refreshRunSources();
    },
    onError: handleError,
  });

  if (
    session.isPending ||
    dashboard.isPending ||
    run.isPending ||
    observationQuery.isPending ||
    environmentQuery.isPending ||
    equipmentQuery.isPending ||
    resultQuery.isPending
  ) {
    return <LoadingState label="Loading test run workspace" />;
  }

  if (session.isError) return <ErrorState error={session.error} />;
  if (dashboard.isError) return <ErrorState error={dashboard.error} />;
  if (run.isError) return <ErrorState error={run.error} />;
  if (observationQuery.isError)
    return <ErrorState error={observationQuery.error} />;
  if (environmentQuery.isError)
    return <ErrorState error={environmentQuery.error} />;
  if (equipmentQuery.isError)
    return <ErrorState error={equipmentQuery.error} />;
  if (resultQuery.isError) return <ErrorState error={resultQuery.error} />;

  const requirement = dashboard.data.requirements.find(
    (item) => item.id === run.data.item.requirement_id,
  );
  if (!requirement) {
    return (
      <ErrorState
        error={
          new Error("Run requirement is not present in the session dashboard.")
        }
      />
    );
  }

  const slot = requirement.slot_snapshot as RequirementSlotSnapshot;
  const testCode = slot.test_code;
  const typed = typeof testCode === "string" && isStage2Test(testCode);
  const testSpec = typed ? TEST_SPECS[testCode] : null;
  const runItem = run.data.item;
  const runEtag = run.data.etag;

  const canExecute = hasPermission("test:execute");
  const editable =
    !runItem.completed_at && session.data.item.workflow_status === "TESTING";

  async function saveProcedure(context: Record<string, unknown>) {
    if (!runEtag)
      throw new Error("Reload the run before saving procedure metadata.");
    try {
      await saveProcedureContext(runId, context, runEtag);
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function addObservation(data: ObservationData, etag: string) {
    try {
      await createObservation(runId, data, etag);
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function editObservation(row: ObservationView, data: ObservationData) {
    try {
      await updateObservation(
        runId,
        row.id,
        data,
        etagFromVersion(row.lock_version),
      );
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function removeObservation(row: ObservationView) {
    if (!window.confirm(`Delete observation ${row.sequence_no}?`)) return;
    try {
      await deleteObservation(runId, row.id, etagFromVersion(row.lock_version));
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
    }
  }

  async function addEnvironment(data: EnvironmentData, etag: string) {
    try {
      await createEnvironment(runId, data, etag);
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function editEnvironment(row: EnvironmentView, data: EnvironmentData) {
    try {
      await updateEnvironment(
        runId,
        row.id,
        data,
        etagFromVersion(row.lock_version),
      );
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function removeEnvironment(row: EnvironmentView) {
    if (!window.confirm("Delete this environment reading?")) return;
    try {
      await deleteEnvironment(runId, row.id, etagFromVersion(row.lock_version));
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
    }
  }

  async function addEquipment(
    equipment: EquipmentView,
    calibrationFile: File | null,
    etag: string,
  ) {
    try {
      let attachmentId: string | null = null;
      if (calibrationFile) {
        const detail = await equipmentDetail(equipment.id);
        if (!detail.etag) {
          throw new Error(
            "Reload the selected equipment before uploading its certificate.",
          );
        }
        const attachment = await uploadEvidence({
          file: calibrationFile,
          laboratoryId: equipment.laboratory_id,
          entityType: "test_equipment",
          entityId: equipment.id,
          purpose: "calibration",
          targetEtag: detail.etag,
        });
        attachmentId = attachment.id;
      }

      await linkEquipment(runId, equipment.id, attachmentId, etag);
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
      throw cause;
    }
  }

  async function removeEquipment(row: EquipmentLinkView) {
    if (!window.confirm("Unlink this equipment snapshot from the run?")) return;
    try {
      await unlinkEquipment(
        runId,
        row.equipment_id,
        etagFromVersion(row.lock_version),
      );
      await refreshRunSources();
    } catch (cause) {
      handleError(cause);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={`Test run · #${runItem.run_no}`}
        title={testSpec?.label ?? String(testCode ?? "Specialized test")}
        description={`Input revision ${runItem.input_revision} · procedure schema ${runItem.procedure_schema_version} · observation schema ${runItem.observation_schema_version}`}
        actions={
          <Link
            className="button button-secondary"
            href={`/evaluations/${sessionId}/sections/${
              dashboard.data.sections.find(
                (item) => item.id === runItem.session_section_id,
              )?.section_number ?? ""
            }`}
          >
            Back to section
          </Link>
        }
      />

      <StatusAxes
        workflow={session.data.item.workflow_status}
        evaluation={runItem.evaluation_status}
        outcome={runItem.compliance_outcome}
      />

      {conflict ? (
        <div className="conflict-banner">
          <strong>Run source changed on the server.</strong>
          <span>
            Reload before another write. Child mutations refetch the run rather
            than guessing its new ETag.
          </span>
          <button
            className="button button-secondary button-compact"
            type="button"
            onClick={() => {
              setConflict(false);
              setActionError(null);
              void refreshRunSources();
            }}
          >
            Reload current run
          </button>
        </div>
      ) : null}

      {actionError ? <div className="form-alert">{actionError}</div> : null}

      {!typed ? (
        <section className="run-panel">
          <div className="information-banner">
            <strong>Specialized Stage 3 workspace required.</strong>
            <span>
              This run does not have a typed execution schema in the current
              frontend contract.
            </span>
          </div>
        </section>
      ) : (
        <>
          <section className="run-panel run-lifecycle-panel">
            <div className="panel-heading">
              <p className="page-eyebrow">Run lifecycle</p>
              <h2>Execution controls</h2>
            </div>
            <div className="run-actions">
              {!runItem.started_at ? (
                <button
                  className="button button-primary"
                  type="button"
                  disabled={!canExecute || lifecycle.isPending}
                  onClick={() => lifecycle.mutate("start")}
                >
                  Start run
                </button>
              ) : null}
              {runItem.started_at && !runItem.completed_at ? (
                <button
                  className="button button-primary"
                  type="button"
                  disabled={
                    !hasPermission("test:evaluate") || lifecycle.isPending
                  }
                  onClick={() => lifecycle.mutate("evaluate")}
                >
                  Evaluate current input
                </button>
              ) : null}
              {runItem.evaluation_status === "COMPLETE" &&
              runItem.current_result_id &&
              !runItem.completed_at ? (
                <button
                  className="button button-primary"
                  type="button"
                  disabled={
                    !hasPermission("test:complete") || lifecycle.isPending
                  }
                  onClick={() => lifecycle.mutate("complete")}
                >
                  Complete run
                </button>
              ) : null}
              {runItem.completed_at ? (
                <span className="completed-note">
                  Completed {new Date(runItem.completed_at).toLocaleString()}
                </span>
              ) : null}
            </div>
          </section>

          <ProcedureForm
            key={`${runId}-${runItem.input_revision}`}
            testCode={testCode}
            slot={slot}
            evaluationContext={session.data.item.evaluation_context}
            procedureSchemaVersion={runItem.procedure_schema_version}
            current={runItem.procedure_context}
            disabled={!editable || !canExecute}
            saving={false}
            onSave={saveProcedure}
          />

          <ObservationManager
            testCode={testCode}
            rows={observationQuery.data}
            runEtag={runEtag}
            canCreate={editable && hasPermission("observation:create")}
            canUpdate={editable && hasPermission("observation:update")}
            canDelete={editable && hasPermission("observation:delete")}
            busy={false}
            onCreate={addObservation}
            onUpdate={editObservation}
            onDelete={removeObservation}
          />

          <EnvironmentManager
            rows={environmentQuery.data}
            runEtag={runEtag}
            canCreate={editable && hasPermission("observation:create")}
            canUpdate={editable && hasPermission("observation:update")}
            canDelete={editable && hasPermission("observation:delete")}
            busy={false}
            onCreate={addEnvironment}
            onUpdate={editEnvironment}
            onDelete={removeEnvironment}
          />

          <EquipmentManager
            available={availableEquipment.data ?? []}
            linked={equipmentQuery.data}
            runEtag={runEtag}
            canLink={editable && canExecute}
            canUnlink={editable && canExecute}
            busy={false}
            onLink={addEquipment}
            onUnlink={removeEquipment}
          />

          {editable && hasPermission("attachment:create") ? (
            <EvidenceUploader
              key={`run-evidence-${runItem.lock_version}`}
              laboratoryId={session.data.item.laboratory_id}
              entityType="test_runs"
              entityId={runId}
              targetEtag={runEtag}
              defaultPurpose="test_evidence"
              onTargetChanged={refreshRunSources}
            />
          ) : null}

          <ResultPanel
            workflow={session.data.item.workflow_status}
            run={runItem}
            results={resultQuery.data}
          />
          <RunHistoryPanel
            sessionId={sessionId}
            run={runItem}
            requirement={requirement}
            canRetest={
              session.data.item.workflow_status === "TESTING" &&
              hasPermission("test:retest")
            }
            canSelect={
              session.data.item.workflow_status === "TESTING" &&
              hasPermission("test:select_run")
            }
          />
        </>
      )}
    </div>
  );
}
