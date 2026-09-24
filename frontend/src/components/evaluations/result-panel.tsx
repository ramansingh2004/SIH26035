import { StatusAxes } from "./status-axes";
import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import type { ResultView, RunView } from "@/lib/evaluations/run-types";
import type { WorkflowStatus } from "@/lib/evaluations/types";

function compactEntries(value: Record<string, unknown>) {
  return Object.entries(value).filter(
    ([, item]) =>
      typeof item === "string" ||
      typeof item === "number" ||
      typeof item === "boolean",
  );
}

function TraceBlock({
  title,
  rows,
}: {
  title: string;
  rows: Array<Record<string, unknown>>;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="result-trace-block">
      <h3>{title}</h3>
      {rows.map((row, index) => (
        <div className="result-trace-row" key={index}>
          {compactEntries(row).map(([key, value]) => (
            <span key={key}>
              <strong>{key.replaceAll("_", " ")}:</strong> {String(value)}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

export function ResultPanel({
  workflow,
  run,
  results,
}: {
  workflow: WorkflowStatus;
  run: RunView;
  results: ResultView[];
}) {
  const current =
    results.find((item) => item.id === run.current_result_id) ??
    results.at(-1) ??
    null;

  return (
    <section className="run-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Deterministic backend result</p>
        <h2>Evaluation result</h2>
      </div>

      {!current ? (
        <p className="muted-copy">
          No persisted result exists for the current captured input revision.
        </p>
      ) : (
        <>
          <StatusAxes
            workflow={workflow}
            evaluation={current.evaluation_status}
            outcome={current.compliance_outcome}
          />

          <dl className="result-metadata">
            <div>
              <dt>Evaluation version</dt>
              <dd>{current.evaluation_version}</dd>
            </div>
            <div>
              <dt>Source revision</dt>
              <dd>{current.source_input_revision}</dd>
            </div>
            <div>
              <dt>Engine</dt>
              <dd>{current.engine_version}</dd>
            </div>
            <div>
              <dt>Ruleset</dt>
              <dd>{current.ruleset_version}</dd>
            </div>
            <div>
              <dt>Reason</dt>
              <dd>{current.reason}</dd>
            </div>
            <div>
              <dt>Input hash</dt>
              <dd className="hash-value">{current.input_hash}</dd>
            </div>
            <div>
              <dt>Result hash</dt>
              <dd className="hash-value">{current.result_hash}</dd>
            </div>
            <div>
              <dt>Ruleset hash</dt>
              <dd className="hash-value">
                {current.ruleset_configuration_hash}
              </dd>
            </div>
          </dl>

          {current.unresolved_rule_ids.length > 0 ? (
            <RegulatoryBlocker ruleIds={current.unresolved_rule_ids} />
          ) : null}

          <TraceBlock
            title="Failed conditions"
            rows={current.failed_conditions_json}
          />
          <TraceBlock
            title="Acceptance limits"
            rows={current.acceptance_limits_json}
          />
          <TraceBlock
            title="Calculation trace"
            rows={current.calculations_json}
          />
          <TraceBlock
            title="Rule references"
            rows={current.rule_references_json}
          />
        </>
      )}
    </section>
  );
}
