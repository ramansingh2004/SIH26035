"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import {
  laboratoryDetail,
  updateLaboratory,
} from "@/lib/admin-laboratories/api";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";

const schema = z.object({
  name: z.string().trim().min(1, "Laboratory name is required.").max(200),
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
  status: z.enum(["active", "inactive"]),
});

type Values = z.infer<typeof schema>;

export default function EditLaboratoryPage() {
  const { laboratoryId } = useParams<{ laboratoryId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const laboratoryGrant = user?.laboratories.find(
    (grant) => grant.laboratory_id === laboratoryId,
  );
  const canRead = Boolean(
    user?.global_permissions.includes("laboratory:read") ||
      laboratoryGrant?.permissions.includes("laboratory:read"),
  );
  const canUpdate = Boolean(
    user?.global_permissions.includes("laboratory:update") ||
      laboratoryGrant?.permissions.includes("laboratory:update"),
  );

  const query = useQuery({
    queryKey: ["admin-laboratory", laboratoryId],
    queryFn: () => laboratoryDetail(laboratoryId),
    enabled: canRead,
  });

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
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
      status: "active",
    },
  });

  useEffect(() => {
    if (!query.data) return;
    const item = query.data.item;
    form.reset({
      name: item.name,
      address_line1: item.address_line1,
      address_line2: item.address_line2,
      city: item.city,
      state: item.state,
      postal_code: item.postal_code,
      country: item.country,
      phone: item.phone,
      email: item.email,
      accreditation_no: item.accreditation_no,
      timezone: item.timezone,
      status: item.is_active ? "active" : "inactive",
    });
  }, [form, query.data]);

  const mutation = useMutation({
    mutationFn: async (values: Values) => {
      if (!query.data?.etag) {
        throw new Error("Reload this laboratory before saving.");
      }

      return updateLaboratory(
        laboratoryId,
        {
          name: values.name.trim(),
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
          is_active: values.status === "active",
        },
        query.data.etag,
      );
    },
  });

  if (!canRead) {
    return (
      <div className="page-stack">
        <PageHeader title="Edit laboratory" eyebrow="Administration" />
        <EmptyState
          title="No laboratory access"
          description="Your account cannot read this laboratory scope."
        />
      </div>
    );
  }

  if (query.isPending) {
    return <LoadingState label="Loading laboratory" />;
  }
  if (query.isError) return <ErrorState error={query.error} />;

  if (!canUpdate) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Administration"
          title={query.data.item.name}
        />
        <EmptyState
          title="No laboratory update access"
          description="Your account does not grant laboratory:update for this laboratory."
        />
      </div>
    );
  }

  async function submit(values: Values) {
    setSubmitError(null);

    try {
      await mutation.mutateAsync(values);
      await queryClient.invalidateQueries({
        queryKey: ["admin-laboratories"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["admin-laboratory", laboratoryId],
      });
      router.push(`/admin/laboratories/${laboratoryId}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  const errors = form.formState.errors;
  const item = query.data.item;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration · Laboratory"
        title={`Edit ${item.name}`}
        description={`Laboratory code ${item.code} is immutable after creation.`}
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
              Updates use the current backend ETag so concurrent administrator
              changes cannot be silently overwritten.
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
              <span>Laboratory code</span>
              <input value={item.code} readOnly />
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
                {...form.register("timezone")}
                aria-invalid={Boolean(errors.timezone)}
              />
              {errors.timezone ? (
                <small className="field-error">
                  {errors.timezone.message}
                </small>
              ) : null}
            </label>

            <label className="form-field form-span-2">
              <span>Laboratory status</span>
              <select {...form.register("status")}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
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

        <div className="validation-panel">
          Setting a laboratory to Inactive removes its laboratory-scoped grants
          from effective authorization until the laboratory is reactivated.
          Existing historical evaluation and report records are not rewritten.
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
            {mutation.isPending ? "Saving…" : "Save laboratory"}
          </button>
        </div>
      </form>
    </div>
  );
}
