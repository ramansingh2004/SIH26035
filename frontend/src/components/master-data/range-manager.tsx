"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { friendlyApiMessage } from "@/lib/api/errors";
import {
  archiveRange,
  createRange,
  listRanges,
  updateRange,
} from "@/lib/master-data/api";
import {
  etagFromVersion,
  type RangeData,
  type RangeView,
} from "@/lib/master-data/types";

const empty: RangeData = {
  range_no: 1,
  min_capacity_g: null,
  max_capacity_g: "",
  scale_interval_d_g: "",
  verification_interval_e_g: "",
};

export function RangeManager({
  instrumentId,
  canManage,
}: {
  instrumentId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<RangeData>(empty);
  const [editing, setEditing] = useState<RangeView | null>(null);
  const [parentEtagOverride, setParentEtagOverride] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["instrument-ranges", instrumentId],
    queryFn: () => listRanges(instrumentId, true),
  });

  const parentEtag = parentEtagOverride ?? query.data?.etag ?? null;

  const save = useMutation({
    mutationFn: async () => {
      if (editing) {
        return updateRange(
          instrumentId,
          editing.id,
          form,
          etagFromVersion(editing.lock_version),
        );
      }
      if (!parentEtag) {
        throw new Error("Reload the instrument before adding a range.");
      }
      return createRange(instrumentId, form, parentEtag);
    },
    onSuccess: async (result) => {
      if (result.instrumentEtag) setParentEtagOverride(result.instrumentEtag);
      setEditing(null);
      setForm(empty);
      setError(null);
      await queryClient.invalidateQueries({
        queryKey: ["instrument-ranges", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument", instrumentId],
      });
    },
  });

  async function archive(item: RangeView) {
    const reason = window.prompt("Reason for archiving this range:");
    if (!reason?.trim()) return;
    try {
      const instrumentEtag = await archiveRange(
        instrumentId,
        item.id,
        reason.trim(),
        etagFromVersion(item.lock_version),
      );
      if (instrumentEtag) setParentEtagOverride(instrumentEtag);
      await queryClient.invalidateQueries({
        queryKey: ["instrument-ranges", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument", instrumentId],
      });
    } catch (cause) {
      setError(friendlyApiMessage(cause));
    }
  }

  function edit(item: RangeView) {
    setEditing(item);
    setForm({
      range_no: item.range_no,
      min_capacity_g: item.min_capacity_g ?? null,
      max_capacity_g: item.max_capacity_g,
      scale_interval_d_g: item.scale_interval_d_g,
      verification_interval_e_g: item.verification_interval_e_g,
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
      <div className="panel-heading-row">
        <div>
          <h2>Instrument ranges</h2>
          <p className="detail-note">
            Capacity values remain exact decimal strings. Backend validation
            prevents invalid active range sets.
          </p>
        </div>
      </div>

      {canManage ? (
        <form className="inline-editor" onSubmit={submit}>
          <label>
            <span>Range no.</span>
            <input
              type="number"
              min="1"
              value={form.range_no}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  range_no: Number.parseInt(event.target.value || "1", 10),
                }))
              }
            />
          </label>
          <label>
            <span>Min (g)</span>
            <input
              inputMode="decimal"
              value={form.min_capacity_g ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  min_capacity_g: event.target.value || null,
                }))
              }
            />
          </label>
          <label>
            <span>Max (g)</span>
            <input
              inputMode="decimal"
              required
              value={form.max_capacity_g}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  max_capacity_g: event.target.value,
                }))
              }
            />
          </label>
          <label>
            <span>d (g)</span>
            <input
              inputMode="decimal"
              required
              value={form.scale_interval_d_g}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  scale_interval_d_g: event.target.value,
                }))
              }
            />
          </label>
          <label>
            <span>e (g)</span>
            <input
              inputMode="decimal"
              required
              value={form.verification_interval_e_g}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  verification_interval_e_g: event.target.value,
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
                  ? "Update range"
                  : "Add range"}
            </button>
          </div>
        </form>
      ) : null}

      {error ? <div className="form-alert">{error}</div> : null}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Range</th>
              <th>Min</th>
              <th>Max</th>
              <th>d</th>
              <th>e</th>
              <th>Status</th>
              {canManage ? <th>Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {(query.data?.page.items ?? []).map((item) => (
              <tr key={item.id}>
                <td>{item.range_no}</td>
                <td>
                  {item.min_capacity_g ? `${item.min_capacity_g} g` : "Unknown"}
                </td>
                <td>{item.max_capacity_g} g</td>
                <td>{item.scale_interval_d_g} g</td>
                <td>{item.verification_interval_e_g} g</td>
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
                <td colSpan={canManage ? 7 : 6}>No ranges recorded.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
