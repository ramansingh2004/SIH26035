"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError, friendlyApiMessage } from "@/lib/api/errors";
import {
  calculateApplicability,
  confirmApplicability,
} from "@/lib/evaluations/api";
import type { ApplicabilityView } from "@/lib/evaluations/types";

export function ApplicabilityPanel({
  sessionId,
  etag,
  canExecute,
  workflowStatus,
  onChanged,
}: {
  sessionId: string;
  etag: string | null;
  canExecute: boolean;
  workflowStatus: string;
  onChanged: () => Promise<void>;
}) {
  const [plan, setPlan] = useState<ApplicabilityView | null>(null);
  const [elections, setElections] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const calculate = useMutation({
    mutationFn: () => calculateApplicability(sessionId),
    onSuccess: (value) => {
      setPlan(value);
      setError(null);
      setConflict(false);
    },
    onError: (cause) => setError(friendlyApiMessage(cause)),
  });

  const optionalSlots = useMemo(
    () =>
      plan?.plan.slots.filter(
        (slot) => slot.decision.applicability === "OPTIONAL",
      ) ?? [],
    [plan],
  );

  const unresolved = useMemo(
    () =>
      Array.from(
        new Set(
          plan?.plan.slots.flatMap(
            (slot) => slot.decision.unresolved_rule_ids ?? [],
          ) ?? [],
        ),
      ).sort(),
    [plan],
  );

  const missingElectionIdentity = optionalSlots.some((slot) => !slot.slot_key);
  const allElectionsAnswered =
    !missingElectionIdentity &&
    optionalSlots.every(
      (slot) =>
        slot.slot_key !== undefined && Object.hasOwn(elections, slot.slot_key),
    );

  const confirm = useMutation({
    mutationFn: async () => {
      if (!etag) throw new Error("Reload the evaluation before confirmation.");
      if (!plan?.confirmable) {
        throw new Error("Applicability is not confirmable.");
      }
      if (!allElectionsAnswered) {
        throw new Error("Every optional test must have an explicit election.");
      }
      return confirmApplicability(sessionId, elections, etag);
    },
    onSuccess: async () => {
      setError(null);
      setConflict(false);
      await onChanged();
    },
    onError: (cause) => {
      if (
        cause instanceof ApiError &&
        (cause.status === 412 || cause.code === "VERSION_CONFLICT")
      ) {
        setConflict(true);
      }
      setError(friendlyApiMessage(cause));
    },
  });

  if (!canExecute) return null;

  return (
    <section className="evaluation-card">
      <div className="panel-heading-row">
        <div className="panel-heading">
          <p className="page-eyebrow">Server-derived plan</p>
          <h2>Applicability</h2>
        </div>
        <button
          className="button button-secondary"
          type="button"
          disabled={calculate.isPending}
          onClick={() => calculate.mutate()}
        >
          {calculate.isPending ? "Checking…" : "Check applicability"}
        </button>
      </div>

      {!plan ? (
        <p className="muted-copy">
          Load the backend applicability plan after confirming the instrument
          snapshot. Unknown facts remain review-required; the UI does not infer
          N/A.
        </p>
      ) : (
        <>
          <div className="applicability-summary">
            <span>
              {plan.plan.slots.length} planned test slot
              {plan.plan.slots.length === 1 ? "" : "s"}
            </span>
            <StatusBadge
              value={plan.confirmable ? "CONFIRMABLE" : "REVIEW_REQUIRED"}
            />
          </div>

          <div className="applicability-list">
            {plan.plan.slots.map((slot, index) => (
              <div
                className="applicability-row"
                key={`${slot.section_number}-${slot.test_code}-${slot.range_no ?? "all"}-${slot.scenario}-${index}`}
              >
                <div>
                  <strong>
                    Section {slot.section_number} · {slot.test_code}
                  </strong>
                  <span>
                    {slot.scenario} · {slot.procedure_variant}
                    {slot.range_no ? ` · range ${slot.range_no}` : ""}
                  </span>
                  <small>{slot.decision.reason}</small>
                </div>
                <div className="applicability-action">
                  <StatusBadge value={slot.decision.applicability} />
                  {slot.decision.applicability === "OPTIONAL" ? (
                    slot.slot_key ? (
                      <select
                        aria-label={`Election for ${slot.test_code}`}
                        value={
                          Object.hasOwn(elections, slot.slot_key)
                            ? elections[slot.slot_key]
                              ? "yes"
                              : "no"
                            : ""
                        }
                        onChange={(event) =>
                          setElections((current) => ({
                            ...current,
                            [slot.slot_key!]: event.target.value === "yes",
                          }))
                        }
                      >
                        <option value="">Choose…</option>
                        <option value="yes">Elect test</option>
                        <option value="no">Do not elect</option>
                      </select>
                    ) : (
                      <span className="slot-identity-warning">
                        Election identity unavailable
                      </span>
                    )
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          {unresolved.length > 0 ? (
            <RegulatoryBlocker ruleIds={unresolved} />
          ) : null}

          {missingElectionIdentity ? (
            <div className="information-banner">
              <strong>Optional election cannot be submitted safely.</strong>
              <span>
                The current API response does not expose the backend semantic
                slot key. The frontend will not recreate canonical regulatory
                identity logic.
              </span>
            </div>
          ) : null}

          {conflict ? (
            <div className="conflict-banner">
              <strong>Source changed.</strong>
              <span>
                Another update changed this evaluation. Reload before
                continuing; the frontend will not overwrite a 412 conflict.
              </span>
            </div>
          ) : null}

          {error ? <div className="form-alert">{error}</div> : null}

          {workflowStatus === "INSTRUMENT_CONFIGURATION" ? (
            <div className="form-actions">
              <button
                className="button button-primary"
                type="button"
                disabled={
                  confirm.isPending ||
                  !plan.confirmable ||
                  !allElectionsAnswered ||
                  missingElectionIdentity
                }
                onClick={() => confirm.mutate()}
              >
                {confirm.isPending ? "Confirming…" : "Confirm applicability"}
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
