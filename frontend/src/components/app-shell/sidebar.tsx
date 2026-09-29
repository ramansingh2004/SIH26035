"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/auth-context";

type NavigationItem = {
  label: string;
  href: string;
  permission: string;
};

type NavigationGroup = {
  label: string;
  items: NavigationItem[];
};

const groups: NavigationGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard", href: "/dashboard", permission: "dashboard:read" },
      { label: "Evaluations", href: "/evaluations", permission: "session:read" },
      { label: "Reports", href: "/reports", permission: "report:read" },
    ],
  },
  {
    label: "Lab data",
    items: [
      { label: "Manufacturers", href: "/manufacturers", permission: "manufacturer:read" },
      { label: "Instruments", href: "/instruments", permission: "instrument:read" },
      { label: "Test equipment", href: "/equipment", permission: "equipment:read" },
    ],
  },
  {
    label: "Governance",
    items: [
      { label: "Technical reviews", href: "/reviews", permission: "approval:read" },
      { label: "Final approvals", href: "/approvals", permission: "approval:read" },
      { label: "Audit events", href: "/admin/audit", permission: "audit:read" },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "Laboratories", href: "/admin/laboratories", permission: "laboratory:read" },
      { label: "Users", href: "/admin/users", permission: "user:read" },
    ],
  },
];

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const { hasPermission } = useAuth();

  return (
    <>
      <button
        className={`sidebar-scrim ${open ? "is-visible" : ""}`}
        type="button"
        aria-label="Close navigation"
        onClick={onClose}
      />
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <Link className="brand-block" href="/dashboard" onClick={onClose}>
          <span className="brand-code" aria-hidden="true">R76</span>
          <span className="brand-copy">
            <strong>SIH26035</strong>
            <span>NAWI Laboratory</span>
          </span>
        </Link>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {groups.map((group) => {
            const visible = group.items.filter((item) =>
              hasPermission(item.permission),
            );
            if (visible.length === 0) return null;

            return (
              <div className="nav-group" key={group.label}>
                <p className="nav-group-label">{group.label}</p>
                {visible.map((item) => {
                  const active =
                    pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);

                  return (
                    <Link
                      className={`nav-item ${active ? "is-active" : ""}`}
                      href={item.href}
                      key={item.href}
                      onClick={onClose}
                    >
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <strong>Controlled workspace</strong>
          <span>OIML R 76 type evaluation</span>
        </div>
      </aside>
    </>
  );
}
