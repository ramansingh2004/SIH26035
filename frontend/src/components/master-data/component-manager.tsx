"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { friendlyApiMessage } from "@/lib/api/errors";
import {
  archiveComponent,
  createComponent,
  listComponents,
  updateComponent,
} from "@/lib/master-data/api";
import {
  etagFromVersion,
  type ComponentData,
  type ComponentView,
} from "@/lib/master-data/types";

const empty: ComponentData = {
  component_type: "",
  manufacturer_name: null,
  model: null,
  serial_or_type: null,
  certificate_reference: null,
  technical_specifications: { schema_version: 1 },
  notes: null,
};

export function ComponentManager({
  instrumentId,
  canManage,
}: {
  instrumentId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ComponentData>(empty);
  const [editing, setEditing] = useState<ComponentView | null>(null);
  const [parentEtagOverride, setParentEtagOverride] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["instrument-components", instrumentId],
    queryFn: () => listComponents(instrumentId, true),
  });

  const parentEtag = parentEtagOverride ?? query.data?.etag ?? null;

  const save = useMutation({
    mutationFn: async () => {
      if (editing) {
        return updateComponent(
          instrumentId,
          editing.id,
          form,
          etagFromVersion(editing.lock_version),
        );
      }
      if (!parentEtag) {
        throw new Error("Reload the instrument before adding a component.");
      }
      return createComponent(instrumentId, form, parentEtag);
    },
    onSuccess: async (result) => {
      if (result.instrumentEtag) setParentEtagOverride(result.instrumentEtag);
      setEditing(null);
      setForm(empty);
      setError(null);
      await queryClient.invalidateQueries({
        queryKey: ["instrument-components", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument", instrumentId],
      });
    },
  });

  async function archive(item: ComponentView) {
    const reason = window.prompt("Reason for archiving this component:");
    if (!reason?.trim()) return;
    try {
      const instrumentEtag = await archiveComponent(
        instrumentId,
        item.id,
        reason.trim(),
        etagFromVersion(item.lock_version),
      );
      if (instrumentEtag) setParentEtagOverride(instrumentEtag);
      await queryClient.invalidateQueries({
        queryKey: ["instrument-components", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument", instrumentId],
      });
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  function edit(item: ComponentView) {
    setEditing(item);
    setForm({
      component_type: item.component_type,
      manufacturer_name: item.manufacturer_name ?? null,
      model: item.model ?? null,
      serial_or_type: item.serial_or_type ?? null,
      certificate_reference: item.certificate_reference ?? null,
      technical_specifications: item.technical_specifications ?? {
        schema_version: 1,
      },
      notes: item.notes ?? null,
    });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await save.mutateAsync();
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  return (
    <section className="detail-card detail-span-2">
      <h2>Instrument components</h2>
      <p className="detail-note">
        Component identity and technical declarations are master facts;
        historical session snapshots remain unchanged by later edits.
      </p>

      {canManage ? (
        <form className="inline-editor component-editor" onSubmit={submit}>
          <label>
            <span>Component type *</span>
            <input
              required
              value={form.component_type}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  component_type: event.target.value,
                }))
              }
            />
          </label>
          <label>
            <span>Manufacturer</span>
            <input
              value={form.manufacturer_name ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  manufacturer_name: event.target.value || null,
                }))
              }
            />
          </label>
          <label>
            <span>Model</span>
            <input
              value={form.model ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  model: event.target.value || null,
                }))
              }
            />
          </label>
          <label>
            <span>Serial / type</span>
            <input
              value={form.serial_or_type ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  serial_or_type: event.target.value || null,
                }))
              }
            />
          </label>
          <label>
            <span>Certificate reference</span>
            <input
              value={form.certificate_reference ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  certificate_reference: event.target.value || null,
                }))
              }
            />
          </label>
          <label>
            <span>Rated capacity (g)</span>
            <input
              inputMode="decimal"
              value={form.technical_specifications?.rated_capacity_g ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  technical_specifications: {
                    ...current.technical_specifications,
                    schema_version: 1,
                    rated_capacity_g: event.target.value || null,
                  },
                }))
              }
            />
          </label>
          <div className="inline-editor-actions">
            {editing ? (
              <button
                className="button button-secondary button-compact"
                type="button"
                onClick={() => {
                  setEditing(null);
                  setForm(empty);
                }}
              >
                Cancel edit
              </button>
            ) : null}
            <button
              className="button button-primary button-compact"
              type="submit"
              disabled={save.isPending}
            >
              {save.isPending
                ? "Saving…"
                : editing
                  ? "Update component"
                  : "Add component"}
            </button>
          </div>
        </form>
      ) : null}

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Manufacturer</th>
              <th>Model</th>
              <th>Serial / type</th>
              <th>Certificate</th>
              <th>Status</th>
              {canManage ? <th>Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {(query.data?.page.items ?? []).map((item) => (
              <tr key={item.id}>
                <td>{item.component_type}</td>
                <td>{item.manufacturer_name ?? "—"}</td>
                <td>{item.model ?? "—"}</td>
                <td>{item.serial_or_type ?? "—"}</td>
                <td>{item.certificate_reference ?? "—"}</td>
                <td>{item.is_active ? "Active" : "Archived"}</td>
                {canManage ? (
                  <td>
                    <div className="table-actions">
                      <button
                        className="button button-secondary button-compact"
                        type="button"
                        disabled={!item.is_active}
                        onClick={() => edit(item)}
                      >
                        Edit
                      </button>
                      <button
                        className="button button-secondary button-compact"
                        type="button"
                        disabled={!item.is_active}
                        onClick={() => void archive(item)}
                      >
                        Archive
                      </button>
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
            {query.data?.page.items.length === 0 ? (
              <tr>
                <td colSpan={canManage ? 7 : 6}>No components recorded.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
