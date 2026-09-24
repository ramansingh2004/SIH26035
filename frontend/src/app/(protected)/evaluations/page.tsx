"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ListToolbar } from "@/components/master-data/list-toolbar";
import { MasterPermissionState } from "@/components/master-data/permission-state";
import { Pagination } from "@/components/master-data/pagination";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth/auth-context";
import { listEvaluations } from "@/lib/evaluations/api";
import type {
  ComplianceOutcome,
  EvaluationStatus,
  WorkflowStatus,
} from "@/lib/evaluations/types";
import { listInstruments } from "@/lib/master-data/api";

export default function EvaluationsPage() {
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [workflow, setWorkflow] = useState<WorkflowStatus | "">("");
  const [evaluation, setEvaluation] = useState<EvaluationStatus | "">("");
  const [outcome, setOutcome] = useState<ComplianceOutcome | "">("");

  const canRead = hasPermission("session:read");
  const canCreate = hasPermission("session:create");

  const query = useQuery({
    queryKey: [
      "evaluations",
      selectedLaboratoryId,
      page,
      search,
      workflow,
      evaluation,
      outcome,
    ],
    queryFn: () =>
      listEvaluations({
        laboratoryId: selectedLaboratoryId!,
        page,
        search,
        workflowStatus: workflow,
        evaluationStatus: evaluation,
        complianceOutcome: outcome,
      }),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  const instruments = useQuery({
    queryKey: ["evaluation-instrument-index", selectedLaboratoryId],
    queryFn: async () => {
      const items = [];
      let current = 1;
      while (true) {
        const result = await listInstruments({
          laboratoryId: selectedLaboratoryId!,
          page: current,
          pageSize: 100,
          status: "",
        });
        items.push(...result.items);
        if (current * result.page_size >= result.total) break;
        current += 1;
      }
      return items;
    },
    enabled: Boolean(selectedLaboratoryId && hasPermission("instrument:read")),
  });

  const instrumentNames = useMemo(
    () =>
      new Map(
        (instruments.data ?? []).map((item) => [item.id, item.model_name]),
      ),
    [instruments.data],
  );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Evaluation workspace"
        title="Evaluations"
        description="NAWI type-evaluation sessions with workflow, evaluation readiness and compliance outcome shown as separate states."
        actions={
          canCreate ? (
            <Link className="button button-primary" href="/evaluations/new">
              New evaluation
            </Link>
          ) : undefined
        }
      />

      {!selectedLaboratoryId || !canRead ? (
        <MasterPermissionState resource="evaluation" />
      ) : (
        <>
          <ListToolbar
            search={draftSearch}
            onSearch={setDraftSearch}
            onSubmit={() => {
              setPage(1);
              setSearch(draftSearch.trim());
            }}
          >
            <select
              aria-label="Workflow status"
              value={workflow}
              onChange={(event) => {
                setPage(1);
                setWorkflow(event.target.value as WorkflowStatus | "");
              }}
            >
              <option value="">All workflow states</option>
              <option value="DRAFT">Draft</option>
              <option value="INSTRUMENT_CONFIGURATION">
                Instrument configuration
              </option>
              <option value="APPLICABILITY_CONFIRMED">
                Applicability confirmed
              </option>
              <option value="TESTING">Testing</option>
              <option value="EXAMINATION">Examination</option>
              <option value="UNDER_REVIEW">Under review</option>
              <option value="APPROVED">Approved</option>
              <option value="REPORT_ISSUED">Report issued</option>
              <option value="REJECTED">Rejected</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
            <select
              aria-label="Evaluation status"
              value={evaluation}
              onChange={(event) => {
                setPage(1);
                setEvaluation(event.target.value as EvaluationStatus | "");
              }}
            >
              <option value="">All evaluation states</option>
              <option value="NOT_STARTED">Not started</option>
              <option value="IN_PROGRESS">In progress</option>
              <option value="INCOMPLETE">Incomplete</option>
              <option value="STALE">Stale</option>
              <option value="REVIEW_REQUIRED">Review required</option>
              <option value="COMPLETE">Complete</option>
            </select>
            <select
              aria-label="Compliance outcome"
              value={outcome}
              onChange={(event) => {
                setPage(1);
                setOutcome(event.target.value as ComplianceOutcome | "");
              }}
            >
              <option value="">All outcomes</option>
              <option value="UNDETERMINED">Undetermined</option>
              <option value="COMPLIANT">Compliant</option>
              <option value="NONCOMPLIANT">Noncompliant</option>
              <option value="NOT_APPLICABLE">Not applicable</option>
            </select>
          </ListToolbar>

          {query.isPending ? (
            <LoadingState label="Loading evaluations" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No evaluations found"
              description="Create the first evaluation or adjust the search/status filters."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table evaluation-table">
                  <thead>
                    <tr>
                      <th>Evaluation</th>
                      <th>Instrument</th>
                      <th>Status axes</th>
                      <th>Revision</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link
                            className="table-link"
                            href={`/evaluations/${item.id}`}
                          >
                            {item.application_number ??
                              `Session ${item.id.slice(0, 8)}`}
                          </Link>
                          <span className="table-secondary">
                            {item.evaluation_context}
                          </span>
                        </td>
                        <td>
                          {instrumentNames.get(item.instrument_id) ??
                            "Instrument record"}
                        </td>
                        <td>
                          <StatusAxes
                            workflow={item.workflow_status}
                            evaluation={item.evaluation_status}
                            outcome={item.compliance_outcome}
                          />
                        </td>
                        <td>#{item.session_revision_no}</td>
                        <td>{new Date(item.updated_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={query.data.page}
                pageSize={query.data.page_size}
                total={query.data.total}
                onPage={setPage}
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}
