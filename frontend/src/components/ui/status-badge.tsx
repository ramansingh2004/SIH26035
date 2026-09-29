const classByValue: Record<string, string> = {
  ACTIVE: "status-success",
  INACTIVE: "status-muted",
  REVOKED: "status-muted",
  COMPLETE: "status-success",
  COMPLIANT: "status-success",
  ISSUED: "status-success",
  APPROVED: "status-success",
  READY: "status-success",
  RESOLVED: "status-success",
  NONCOMPLIANT: "status-danger",
  FAILED: "status-danger",
  BLOCKED: "status-danger",
  REJECTED: "status-danger",
  REVIEW_REQUIRED: "status-warning",
  UNDER_REVIEW: "status-info",
  RETURNED_FOR_CORRECTION: "status-warning",
  OPEN: "status-warning",
  REQUIRED: "status-info",
  TESTING: "status-muted",
  EXAMINATION: "status-muted",
  DRAFT: "status-muted",
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

const strongValues = new Set([
  "COMPLIANT",
  "NONCOMPLIANT",
  "FAILED",
  "BLOCKED",
  "READY",
  "APPROVED",
  "ISSUED",
]);

export function StatusBadge({ value }: { value: string }) {
  const emphasis = strongValues.has(value)
    ? "status-chip-strong"
    : "status-chip-quiet";

  return (
    <span
      className={`status-chip ${classByValue[value] ?? "status-info"} ${emphasis}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
