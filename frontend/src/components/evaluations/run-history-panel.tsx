"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { createRetest, runHistory, selectRun } from "@/lib/evaluations/run-api";
import type { RunView } from "@/lib/evaluations/run-types";
import type { RequirementView } from "@/lib/evaluations/types";
import { etagFromVersion } from "@/lib/master-data/types";

export function RunHistoryPanel({
  sessionId,
  run,
  requirement,
  canRetest,
  canSelect,
}: {
  sessionId: string;
  run: RunView;
  requirement: RequirementView;
  canRetest: boolean;
  canSelect: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [retestReason, setRetestReason] = useState("");
  const [candidate, setCandidate] = useState<string | null>(null);
  const [selectionReason, setSelectionReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const history = useQuery({
    queryKey: ["run-history", run.id],
    queryFn: () => runHistory(run.id, 1, 100),
  });

  const retest = useMutation({
    mutationFn: () =>
      createRetest(
        run.id,
        retestReason.trim(),
        etagFromVersion(run.lock_version),
      ),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({
        queryKey: ["evaluation-dashboard", sessionId],
      });
      router.push(`/evaluations/${sessionId}/runs/${created.item.id}`);
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  const selection = useMutation({
    mutationFn: () =>
      selectRun(
        requirement.id,
        candidate!,
        selectionReason.trim(),
        etagFromVersion(requirement.lock_version),
      ),
    onSuccess: async () => {
      setCandidate(null);
      setSelectionReason("");
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["run-history", run.id] }),
        queryClient.invalidateQueries({
          queryKey: ["evaluation-dashboard", sessionId],
        }),
      ]);
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  return (
    <section className="run-panel">
      <div className="panel-heading">
        <p className="page-eyebrow">Retest provenance</p>
        <h2>Run & result history</h2>
        <p>
          Retests preserve the original run. Authoritative selection is a
          separate reasoned action controlled by backend policy.
        </p>
      </div>

      {history.isPending ? (
        <p className="muted-copy">Loading run history…</p>
      ) : history.isError ? (
        <div className="form-alert">{friendlyApiMessage(history.error)}</div>
      ) : (
        <>
          <div className="history-run-list">
            {history.data.runs.items.map((item) => (
              <div className="history-run-row" key={item.id}>
                <div>
                  <strong>Run #{item.run_no}</strong>
                  <span>
                    input revision {item.input_revision}
                    {item.retest_reason ? ` · ${item.retest_reason}` : ""}
                  </span>
                </div>
                <div className="history-run-state">
                  {item.is_selected ? (
                    <span className="mini-tag">Selected</span>
                  ) : null}
                  <StatusBadge value={item.evaluation_status} />
                  <StatusBadge value={item.compliance_outcome} />
                  <Link
                    className="button button-secondary button-compact"
                    href={`/evaluations/${sessionId}/runs/${item.id}`}
                  >
                    Open
                  </Link>
                  {canSelect && !item.is_selected ? (
                    <button
                      className="button button-secondary button-compact"
                      type="button"
                      onClick={() => setCandidate(item.id)}
                    >
                      Select
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {candidate ? (
            <div className="history-action-form">
              <label className="form-field">
                <span>Selection reason *</span>
                <textarea
                  rows={3}
                  value={selectionReason}
                  onChange={(event) => setSelectionReason(event.target.value)}
                />
              </label>
              <div className="form-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => {
                    setCandidate(null);
                    setSelectionReason("");
                  }}
                >
                  Cancel
                </button>
                <button
                  className="button button-primary"
                  type="button"
                  disabled={selection.isPending || !selectionReason.trim()}
                  onClick={() => selection.mutate()}
                >
                  {selection.isPending ? "Selecting…" : "Confirm selected run"}
                </button>
              </div>
            </div>
          ) : null}

          {canRetest ? (
            <div className="history-action-form">
              <label className="form-field">
                <span>Create retest — reason *</span>
                <textarea
                  rows={3}
                  value={retestReason}
                  onChange={(event) => setRetestReason(event.target.value)}
                />
              </label>
              <button
                className="button button-secondary"
                type="button"
                disabled={retest.isPending || !retestReason.trim()}
                onClick={() => retest.mutate()}
              >
                {retest.isPending ? "Creating retest…" : "Create retest"}
              </button>
            </div>
          ) : null}

          {error ? <div className="form-alert">{error}</div> : null}

          <div className="history-timeline-grid">
            <div>
              <h3>Result events</h3>
              {history.data.events.map((event) => (
                <div className="timeline-row" key={event.id}>
                  <StatusBadge value={event.event_type} />
                  <div>
                    <strong>
                      Regulatory revision {event.regulatory_revision}
                    </strong>
                    <span>{event.reason}</span>
                    <small>{new Date(event.created_at).toLocaleString()}</small>
                  </div>
                </div>
              ))}
              {history.data.events.length === 0 ? (
                <p className="muted-copy">No result events.</p>
              ) : null}
            </div>

            <div>
              <h3>Selection events</h3>
              {history.data.selections.map((event) => (
                <div className="timeline-row" key={event.id}>
                  <span className="mini-tag">Run selected</span>
                  <div>
                    <strong>
                      Regulatory revision {event.regulatory_revision}
                    </strong>
                    <span>{event.reason}</span>
                    <small>{new Date(event.created_at).toLocaleString()}</small>
                  </div>
                </div>
              ))}
              {history.data.selections.length === 0 ? (
                <p className="muted-copy">No selection changes.</p>
              ) : null}
            </div>
          </div>

          <div className="result-version-list">
            <h3>Persisted result versions for this run</h3>
            {history.data.results.map((result) => (
              <div className="result-version-row" key={result.id}>
                <div>
                  <strong>Evaluation v{result.evaluation_version}</strong>
                  <span>
                    source revision {result.source_input_revision} ·{" "}
                    {result.engine_version}
                  </span>
                  <code>{result.result_hash}</code>
                </div>
                <div className="history-run-state">
                  <StatusBadge value={result.evaluation_status} />
                  <StatusBadge value={result.compliance_outcome} />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
