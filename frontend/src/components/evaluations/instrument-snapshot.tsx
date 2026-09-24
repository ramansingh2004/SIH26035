import { DetailList } from "@/components/master-data/detail-list";
import type { InstrumentSnapshot } from "@/lib/evaluations/types";

function fact(value: boolean | null | undefined) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Unknown";
}

export function InstrumentSnapshotPanel({
  snapshot,
}: {
  snapshot: InstrumentSnapshot;
}) {
  return (
    <section className="evaluation-card">
      <div className="panel-heading">
        <p className="page-eyebrow">Frozen session input</p>
        <h2>Instrument snapshot</h2>
      </div>
      <DetailList
        items={[
          { label: "Accuracy class", value: snapshot.accuracy_class },
          {
            label: "Maximum capacity",
            value: `${snapshot.max_capacity_g} g`,
          },
          {
            label: "Minimum capacity",
            value: snapshot.min_capacity_g
              ? `${snapshot.min_capacity_g} g`
              : "Unknown",
          },
          {
            label: "Scale interval d",
            value: `${snapshot.scale_interval_d_g} g`,
          },
          {
            label: "Verification interval e",
            value: `${snapshot.verification_interval_e_g} g`,
          },
          { label: "Range count", value: snapshot.ranges.length },
          {
            label: "Electronic",
            value: fact(snapshot.is_electronic),
          },
          {
            label: "Software controlled",
            value: fact(snapshot.is_software_controlled),
          },
        ]}
      />
      <p className="detail-note">
        The browser displays the snapshot returned by the backend. It does not
        recompute capacities, applicability, limits or compliance.
      </p>
    </section>
  );
}
