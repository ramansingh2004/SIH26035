const classByValue: Record<string, string> = {
  COMPLETE: "status-success",
  COMPLIANT: "status-success",
  ISSUED: "status-success",
  NONCOMPLIANT: "status-danger",
  REJECTED: "status-danger",
  REVIEW_REQUIRED: "status-warning",
  INCOMPLETE: "status-warning",
  UNISSUED: "status-warning",
  STALE: "status-muted",
  NOT_STARTED: "status-muted",
  UNDETERMINED: "status-muted",
  NOT_APPLICABLE: "status-muted",
  SUPERSEDED: "status-muted",
};

export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`status-chip ${classByValue[value] ?? "status-info"}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
