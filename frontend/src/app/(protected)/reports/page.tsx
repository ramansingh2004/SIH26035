"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { listReports } from "@/lib/reports/api";

export default function ReportsPage() {
  const { selectedLaboratoryId } = useAuth();
  const [search, setSearch] = useState("");
  const [reportStatus, setReportStatus] = useState("");
  const [page, setPage] = useState(1);

  const reports = useQuery({
    queryKey: ["reports", selectedLaboratoryId, search, reportStatus, page],
    queryFn: () =>
      listReports({
        laboratoryId: selectedLaboratoryId!,
        page,
        search: search.trim() || undefined,
        reportStatus: reportStatus || undefined,
      }),
    enabled: Boolean(selectedLaboratoryId),
  });

  const hasFilters = Boolean(search.trim() || reportStatus);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reporting"
        title="Report repository"
        description="Search official report series while preserving every issued and superseded revision."
      />
      {!selectedLaboratoryId ? (
        <EmptyState
          title="Select a laboratory"
          description="Choose an authorized laboratory scope to access its report repository."
        />
      ) : (
        <>
          <section className="report-filter-bar" aria-label="Report filters">
            <label className="form-field">
              <span>Search</span>
              <input
                value={search}
                placeholder="Report, application, manufacturer, model…"
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
              />
            </label>
            <label className="form-field">
              <span>Report status</span>
              <select
                value={reportStatus}
                onChange={(event) => {
                  setReportStatus(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All statuses</option>
                <option value="UNISSUED">Unissued</option>
                <option value="ISSUED">Issued</option>
                <option value="SUPERSEDED">Superseded</option>
              </select>
            </label>
          </section>

          {reports.isPending ? (
            <LoadingState label="Loading report repository" />
          ) : reports.isError ? (
            <ErrorState
              error={reports.error}
              onRetry={() => void reports.refetch()}
            />
          ) : reports.data.items.length === 0 ? (
            <EmptyState
              title={hasFilters ? "No matching reports" : "No reports yet"}
              description={
                hasFilters
                  ? "No report revisions match the current search and status filters."
                  : "Generated and issued report revisions for this laboratory will appear here."
              }
            />
          ) : (
            <section
              className="report-repository-card"
              aria-label="Report revisions"
            >
              <div className="report-repository-list">
                {reports.data.items.map((item) => (
                  <div className="report-revision-row" key={item.id}>
                    <div>
                      <strong>
                        {item.report_number} · revision {item.revision_no}
                      </strong>
                      <span>
                        {item.manufacturer_name} · {item.instrument_model_name}
                      </span>
                      <div className="report-status-stack">
                        <StatusBadge value={item.evaluation_status} />
                        <StatusBadge value={item.compliance_outcome} />
                        <StatusBadge value={item.report_status} />
                      </div>
                    </div>
                    <Link
                      className="button button-secondary button-compact"
                      href={`/reports/${item.id}`}
                    >
                      Open
                    </Link>
                  </div>
                ))}
              </div>
              <Pagination
                page={reports.data.page}
                pageSize={reports.data.page_size}
                total={reports.data.total}
                onPage={setPage}
              />
            </section>
          )}
        </>
      )}
    </div>
  );
}
