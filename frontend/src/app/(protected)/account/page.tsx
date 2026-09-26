"use client";

import {
  type FormEvent,
  useMemo,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailList } from "@/components/master-data/detail-list";
import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  accountMe,
  changeOwnPassword,
  listAccountSessions,
  revokeAccountSession,
} from "@/lib/account/api";
import type { SessionFamilyView } from "@/lib/account/types";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { getAccessibleLaboratories } from "@/lib/laboratories/queries";

function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  return new Date(value).toLocaleString();
}

function roleLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function SessionRow({
  session,
  revoking,
  onRevoke,
}: {
  session: SessionFamilyView;
  revoking: boolean;
  onRevoke: (session: SessionFamilyView) => void;
}) {
  return (
    <tr>
      <td>
        <strong className="account-session-id">{session.family_id}</strong>
        <span className="admin-user-secondary">
          Created {formatDate(session.created_at)}
        </span>
      </td>
      <td>{formatDate(session.expires_at)}</td>
      <td>{formatDate(session.family_expires_at)}</td>
      <td>{session.client_ip ?? "Not recorded"}</td>
      <td>
        <details className="account-user-agent">
          <summary>View client</summary>
          <span>{session.user_agent ?? "Not recorded"}</span>
        </details>
      </td>
      <td>
        <StatusBadge value={session.is_active ? "ACTIVE" : "REVOKED"} />
      </td>
      <td>
        {session.is_active ? (
          <button
            className="button button-secondary button-compact"
            type="button"
            disabled={revoking}
            onClick={() => onRevoke(session)}
          >
            {revoking ? "Revoking…" : "Revoke"}
          </button>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

export default function AccountPage() {
  const queryClient = useQueryClient();
  const { user, clearAuthentication, logoutAll } = useAuth();
  const [sessionPage, setSessionPage] = useState(1);
  const [securityError, setSecurityError] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [logoutAllPending, setLogoutAllPending] = useState(false);

  const account = useQuery({
    queryKey: ["account", "me"],
    queryFn: accountMe,
  });

  const sessions = useQuery({
    queryKey: ["account", "sessions", sessionPage],
    queryFn: () => listAccountSessions(sessionPage),
  });

  const laboratoryIds = useMemo(
    () => user?.laboratories.map((grant) => grant.laboratory_id) ?? [],
    [user],
  );

  const laboratories = useQuery({
    queryKey: ["account", "laboratories", laboratoryIds],
    queryFn: () => getAccessibleLaboratories(laboratoryIds),
    enabled: laboratoryIds.length > 0,
    staleTime: 5 * 60_000,
  });

  const laboratoryById = useMemo(
    () =>
      new Map(
        (laboratories.data ?? []).map((laboratory) => [
          laboratory.id,
          laboratory,
        ]),
      ),
    [laboratories.data],
  );

  const revokeMutation = useMutation({
    mutationFn: (session: SessionFamilyView) =>
      revokeAccountSession(session.family_id, session.etag),
    onSuccess: async () => {
      setSecurityError(null);
      await queryClient.invalidateQueries({
        queryKey: ["account", "sessions"],
      });
    },
  });

  const passwordMutation = useMutation({
    mutationFn: changeOwnPassword,
  });

  function revokeSession(session: SessionFamilyView) {
    setSecurityError(null);
    revokeMutation.mutate(session, {
      onError: (error) => {
        setSecurityError(friendlyApiMessage(error));
      },
    });
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError(null);

    if (!currentPassword) {
      setPasswordError("Enter your current password.");
      return;
    }
    if (newPassword.length < 12 || newPassword.length > 128) {
      setPasswordError("New password must be between 12 and 128 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }
    if (!account.data?.etag) {
      setPasswordError("Reload your account before changing the password.");
      return;
    }

    try {
      await passwordMutation.mutateAsync({
        currentPassword,
        newPassword,
        etag: account.data.etag,
      });
      clearAuthentication();
    } catch (error) {
      setPasswordError(friendlyApiMessage(error));
    }
  }

  async function signOutAllDevices() {
    setSecurityError(null);
    setLogoutAllPending(true);

    try {
      await logoutAll();
    } catch (error) {
      setSecurityError(friendlyApiMessage(error));
      setLogoutAllPending(false);
    }
  }

  if (account.isPending) {
    return <LoadingState label="Loading account" />;
  }

  if (account.isError) {
    return (
      <ErrorState
        title="Unable to load account"
        error={account.error}
        onRetry={() => void account.refetch()}
      />
    );
  }

  const profile = account.data.item;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Account"
        title="Account & Security"
        description="Review your issued identity, authorization scope and refresh-session families, or change your password using the existing authentication controls."
      />

      <div className="information-banner">
        <strong>Your account identity is read-only here.</strong>
        <span>
          This page does not create a self-service profile mutation. User
          identity changes remain controlled through Administration → Users by
          an authorized administrator.
        </span>
      </div>

      <div className="account-grid">
        <section className="detail-card">
          <h2>Account identity</h2>
          <DetailList
            items={[
              { label: "Full name", value: profile.full_name },
              { label: "Email", value: profile.email },
              {
                label: "Account status",
                value: profile.is_active ? "Active" : "Inactive",
              },
              {
                label: "Last login",
                value: formatDate(profile.last_login_at),
              },
              { label: "Record version", value: profile.lock_version },
              { label: "User ID", value: profile.id },
            ]}
          />
        </section>

        <section className="detail-card">
          <h2>Global authorization</h2>
          <div className="account-authorization-block">
            <div>
              <span className="account-section-label">Roles</span>
              <div className="account-chip-list">
                {user?.global_roles.length ? (
                  user.global_roles.map((role) => (
                    <span className="account-chip" key={role}>
                      {roleLabel(role)}
                    </span>
                  ))
                ) : (
                  <span className="muted-copy">No global roles</span>
                )}
              </div>
            </div>

            <div>
              <span className="account-section-label">Permissions</span>
              <div className="account-chip-list">
                {user?.global_permissions.length ? (
                  user.global_permissions.map((permission) => (
                    <span className="account-chip account-chip-permission" key={permission}>
                      {permission}
                    </span>
                  ))
                ) : (
                  <span className="muted-copy">No global permissions</span>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="detail-card">
        <div className="panel-heading">
          <h2>Laboratory authorization</h2>
          <p>
            Roles and permissions below come from the authenticated backend
            identity. Global ADMIN status does not automatically create
            laboratory operational or regulatory roles.
          </p>
        </div>

        {laboratories.isError ? (
          <ErrorState
            title="Unable to load laboratory labels"
            error={laboratories.error}
            onRetry={() => void laboratories.refetch()}
          />
        ) : user?.laboratories.length ? (
          <div className="account-laboratory-list">
            {user.laboratories.map((grant) => {
              const laboratory = laboratoryById.get(grant.laboratory_id);

              return (
                <article
                  className="account-laboratory-card"
                  key={grant.laboratory_id}
                >
                  <div className="account-laboratory-heading">
                    <div>
                      <strong>
                        {laboratory
                          ? `${laboratory.name} (${laboratory.code})`
                          : laboratories.isPending
                            ? "Loading laboratory…"
                            : "Laboratory"}
                      </strong>
                      <span>{grant.laboratory_id}</span>
                    </div>
                    {laboratory ? (
                      <StatusBadge
                        value={laboratory.is_active ? "ACTIVE" : "INACTIVE"}
                      />
                    ) : null}
                  </div>

                  <div className="account-authorization-block">
                    <div>
                      <span className="account-section-label">Roles</span>
                      <div className="account-chip-list">
                        {grant.roles.map((role) => (
                          <span className="account-chip" key={role}>
                            {roleLabel(role)}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <span className="account-section-label">
                        Permissions
                      </span>
                      <div className="account-chip-list">
                        {grant.permissions.map((permission) => (
                          <span
                            className="account-chip account-chip-permission"
                            key={permission}
                          >
                            {permission}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No laboratory assignments"
            description="This account currently operates only in its global authorization scope."
          />
        )}
      </section>

      <section className="data-card">
        <div className="account-card-heading">
          <div>
            <h2>Login sessions</h2>
            <p>
              The backend groups refresh-token rotation records into session
              families. The current API does not identify which family belongs
              to this browser.
            </p>
          </div>
        </div>

        {securityError ? (
          <div className="form-alert account-inline-alert" role="alert">
            {securityError}
          </div>
        ) : null}

        {sessions.isPending ? (
          <div className="account-state-pad">
            <LoadingState label="Loading sessions" />
          </div>
        ) : sessions.isError ? (
          <div className="account-state-pad">
            <ErrorState
              error={sessions.error}
              onRetry={() => void sessions.refetch()}
            />
          </div>
        ) : sessions.data.items.length === 0 ? (
          <div className="account-state-pad">
            <EmptyState
              title="No session families"
              description="No refresh-session families are currently visible for this account."
            />
          </div>
        ) : (
          <>
            <div className="table-scroll">
              <table className="data-table account-session-table">
                <thead>
                  <tr>
                    <th>Session family</th>
                    <th>Refresh expiry</th>
                    <th>Family expiry</th>
                    <th>Client IP</th>
                    <th>Client</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {sessions.data.items.map((session) => (
                    <SessionRow
                      key={session.family_id}
                      session={session}
                      revoking={
                        revokeMutation.isPending &&
                        revokeMutation.variables?.family_id ===
                          session.family_id
                      }
                      onRevoke={revokeSession}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={sessions.data.page}
              pageSize={sessions.data.page_size}
              total={sessions.data.total}
              onPage={setSessionPage}
            />
          </>
        )}

        <div className="account-session-note">
          Revoking a session family prevents future refresh for that family.
          An already-issued short-lived access token can remain valid until it
          expires.
        </div>
      </section>

      <div className="account-security-grid">
        <section className="form-card">
          <div className="form-section-heading">
            <h2>Change password</h2>
            <p>
              Changing your password revokes all refresh sessions. You will be
              signed out after the backend accepts the change.
            </p>
          </div>

          <form onSubmit={submitPassword}>
            <label className="form-field">
              <span>Current password *</span>
              <input
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>

            <label className="form-field">
              <span>New password *</span>
              <input
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
              <small>12–128 characters.</small>
            </label>

            <label className="form-field">
              <span>Confirm new password *</span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </label>

            {passwordError ? (
              <div className="form-alert" role="alert">
                {passwordError}
              </div>
            ) : null}

            <div className="form-actions">
              <button
                className="button button-primary"
                type="submit"
                disabled={passwordMutation.isPending}
              >
                {passwordMutation.isPending
                  ? "Changing password…"
                  : "Change password and sign out"}
              </button>
            </div>
          </form>
        </section>

        <section className="account-danger-card">
          <div>
            <span className="page-eyebrow">Security</span>
            <h2>Sign out all devices</h2>
            <p>
              Revoke every refresh-session family for this account, including
              this browser, then clear the local authenticated state.
            </p>
          </div>

          <button
            className="button button-danger"
            type="button"
            disabled={logoutAllPending}
            onClick={() => void signOutAllDevices()}
          >
            {logoutAllPending ? "Signing out…" : "Sign out all devices"}
          </button>
        </section>
      </div>
    </div>
  );
}
