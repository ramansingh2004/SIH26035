"use client";

import { useParams } from "next/navigation";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  adminUser,
  grantAssignment,
  listAdministrativeLaboratories,
  listAssignments,
  listRoles,
  resetUserPassword,
  revokeAssignment,
  updateUser,
} from "@/lib/admin-users/api";
import {
  ROLE_LABELS,
  type AssignmentScope,
  type RoleCode,
} from "@/lib/admin-users/types";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const queryClient = useQueryClient();
  const { user: actor, selectedLaboratoryId, hasPermission } = useAuth();

  const [identityError, setIdentityError] = useState<string | null>(null);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const canRead = hasPermission("user:read");
  const canUpdate = hasPermission("user:update");
  const canDeactivate = hasPermission("user:deactivate");
  const canManageRoles = hasPermission("user:manage_roles");
  const canManageGlobal = Boolean(
    actor?.global_permissions.includes("user:manage_roles"),
  );

  const userQuery = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => adminUser(userId),
    enabled: canRead,
  });

  const assignmentsQuery = useQuery({
    queryKey: ["admin-user-assignments", userId],
    queryFn: () => listAssignments(userId),
    enabled: canRead,
  });

  const rolesQuery = useQuery({
    queryKey: ["admin-roles"],
    queryFn: listRoles,
    enabled: canRead,
    staleTime: 5 * 60_000,
  });

  const laboratoriesQuery = useQuery({
    queryKey: ["admin-laboratories", "user-detail"],
    queryFn: listAdministrativeLaboratories,
    enabled: canRead,
    staleTime: 5 * 60_000,
  });

  const manageableLaboratoryIds = useMemo(
    () =>
      new Set(
        actor?.laboratories
          .filter((grant) =>
            grant.permissions.includes("user:manage_roles"),
          )
          .map((grant) => grant.laboratory_id) ?? [],
      ),
    [actor],
  );

  const availableLaboratories = useMemo(() => {
    const activeLabs = (laboratoriesQuery.data ?? []).filter(
      (laboratory) => laboratory.is_active,
    );
    if (canManageGlobal) return activeLabs;
    return activeLabs.filter((laboratory) =>
      manageableLaboratoryIds.has(laboratory.id),
    );
  }, [
    canManageGlobal,
    laboratoriesQuery.data,
    manageableLaboratoryIds,
  ]);

  const [assignmentScope, setAssignmentScope] =
    useState<AssignmentScope>("LABORATORY");
  const [assignmentRole, setAssignmentRole] =
    useState<RoleCode>("LAB_TECHNICIAN");
  const [assignmentLaboratoryId, setAssignmentLaboratoryId] = useState(
    selectedLaboratoryId ?? "",
  );
  const [assignmentError, setAssignmentError] = useState<string | null>(null);

  const roleById = useMemo(
    () =>
      new Map(
        (rolesQuery.data ?? []).map((role) => [role.id, role]),
      ),
    [rolesQuery.data],
  );

  const labById = useMemo(
    () =>
      new Map(
        (laboratoriesQuery.data ?? []).map((laboratory) => [
          laboratory.id,
          laboratory,
        ]),
      ),
    [laboratoriesQuery.data],
  );

  const saveIdentity = useMutation({
    mutationFn: async ({
      fullName,
      active,
    }: {
      fullName: string;
      active: boolean;
    }) => {
      if (!userQuery.data) throw new Error("Reload this user before saving.");
      return updateUser(
        userId,
        {
          full_name: fullName,
          is_active: active,
        },
        userQuery.data.etag,
      );
    },
  });

  const passwordMutation = useMutation({
    mutationFn: async () => {
      if (!userQuery.data) throw new Error("Reload this user before saving.");
      return resetUserPassword(
        userId,
        newPassword,
        userQuery.data.etag,
      );
    },
  });

  const grantMutation = useMutation({
    mutationFn: async () => {
      if (!userQuery.data) throw new Error("Reload this user before saving.");
      if (
        assignmentScope === "LABORATORY" &&
        !assignmentLaboratoryId
      ) {
        throw new Error("Select a laboratory.");
      }

      return grantAssignment(
        userId,
        {
          scope_type: assignmentScope,
          role_code:
            assignmentScope === "GLOBAL" ? "ADMIN" : assignmentRole,
          laboratory_id:
            assignmentScope === "GLOBAL"
              ? null
              : assignmentLaboratoryId,
        },
        userQuery.data.etag,
      );
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async ({
      assignmentId,
      lockVersion,
      reason,
    }: {
      assignmentId: string;
      lockVersion: number;
      reason: string;
    }) =>
      revokeAssignment(
        userId,
        assignmentId,
        lockVersion,
        reason,
      ),
  });

  async function refreshUserAdministration() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
      queryClient.invalidateQueries({
        queryKey: ["admin-user", userId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["admin-user-assignments", userId],
      }),
    ]);
  }

  if (!canRead) {
    return (
      <div className="page-stack">
        <PageHeader title="User" eyebrow="Administration" />
        <div className="form-alert">
          You do not have permission to view user administration.
        </div>
      </div>
    );
  }

  if (
    userQuery.isPending ||
    assignmentsQuery.isPending ||
    rolesQuery.isPending ||
    laboratoriesQuery.isPending
  ) {
    return <LoadingState label="Loading user administration" />;
  }

  if (userQuery.isError) return <ErrorState error={userQuery.error} />;
  if (assignmentsQuery.isError) {
    return <ErrorState error={assignmentsQuery.error} />;
  }
  if (rolesQuery.isError) return <ErrorState error={rolesQuery.error} />;
  if (laboratoriesQuery.isError) {
    return <ErrorState error={laboratoriesQuery.error} />;
  }

  const item = userQuery.data.item;
  const isSelf = actor?.id === item.id;

  async function submitIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIdentityError(null);

    const data = new FormData(event.currentTarget);
    const nextFullName = String(data.get("full_name") ?? "").trim();
    const nextActive = data.get("account_status") === "active";

    if (!nextFullName) {
      setIdentityError("Full name is required.");
      return;
    }

    if (!nextActive && !canDeactivate) {
      setIdentityError("You do not have permission to deactivate users.");
      return;
    }

    try {
      await saveIdentity.mutateAsync({
        fullName: nextFullName,
        active: nextActive,
      });
      await refreshUserAdministration();
    } catch (error) {
      setIdentityError(friendlyApiMessage(error));
    }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);

    if (newPassword.length < 12) {
      setPasswordError("Use at least 12 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }

    try {
      await passwordMutation.mutateAsync();
      setNewPassword("");
      setConfirmPassword("");
      await refreshUserAdministration();
    } catch (error) {
      setPasswordError(friendlyApiMessage(error));
    }
  }

  async function submitAssignment(event: FormEvent) {
    event.preventDefault();
    setAssignmentError(null);

    try {
      await grantMutation.mutateAsync();
      await refreshUserAdministration();
    } catch (error) {
      setAssignmentError(friendlyApiMessage(error));
    }
  }

  async function revokeRole(
    assignmentId: string,
    lockVersion: number,
  ) {
    const reason = window
      .prompt("Reason for revoking this role assignment:")
      ?.trim();
    if (!reason) return;

    setAssignmentError(null);
    try {
      await revokeMutation.mutateAsync({
        assignmentId,
        lockVersion,
        reason,
      });
      await refreshUserAdministration();
    } catch (error) {
      setAssignmentError(friendlyApiMessage(error));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration · User"
        title={item.full_name}
        description={item.email}
        actions={
          <StatusBadge value={item.is_active ? "ACTIVE" : "INACTIVE"} />
        }
      />

      {isSelf ? (
        <div className="information-banner">
          <strong>This is your own account.</strong>
          <span>
            Resetting your password or deactivating this account revokes
            backend sessions and can sign you out.
          </span>
        </div>
      ) : null}

      <div className="detail-grid">
        <section className="detail-card">
          <h2>Account identity</h2>
          <dl className="detail-list">
            <div>
              <dt>Email</dt>
              <dd>{item.email}</dd>
            </div>
            <div>
              <dt>User ID</dt>
              <dd>{item.id}</dd>
            </div>
            <div>
              <dt>Last login</dt>
              <dd>{formatDate(item.last_login_at)}</dd>
            </div>
            <div>
              <dt>Record version</dt>
              <dd>{item.lock_version}</dd>
            </div>
          </dl>
        </section>

        <section className="detail-card">
          <h2>Authorization model</h2>
          <p className="detail-note">
            Account activity and role assignment are separate. Regulatory
            approval authority is granted only through explicit role
            assignments; ADMIN alone does not become an approving officer.
          </p>
        </section>
      </div>

      {canUpdate ? (
        <form
          className="form-card"
          key={item.lock_version}
          onSubmit={submitIdentity}
        >
          <section className="form-section">
            <div className="form-section-heading">
              <h2>Account state</h2>
              <p>
                Changes use optimistic concurrency. If another administrator
                edits this account first, reload the current version.
              </p>
            </div>
            <div className="form-grid">
              <label className="form-field">
                <span>Full name *</span>
                <input
                  name="full_name"
                  defaultValue={item.full_name}
                  maxLength={200}
                />
              </label>

              <label className="form-field">
                <span>Account status</span>
                <select
                  name="account_status"
                  defaultValue={item.is_active ? "active" : "inactive"}
                  disabled={!canDeactivate && item.is_active}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
            </div>

            {canDeactivate ? (
              <div className="validation-panel">
                Choosing Inactive revokes the user’s active backend sessions.
              </div>
            ) : null}

            {identityError ? (
              <div className="form-alert" role="alert">
                {identityError}
              </div>
            ) : null}

            <div className="form-actions">
              <button
                className="button button-primary"
                type="submit"
                disabled={saveIdentity.isPending}
              >
                {saveIdentity.isPending ? "Saving…" : "Save account"}
              </button>
            </div>
          </section>
        </form>
      ) : null}

      {canUpdate ? (
        <form className="form-card" onSubmit={submitPassword}>
          <section className="form-section">
            <div className="form-section-heading">
              <h2>Reset password</h2>
              <p>
                Administrator reset replaces the password hash and revokes all
                existing refresh-session families for this user.
              </p>
            </div>

            <div className="form-grid">
              <label className="form-field">
                <span>New password *</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  minLength={12}
                  maxLength={128}
                />
              </label>
              <label className="form-field">
                <span>Confirm password *</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  minLength={12}
                  maxLength={128}
                />
              </label>
            </div>

            {passwordError ? (
              <div className="form-alert" role="alert">
                {passwordError}
              </div>
            ) : null}

            <div className="form-actions">
              <button
                className="button button-secondary"
                type="submit"
                disabled={passwordMutation.isPending}
              >
                {passwordMutation.isPending
                  ? "Resetting…"
                  : "Reset password"}
              </button>
            </div>
          </section>
        </form>
      ) : null}

      <section className="data-card">
        <div className="admin-section-heading">
          <div>
            <p className="page-eyebrow">Authorization</p>
            <h2>Role assignments</h2>
          </div>
          <span>
            Active and revoked assignments are retained for traceability.
          </span>
        </div>

        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Scope</th>
                <th>Laboratory</th>
                <th>Assigned</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {assignmentsQuery.data.length === 0 ? (
                <tr>
                  <td colSpan={6}>No role assignments are visible.</td>
                </tr>
              ) : (
                assignmentsQuery.data.map((assignment) => {
                  const role = roleById.get(assignment.role_id);
                  const lab = assignment.laboratory_id
                    ? labById.get(assignment.laboratory_id)
                    : null;

                  return (
                    <tr key={assignment.id}>
                      <td>
                        {role
                          ? ROLE_LABELS[role.code] ?? role.name
                          : assignment.role_id}
                      </td>
                      <td>{assignment.scope_type}</td>
                      <td>
                        {assignment.scope_type === "GLOBAL"
                          ? "All deployment"
                          : lab
                            ? `${lab.name} (${lab.code})`
                            : assignment.laboratory_id ?? "—"}
                      </td>
                      <td>{formatDate(assignment.assigned_at)}</td>
                      <td>
                        <StatusBadge
                          value={
                            assignment.revoked_at ? "REVOKED" : "ACTIVE"
                          }
                        />
                      </td>
                      <td>
                        {!assignment.revoked_at && canManageRoles ? (
                          <button
                            className="button button-danger button-compact"
                            type="button"
                            disabled={revokeMutation.isPending}
                            onClick={() =>
                              void revokeRole(
                                assignment.id,
                                assignment.lock_version,
                              )
                            }
                          >
                            Revoke
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {canManageRoles ? (
        <form className="form-card" onSubmit={submitAssignment}>
          <section className="form-section">
            <div className="form-section-heading">
              <h2>Grant role</h2>
              <p>
                The backend remains authoritative for role scope and
                permission checks. Global assignments are restricted to ADMIN.
              </p>
            </div>

            <div className="form-grid">
              {canManageGlobal ? (
                <label className="form-field">
                  <span>Scope *</span>
                  <select
                    value={assignmentScope}
                    onChange={(event) => {
                      const next = event.target.value as AssignmentScope;
                      setAssignmentScope(next);
                      if (next === "GLOBAL") {
                        setAssignmentRole("ADMIN");
                        setAssignmentLaboratoryId("");
                      }
                    }}
                  >
                    <option value="LABORATORY">Laboratory</option>
                    <option value="GLOBAL">Global administration</option>
                  </select>
                </label>
              ) : null}

              <label className="form-field">
                <span>Role *</span>
                <select
                  value={
                    assignmentScope === "GLOBAL"
                      ? "ADMIN"
                      : assignmentRole
                  }
                  disabled={assignmentScope === "GLOBAL"}
                  onChange={(event) =>
                    setAssignmentRole(event.target.value as RoleCode)
                  }
                >
                  {(assignmentScope === "GLOBAL"
                    ? rolesQuery.data.filter(
                        (role) => role.code === "ADMIN",
                      )
                    : rolesQuery.data
                  ).map((role) => (
                    <option key={role.id} value={role.code}>
                      {ROLE_LABELS[role.code] ?? role.name}
                    </option>
                  ))}
                </select>
              </label>

              {assignmentScope === "LABORATORY" ? (
                <label className="form-field form-span-2">
                  <span>Laboratory *</span>
                  <select
                    value={assignmentLaboratoryId}
                    onChange={(event) =>
                      setAssignmentLaboratoryId(event.target.value)
                    }
                  >
                    <option value="">Select laboratory</option>
                    {availableLaboratories.map((laboratory) => (
                      <option key={laboratory.id} value={laboratory.id}>
                        {laboratory.name} ({laboratory.code})
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>

            {assignmentError ? (
              <div className="form-alert" role="alert">
                {assignmentError}
              </div>
            ) : null}

            <div className="form-actions">
              <button
                className="button button-primary"
                type="submit"
                disabled={
                  grantMutation.isPending ||
                  (assignmentScope === "LABORATORY" &&
                    !assignmentLaboratoryId)
                }
              >
                {grantMutation.isPending ? "Granting…" : "Grant role"}
              </button>
            </div>
          </section>
        </form>
      ) : null}
    </div>
  );
}
