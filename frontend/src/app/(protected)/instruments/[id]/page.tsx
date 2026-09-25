"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { EvidenceUploader } from "@/components/evidence/evidence-uploader";
import { ArchiveAction } from "@/components/master-data/archive-action";
import { ComponentManager } from "@/components/master-data/component-manager";
import { InstrumentHistoryPanel } from "@/components/master-data/instrument-history-panel";
import { DetailList } from "@/components/master-data/detail-list";
import { RangeManager } from "@/components/master-data/range-manager";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth/auth-context";
import {
  allManufacturers,
  archiveInstrument,
  instrumentDetail,
} from "@/lib/master-data/api";

function fact(value: boolean | null | undefined) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Unknown";
}

export default function InstrumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();

  const query = useQuery({
    queryKey: ["instrument", id],
    queryFn: () => instrumentDetail(id),
  });

  const manufacturers = useQuery({
    queryKey: [
      "manufacturers",
      "instrument-detail",
      query.data?.item.laboratory_id,
    ],
    queryFn: () => allManufacturers(query.data!.item.laboratory_id),
    enabled: Boolean(query.data?.item.laboratory_id),
  });

  if (query.isPending) return <LoadingState label="Loading instrument" />;
  if (query.isError) return <ErrorState error={query.error} />;

  const item = query.data.item;
  const resourceEtag = query.data.etag;
  const manufacturer =
    manufacturers.data?.find((entry) => entry.id === item.manufacturer_id)
      ?.name ?? "Manufacturer record";

  async function archive(reason: string) {
    if (!resourceEtag) throw new Error("Reload before archiving.");
    await archiveInstrument(id, reason, resourceEtag);
    await queryClient.invalidateQueries({ queryKey: ["instrument", id] });
    await queryClient.invalidateQueries({ queryKey: ["instruments"] });
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Instrument"
        title={item.model_name}
        description={`${manufacturer} · ${item.type_designation ?? item.serial_number ?? "NAWI master record"}`}
        actions={
          <div className="page-actions">
            <StatusBadge value={item.instrument_status} />
            {item.instrument_status === "ACTIVE" &&
            hasPermission("instrument:update") ? (
              <Link
                className="button button-secondary"
                href={`/instruments/${id}/edit`}
              >
                Edit
              </Link>
            ) : null}
          </div>
        }
      />

      <div className="detail-grid">
        <section className="detail-card">
          <h2>Identification</h2>
          <DetailList
            items={[
              { label: "Manufacturer", value: manufacturer },
              { label: "Model", value: item.model_name },
              {
                label: "Type designation",
                value: item.type_designation ?? "—",
              },
              { label: "Serial number", value: item.serial_number ?? "—" },
              { label: "Accuracy class", value: item.accuracy_class },
              { label: "Record version", value: item.lock_version },
            ]}
          />
        </section>

        <section className="detail-card">
          <h2>Capacity</h2>
          <DetailList
            items={[
              {
                label: "Min",
                value: item.min_capacity_g
                  ? `${item.min_capacity_g} g`
                  : "Unknown",
              },
              { label: "Max", value: `${item.max_capacity_g} g` },
              { label: "d", value: `${item.scale_interval_d_g} g` },
              { label: "e", value: `${item.verification_interval_e_g} g` },
              { label: "n", value: item.verification_intervals_n },
              { label: "Range type", value: item.range_type ?? "—" },
            ]}
          />
        </section>

        <section className="detail-card detail-span-2">
          <h2>Declared applicability facts</h2>
          <DetailList
            items={[
              {
                label: "Self-indicating",
                value: fact(item.is_self_indicating),
              },
              { label: "Electronic", value: fact(item.is_electronic) },
              {
                label: "Software controlled",
                value: fact(item.is_software_controlled),
              },
              { label: "Portable", value: fact(item.is_portable) },
              { label: "Mobile", value: fact(item.is_mobile) },
              {
                label: "Direct sales",
                value: fact(item.metadata_json?.is_direct_sales),
              },
            ]}
          />
          <p className="detail-note">
            Unknown is intentionally preserved. This screen does not infer OIML
            applicability or compliance.
          </p>
        </section>

        <RangeManager
          instrumentId={id}
          canManage={
            item.instrument_status === "ACTIVE" &&
            hasPermission("instrument:manage_ranges")
          }
        />
        <ComponentManager
          instrumentId={id}
          canManage={
            item.instrument_status === "ACTIVE" &&
            hasPermission("instrument:manage_components")
          }
        />
      </div>

      <InstrumentHistoryPanel instrumentId={id} />

      {item.instrument_status === "ACTIVE" &&
      hasPermission("attachment:create") ? (
        <EvidenceUploader
          laboratoryId={item.laboratory_id}
          entityType="instruments"
          entityId={item.id}
          targetEtag={resourceEtag}
          defaultPurpose="technical_document"
          onTargetChanged={() =>
            void queryClient.invalidateQueries({ queryKey: ["instrument", id] })
          }
        />
      ) : null}

      {item.instrument_status === "ACTIVE" &&
      hasPermission("instrument:archive") ? (
        <ArchiveAction label="instrument" onArchive={archive} />
      ) : null}
    </div>
  );
}
