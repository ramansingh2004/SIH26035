"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { EvidenceUploader } from "@/components/evidence/evidence-uploader";
import { ArchiveAction } from "@/components/master-data/archive-action";
import { DetailList } from "@/components/master-data/detail-list";
import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import { archiveEquipment, equipmentDetail } from "@/lib/master-data/api";

export default function EquipmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const query = useQuery({
    queryKey: ["equipment-detail", id],
    queryFn: () => equipmentDetail(id),
  });

  if (query.isPending) return <LoadingState label="Loading equipment" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const item = query.data.item;
  const resourceEtag = query.data.etag;

  async function archive(reason: string) {
    if (!resourceEtag) throw new Error("Reload before archiving.");
    await archiveEquipment(id, reason, resourceEtag);
    await queryClient.invalidateQueries({ queryKey: ["equipment-detail", id] });
    await queryClient.invalidateQueries({ queryKey: ["equipment"] });
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Test equipment"
        title={item.reference_number ?? item.model ?? item.category}
        description={item.category}
        actions={
          <div className="page-actions">
            <StatusBadge value={item.is_active ? "ACTIVE" : "ARCHIVED"} />
            {item.is_active && hasPermission("equipment:update") ? (
              <Link
                className="button button-secondary"
                href={`/equipment/${id}/edit`}
              >
                Edit
              </Link>
            ) : null}
          </div>
        }
      />

      <div className="detail-grid">
        <section className="detail-card">
          <h2>Equipment identity</h2>
          <DetailList
            items={[
              { label: "Category", value: item.category },
              { label: "Manufacturer", value: item.manufacturer ?? "—" },
              { label: "Model", value: item.model ?? "—" },
              { label: "Serial number", value: item.serial_number ?? "—" },
              {
                label: "Reference number",
                value: item.reference_number ?? "—",
              },
              {
                label: "Accuracy / class",
                value: item.accuracy_or_class ?? "—",
              },
            ]}
          />
        </section>

        <section className="detail-card">
          <h2>Calibration facts</h2>
          <DetailList
            items={[
              {
                label: "Certificate",
                value: item.calibration_certificate_no ?? "—",
              },
              {
                label: "Calibration date",
                value: item.calibration_date ?? "—",
              },
              { label: "Due date", value: item.calibration_due_date ?? "—" },
              {
                label: "Nominal mass",
                value: item.metadata_json?.nominal_mass_g
                  ? `${item.metadata_json.nominal_mass_g} g`
                  : "—",
              },
              {
                label: "Certificate reference",
                value: item.metadata_json?.certificate_reference ?? "—",
              },
              { label: "Notes", value: item.metadata_json?.notes ?? "—" },
            ]}
          />
        </section>
      </div>

      <RegulatoryBlocker ruleIds={[]} />
      <p className="detail-note">
        Equipment master facts do not independently establish calibration
        acceptance for a specific measurement.
      </p>

      {item.is_active && hasPermission("attachment:create") ? (
        <EvidenceUploader
          laboratoryId={item.laboratory_id}
          entityType="test_equipment"
          entityId={item.id}
          targetEtag={resourceEtag}
          defaultPurpose="calibration"
          onTargetChanged={() =>
            void queryClient.invalidateQueries({
              queryKey: ["equipment-detail", id],
            })
          }
        />
      ) : null}

      {item.is_active && hasPermission("equipment:archive") ? (
        <ArchiveAction label="equipment" onArchive={archive} />
      ) : null}
    </div>
  );
}
