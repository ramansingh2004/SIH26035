import { StatusBadge } from "@/components/ui/status-badge";
import type {
  ComplianceOutcome,
  EvaluationStatus,
  WorkflowStatus,
} from "@/lib/evaluations/types";

export function StatusAxes({
  workflow,
  evaluation,
  outcome,
}: {
  workflow: WorkflowStatus;
  evaluation: EvaluationStatus;
  outcome: ComplianceOutcome;
}) {
  return (
    <div className="status-axes" aria-label="Evaluation status axes">
      <div>
        <span>Workflow</span>
        <StatusBadge value={workflow} />
      </div>
      <div>
        <span>Evaluation</span>
        <StatusBadge value={evaluation} />
      </div>
      <div>
        <span>Outcome</span>
        <StatusBadge value={outcome} />
      </div>
    </div>
  );
}
