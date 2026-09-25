const classByValue: Record<string, string> = {
  ACTIVE: "status-success",
  COMPLETE: "status-success",
  COMPLIANT: "status-success",
  ISSUED: "status-success",
  APPROVED: "status-success",
  RESOLVED: "status-success",
  NONCOMPLIANT: "status-danger",
  REJECTED: "status-danger",
  REVIEW_REQUIRED: "status-warning",
  UNDER_REVIEW: "status-info",
  RETURNED_FOR_CORRECTION: "status-warning",
  OPEN: "status-warning",
  INVALIDATED: "status-muted",
  INCOMPLETE: "status-warning",
  UNISSUED: "status-warning",
  STALE: "status-muted",
  NOT_STARTED: "status-muted",
  UNDETERMINED: "status-muted",
  NOT_APPLICABLE: "status-muted",
  SUPERSEDED: "status-muted",
  ARCHIVED: "status-muted",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`status-chip ${classByValue[value] ?? "status-info"}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
