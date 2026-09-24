"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import {
  allManufacturers,
  instrumentDetail,
  updateInstrument,
} from "@/lib/master-data/api";

const decimal = z
  .string()
  .trim()
  .regex(/^[+-]?(?:\d+)(?:\.\d+)?$/);
const optionalDecimal = z.union([z.literal(""), decimal]);
const triState = z.enum(["unknown", "yes", "no"]);
const schema = z.object({
  manufacturer_id: z.string().min(1),
  model_name: z.string().trim().min(1).max(200),
  type_designation: z.string().trim().max(200),
  serial_number: z.string().trim().max(200),
  accuracy_class: z.enum(["I", "II", "III", "IIII"]),
  min_capacity_g: optionalDecimal,
  max_capacity_g: decimal,
  scale_interval_d_g: decimal,
  verification_interval_e_g: decimal,
  range_type: z.string().trim().max(200),
  indication_type: z.string().trim().max(200),
  is_self_indicating: triState,
  is_electronic: triState,
  is_software_controlled: triState,
  is_portable: triState,
  is_mobile: triState,
  is_direct_sales: triState,
});
type Values = z.infer<typeof schema>;
const nullable = (value: string) => value.trim() || null;
const tri = (value: boolean | null | undefined): "unknown" | "yes" | "no" =>
  value === true ? "yes" : value === false ? "no" : "unknown";
const boolOrNull = (value: "unknown" | "yes" | "no") =>
  value === "unknown" ? null : value === "yes";

