import { friendlyApiMessage } from "@/lib/api/errors";

export function ErrorState({
  error,
  title = "Unable to load this view",
  onRetry,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state-panel state-panel-error" role="alert">
      <div>
        <strong>{title}</strong>
        <p>{friendlyApiMessage(error)}</p>
        {onRetry ? (
          <button
            className="button button-secondary"
            type="button"
            onClick={onRetry}
          >
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
