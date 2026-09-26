"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { listLaboratories } from "@/lib/admin-laboratories/api";
import { useAuth } from "@/lib/auth/auth-context";

export default function AdminLaboratoriesPage() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);

  const canRead = Boolean(
    user?.global_permissions.includes("laboratory:read") ||
      user?.laboratories.some((grant) =>
        grant.permissions.includes("laboratory:read"),
      ),
  );
  const canCreate = Boolean(
    user?.global_permissions.includes("laboratory:create"),
  );

  const query = useQuery({
    queryKey: ["admin-laboratories", page],
    queryFn: () => listLaboratories({ page }),
    enabled: canRead,
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Laboratories"
        description="Manage laboratory identity, contact details, accreditation metadata, timezone and active state within the backend authorization boundary."
        actions={
          canCreate ? (
            <Link
              className="button button-primary"
              href="/admin/laboratories/new"
            >
              Add laboratory
            </Link>
          ) : undefined
        }
      />

      {!canRead ? (
        <EmptyState
          title="No laboratory administration access"
          description="Your account does not grant laboratory:read in any visible scope."
        />
      ) : query.isPending ? (
        <LoadingState label="Loading laboratories" />
      ) : query.isError ? (
        <ErrorState
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title="No laboratories found"
          description="A global administrator can create the first laboratory."
        />
      ) : (
        <section className="data-card">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Laboratory</th>
                  <th>Location</th>
                  <th>Accreditation</th>
                  <th>Timezone</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        className="table-link"
                        href={`/admin/laboratories/${item.id}`}
                      >
                        {item.name}
                      </Link>
                      <span className="admin-user-secondary">
                        {item.code}
                      </span>
                    </td>
                    <td>
                      {[item.city, item.state, item.country]
                        .filter(Boolean)
                        .join(", ") || "—"}
                    </td>
                    <td>{item.accreditation_no}</td>
                    <td>{item.timezone}</td>
                    <td>
                      <StatusBadge
                        value={item.is_active ? "ACTIVE" : "INACTIVE"}
                      />
                    </td>
                    <td>
                      <Link
                        className="button button-secondary button-compact"
                        href={`/admin/laboratories/${item.id}`}
                      >
                        Manage
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
    </div>
  );
}
