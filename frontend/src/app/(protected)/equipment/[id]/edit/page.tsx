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
import { equipmentDetail, updateEquipment } from "@/lib/master-data/api";

const optionalDecimal = z.union([
  z.literal(""),
  z
    .string()
    .trim()
    .regex(/^[+-]?(?:\d+)(?:\.\d+)?$/),
]);
const schema = z.object({
  category: z.string().trim().min(1).max(200),
  manufacturer: z.string().trim().max(200),
  model: z.string().trim().max(200),
  serial_number: z.string().trim().max(200),
  reference_number: z.string().trim().max(200),
  calibration_certificate_no: z.string().trim().max(200),
  calibration_date: z.string(),
  calibration_due_date: z.string(),
  accuracy_or_class: z.string().trim().max(200),
  nominal_mass_g: optionalDecimal,
  certificate_reference: z.string().trim().max(200),
  notes: z.string().trim().max(1000),
});
type Values = z.infer<typeof schema>;
const nullable = (value: string) => value.trim() || null;

export default function EditEquipmentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["equipment-detail", id],
    queryFn: () => equipmentDetail(id),
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      category: "",
      manufacturer: "",
      model: "",
      serial_number: "",
      reference_number: "",
      calibration_certificate_no: "",
      calibration_date: "",
      calibration_due_date: "",
      accuracy_or_class: "",
      nominal_mass_g: "",
      certificate_reference: "",
      notes: "",
    },
  });

  useEffect(() => {
    if (!query.data) return;
    const item = query.data.item;
    form.reset({
      category: item.category,
      manufacturer: item.manufacturer ?? "",
      model: item.model ?? "",
      serial_number: item.serial_number ?? "",
      reference_number: item.reference_number ?? "",
      calibration_certificate_no: item.calibration_certificate_no ?? "",
      calibration_date: item.calibration_date ?? "",
      calibration_due_date: item.calibration_due_date ?? "",
      accuracy_or_class: item.accuracy_or_class ?? "",
      nominal_mass_g: item.metadata_json?.nominal_mass_g ?? "",
      certificate_reference: item.metadata_json?.certificate_reference ?? "",
      notes: item.metadata_json?.notes ?? "",
    });
  }, [form, query.data]);

  const mutation = useMutation({
    mutationFn: async (values: Values) => {
      if (!query.data?.etag) throw new Error("Reload before saving changes.");
      return updateEquipment(
        id,
        {
          category: values.category.trim(),
          manufacturer: nullable(values.manufacturer),
          model: nullable(values.model),
          serial_number: nullable(values.serial_number),
          reference_number: nullable(values.reference_number),
          calibration_certificate_no: nullable(
            values.calibration_certificate_no,
          ),
          calibration_date: nullable(values.calibration_date),
          calibration_due_date: nullable(values.calibration_due_date),
          accuracy_or_class: nullable(values.accuracy_or_class),
          metadata_schema_version: 1,
          metadata_json: {
            nominal_mass_g: nullable(values.nominal_mass_g),
            certificate_reference: nullable(values.certificate_reference),
            notes: nullable(values.notes),
          },
        },
        query.data.etag,
      );
    },
  });

  if (query.isPending) return <LoadingState label="Loading equipment" />;
  if (query.isError) return <ErrorState error={query.error} />;
  if (!hasPermission("equipment:update")) {
    return (
      <div className="form-alert">
        You do not have permission to edit this equipment.
      </div>
    );
  }

  async function submit(values: Values) {
    setSubmitError(null);
    try {
      await mutation.mutateAsync(values);
      await queryClient.invalidateQueries({
        queryKey: ["equipment-detail", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["equipment"] });
      router.push(`/equipment/${id}`);
    } catch (cause) {
      setSubmitError(friendlyApiMessage(cause));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Test equipment"
        title="Edit equipment"
        description="Calibration master facts can be corrected without rewriting historical measurement snapshots."
      />
      <form className="form-card" onSubmit={form.handleSubmit(submit)}>
        <div className="form-grid">
          <label className="form-field">
            <span>Category *</span>
            <input {...form.register("category")} />
          </label>
          <label className="form-field">
            <span>Reference number</span>
            <input {...form.register("reference_number")} />
          </label>
          <label className="form-field">
            <span>Manufacturer</span>
            <input {...form.register("manufacturer")} />
          </label>
          <label className="form-field">
            <span>Model</span>
            <input {...form.register("model")} />
          </label>
          <label className="form-field">
            <span>Serial number</span>
            <input {...form.register("serial_number")} />
          </label>
          <label className="form-field">
            <span>Accuracy / class</span>
            <input {...form.register("accuracy_or_class")} />
          </label>
          <label className="form-field">
            <span>Certificate number</span>
            <input {...form.register("calibration_certificate_no")} />
          </label>
          <label className="form-field">
            <span>Certificate reference</span>
            <input {...form.register("certificate_reference")} />
          </label>
          <label className="form-field">
            <span>Calibration date</span>
            <input type="date" {...form.register("calibration_date")} />
          </label>
          <label className="form-field">
            <span>Calibration due date</span>
            <input type="date" {...form.register("calibration_due_date")} />
          </label>
          <label className="form-field">
            <span>Nominal mass (g)</span>
            <input inputMode="decimal" {...form.register("nominal_mass_g")} />
          </label>
          <label className="form-field form-span-2">
            <span>Notes</span>
            <textarea rows={4} {...form.register("notes")} />
          </label>
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