export default function EditInstrumentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["instrument", id],
    queryFn: () => instrumentDetail(id),
  });

  const manufacturers = useQuery({
    queryKey: [
      "manufacturers",
      "edit-instrument",
      query.data?.item.laboratory_id,
    ],
    queryFn: () => allManufacturers(query.data!.item.laboratory_id),
    enabled: Boolean(query.data?.item.laboratory_id),
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      manufacturer_id: "",
      model_name: "",
      type_designation: "",
      serial_number: "",
      accuracy_class: "III",
      min_capacity_g: "",
      max_capacity_g: "",
      scale_interval_d_g: "",
      verification_interval_e_g: "",
      range_type: "",
      indication_type: "",
      is_self_indicating: "unknown",
      is_electronic: "unknown",
      is_software_controlled: "unknown",
      is_portable: "unknown",
      is_mobile: "unknown",
      is_direct_sales: "unknown",
    },
  });

  useEffect(() => {
    if (!query.data) return;
    const item = query.data.item;
    form.reset({
      manufacturer_id: item.manufacturer_id,
      model_name: item.model_name,
      type_designation: item.type_designation ?? "",
      serial_number: item.serial_number ?? "",
      accuracy_class: item.accuracy_class,
      min_capacity_g: item.min_capacity_g ?? "",
      max_capacity_g: item.max_capacity_g,
      scale_interval_d_g: item.scale_interval_d_g,
      verification_interval_e_g: item.verification_interval_e_g,
      range_type: item.range_type ?? "",
      indication_type: item.indication_type ?? "",
      is_self_indicating: tri(item.is_self_indicating),
      is_electronic: tri(item.is_electronic),
      is_software_controlled: tri(item.is_software_controlled),
      is_portable: tri(item.is_portable),
      is_mobile: tri(item.is_mobile),
      is_direct_sales: tri(item.metadata_json?.is_direct_sales),
    });
  }, [form, query.data]);

  const mutation = useMutation({
    mutationFn: async (values: Values) => {
      if (!query.data?.etag) throw new Error("Reload before saving changes.");
      const currentMetadata = query.data.item.metadata_json ?? {};
      return updateInstrument(
        id,
        {
          manufacturer_id: values.manufacturer_id,
          model_name: values.model_name.trim(),
          type_designation: nullable(values.type_designation),
          serial_number: nullable(values.serial_number),
          accuracy_class: values.accuracy_class,
          min_capacity_g: nullable(values.min_capacity_g),
          max_capacity_g: values.max_capacity_g.trim(),
          scale_interval_d_g: values.scale_interval_d_g.trim(),
          verification_interval_e_g: values.verification_interval_e_g.trim(),
          range_type: nullable(values.range_type),
          indication_type: nullable(values.indication_type),
          is_self_indicating: boolOrNull(values.is_self_indicating),
          is_electronic: boolOrNull(values.is_electronic),
          is_software_controlled: boolOrNull(values.is_software_controlled),
          is_portable: boolOrNull(values.is_portable),
          is_mobile: boolOrNull(values.is_mobile),
          metadata_schema_version: 1,
          metadata_json: {
            ...currentMetadata,
            is_direct_sales: boolOrNull(values.is_direct_sales),
          },
        },
        query.data.etag,
      );
    },
  });

  if (query.isPending) return <LoadingState label="Loading instrument" />;
  if (query.isError) return <ErrorState error={query.error} />;
  if (!hasPermission("instrument:update")) {
    return (
      <div className="form-alert">
        You do not have permission to edit this instrument.
      </div>
    );
  }

  async function submit(values: Values) {
    setSubmitError(null);
    try {
      await mutation.mutateAsync(values);
      await queryClient.invalidateQueries({ queryKey: ["instrument", id] });
      await queryClient.invalidateQueries({ queryKey: ["instruments"] });
      router.push(`/instruments/${id}`);
    } catch (cause) {
      setSubmitError(friendlyApiMessage(cause));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Instrument"
        title="Edit instrument"
        description="Master edits do not rewrite historical session or report snapshots."
      />
      <form className="form-card" onSubmit={form.handleSubmit(submit)}>
        <div className="form-grid">
          <label className="form-field form-span-2">
            <span>Manufacturer *</span>
            <select {...form.register("manufacturer_id")}>
              {(manufacturers.data ?? []).map((manufacturer) => (
                <option key={manufacturer.id} value={manufacturer.id}>
                  {manufacturer.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Model *</span>
            <input {...form.register("model_name")} />
          </label>
          <label className="form-field">
            <span>Accuracy class</span>
            <select {...form.register("accuracy_class")}>
              <option>I</option>
              <option>II</option>
              <option>III</option>
              <option>IIII</option>
            </select>
          </label>
          <label className="form-field">
            <span>Type designation</span>
            <input {...form.register("type_designation")} />
          </label>
          <label className="form-field">
            <span>Serial number</span>
            <input {...form.register("serial_number")} />
          </label>
          <label className="form-field">
            <span>Min (g)</span>
            <input inputMode="decimal" {...form.register("min_capacity_g")} />
          </label>
          <label className="form-field">
            <span>Max (g) *</span>
            <input inputMode="decimal" {...form.register("max_capacity_g")} />
          </label>
          <label className="form-field">
            <span>d (g) *</span>
            <input
              inputMode="decimal"
              {...form.register("scale_interval_d_g")}
            />
          </label>
          <label className="form-field">
            <span>e (g) *</span>
            <input
              inputMode="decimal"
              {...form.register("verification_interval_e_g")}
            />
          </label>
          <label className="form-field">
            <span>Range type</span>
            <input {...form.register("range_type")} />
          </label>
          <label className="form-field">
            <span>Indication type</span>
            <input {...form.register("indication_type")} />
          </label>
          {[
            ["is_self_indicating", "Self-indicating"],
            ["is_electronic", "Electronic"],
            ["is_software_controlled", "Software controlled"],
            ["is_portable", "Portable"],
            ["is_mobile", "Mobile"],
            ["is_direct_sales", "Direct sales"],
          ].map(([name, label]) => (
            <label className="form-field" key={name}>
              <span>{label}</span>
              <select {...form.register(name as keyof Values)}>
                <option value="unknown">Unknown / not established</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
          ))}
        </div>

        <div className="information-banner">
          <strong>Unknown remains unknown.</strong>
          <span>
            Updating master facts does not determine applicability or
            compliance. Those remain backend regulatory decisions.
          </span>
        </div>

        {submitError ? <div className="form-alert">{submitError}</div> : null}
        <div className="form-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => router.back()}
          >
            Cancel
          </button>
          <button
            className="button button-primary"
            type="submit"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
