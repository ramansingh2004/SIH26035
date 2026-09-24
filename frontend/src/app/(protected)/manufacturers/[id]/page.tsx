"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { EvidenceUploader } from "@/components/evidence/evidence-uploader";
import { ArchiveAction } from "@/components/master-data/archive-action";
import { DetailList } from "@/components/master-data/detail-list";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { archiveManufacturer, manufacturerDetail } from "@/lib/master-data/api";

export default function ManufacturerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const query = useQuery({
    queryKey: ["manufacturer", id],
    queryFn: () => manufacturerDetail(id),
  });

  if (query.isPending) return <LoadingState label="Loading manufacturer" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const item = query.data.item;
  const resourceEtag = query.data.etag;
  const address = [
    item.address.address_line1,
    item.address.address_line2,
    item.address.city,
    item.address.state,
    item.address.postal_code,
    item.address.country,
  ]
    .filter(Boolean)
    .join(", ");

  async function archive(reason: string) {
    if (!resourceEtag) throw new Error("Reload before archiving.");
    await archiveManufacturer(id, reason, resourceEtag);
    await queryClient.invalidateQueries({ queryKey: ["manufacturer", id] });
    await queryClient.invalidateQueries({ queryKey: ["manufacturers"] });
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Manufacturer"
        title={item.name}
        description="Laboratory-owned manufacturer master record."
        actions={
          <div className="page-actions">
            <StatusBadge value={item.is_active ? "ACTIVE" : "ARCHIVED"} />
            {item.is_active && hasPermission("manufacturer:update") ? (
              <Link
                className="button button-secondary"
                href={`/manufacturers/${id}/edit`}
              >
                Edit
              </Link>
            ) : null}
          </div>
        }
      />

      <section className="detail-card">
        <h2>Manufacturer information</h2>
        <DetailList
          items={[
            {
              label: "Registration number",
              value: item.registration_no ?? "—",
            },
            { label: "Country", value: item.country ?? "—" },
            { label: "Contact person", value: item.contact_person ?? "—" },
            { label: "Email", value: item.email ?? "—" },
            { label: "Phone", value: item.phone ?? "—" },
            { label: "Address", value: address || "—" },
            { label: "Record version", value: item.lock_version },
            {
              label: "Updated",
              value: new Date(item.updated_at).toLocaleString(),
            },
          ]}
        />
      </section>

      {item.is_active && hasPermission("attachment:create") ? (
        <EvidenceUploader
          laboratoryId={item.laboratory_id}
          entityType="manufacturers"
          entityId={item.id}
          targetEtag={resourceEtag}
          defaultPurpose="manufacturer_document"
          onTargetChanged={() =>
            void queryClient.invalidateQueries({
              queryKey: ["manufacturer", id],
            })
          }
        />
      ) : null}

      {item.is_active && hasPermission("manufacturer:archive") ? (
        <ArchiveAction label="manufacturer" onArchive={archive} />
      ) : null}
    </div>
  );
}
