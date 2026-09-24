"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/ui/page-header";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { createEquipment } from "@/lib/master-data/api";

const optionalDecimal = z.union([
  z.literal(""),
  z
    .string()
    .trim()
    .regex(/^[+-]?(?:\d+)(?:\.\d+)?$/, "Enter a decimal value as text."),
]);

const schema = z.object({
  category: z
    .string()
    .trim()
    .min(1, "Equipment category is required.")
    .max(200),
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

export default function NewEquipmentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

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

  const mutation = useMutation({ mutationFn: createEquipment });

  if (!selectedLaboratoryId || !hasPermission("equipment:create")) {
    return (
      <div className="page-stack">
        <PageHeader title="Add equipment" eyebrow="Master data" />
        <div className="form-alert">
          You do not have permission to create equipment in this laboratory.
        </div>
      </div>
    );
  }

  const laboratoryId = selectedLaboratoryId;

  async function submit(values: Values) {
    setSubmitError(null);
    try {
      const result = await mutation.mutateAsync({
        laboratory_id: laboratoryId,
        category: values.category.trim(),
        manufacturer: nullable(values.manufacturer),
        model: nullable(values.model),
        serial_number: nullable(values.serial_number),
        reference_number: nullable(values.reference_number),
        calibration_certificate_no: nullable(values.calibration_certificate_no),
        calibration_date: nullable(values.calibration_date),
        calibration_due_date: nullable(values.calibration_due_date),
        accuracy_or_class: nullable(values.accuracy_or_class),
        metadata_schema_version: 1,
        metadata_json: {
          notes: nullable(values.notes),
          nominal_mass_g: nullable(values.nominal_mass_g),
          certificate_reference: nullable(values.certificate_reference),
        },
      });
      await queryClient.invalidateQueries({ queryKey: ["equipment"] });
      router.push(`/equipment/${result.item.id}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Add test equipment"
        description="Record equipment and calibration facts. Calibration acceptance remains a regulated evaluation concern."
      />

      <form
        className="form-card"
        onSubmit={form.handleSubmit(submit)}
        noValidate
      >
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Equipment identity</h2>
          </div>
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
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Calibration facts</h2>
          </div>
          <div className="form-grid">
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
        </section>

        {submitError ? (
          <div className="form-alert" role="alert">
            {submitError}
          </div>
        ) : null}

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
            {mutation.isPending ? "Saving…" : "Save equipment"}
          </button>
        </div>
      </form>
    </div>
  );
}
