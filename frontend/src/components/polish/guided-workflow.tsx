"use client";

import Link from "next/link";

import { useAuth } from "@/lib/auth/auth-context";

const STEPS = [
  {
    number: "01",
    title: "Orient",
    description:
      "Read the laboratory dashboard first. Workflow, evaluation readiness and compliance outcome are separate status axes.",
    href: "/dashboard",
    label: "Open dashboard",
    permission: "dashboard:read",
  },
  {
    number: "02",
    title: "Evaluate",
    description:
      "Open an evaluation to inspect the pinned instrument snapshot, 17 sections, deterministic results and history.",
    href: "/evaluations",
    label: "Browse evaluations",
    permission: "session:read",
  },
  {
    number: "03",
    title: "Review",
    description:
      "Technical review and final approval are governance actions. A COMPLIANT result is not automatically an approved record.",
    href: "/reviews",
    label: "Open reviews",
    permission: "approval:read",
  },
  {
    number: "04",
    title: "Report",
    description:
      "Use an unofficial preview for working review. Official generation and issue remain separate controlled gates.",
    href: "/reports",
    label: "Open reports",
    permission: "report:read",
  },
] as const;

export function GuidedWorkflow() {
  const { hasPermission } = useAuth();

  return (
    <section className="polish-guide" aria-labelledby="guided-workflow-title">
      <div className="polish-guide-heading">
        <div>
          <p className="page-eyebrow">Guided onboarding</p>
          <h2 id="guided-workflow-title">How to read the workflow</h2>
          <p>
            Follow the record from laboratory scope to deterministic evaluation,
            independent review and reporting. Each step preserves its own
            authorization and traceability boundary.
          </p>
        </div>
        <div className="polish-axis-note">
          <strong>Three axes, three meanings</strong>
          <span>Workflow = lifecycle</span>
          <span>Evaluation = readiness/completeness</span>
          <span>Outcome = deterministic result</span>
        </div>
      </div>

      <div className="polish-guide-grid">
        {STEPS.map((step) => {
          const allowed = hasPermission(step.permission);
          return (
            <article className="polish-guide-step" key={step.number}>
              <span className="polish-step-number">{step.number}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
              {allowed ? (
                <Link
                  className="button button-secondary button-compact"
                  href={step.href}
                >
                  {step.label}
                </Link>
              ) : (
                <span className="polish-role-note">
                  Not available for the current laboratory role
                </span>
              )}
            </article>
          );
        })}
      </div>

      <p className="polish-safety-note">
        The interface explains backend-persisted decisions; it does not calculate
        regulatory thresholds or compliance outcomes in the browser.
      </p>
    </section>
  );
}
