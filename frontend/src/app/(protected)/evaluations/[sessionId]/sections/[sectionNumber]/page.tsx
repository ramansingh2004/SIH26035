"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ChecklistWorkspace } from "@/components/evaluations/checklist-workspace";
import { ConstructionWorkspace } from "@/components/evaluations/construction-workspace";
import { ExaminationStartGate } from "@/components/evaluations/examination-start-gate";
import { SectionNavigator } from "@/components/evaluations/section-navigator";
import { StatusAxes } from "@/components/evaluations/status-axes";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { evaluationDashboard } from "@/lib/evaluations/api";

export default function EvaluationSectionPage() {
  const { sessionId, sectionNumber } = useParams<{
    sessionId: string;
    sectionNumber: string;
  }>();
  const number = Number.parseInt(sectionNumber, 10);
  const query = useQuery({
    queryKey: ["evaluation-dashboard", sessionId],
    queryFn: () => evaluationDashboard(sessionId),
  });

  if (query.isPending) return <LoadingState label="Loading section" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const section = query.data.sections.find(
    (item) => item.section_number === number,
  );
  if (!section) {
    return (
      <EmptyState
        title="Section not found"
        description="This evaluation does not contain the requested section."
      />
    );
  }

  const requirements = query.data.requirements.filter(
    (item) => item.session_section_id === section.id,
  );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={`OIML R76 · Section ${section.section_number}`}
        title={section.name}
        description={section.applicability_reason}
        actions={
          <Link
            className="button button-secondary"
            href={`/evaluations/${sessionId}`}
          >
            Back to workspace
          </Link>
        }
      />

      <StatusAxes
        workflow={query.data.session.workflow_status}
        evaluation={section.evaluation_status}
        outcome={section.compliance_outcome}
      />

      <div className="evaluation-workspace-grid">
        <aside className="evaluation-sections-panel">
          <SectionNavigator
            sessionId={sessionId}
            sections={query.data.sections}
          />
        </aside>

        <div className="evaluation-main-column">
          <section className="evaluation-card">
            <div className="panel-heading">
              <p className="page-eyebrow">Server status</p>
              <h2>Section applicability</h2>
            </div>
            <div className="section-applicability">
              <StatusBadge value={section.applicability_status} />
              <p>{section.applicability_reason}</p>
            </div>
          </section>

          {number === 16 ? (
            <ExaminationStartGate sessionId={sessionId}>
              <ConstructionWorkspace sessionId={sessionId} />
            </ExaminationStartGate>
          ) : number === 17 ? (
            <ExaminationStartGate sessionId={sessionId}>
              <ChecklistWorkspace sessionId={sessionId} />
            </ExaminationStartGate>
          ) : (
            <section className="evaluation-card">
              <div className="panel-heading">
                <p className="page-eyebrow">Planned work</p>
                <h2>Requirements</h2>
              </div>
              {requirements.length === 0 ? (
                <EmptyState
                  title="No confirmed requirements yet"
                  description="Requirements are created by the backend after authoritative applicability confirmation."
                />
              ) : (
                <div className="requirement-list">
                  {requirements.map((requirement) => (
                    <div className="requirement-row" key={requirement.id}>
                      <div>
                        <strong>{requirement.requirement_key}</strong>
                        <span>{requirement.applicability_reason}</span>
                      </div>
                      <div className="requirement-status">
                        <StatusBadge value={requirement.applicability_status} />
                        {requirement.selected_run_id ? (
                          <Link
                            className="button button-primary button-compact"
                            href={`/evaluations/${sessionId}/runs/${requirement.selected_run_id}`}
                          >
                            Open selected run
                          </Link>
                        ) : (
                          <span className="selected-run-note">
                            No selected run
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
