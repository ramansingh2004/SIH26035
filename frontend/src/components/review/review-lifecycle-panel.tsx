"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError, friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import type { SessionView } from "@/lib/evaluations/types";
import {
  correctionHistory,
  resolveCorrection,
  reviewHistory,
  submitForReview,
} from "@/lib/review/api";
import { etagFromVersion } from "@/lib/master-data/types";

function scopeTargets(scope: Record<string, unknown>) {
  const raw = scope.targets;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === "object",
  );
}

export function ReviewLifecyclePanel({
  session,
  sessionEtag,
  onChanged,
}: {
  session: SessionView;
  sessionEtag: string | null;
  onChanged: () => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [resolutionNote, setResolutionNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);

  const corrections = useQuery({
    queryKey: ["corrections", session.id],
    queryFn: () => correctionHistory(session.id),
  });
  const history = useQuery({
    queryKey: ["review-history", session.id],
    queryFn: () => reviewHistory(session.id),
    enabled: hasPermission("approval:read"),
  });

  const openCorrection = corrections.data?.find(
    (item) => item.correction_status === "OPEN",
  );

  const returnRevision = useMemo(() => {
    if (!openCorrection || !history.data) return null;
    return (
      history.data.find(
        (action) => action.id === openCorrection.approval_action_id,
      )?.regulatory_revision ?? null
    );
  }, [history.data, openCorrection]);

  const changedAfterReturn =
    returnRevision !== null && session.regulatory_revision > returnRevision;

  async function refresh() {
    setBlockers([]);
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["corrections", session.id],
      }),
      queryClient.invalidateQueries({
        queryKey: ["review-history", session.id],
      }),
      onChanged(),
    ]);
  }

  function capture(cause: unknown) {
    setError(friendlyApiMessage(cause));
    if (cause instanceof ApiError) {
      const raw = cause.details.blockers;
      if (Array.isArray(raw)) {
        setBlockers(
          raw.filter((value): value is string => typeof value === "string"),
        );
      }
    }
  }

  const submit = useMutation({
    mutationFn: async () => {
      if (!sessionEtag) throw new Error("Reload before submitting review.");
      return submitForReview(session.id, sessionEtag);
    },
    onSuccess: async () => {
      setError(null);
      await refresh();
    },
    onError: capture,
  });

  const resolve = useMutation({
    mutationFn: async () => {
      if (!openCorrection) throw new Error("No open correction exists.");
      if (!resolutionNote.trim()) {
        throw new Error("Resolution note is required.");
      }
      return resolveCorrection(
        session.id,
        openCorrection.id,
        resolutionNote.trim(),
        etagFromVersion(openCorrection.lock_version),
      );
    },
    onSuccess: async () => {
      setResolutionNote("");
      setError(null);
      await refresh();
    },
    onError: capture,
  });

  const canSubmit =
    hasPermission("review:submit") &&
    ["TESTING", "EXAMINATION"].includes(session.workflow_status) &&
    !openCorrection &&
    session.evaluation_status === "COMPLETE" &&
    ["COMPLIANT", "NONCOMPLIANT"].includes(session.compliance_outcome);

  const canResolve =
    Boolean(openCorrection) &&
    hasPermission("session:update") &&
    changedAfterReturn;

  return (
    <section className="evaluation-card review-lifecycle-card">
      <div className="panel-heading-row">
        <div className="panel-heading">
          <p className="page-eyebrow">Governance</p>
          <h2>Review lifecycle</h2>
        </div>
        {session.workflow_status === "UNDER_REVIEW" ? (
          <Link
            className="button button-secondary button-compact"
            href={`/reviews/${session.id}`}
          >
            Open technical review
          </Link>
        ) : null}
      </div>

      {openCorrection ? (
        <div className="open-correction">
          <div className="open-correction-head">
            <StatusBadge value="OPEN" />
            <strong>Bounded correction request</strong>
          </div>
          <p>{openCorrection.reason}</p>
          <span>
            Returned to {openCorrection.target_workflow_status} · requested{" "}
            {new Date(openCorrection.requested_at).toLocaleString()}
          </span>

          <div className="correction-scope-summary">
            {scopeTargets(openCorrection.requested_scope_json).map(
              (target, index) => (
                <div key={`${String(target.entity_type)}-${index}`}>
                  <strong>{String(target.entity_type)}</strong>
                  <span>{String(target.entity_id)}</span>
                  <small>
                    {Array.isArray(target.field_paths)
                      ? target.field_paths.map(String).join(", ")
                      : "No fields"}
                  </small>
                </div>
              ),
            )}
          </div>

          {!changedAfterReturn ? (
            <div className="information-banner">
              <strong>A source change is required before resolution.</strong>
              <span>
                Make only the corrections authorized above. The backend will
                reject mutations outside this scope.
              </span>
            </div>
          ) : (
            <div className="correction-resolution">
              <label className="form-field">
                <span>Resolution note *</span>
                <textarea
                  rows={3}
                  value={resolutionNote}
                  onChange={(event) =>
                    setResolutionNote(event.target.value)
                  }
                />
              </label>
              <button
                className="button button-primary"
                type="button"
                disabled={!canResolve || resolve.isPending}
                onClick={() => resolve.mutate()}
              >
                {resolve.isPending ? "Resolving…" : "Resolve correction"}
              </button>
            </div>
          )}
        </div>
      ) : (
        <>
          <p className="muted-copy">
            A session can be submitted only when the backend determines the
            complete current record is review-ready. COMPLIANT and
            NONCOMPLIANT are both determined outcomes.
          </p>

          {canSubmit ? (
            <button
              className="button button-primary"
              type="button"
              disabled={submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending
                ? "Submitting…"
                : "Submit for technical review"}
            </button>
          ) : null}

          {session.workflow_status === "UNDER_REVIEW" ? (
            <div className="review-links">
              <Link href={`/reviews/${session.id}`}>
                Technical review case
              </Link>
              {hasPermission("approval:finalize") ? (
                <Link href={`/approvals/${session.id}`}>
                  Final approval case
                </Link>
              ) : null}
            </div>
          ) : null}

          {session.workflow_status === "APPROVED" ? (
            <div className="governance-banner">
              <strong>Record finally approved.</strong>
              <span>
                Approval does not change the stored compliance outcome:{" "}
                {session.compliance_outcome}.
              </span>
            </div>
          ) : null}
        </>
      )}

      {error ? <div className="form-alert">{error}</div> : null}

      {blockers.length > 0 ? (
        <div className="review-blocker-list">
          <strong>Backend review blockers</strong>
          {blockers.map((blocker) => (
            <code key={blocker}>{blocker}</code>
          ))}
        </div>
      ) : null}
    </section>
  );
}
