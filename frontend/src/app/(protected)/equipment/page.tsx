"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { MasterPermissionState } from "@/components/master-data/permission-state";
import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { listEquipment } from "@/lib/master-data/api";

export default function EquipmentPage() {
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [active, setActive] = useState<"all" | "active" | "archived">("active");
  const [page, setPage] = useState(1);

  const canRead = hasPermission("equipment:read");
  const canCreate = hasPermission("equipment:create");

  const query = useQuery({
    queryKey: ["equipment", selectedLaboratoryId, page, active],
    queryFn: () =>
      listEquipment({
        laboratoryId: selectedLaboratoryId!,
        page,
        active: active === "all" ? null : active === "active",
      }),
    enabled: Boolean(selectedLaboratoryId && canRead),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Test equipment"
        description="Laboratory equipment and calibration master facts used for test-run snapshots."
        actions={
          canCreate ? (
            <Link className="button button-primary" href="/equipment/new">
              Add equipment
            </Link>
          ) : undefined
        }
      />

      {!selectedLaboratoryId || !canRead ? (
        <MasterPermissionState resource="equipment" />
      ) : (
        <>
          <div className="master-toolbar master-toolbar-compact">
            <label>
              <span className="sr-only">Equipment status</span>
              <select
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
            </label>
          </div>

          {query.isPending ? (
            <LoadingState label="Loading test equipment" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No equipment found"
              description="Add laboratory test equipment or adjust the status filter."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Reference</th>
                      <th>Category</th>
                      <th>Manufacturer / model</th>
                      <th>Calibration due</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <Link
                            className="table-link"
                            href={`/equipment/${item.id}`}
                          >
                            {item.reference_number ??
                              item.serial_number ??
                              "Equipment"}
                          </Link>
                        </td>
                        <td>{item.category}</td>
                        <td>
                          {[item.manufacturer, item.model]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </td>
                        <td>{item.calibration_due_date ?? "Not recorded"}</td>
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
