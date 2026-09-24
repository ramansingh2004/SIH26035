"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ListToolbar } from "@/components/master-data/list-toolbar";
import { MasterPermissionState } from "@/components/master-data/permission-state";
import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { allManufacturers, listInstruments } from "@/lib/master-data/api";

export default function InstrumentsPage() {
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | "ACTIVE" | "ARCHIVED">("ACTIVE");
  const [page, setPage] = useState(1);

  const canRead = hasPermission("instrument:read");
  const canCreate = hasPermission("instrument:create");

  const query = useQuery({
    queryKey: ["instruments", selectedLaboratoryId, page, search, status],
    queryFn: () =>
      listInstruments({
        laboratoryId: selectedLaboratoryId!,
        page,
        search,
        status,
      }),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  const manufacturers = useQuery({
    queryKey: ["manufacturers", "all", selectedLaboratoryId],
    queryFn: () => allManufacturers(selectedLaboratoryId!),
    enabled: Boolean(
      selectedLaboratoryId && hasPermission("manufacturer:read"),
    ),
  });

  const names = useMemo(
    () =>
      new Map((manufacturers.data ?? []).map((item) => [item.id, item.name])),
    [manufacturers.data],
  );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Instruments"
        description="NAWI instrument master records. Regulatory applicability is established later from verified rules and session snapshots."
        actions={
          canCreate ? (
            <Link className="button button-primary" href="/instruments/new">
              Register instrument
            </Link>
          ) : undefined
        }
      />

      {!selectedLaboratoryId || !canRead ? (
        <MasterPermissionState resource="instrument" />
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
              aria-label="Instrument status"
              value={status}
              onChange={(event) => {
                setPage(1);
                setStatus(event.target.value as typeof status);
              }}
            >
              <option value="ACTIVE">Active</option>
              <option value="ARCHIVED">Archived</option>
              <option value="">All</option>
            </select>
          </ListToolbar>

          {query.isPending ? (
            <LoadingState label="Loading instruments" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No instruments found"
              description="Adjust the filters or register the first instrument for this laboratory."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Manufacturer</th>
                      <th>Serial / type</th>
                      <th>Class</th>
                      <th>Max / e</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link
                            className="table-link"
                            href={`/instruments/${item.id}`}
                          >
                            {item.model_name}
                          </Link>
                        </td>
                        <td>
                          {names.get(item.manufacturer_id) ??
                            "Manufacturer record"}
                        </td>
                        <td>
                          {item.serial_number ?? item.type_designation ?? "—"}
                        </td>
                        <td>{item.accuracy_class}</td>
                        <td>
                          {item.max_capacity_g} g /{" "}
                          {item.verification_interval_e_g} g
                        </td>
                        <td>
                          <StatusBadge value={item.instrument_status} />
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
