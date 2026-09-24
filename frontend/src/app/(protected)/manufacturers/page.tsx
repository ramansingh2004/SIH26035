"use client";

import Link from "next/link";
import { useState } from "react";
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
import { listManufacturers } from "@/lib/master-data/api";

export default function ManufacturersPage() {
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<"all" | "active" | "archived">("active");
  const [page, setPage] = useState(1);

  const canRead = hasPermission("manufacturer:read");
  const canCreate = hasPermission("manufacturer:create");

  const query = useQuery({
    queryKey: ["manufacturers", selectedLaboratoryId, page, search, active],
    queryFn: () =>
      listManufacturers({
        laboratoryId: selectedLaboratoryId!,
        page,
        search,
        active: active === "all" ? null : active === "active",
      }),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Manufacturers"
        description="Laboratory-owned manufacturer records used by NAWI instruments and evaluation snapshots."
        actions={
          canCreate ? (
            <Link className="button button-primary" href="/manufacturers/new">
              Add manufacturer
            </Link>
          ) : undefined
        }
      />

      {!selectedLaboratoryId || !canRead ? (
        <MasterPermissionState resource="manufacturer" />
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
              aria-label="Manufacturer status"
              value={active}
              onChange={(event) => {
                setPage(1);
                setActive(event.target.value as typeof active);
              }}
            >
              <option value="active">Active</option>
              <option value="archived">Archived</option>
              <option value="all">All</option>
            </select>
          </ListToolbar>

          {query.isPending ? (
            <LoadingState label="Loading manufacturers" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No manufacturers found"
              description="Adjust the filters or create the first manufacturer for this laboratory."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Registration</th>
                      <th>Country</th>
                      <th>Contact</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link
                            className="table-link"
                            href={`/manufacturers/${item.id}`}
                          >
                            {item.name}
                          </Link>
                        </td>
                        <td>{item.registration_no ?? "—"}</td>
                        <td>{item.country ?? item.address.country ?? "—"}</td>
                        <td>{item.email ?? item.phone ?? "—"}</td>
                        <td>
                          <StatusBadge
                            value={item.is_active ? "ACTIVE" : "ARCHIVED"}
                          />
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
