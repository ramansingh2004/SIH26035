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
import { createManufacturer } from "@/lib/master-data/api";

const optionalEmail = z.union([
  z.literal(""),
  z.string().trim().email("Enter a valid email address."),
]);

const schema = z.object({
  name: z.string().trim().min(1, "Manufacturer name is required.").max(200),
  registration_no: z.string().trim().max(200),
  address_line1: z
    .string()
    .trim()
    .min(1, "Address line 1 is required.")
    .max(1000),
  address_line2: z.string().trim().max(1000),
  city: z.string().trim().max(200),
  state: z.string().trim().max(200),
  postal_code: z.string().trim().max(200),
  country: z.string().trim().max(200),
  contact_person: z.string().trim().max(200),
  email: optionalEmail,
  phone: z.string().trim().max(200),
});

type Values = z.infer<typeof schema>;
const nullable = (value: string) => value.trim() || null;

export default function NewManufacturerPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      registration_no: "",
      address_line1: "",
      address_line2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "",
      contact_person: "",
      email: "",
      phone: "",
    },
  });

  const mutation = useMutation({
    mutationFn: createManufacturer,
  });

  if (!selectedLaboratoryId || !hasPermission("manufacturer:create")) {
    return (
      <div className="page-stack">
        <PageHeader title="Add manufacturer" eyebrow="Master data" />
        <div className="form-alert">
          You do not have permission to create manufacturers in this laboratory.
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
        name: values.name.trim(),
        registration_no: nullable(values.registration_no),
        address: {
          schema_version: 1,
          address_line1: values.address_line1.trim(),
          address_line2: nullable(values.address_line2),
          city: nullable(values.city),
          state: nullable(values.state),
          postal_code: nullable(values.postal_code),
          country: nullable(values.country),
        },
        contact_person: nullable(values.contact_person),
        email: nullable(values.email),
        phone: nullable(values.phone),
        country: nullable(values.country),
      });
      await queryClient.invalidateQueries({ queryKey: ["manufacturers"] });
      router.push(`/manufacturers/${result.item.id}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  const errors = form.formState.errors;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Add manufacturer"
        description="Create a laboratory-owned manufacturer record. This is master data, not a regulatory approval."
      />

      <form
        className="form-card"
        onSubmit={form.handleSubmit(submit)}
        noValidate
      >
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Manufacturer identity</h2>
            <p>
              Enter the legal or declared manufacturer details available to the
              laboratory.
            </p>
          </div>
          <div className="form-grid">
            <label className="form-field form-span-2">
              <span>Manufacturer name *</span>
              <input
                {...form.register("name")}
                aria-invalid={Boolean(errors.name)}
              />
              {errors.name ? (
                <small className="field-error">{errors.name.message}</small>
              ) : null}
            </label>
            <label className="form-field">
              <span>Registration number</span>
              <input {...form.register("registration_no")} />
            </label>
            <label className="form-field">
              <span>Country</span>
              <input {...form.register("country")} />
            </label>
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Address</h2>
          </div>
          <div className="form-grid">
            <label className="form-field form-span-2">
              <span>Address line 1 *</span>
              <input
                {...form.register("address_line1")}
                aria-invalid={Boolean(errors.address_line1)}
              />
              {errors.address_line1 ? (
                <small className="field-error">
                  {errors.address_line1.message}
                </small>
              ) : null}
            </label>
            <label className="form-field form-span-2">
              <span>Address line 2</span>
              <input {...form.register("address_line2")} />
            </label>
            <label className="form-field">
              <span>City</span>
              <input {...form.register("city")} />
            </label>
            <label className="form-field">
              <span>State</span>
              <input {...form.register("state")} />
            </label>
            <label className="form-field">
              <span>Postal code</span>
              <input {...form.register("postal_code")} />
            </label>
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Contact</h2>
          </div>
          <div className="form-grid">
            <label className="form-field">
              <span>Contact person</span>
              <input {...form.register("contact_person")} />
            </label>
            <label className="form-field">
              <span>Email</span>
              <input
                type="email"
                {...form.register("email")}
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email ? (
                <small className="field-error">{errors.email.message}</small>
              ) : null}
            </label>
            <label className="form-field">
              <span>Phone</span>
              <input {...form.register("phone")} />
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
            {mutation.isPending ? "Saving…" : "Save manufacturer"}
          </button>
        </div>
      </form>
    </div>
  );
}
