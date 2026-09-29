"use client"

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { SectionView } from "@/lib/evaluations/types";

function sectionIndicator(section: SectionView) {
  if (section.compliance_outcome === "NONCOMPLIANT") {
    return { mark: "!", tone: "is-danger", label: "Noncompliant" };
  }

  if (section.applicability_status === "NOT_APPLICABLE") {
    return { mark: "—", tone: "is-muted", label: "Not applicable" };
  }

  if (section.evaluation_status === "COMPLETE") {
    return { mark: "✓", tone: "is-complete", label: "Complete" };
  }

  if (
    section.applicability_status === "REQUIRES_REVIEW" ||
    ["INCOMPLETE", "STALE", "REVIEW_REQUIRED"].includes(
      section.evaluation_status,
    )
  ) {
    return { mark: "•", tone: "is-warning", label: "Needs attention" };
  }

  return { mark: "•", tone: "is-pending", label: section.evaluation_status };
}

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
          const indicator = sectionIndicator(section);

          return (
            <Link
              key={section.id}
              href={href}
              className={`section-nav-item ${
                pathname === href ? "is-active" : ""
              }`}
            >
              <span className="section-number">
                {String(section.section_number).padStart(2, "0")}
              </span>

              <span className="section-copy">
                <strong>{section.name}</strong>
                <small>{section.code.replaceAll("_", " ")}</small>
              </span>

              <span
                className={`section-indicator ${indicator.tone}`}
                title={indicator.label}
                aria-label={indicator.label}
              >
                {indicator.mark}
              </span>
            </Link>
          );
        })}
    </nav>
  );
}
