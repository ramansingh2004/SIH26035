import type { ReactNode } from "react";

export function DetailList({
  items,
}: {
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <dl className="detail-list">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
