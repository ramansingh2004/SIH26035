"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="standalone-state">
      <p className="page-eyebrow">Application error</p>
      <h1>This view could not be rendered</h1>
      <p>
        No regulatory action has been assumed successful. Reload the current
        server state before continuing.
      </p>
      <button className="button button-primary" type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
