export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination" aria-label="Pagination">
      <span>
        Page {page} of {pages} · {total} record{total === 1 ? "" : "s"}
      </span>
      <div>
        <button
          className="button button-secondary button-compact"
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          Previous
        </button>
        <button
          className="button button-secondary button-compact"
          type="button"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
