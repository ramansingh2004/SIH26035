"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

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

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reporting"
        title="Report repository"
        description="Search official report series while preserving every issued and superseded revision."
      />
      {!selectedLaboratoryId ? (
        <p className="detail-note">Select a laboratory to access reports.</p>
      ) : (
        <>
          <section className="report-filter-bar">
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
            <ErrorState error={reports.error} />
          ) : (
            <section className="report-repository-card">
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
              <div className="report-pagination">
                <button
                  className="button button-secondary button-compact"
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  Previous
                </button>
                <span>
                  Page {reports.data.page} · {reports.data.total} records
                </span>
                <button
                  className="button button-secondary button-compact"
                  type="button"
                  disabled={page * reports.data.page_size >= reports.data.total}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
