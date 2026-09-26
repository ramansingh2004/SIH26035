"use client";

import { type FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Pagination } from "@/components/master-data/pagination";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import {
  listAuditEvents,
  listAuditLaboratories,
} from "@/lib/admin-audit/api";
import type {
  AuditFilters,
  AuditEventView,
} from "@/lib/admin-audit/types";
import { useAuth } from "@/lib/auth/auth-context";

const EMPTY_FILTERS: AuditFilters = {
  laboratoryId: "",
  entityType: "",
  entityId: "",
  since: "",
  until: "",
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function shortId(value: string | null): string {
  if (!value) return "—";
  return value;
}

function prettyJson(value: Record<string, unknown> | null): string {
  if (!value) return "Not recorded";
  return JSON.stringify(value, null, 2);
}

function revisionLabel(event: AuditEventView): string {
  if (
    event.source_revision === null &&
    event.target_revision === null
  ) {
    return "—";
  }

  return `${event.source_revision ?? "—"} → ${event.target_revision ?? "—"}`;
}

export default function AdminAuditPage() {
  const { user, hasPermission } = useAuth();
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<AuditFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [filterError, setFilterError] = useState<string | null>(null);

  const canRead = hasPermission("audit:read");
  const hasGlobalAudit = Boolean(
    user?.global_permissions.includes("audit:read"),
  );

  const laboratories = useQuery({
    queryKey: ["admin-audit", "laboratories"],
    queryFn: listAuditLaboratories,
    enabled: canRead,
    staleTime: 5 * 60_000,
  });

  const events = useQuery({
    queryKey: ["admin-audit", "events", page, filters],
    queryFn: () =>
      listAuditEvents({
        page,
        filters,
      }),
    enabled: canRead,
  });

  const laboratoryById = useMemo(
    () =>
      new Map(
        (laboratories.data ?? []).map((laboratory) => [
          laboratory.id,
          laboratory,
        ]),
      ),
    [laboratories.data],
  );

  function updateDraft<K extends keyof AuditFilters>(
    key: K,
    value: AuditFilters[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilterError(null);

    const entityId = draft.entityId.trim();
    if (entityId && !UUID_PATTERN.test(entityId)) {
      setFilterError("Entity ID must be a valid UUID.");
      return;
    }

    if (draft.since && draft.until) {
      const since = new Date(draft.since);
      const until = new Date(draft.until);

      if (Number.isNaN(since.valueOf()) || Number.isNaN(until.valueOf())) {
        setFilterError("Enter a valid date and time range.");
        return;
      }

      if (since > until) {
        setFilterError("From date/time must be before To date/time.");
        return;
      }
    }

    setPage(1);
    setFilters({
      laboratoryId: draft.laboratoryId,
      entityType: draft.entityType.trim(),
      entityId,
      since: draft.since,
      until: draft.until,
    });
  }

  function clearFilters() {
    setFilterError(null);
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setPage(1);
  }

  if (!canRead) {
    return (
      <div className="page-stack">
        <PageHeader title="Audit Events" eyebrow="Administration" />
        <EmptyState
          title="No audit access"
          description="Your current authorization scope does not grant audit:read."
        />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Audit Events"
        description="Read-only append-only traceability for authenticated actions, administrative changes and governed workflow events visible to your authorization scope."
      />

      <div className="information-banner">
        <strong>Audit history is observational.</strong>
        <span>
          This screen reads backend audit records only. It does not edit,
          delete, recalculate or replay the actions represented by those
          records.
        </span>
      </div>

      <form className="audit-filter-card" onSubmit={applyFilters}>
        <div className="audit-filter-grid">
          <label className="form-field">
            <span>Laboratory</span>
            <select
              value={draft.laboratoryId}
              onChange={(event) =>
                updateDraft("laboratoryId", event.target.value)
              }
              disabled={laboratories.isPending}
            >
              <option value="">
                {hasGlobalAudit
                  ? "All laboratories / global events"
                  : "All authorized laboratories"}
              </option>
              {(laboratories.data ?? []).map((laboratory) => (
                <option key={laboratory.id} value={laboratory.id}>
                  {laboratory.name} ({laboratory.code})
                  {laboratory.is_active ? "" : " — inactive"}
                </option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span>Entity type</span>
            <input
              value={draft.entityType}
              onChange={(event) =>
                updateDraft("entityType", event.target.value)
              }
              maxLength={80}
              placeholder="e.g. users, test_sessions"
            />
          </label>

          <label className="form-field">
            <span>Entity ID</span>
            <input
              value={draft.entityId}
              onChange={(event) =>
                updateDraft("entityId", event.target.value)
              }
              placeholder="UUID"
            />
          </label>

          <label className="form-field">
            <span>From</span>
            <input
              type="datetime-local"
              value={draft.since}
              onChange={(event) =>
                updateDraft("since", event.target.value)
              }
            />
          </label>

          <label className="form-field">
            <span>To</span>
            <input
              type="datetime-local"
              value={draft.until}
              onChange={(event) =>
                updateDraft("until", event.target.value)
              }
            />
          </label>
        </div>

        {filterError ? (
          <div className="form-alert" role="alert">
            {filterError}
          </div>
        ) : null}

        <div className="audit-filter-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={clearFilters}
          >
            Clear filters
          </button>
          <button className="button button-primary" type="submit">
            Apply filters
          </button>
        </div>
      </form>

      {laboratories.isError ? (
        <ErrorState
          title="Unable to load laboratory labels"
          error={laboratories.error}
          onRetry={() => void laboratories.refetch()}
        />
      ) : null}

      {events.isPending ? (
        <LoadingState label="Loading audit events" />
      ) : events.isError ? (
        <ErrorState
          error={events.error}
          onRetry={() => void events.refetch()}
        />
      ) : events.data.items.length === 0 ? (
        <EmptyState
          title="No audit events found"
          description="No visible audit events match the current backend filters."
        />
      ) : (
        <section className="data-card">
          <div className="table-scroll">
            <table className="data-table audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Entity</th>
                  <th>Laboratory</th>
                  <th>Revision</th>
                  <th>Trace</th>
                </tr>
              </thead>
              <tbody>
                {events.data.items.map((event) => {
                  const laboratory = event.laboratory_id
                    ? laboratoryById.get(event.laboratory_id)
                    : null;

                  return (
                    <tr key={event.id}>
                      <td className="audit-time">
                        {formatDate(event.created_at)}
                      </td>
                      <td>
                        <strong className="audit-action">
                          {event.action}
                        </strong>
                        {event.reason ? (
                          <span className="admin-user-secondary">
                            {event.reason}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <strong>{event.actor_type}</strong>
                        <span className="admin-user-secondary audit-id">
                          {shortId(event.actor_id)}
                        </span>
                      </td>
                      <td>
                        <strong>{event.entity_type}</strong>
                        <span className="admin-user-secondary audit-id">
                          {shortId(event.entity_id)}
                        </span>
                      </td>
                      <td>
                        {event.laboratory_id
                          ? laboratory
                            ? `${laboratory.name} (${laboratory.code})`
                            : event.laboratory_id
                          : "Global / unscoped"}
                      </td>
                      <td>{revisionLabel(event)}</td>
                      <td>
                        <details className="audit-trace">
                          <summary>Inspect</summary>
                          <div className="audit-trace-body">
                            <dl className="audit-trace-meta">
                              <div>
                                <dt>Audit event ID</dt>
                                <dd>{event.id}</dd>
                              </div>
                              <div>
                                <dt>Request ID</dt>
                                <dd>{event.request_id}</dd>
                              </div>
                              <div>
                                <dt>Correlation ID</dt>
                                <dd>{event.correlation_id}</dd>
                              </div>
                              <div>
                                <dt>IP address</dt>
                                <dd>{event.ip_address ?? "Not recorded"}</dd>
                              </div>
                              <div>
                                <dt>User agent</dt>
                                <dd>{event.user_agent ?? "Not recorded"}</dd>
                              </div>
                            </dl>

                            <div className="audit-json-grid">
                              <div className="audit-json-block">
                                <strong>Before</strong>
                                <pre>{prettyJson(event.before_json)}</pre>
                              </div>
                              <div className="audit-json-block">
                                <strong>After</strong>
                                <pre>{prettyJson(event.after_json)}</pre>
                              </div>
                            </div>
                          </div>
                        </details>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <Pagination
            page={events.data.page}
            pageSize={events.data.page_size}
            total={events.data.total}
            onPage={setPage}
          />
        </section>
      )}
    </div>
  );
}
