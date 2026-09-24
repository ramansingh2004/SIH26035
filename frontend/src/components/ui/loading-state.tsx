export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <span className="loading-spinner" aria-hidden="true" />
      <div>
        <strong>{label}</strong>
        <p>Please wait while the current server state is retrieved.</p>
      </div>
    </div>
  );
}
