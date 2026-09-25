"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { StatusAxes } from "@/components/evaluations/status-axes";
import { ListToolbar } from "@/components/master-data/list-toolbar";
import { MasterPermissionState } from "@/components/master-data/permission-state";
import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth/auth-context";
import { listEvaluations } from "@/lib/evaluations/api";

export function ReviewQueue({
  mode,
}: {
  mode: "technical" | "approval";
}) {
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const canRead =
    hasPermission("session:read") && hasPermission("approval:read");

  const query = useQuery({
    queryKey: [
      mode === "technical" ? "technical-review-queue" : "approval-queue",
      selectedLaboratoryId,
      page,
      search,
    ],
    queryFn: () =>
      listEvaluations({
        laboratoryId: selectedLaboratoryId!,
        page,
        pageSize: 20,
        search,
        workflowStatus: "UNDER_REVIEW",
      }),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Review & approval"
        title={
          mode === "technical" ? "Technical Reviews" : "Final Approvals"
        }
        description={
          mode === "technical"
            ? "Sessions submitted for independent technical review, correction or technical approval."
            : "Under-review sessions awaiting governance decisions. Final approval is independent from the compliance outcome."
        }
      />

      {!selectedLaboratoryId || !canRead ? (
        <MasterPermissionState resource="review queue" />
      ) : (
        <>
          <ListToolbar
            search={draftSearch}
            onSearch={setDraftSearch}
            onSubmit={() => {
              setPage(1);
              setSearch(draftSearch.trim());
            }}
          />

          {query.isPending ? (
            <LoadingState label="Loading review queue" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No sessions currently under review"
              description="Sessions appear here after a review-ready evaluation is submitted."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Evaluation</th>
                      <th>Status axes</th>
                      <th>Regulatory revision</th>
                      <th>Submitted</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <strong>
                            {item.application_number ??
                              `Session ${item.id.slice(0, 8)}`}
                          </strong>
                          <span className="table-secondary">
                            {item.evaluation_context}
                          </span>
                        </td>
                        <td>
                          <StatusAxes
                            workflow={item.workflow_status}
                            evaluation={item.evaluation_status}
                            outcome={item.compliance_outcome}
                          />
                        </td>
                        <td>{item.regulatory_revision}</td>
                        <td>
                          {item.submitted_at
                            ? new Date(item.submitted_at).toLocaleString()
                            : "—"}
                        </td>
                        <td>
                          <Link
                            className="button button-primary button-compact"
                            href={`/${
                              mode === "technical" ? "reviews" : "approvals"
                            }/${item.id}`}
                          >
                            Open case
                          </Link>
                        </td>
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
