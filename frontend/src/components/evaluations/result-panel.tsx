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

          <div className="result-explainer">
            <div className="result-explainer-heading">
              <div>
                <span className="report-kicker">Deterministic explanation</span>
                <h3>How to read this result</h3>
              </div>
              {current.deterministic_result.synthetic_fixture === true ? (
                <span className="mini-tag">Synthetic fixture · demo only</span>
              ) : null}
            </div>
            <div className="result-explainer-grid">
              <div>
                <span>Calculation entries</span>
                <strong>{current.calculations_json.length}</strong>
                <small>Persisted backend trace entries.</small>
              </div>
              <div>
                <span>Acceptance criteria</span>
                <strong>{current.acceptance_limits_json.length}</strong>
                <small>Persisted limits/rules used by the engine.</small>
              </div>
              <div>
                <span>Failed checks</span>
                <strong>{current.failed_conditions_json.length}</strong>
                <small>
                  {current.failed_conditions_json.length > 0
                    ? "At least one persisted condition did not pass."
                    : "No failed condition is persisted for this result."}
                </small>
              </div>
              <div>
                <span>Unresolved rules</span>
                <strong>{current.unresolved_rule_ids.length}</strong>
                <small>
                  {current.unresolved_rule_ids.length > 0
                    ? "Regulatory blockers remain explicit."
                    : "No unresolved rule ID is attached to this result."}
                </small>
              </div>
            </div>
            <p>
              <strong>No browser calculation:</strong> this panel explains the
              immutable result returned by the backend engine. It does not derive,
              adjust or override a compliance outcome.
            </p>
          </div>

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
            title="Persisted failed checks"
            rows={current.failed_conditions_json}
          />
          <TraceBlock
            title="Acceptance limits (persisted criteria)"
            rows={current.acceptance_limits_json}
          />
          <TraceBlock
            title="Calculation trace (persisted)"
            rows={current.calculations_json}
          />
          <TraceBlock
            title="Rule references (persisted)"
            rows={current.rule_references_json}
          />
        </>
      )}
    </section>
  );
}
