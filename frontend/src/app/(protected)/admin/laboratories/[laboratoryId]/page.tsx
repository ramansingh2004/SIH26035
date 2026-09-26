"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { DetailList } from "@/components/master-data/detail-list";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { laboratoryDetail } from "@/lib/admin-laboratories/api";
import { useAuth } from "@/lib/auth/auth-context";

export default function LaboratoryDetailPage() {
  const { laboratoryId } = useParams<{ laboratoryId: string }>();
  const { user } = useAuth();

  const globalRead = Boolean(
    user?.global_permissions.includes("laboratory:read"),
  );
  const laboratoryGrant = user?.laboratories.find(
    (grant) => grant.laboratory_id === laboratoryId,
  );
  const canRead = Boolean(
    globalRead ||
      laboratoryGrant?.permissions.includes("laboratory:read"),
  );
  const canUpdate = Boolean(
    user?.global_permissions.includes("laboratory:update") ||
      laboratoryGrant?.permissions.includes("laboratory:update"),
  );

  const query = useQuery({
    queryKey: ["admin-laboratory", laboratoryId],
    queryFn: () => laboratoryDetail(laboratoryId),
    enabled: canRead,
  });

  if (!canRead) {
    return (
      <div className="page-stack">
        <PageHeader title="Laboratory" eyebrow="Administration" />
        <EmptyState
          title="No laboratory access"
          description="Your account cannot read this laboratory scope."
        />
      </div>
    );
  }

  if (query.isPending) {
    return <LoadingState label="Loading laboratory" />;
  }
  if (query.isError) return <ErrorState error={query.error} />;

  const item = query.data.item;
  const address = [
    item.address_line1,
    item.address_line2,
    item.city,
    item.state,
    item.postal_code,
    item.country,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration · Laboratory"
        title={item.name}
        description={`Controlled laboratory scope ${item.code}.`}
        actions={
          <div className="page-actions">
            <StatusBadge value={item.is_active ? "ACTIVE" : "INACTIVE"} />
            {canUpdate ? (
              <Link
                className="button button-secondary"
                href={`/admin/laboratories/${item.id}/edit`}
              >
                Edit
              </Link>
            ) : null}
          </div>
        }
      />

      {!item.is_active ? (
        <div className="validation-panel">
          This laboratory is inactive. Lab-scoped authorization grants are not
          effective while the laboratory remains inactive.
        </div>
      ) : null}

      <section className="detail-card">
        <h2>Laboratory identity</h2>
        <DetailList
          items={[
            { label: "Code", value: item.code },
            { label: "Accreditation number", value: item.accreditation_no },
            { label: "Timezone", value: item.timezone },
            { label: "Record version", value: item.lock_version },
            { label: "Address", value: address },
            { label: "Email", value: item.email },
            { label: "Phone", value: item.phone },
            {
              label: "Logo attachment",
              value: item.logo_attachment_id ?? "Not configured",
            },
          ]}
        />
      </section>

      <div className="information-banner">
        <strong>Administrative scope, not regulatory outcome.</strong>
        <span>
          Laboratory metadata controls ownership and authorization boundaries.
          Editing it does not recalculate or rewrite historical evaluation and
          report snapshots.
        </span>
      </div>
    </div>
  );
}
