"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { evaluationDetail } from "@/lib/evaluations/api";
import { startExamination } from "@/lib/evaluations/special-api";

export function ExaminationStartGate({
  sessionId,
  children,
}: {
  sessionId: string;
  children: React.ReactNode;
}) {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const detail = useQuery({
    queryKey: ["evaluation", sessionId],
    queryFn: () => evaluationDetail(sessionId),
  });
  const mutation = useMutation({
    mutationFn: async () => {
      if (!detail.data?.etag)
        throw new Error("Reload before starting examination.");
      return startExamination(sessionId, detail.data.etag);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] }),
        queryClient.invalidateQueries({
          queryKey: ["evaluation-dashboard", sessionId],
        }),
      ]);
    },
  });

  if (detail.isPending)
    return <LoadingState label="Loading examination state" />;
  if (detail.isError) return <ErrorState error={detail.error} />;

  const workflow = detail.data.item.workflow_status;
  if (workflow === "TESTING") {
    return (
      <section className="run-panel">
        <div className="panel-heading">
          <p className="page-eyebrow">Examination transition</p>
          <h2>Start Sections 16–17 examination</h2>
          <p>
            This changes the workflow to EXAMINATION and initializes the pinned
            construction/checklist catalogues. It does not approve a result.
          </p>
        </div>
        {mutation.isError ? (
          <div className="form-alert">{friendlyApiMessage(mutation.error)}</div>
        ) : null}
        <button
          className="button button-primary"
          type="button"
          disabled={!hasPermission("construction:update") || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "Starting examination…" : "Start examination"}
        </button>
      </section>
    );
  }

  if (
    workflow === "DRAFT" ||
    workflow === "INSTRUMENT_CONFIGURATION" ||
    workflow === "APPLICABILITY_CONFIRMED"
  ) {
    return (
      <section className="run-panel">
        <div className="information-banner">
          <strong>Examination is not available yet.</strong>
          <span>The evaluation must first enter TESTING.</span>
        </div>
      </section>
    );
  }

  return <>{children}</>;
}
