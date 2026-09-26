"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ListToolbar } from "@/components/master-data/list-toolbar";
import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { listRoles, listUsers } from "@/lib/admin-users/api";
import { ROLE_LABELS, type RoleCode } from "@/lib/admin-users/types";
import { useAuth } from "@/lib/auth/auth-context";

function formatLastLogin(value: string | null): string {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

export default function AdminUsersPage() {
  const { user, selectedLaboratoryId, hasPermission } = useAuth();
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<"all" | "active" | "inactive">("all");
  const [role, setRole] = useState<RoleCode | "">("");
  const [page, setPage] = useState(1);

  const hasGlobalRead = Boolean(
    user?.global_permissions.includes("user:read"),
  );
  const canRead = hasPermission("user:read");
  const canCreate = hasPermission("user:create");
  const laboratoryScope = hasGlobalRead ? null : selectedLaboratoryId;

  const query = useQuery({
    queryKey: [
      "admin-users",
      laboratoryScope,
      page,
      search,
      active,
      role,
    ],
    queryFn: () =>
      listUsers({
        page,
        laboratoryId: laboratoryScope,
        search,
        role,
        active:
          active === "all" ? null : active === "active",
      }),
    enabled: Boolean(canRead && (hasGlobalRead || laboratoryScope)),
  });

  const roles = useQuery({
    queryKey: ["admin-roles"],
    queryFn: listRoles,
    enabled: canRead,
    staleTime: 5 * 60_000,
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description={
          hasGlobalRead
            ? "Manage authorized accounts across the deployment. Regulatory privileges still require explicit role assignments."
            : "Manage authorized accounts visible in the selected laboratory scope."
        }
        actions={
          canCreate ? (
            <Link className="button button-primary" href="/admin/users/new">
              Add user
            </Link>
          ) : undefined
        }
      />

      {!canRead || (!hasGlobalRead && !selectedLaboratoryId) ? (
        <EmptyState
          title="No user administration access"
          description="Your current role or laboratory scope does not grant user:read."
        />
      ) : (
        <>
          <div className="information-banner">
            <strong>Controlled provisioning only.</strong>
            <span>
              SIH26035 does not expose public self-registration. Authorized
              administrators create accounts and assign explicit global or
              laboratory-scoped roles.
            </span>
          </div>

          <ListToolbar
            search={draftSearch}
            onSearch={setDraftSearch}
            onSubmit={() => {
              setPage(1);
              setSearch(draftSearch.trim());
            }}
          >
            <select
              aria-label="User status"
              value={active}
              onChange={(event) => {
                setPage(1);
                setActive(event.target.value as typeof active);
              }}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>

            <select
              aria-label="Role filter"
              value={role}
              onChange={(event) => {
                setPage(1);
                setRole(event.target.value as RoleCode | "");
              }}
            >
              <option value="">All roles</option>
              {(roles.data ?? []).map((item) => (
                <option key={item.id} value={item.code}>
                  {ROLE_LABELS[item.code] ?? item.name}
                </option>
              ))}
            </select>
          </ListToolbar>

          {query.isPending ? (
            <LoadingState label="Loading users" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data.items.length === 0 ? (
            <EmptyState
              title="No users found"
              description="Adjust the filters or create an authorized user account."
            />
          ) : (
            <section className="data-card">
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Last login</th>
                      <th>Version</th>
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
                            href={`/admin/users/${item.id}`}
                          >
                            {item.full_name}
                          </Link>
                          <span className="admin-user-secondary">
                            {item.email}
                          </span>
                        </td>
                        <td>{formatLastLogin(item.last_login_at)}</td>
                        <td>{item.lock_version}</td>
                        <td>
                          <StatusBadge
                            value={item.is_active ? "ACTIVE" : "INACTIVE"}
                          />
                        </td>
                        <td>
                          <Link
                            className="button button-secondary button-compact"
                            href={`/admin/users/${item.id}`}
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
        </>
      )}
    </div>
  );
}
