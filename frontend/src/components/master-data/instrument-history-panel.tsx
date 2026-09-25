"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { StatusAxes } from "@/components/evaluations/status-axes";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { instrumentEvaluationHistory } from "@/lib/history/api";

export function InstrumentHistoryPanel({
  instrumentId,
}: {
  instrumentId: string;
}) {
  const history = useQuery({
    queryKey: ["instrument-evaluation-history", instrumentId],
    queryFn: () => instrumentEvaluationHistory(instrumentId),
  });

  return (
    <section className="traceability-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Traceability</p>
        <h2>Evaluation and report history</h2>
        <p>
          Every evaluation revision and associated report remains visible,
          including superseded report revisions and retest counts.
        </p>
      </div>

      {history.isPending ? (
        <LoadingState label="Loading instrument history" />
      ) : history.isError ? (
        <ErrorState error={history.error} />
      ) : history.data.items.length === 0 ? (
        <p className="detail-note">
          No evaluation sessions have been recorded for this instrument.
        </p>
      ) : (
        <div className="instrument-history-list">
          {history.data.items
            .slice()
            .sort(
              (left, right) =>
                right.session_revision_no - left.session_revision_no,
            )
            .map((item) => (
              <article className="instrument-history-row" key={item.session_id}>
                <div className="instrument-history-main">
                  <div>
                    <strong>
                      Evaluation revision {item.session_revision_no}
                    </strong>
                    <span>
                      {item.application_number ?? "No application number"}
                      {" · "}
                      regulatory revision {item.regulatory_revision}
                    </span>
                    <small>
                      {item.run_count} run(s) · {item.retest_count} retest(s)
                    </small>
                  </div>
                  <StatusAxes
                    workflow={item.workflow_status}
                    evaluation={item.evaluation_status}
                    outcome={item.compliance_outcome}
                  />
                </div>

                <div className="instrument-history-links">
                  <Link
                    className="button button-secondary button-compact"
                    href={`/evaluations/${item.session_id}`}
                  >
                    Open evaluation
                  </Link>

                  {item.report_id && item.report_number ? (
                    <>
                      <StatusBadge value={item.report_status ?? "UNISSUED"} />
                      <Link
                        className="button button-secondary button-compact"
                        href={`/reports/${item.report_id}`}
                      >
                        {item.report_number}
                        {item.report_revision_no
                          ? ` · R${item.report_revision_no}`
                          : ""}
                      </Link>
                    </>
                  ) : (
                    <span className="history-no-report">No report</span>
                  )}
                </div>
              </article>
            ))}
        </div>
      )}
    </section>
  );
}
