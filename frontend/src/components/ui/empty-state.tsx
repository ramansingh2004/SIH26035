import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-state-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M5.5 7.5h13v10h-13z" />
          <path d="M8 4.5h8M9 11h6M9 14h4" />
        </svg>
      </span>
      <div className="empty-state-copy">
        <strong>{title}</strong>
        <p>{description}</p>
        {action ? <div className="empty-state-actions">{action}</div> : null}
      </div>
    </div>
  );
}
