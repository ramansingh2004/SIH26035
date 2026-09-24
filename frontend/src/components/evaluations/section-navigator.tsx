"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { StatusBadge } from "@/components/ui/status-badge";
import type { SectionView } from "@/lib/evaluations/types";

export function SectionNavigator({
  sessionId,
  sections,
}: {
  sessionId: string;
  sections: SectionView[];
}) {
  const pathname = usePathname();

  return (
    <nav className="section-navigator" aria-label="OIML R76 sections">
      {sections
        .slice()
        .sort((left, right) => left.section_number - right.section_number)
        .map((section) => {
          const href = `/evaluations/${sessionId}/sections/${section.section_number}`;
          return (
            <Link
              key={section.id}
              href={href}
              className={`section-nav-item ${
                pathname === href ? "is-active" : ""
              }`}
            >
              <span className="section-number">{section.section_number}</span>
              <span className="section-copy">
                <strong>{section.name}</strong>
                <small>{section.code}</small>
              </span>
              <span className="section-status">
                <StatusBadge value={section.evaluation_status} />
              </span>
            </Link>
          );
        })}
    </nav>
  );
}
