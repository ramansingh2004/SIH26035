import Link from "next/link";

export default function NotFound() {
  return (
    <main className="standalone-state">
      <p className="page-eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The requested frontend route does not exist in the current phase.</p>
      <Link className="button button-primary" href="/dashboard">
        Return to dashboard
      </Link>
    </main>
  );
}
