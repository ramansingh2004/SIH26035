import { StatusBadge } from "@/components/ui/status-badge";
import type { ApprovalActionView } from "@/lib/review/types";

export function ReviewHistory({
  actions,
  regulatoryRevision,
}: {
  actions: ApprovalActionView[];
  regulatoryRevision: number;
}) {
  if (actions.length === 0) {
    return <p className="muted-copy">No review or approval actions recorded.</p>;
  }

  return (
    <div className="review-history-list">
      {actions
        .slice()
        .sort(
          (left, right) =>
            new Date(right.created_at).getTime() -
            new Date(left.created_at).getTime(),
        )
        .map((action) => (
          <div className="review-history-row" key={action.id}>
            <div className="review-history-marker">
              <StatusBadge value={action.decision} />
            </div>
            <div>
              <strong>
                {action.stage.replaceAll("_", " ")} · revision{" "}
                {action.regulatory_revision}
              </strong>
              <span>
                Actor {action.actor_id}
                {action.regulatory_revision === regulatoryRevision
                  ? " · current regulatory revision"
                  : ""}
              </span>
              {action.comment ? <p>{action.comment}</p> : null}
              {action.reason && action.reason !== action.comment ? (
                <p>{action.reason}</p>
              ) : null}
              <small>{new Date(action.created_at).toLocaleString()}</small>
            </div>
          </div>
        ))}
    </div>
  );
}
