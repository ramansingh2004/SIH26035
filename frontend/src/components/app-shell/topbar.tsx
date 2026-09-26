"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth/auth-context";
import { laboratoryGrant } from "@/lib/auth/permissions";
import { getAccessibleLaboratories } from "@/lib/laboratories/queries";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { user, selectedLaboratoryId, setSelectedLaboratoryId, logout } =
    useAuth();

  const laboratoryIds = useMemo(
    () => user?.laboratories.map((item) => item.laboratory_id) ?? [],
    [user],
  );

  const laboratories = useQuery({
    queryKey: ["laboratories", "accessible", laboratoryIds],
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

  const roles = useMemo(() => {
    const selected = laboratoryGrant(user, selectedLaboratoryId);
    const values = selected?.roles.length
      ? selected.roles
      : (user?.global_roles ?? []);
    return values.map((role) => role.replaceAll("_", " ")).join(", ");
  }, [selectedLaboratoryId, user]);

  const initials =
    user?.full_name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "U";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="menu-button"
          type="button"
          aria-label="Open navigation"
          onClick={onMenu}
        >
          ☰
        </button>
        <div>
          <p className="department-label">Department of Consumer Affairs</p>
          <strong className="application-title">
            NAWI Type Evaluation & Reporting
          </strong>
        </div>
      </div>

      <div className="topbar-actions">
        {user && user.laboratories.length > 0 ? (
          <label className="laboratory-picker">
            <span>Laboratory scope</span>
            <select
              value={selectedLaboratoryId ?? ""}
              onChange={(event) => setSelectedLaboratoryId(event.target.value)}
              aria-label="Selected laboratory scope"
            >
              {user.laboratories.map((grant) => {
                const laboratory = laboratoryById.get(grant.laboratory_id);
                const label = laboratory
                  ? `${laboratory.name} (${laboratory.code})`
                  : laboratories.isPending
                    ? "Loading laboratory…"
                    : "Laboratory";

                return (
                  <option value={grant.laboratory_id} key={grant.laboratory_id}>
                    {label}
                  </option>
                );
              })}
            </select>
          </label>
        ) : (
          <div className="scope-note">
            <span>Scope</span>
            <strong>Global administration</strong>
          </div>
        )}

        <Link
          className="user-summary user-summary-link"
          href="/account"
          aria-label="Open account and security settings"
        >
          <div className="user-avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="user-summary-copy">
            <strong>{user?.full_name ?? "User"}</strong>
            <span>{roles || "Authorized user"}</span>
          </div>
        </Link>

        <button
          type="button"
          className="button button-secondary button-compact"
          onClick={() => void logout()}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
