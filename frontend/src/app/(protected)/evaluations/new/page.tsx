"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { createEvaluation, listRulesets } from "@/lib/evaluations/api";
import { listInstruments } from "@/lib/master-data/api";

export default function NewEvaluationPage() {
  const router = useRouter();
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [instrumentId, setInstrumentId] = useState("");
  const [rulesetId, setRulesetId] = useState("");
  const [evaluationContext, setEvaluationContext] = useState("");
  const [applicationNumber, setApplicationNumber] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const instruments = useQuery({
    queryKey: ["evaluation-create-instruments", selectedLaboratoryId],
    queryFn: async () => {
      const output = [];
      let page = 1;
      while (true) {
        const result = await listInstruments({
          laboratoryId: selectedLaboratoryId!,
          page,
          pageSize: 100,
          status: "ACTIVE",
        });
        output.push(...result.items);
        if (page * result.page_size >= result.total) break;
        page += 1;
      }
      return output;
    },
    enabled: Boolean(selectedLaboratoryId && hasPermission("instrument:read")),
  });

  const rulesets = useQuery({
    queryKey: ["rulesets", "evaluation-create"],
    queryFn: listRulesets,
    enabled: hasPermission("ruleset:read"),
  });

  const availableRulesets = useMemo(
    () =>
      (rulesets.data ?? []).filter(
        (ruleset) => ruleset.ruleset_status !== "RETIRED",
      ),
    [rulesets.data],
  );

  const selectedRuleset = availableRulesets.find(
    (ruleset) => ruleset.id === rulesetId,
  );

  const mutation = useMutation({
    mutationFn: createEvaluation,
  });

  if (!selectedLaboratoryId || !hasPermission("session:create")) {
    return (
      <div className="page-stack">
        <PageHeader eyebrow="Evaluation workspace" title="New evaluation" />
        <div className="form-alert">
          You do not have permission to create an evaluation in this laboratory.
        </div>
      </div>
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = await mutation.mutateAsync({
        instrument_id: instrumentId,
        rule_set_id: rulesetId,
        evaluation_context: evaluationContext.trim(),
        application_number: applicationNumber.trim() || null,
        notes: notes.trim() || null,
      });
      router.push(`/evaluations/${result.item.id}`);
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Evaluation workspace"
        title="New evaluation"
        description="Create a session that pins the current instrument and ruleset snapshots. Creating a session does not imply regulatory confirmation."
      />

      <form className="form-card" onSubmit={submit}>
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Evaluation identity</h2>
          </div>
          <div className="form-grid">
            <label className="form-field form-span-2">
              <span>Instrument *</span>
              <select
                required
                value={instrumentId}
                onChange={(event) => setInstrumentId(event.target.value)}
              >
                <option value="">Select active instrument</option>
                {(instruments.data ?? []).map((instrument) => (
                  <option key={instrument.id} value={instrument.id}>
                    {instrument.model_name} · Class {instrument.accuracy_class}{" "}
                    · Max {instrument.max_capacity_g} g
                  </option>
                ))}
              </select>
            </label>

            <label className="form-field form-span-2">
              <span>Ruleset *</span>
              <select
                required
                value={rulesetId}
                onChange={(event) => setRulesetId(event.target.value)}
              >
                <option value="">Select registered ruleset</option>
                {availableRulesets.map((ruleset) => (
                  <option key={ruleset.id} value={ruleset.id}>
                    {ruleset.standard_code} · {ruleset.edition} ·{" "}
                    {ruleset.version} · {ruleset.ruleset_status}
                  </option>
                ))}
              </select>
            </label>

            <label className="form-field">
              <span>Evaluation context *</span>
              <input
                required
                maxLength={100}
                value={evaluationContext}
                onChange={(event) => setEvaluationContext(event.target.value)}
                placeholder="e.g. type evaluation"
              />
            </label>

            <label className="form-field">
              <span>Application number</span>
              <input
                maxLength={200}
                value={applicationNumber}
                onChange={(event) => setApplicationNumber(event.target.value)}
              />
            </label>

            <label className="form-field form-span-2">
              <span>Notes</span>
              <textarea
                rows={4}
                maxLength={4000}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
          </div>
        </section>

        {selectedRuleset?.ruleset_status !== "ACTIVE" && selectedRuleset ? (
          <div className="information-banner">
            <strong>
              Selected ruleset is {selectedRuleset.ruleset_status}.
            </strong>
            <span>
              A draft session may be created for preparation, but authoritative
              applicability confirmation remains gated by the backend until the
              ruleset is ACTIVE and its required regulatory dependencies are
              verified.
            </span>
          </div>
        ) : null}

        {selectedRuleset ? (
          <div className="ruleset-selection-summary">
            <span>{selectedRuleset.standard_name}</span>
            <StatusBadge value={selectedRuleset.ruleset_status} />
          </div>
        ) : null}

        {error ? <div className="form-alert">{error}</div> : null}

        <div className="form-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => router.back()}
          >
            Cancel
          </button>
          <button
            className="button button-primary"
            type="submit"
            disabled={
              mutation.isPending ||
              !instrumentId ||
              !rulesetId ||
              !evaluationContext.trim()
            }
          >
            {mutation.isPending ? "Creating…" : "Create evaluation"}
          </button>
        </div>
      </form>
    </div>
  );
}
