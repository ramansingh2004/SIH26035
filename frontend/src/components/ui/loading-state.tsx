export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div
      className="state-panel loading-state"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="loading-state-heading">
        <span className="loading-spinner" aria-hidden="true" />
        <div>
          <strong>{label}</strong>
          <p>Please wait while the current server state is retrieved.</p>
        </div>
      </div>
      <div className="loading-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}
