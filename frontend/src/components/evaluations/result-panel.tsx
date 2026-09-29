import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import { StatusBadge } from "@/components/ui/status-badge";
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

function firstValue(
  row: Record<string, unknown> | undefined,
  keys: string[],
): unknown {
  if (!row) return undefined;

  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }

  return undefined;
}

function displayMetric(value: unknown, unit?: unknown) {
  if (value === undefined || value === null || value === "") return "—";
  return `${String(value)}${unit ? ` ${String(unit)}` : ""}`;
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

  if (!current) {
    return (
      <section className="run-panel deterministic-result-panel">
        <div className="panel-heading">
          <p className="page-eyebrow">Deterministic backend result</p>
          <h2>Evaluation result</h2>
        </div>
        <p className="muted-copy">
          No persisted result exists for the current captured input revision.
        </p>
      </section>
    );
  }

  const failedCheck = current.failed_conditions_json[0] as
    | Record<string, unknown>
    | undefined;

  const failingCalculation =
    (current.calculations_json.find(
      (row) =>
        String((row as Record<string, unknown>).compliance_outcome ?? "") ===
        "NONCOMPLIANT",
    ) as Record<string, unknown> | undefined) ??
    (current.calculations_json[0] as Record<string, unknown> | undefined);

  const primaryLimit = current.acceptance_limits_json[0] as
    | Record<string, unknown>
    | undefined;

  const unit =
    firstValue(primaryLimit, ["unit"]) ??
    firstValue(failingCalculation, ["unit"]) ??
    "";

  const observedError = firstValue(failingCalculation, [
    "corrected_error_g",
    "error_g",
    "actual",
    "value",
  ]);
  const permittedError = firstValue(primaryLimit, [
    "value",
    "mpe_g",
    "limit",
    "maximum",
  ]);
  const load = firstValue(failingCalculation, ["load_g", "load"]);
  const indication = firstValue(failingCalculation, [
    "indication_g",
    "indication",
    "prerounding_indication_g",
  ]);

  const decisionTone =
    current.compliance_outcome === "NONCOMPLIANT"
      ? "is-danger"
      : current.compliance_outcome === "COMPLIANT"
        ? "is-success"
        : "is-neutral";

  return (
    <section className="run-panel deterministic-result-panel">
      <div className="deterministic-result-heading">
        <div>
          <p className="page-eyebrow">Deterministic backend result</p>
          <h2>Evaluation result</h2>
          <p>
            Persisted engine decision for input revision{" "}
            {current.source_input_revision}. The browser does not recalculate
            compliance.
          </p>
        </div>

        {current.deterministic_result.synthetic_fixture === true ? (
          <span className="mini-tag">Synthetic fixture · demo only</span>
        ) : null}
      </div>

      <div className={`decision-block ${decisionTone}`}>
        <div className="decision-outcome">
          <span>Backend decision</span>
          <StatusBadge value={current.compliance_outcome} />
          <small>
            Evaluation{" "}
            {current.evaluation_status.replaceAll("_", " ").toLowerCase()}
            {" · "}
            workflow {workflow.replaceAll("_", " ").toLowerCase()}
          </small>
        </div>

        <div className="decision-measurements">
          <div>
            <span>Load</span>
            <strong>{displayMetric(load, load !== undefined ? "g" : "")}</strong>
          </div>
          <div>
            <span>Indication</span>
            <strong>
              {displayMetric(indication, indication !== undefined ? "g" : "")}
            </strong>
          </div>
          <div>
            <span>Observed error</span>
            <strong>{displayMetric(observedError, unit)}</strong>
          </div>
          <div>
            <span>Permitted error</span>
            <strong>{displayMetric(permittedError, unit)}</strong>
          </div>
        </div>
      </div>

      {failedCheck ? (
        <div className="decision-failure">
          <div>
            <span>Failed condition</span>
            <strong>
              {String(
                firstValue(failedCheck, ["code", "rule_id", "name"]) ??
                  "Persisted check failed",
              )}
            </strong>
          </div>
          <p>
            {String(
              firstValue(failedCheck, ["reason", "message", "description"]) ??
                "The backend persisted a failed acceptance condition.",
            )}
          </p>
        </div>
      ) : (
        <div className="decision-pass-note">
          <strong>No failed checks persisted.</strong>
          <span>
            The backend result contains {current.calculations_json.length}{" "}
            calculation trace entries and{" "}
            {current.acceptance_limits_json.length} acceptance criteria.
          </span>
        </div>
      )}

      {current.unresolved_rule_ids.length > 0 ? (
        <RegulatoryBlocker ruleIds={current.unresolved_rule_ids} />
      ) : null}

      <details className="technical-trace">
        <summary>
          <span>Technical trace</span>
          <small>
            Engine metadata, hashes, persisted criteria and calculation trace
          </small>
        </summary>

        <div className="technical-trace-body">
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
        </div>
      </details>
    </section>
  );
}
