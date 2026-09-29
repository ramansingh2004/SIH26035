import type {
  SectionView,
  SessionView,
} from "@/lib/evaluations/types";

const ATTENTION = new Set(["INCOMPLETE", "STALE", "REVIEW_REQUIRED"]);

function nextAction(session: SessionView): string {
  switch (session.workflow_status) {
    case "DRAFT":
      return "Confirm the frozen instrument snapshot.";
    case "INSTRUMENT_CONFIGURATION":
      return "Resolve applicability before testing can start.";
    case "APPLICABILITY_CONFIRMED":
      return "Start testing when the assigned role is ready.";
    case "TESTING":
      return "Complete the required deterministic tests and selected runs.";
    case "EXAMINATION":
      return "Finish construction examination and checklist evidence.";
    case "UNDER_REVIEW":
      return "Technical review is in progress; preserve source traceability.";
    case "APPROVED":
      return "Proceed through the controlled report workflow.";
    case "REPORT_ISSUED":
      return "The issued record is immutable; use history for traceability.";
    case "REJECTED":
      return "Inspect review history for the recorded rejection reason.";
    case "CANCELLED":
      return "This workflow is cancelled.";
  }
}

export function EvaluationProgressOverview({
  session,
  sections,
}: {
  session: SessionView;
  sections: SectionView[];
}) {
  const total = sections.length;
  const required = sections.filter(
    (section) => section.applicability_status === "REQUIRED",
  ).length;
  const notApplicable = sections.filter(
    (section) => section.applicability_status === "NOT_APPLICABLE",
  ).length;
  const complete = sections.filter(
    (section) => section.evaluation_status === "COMPLETE",
  ).length;
  const attention = sections.filter(
    (section) =>
      section.applicability_status === "REQUIRES_REVIEW" ||
      ATTENTION.has(section.evaluation_status),
  ).length;
  const covered = sections.filter(
    (section) =>
      section.applicability_status === "NOT_APPLICABLE" ||
      section.evaluation_status === "COMPLETE",
  ).length;

  return (
    <section
      className="evaluation-coverage-strip"
      aria-labelledby="evaluation-progress-title"
    >
      <div className="coverage-primary">
        <span id="evaluation-progress-title">Section coverage</span>
        <strong>
          {covered} / {total}
        </strong>
      </div>

      <dl className="coverage-metrics">
        <div>
          <dt>Required</dt>
          <dd>{required}</dd>
        </div>
        <div>
          <dt>Complete</dt>
          <dd>{complete}</dd>
        </div>
        <div>
          <dt>Not applicable</dt>
          <dd>{notApplicable}</dd>
        </div>
        <div>
          <dt>Attention</dt>
          <dd>{attention}</dd>
        </div>
      </dl>

      <p className="coverage-next-action">{nextAction(session)}</p>
    </section>
  );
}
