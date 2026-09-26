"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/ui/page-header";
import { createLaboratory } from "@/lib/admin-laboratories/api";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";

const schema = z.object({
  name: z.string().trim().min(1, "Laboratory name is required.").max(200),
  code: z
    .string()
    .trim()
    .min(1, "Laboratory code is required.")
    .max(50)
    .regex(
      /^[A-Za-z0-9_-]+$/,
      "Use only letters, numbers, underscores or hyphens.",
    ),
  address_line1: z.string().trim().min(1, "Address line 1 is required.").max(300),
  address_line2: z.string().trim().max(300),
  city: z.string().trim().min(1, "City is required.").max(100),
  state: z.string().trim().min(1, "State is required.").max(100),
  postal_code: z.string().trim().min(1, "Postal code is required.").max(30),
  country: z.string().trim().min(1, "Country is required.").max(100),
  phone: z.string().trim().min(1, "Phone is required.").max(40),
  email: z.string().trim().email("Enter a valid email address."),
  accreditation_no: z
    .string()
    .trim()
    .min(1, "Accreditation number is required.")
    .max(100),
  timezone: z.string().trim().min(1, "IANA timezone is required.").max(100),
});

type Values = z.infer<typeof schema>;

export default function NewLaboratoryPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const canCreate = Boolean(
    user?.global_permissions.includes("laboratory:create"),
  );

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      code: "",
      address_line1: "",
      address_line2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "",
      phone: "",
      email: "",
      accreditation_no: "",
      timezone: "UTC",
    },
  });

  const mutation = useMutation({
    mutationFn: createLaboratory,
  });

  if (!canCreate) {
    return (
      <div className="page-stack">
        <PageHeader title="Add laboratory" eyebrow="Administration" />
        <div className="form-alert">
          Only a global administrator with laboratory:create can create a
          laboratory.
        </div>
      </div>
    );
  }

  async function submit(values: Values) {
    setSubmitError(null);

    try {
      const result = await mutation.mutateAsync({
        name: values.name.trim(),
        code: values.code.trim(),
        address_line1: values.address_line1.trim(),
        address_line2: values.address_line2.trim(),
        city: values.city.trim(),
        state: values.state.trim(),
        postal_code: values.postal_code.trim(),
        country: values.country.trim(),
        phone: values.phone.trim(),
        email: values.email.trim(),
        accreditation_no: values.accreditation_no.trim(),
        timezone: values.timezone.trim(),
      });

      await queryClient.invalidateQueries({
        queryKey: ["admin-laboratories"],
      });
      router.push(`/admin/laboratories/${result.item.id}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  const errors = form.formState.errors;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Add laboratory"
        description="Create a controlled laboratory scope. The laboratory code becomes its stable administrative identifier and is not editable later."
      />

      <form
        className="form-card"
        onSubmit={form.handleSubmit(submit)}
        noValidate
      >
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Laboratory identity</h2>
            <p>
              Use the official laboratory identity and accreditation metadata
              available to the organization.
            </p>
          </div>

          <div className="form-grid">
            <label className="form-field">
              <span>Laboratory name *</span>
              <input
                {...form.register("name")}
                aria-invalid={Boolean(errors.name)}
              />
              {errors.name ? (
                <small className="field-error">{errors.name.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Laboratory code *</span>
              <input
                {...form.register("code")}
                aria-invalid={Boolean(errors.code)}
              />
              {errors.code ? (
                <small className="field-error">{errors.code.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Accreditation number *</span>
              <input
                {...form.register("accreditation_no")}
                aria-invalid={Boolean(errors.accreditation_no)}
              />
              {errors.accreditation_no ? (
                <small className="field-error">
                  {errors.accreditation_no.message}
                </small>
              ) : null}
            </label>

            <label className="form-field">
              <span>IANA timezone *</span>
              <input
                placeholder="UTC or Asia/Kolkata"
                {...form.register("timezone")}
                aria-invalid={Boolean(errors.timezone)}
              />
              {errors.timezone ? (
                <small className="field-error">
                  {errors.timezone.message}
                </small>
              ) : null}
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
              <span>City *</span>
              <input
                {...form.register("city")}
                aria-invalid={Boolean(errors.city)}
              />
              {errors.city ? (
                <small className="field-error">{errors.city.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>State *</span>
              <input
                {...form.register("state")}
                aria-invalid={Boolean(errors.state)}
              />
              {errors.state ? (
                <small className="field-error">{errors.state.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Postal code *</span>
              <input
                {...form.register("postal_code")}
                aria-invalid={Boolean(errors.postal_code)}
              />
              {errors.postal_code ? (
                <small className="field-error">
                  {errors.postal_code.message}
                </small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Country *</span>
              <input
                {...form.register("country")}
                aria-invalid={Boolean(errors.country)}
              />
              {errors.country ? (
                <small className="field-error">
                  {errors.country.message}
                </small>
              ) : null}
            </label>
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Contact</h2>
          </div>

          <div className="form-grid">
            <label className="form-field">
              <span>Email *</span>
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
              <span>Phone *</span>
              <input
                {...form.register("phone")}
                aria-invalid={Boolean(errors.phone)}
              />
              {errors.phone ? (
                <small className="field-error">{errors.phone.message}</small>
              ) : null}
            </label>
          </div>
        </section>

        <div className="information-banner">
          <strong>Backend-validated scope.</strong>
          <span>
            The server validates the IANA timezone and records laboratory
            creation in the audit trail. Creating a laboratory does not assign
            regulatory roles automatically.
          </span>
        </div>

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
            {mutation.isPending ? "Creating…" : "Create laboratory"}
          </button>
        </div>
      </form>
    </div>
  );
}
