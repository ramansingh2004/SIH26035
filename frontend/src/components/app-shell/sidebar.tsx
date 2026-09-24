"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/auth-context";

type NavigationItem = {
  label: string;
  href: string;
  permission: string;
  implemented: boolean;
};

type NavigationGroup = {
  label?: string;
  items: NavigationItem[];
};

const groups: NavigationGroup[] = [
  {
    items: [
      {
        label: "Dashboard",
        href: "/dashboard",
        permission: "dashboard:read",
        implemented: true,
      },
    ],
  },
  {
    label: "Master Data",
    items: [
      {
        label: "Manufacturers",
        href: "/manufacturers",
        permission: "manufacturer:read",
        implemented: true,
      },
      {
        label: "Instruments",
        href: "/instruments",
        permission: "instrument:read",
        implemented: true,
      },
      {
        label: "Test Equipment",
        href: "/equipment",
        permission: "equipment:read",
        implemented: true,
      },
    ],
  },
  {
    label: "Evaluation",
    items: [
      {
        label: "Evaluations",
        href: "/evaluations",
        permission: "session:read",
        implemented: false,
      },
    ],
  },
  {
    label: "Review & Approval",
    items: [
      {
        label: "Technical Reviews",
        href: "/reviews",
        permission: "approval:read",
        implemented: false,
      },
      {
        label: "Final Approvals",
        href: "/approvals",
        permission: "approval:read",
        implemented: false,
      },
    ],
  },
  {
    label: "Reporting",
    items: [
      {
        label: "Reports",
        href: "/reports",
        permission: "report:read",
        implemented: false,
      },
    ],
  },
  {
    label: "Administration",
    items: [
      {
        label: "Users",
        href: "/admin/users",
        permission: "user:read",
        implemented: false,
      },
      {
        label: "Laboratories",
        href: "/admin/laboratories",
        permission: "laboratory:read",
        implemented: false,
      },
      {
        label: "Audit Events",
        href: "/admin/audit",
        permission: "audit:read",
        implemented: false,
      },
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
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            LM
          </div>
          <div>
            <strong>SIH26035</strong>
            <span>Legal Metrology Laboratory</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {groups.map((group, index) => {
            const visible = group.items.filter((item) =>
              hasPermission(item.permission),
            );
            if (visible.length === 0) return null;

            return (
              <div className="nav-group" key={group.label ?? `group-${index}`}>
                {group.label ? (
                  <p className="nav-group-label">{group.label}</p>
                ) : null}
                {visible.map((item) =>
                  item.implemented ? (
                    <Link
                      className={`nav-item ${
                        pathname === item.href ||
                        pathname.startsWith(`${item.href}/`)
                          ? "is-active"
                          : ""
                      }`}
                      href={item.href}
                      key={item.href}
                      onClick={onClose}
                    >
                      <span>{item.label}</span>
                    </Link>
                  ) : (
                    <span
                      className="nav-item nav-item-disabled"
                      key={item.href}
                    >
                      <span>{item.label}</span>
                      <small>Upcoming</small>
                    </span>
                  ),
                )}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <span>OIML R76 workflow</span>
          <small>Authoritative calculations remain server-side.</small>
        </div>
      </aside>
    </>
  );
}
