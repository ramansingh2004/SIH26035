import type { FormEvent } from "react";

export function ListToolbar({
  search,
  onSearch,
  onSubmit,
  children,
}: {
  search: string;
  onSearch: (value: string) => void;
  onSubmit: () => void;
  children?: React.ReactNode;
}) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="master-toolbar" onSubmit={submit}>
      <label>
        <span className="sr-only">Search</span>
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search records…"
        />
      </label>
      {children}
      <button className="button button-secondary" type="submit">
        Apply
      </button>
    </form>
  );
}
