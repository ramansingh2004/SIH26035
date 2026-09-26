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
      return "The approved record may proceed through the controlled report workflow.";
    case "REPORT_ISSUED":
      return "The issued record is immutable; use history for traceability.";
    case "REJECTED":
      return "This workflow is rejected; inspect review history for the recorded reason.";
    case "CANCELLED":
      return "This workflow is cancelled and no longer accepts evaluation work.";
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
  const coverage = total === 0 ? 0 : Math.round((covered / total) * 100);

  return (
    <section
      className="polish-progress"
      aria-labelledby="evaluation-progress-title"
    >
      <div className="polish-progress-heading">
        <div>
          <p className="page-eyebrow">Progress visibility</p>
          <h2 id="evaluation-progress-title">17-section readiness overview</h2>
          <p>{nextAction(session)}</p>
        </div>
        <div className="polish-progress-score" aria-label="Section coverage">
          <strong>{coverage}%</strong>
          <span>section coverage</span>
        </div>
      </div>

      <div
        className="polish-progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={coverage}
        aria-label="Completed or explicitly not-applicable section coverage"
      >
        <span style={{ width: `${coverage}%` }} />
      </div>

      <div className="polish-progress-metrics">
        <div>
          <span>Total sections</span>
          <strong>{total}</strong>
        </div>
        <div>
          <span>Complete</span>
          <strong>{complete}</strong>
        </div>
        <div>
          <span>Not applicable</span>
          <strong>{notApplicable}</strong>
        </div>
        <div>
          <span>Needs attention</span>
          <strong>{attention}</strong>
        </div>
      </div>

      <div className="polish-progress-explainer">
        <strong>Presentation progress only</strong>
        <span>
          Coverage counts sections that are COMPLETE or explicitly
          NOT_APPLICABLE. It is not a compliance score and never changes the
          backend evaluation or outcome.
        </span>
      </div>
    </section>
  );
}
