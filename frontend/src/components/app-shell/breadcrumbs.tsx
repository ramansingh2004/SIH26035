"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const labels: Record<string, string> = {
  dashboard: "Dashboard",
  manufacturers: "Manufacturers",
  instruments: "Instruments",
  equipment: "Test Equipment",
  evaluations: "Evaluations",
  reviews: "Technical Reviews",
  approvals: "Final Approvals",
  reports: "Reports",
  admin: "Administration",
  users: "Users",
  laboratories: "Laboratories",
  audit: "Audit Events",
};

function title(segment: string): string {
  return labels[segment] ?? segment.replaceAll("-", " ");
}

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <Link href="/dashboard">Home</Link>
      {segments.map((segment, index) => {
        const href = `/${segments.slice(0, index + 1).join("/")}`;
        const last = index === segments.length - 1;

        return (
          <span key={href}>
            <span className="breadcrumb-separator" aria-hidden="true">
              /
            </span>
            {last ? (
              <span aria-current="page">{title(segment)}</span>
            ) : (
              <Link href={href}>{title(segment)}</Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
