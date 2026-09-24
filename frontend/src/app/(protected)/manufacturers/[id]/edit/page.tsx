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
import { manufacturerDetail, updateManufacturer } from "@/lib/master-data/api";

const schema = z.object({
  name: z.string().trim().min(1).max(200),
  registration_no: z.string().trim().max(200),
  address_line1: z.string().trim().min(1).max(1000),
  address_line2: z.string().trim().max(1000),
  city: z.string().trim().max(200),
  state: z.string().trim().max(200),
  postal_code: z.string().trim().max(200),
  country: z.string().trim().max(200),
  contact_person: z.string().trim().max(200),
  email: z.union([z.literal(""), z.string().trim().email()]),
  phone: z.string().trim().max(200),
});
type Values = z.infer<typeof schema>;
const nullable = (value: string) => value.trim() || null;

export default function EditManufacturerPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["manufacturer", id],
    queryFn: () => manufacturerDetail(id),
  });

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

  useEffect(() => {
    if (!query.data) return;
    const item = query.data.item;
    form.reset({
      name: item.name,
      registration_no: item.registration_no ?? "",
      address_line1: item.address.address_line1,
      address_line2: item.address.address_line2 ?? "",
      city: item.address.city ?? "",
      state: item.address.state ?? "",
      postal_code: item.address.postal_code ?? "",
      country: item.country ?? item.address.country ?? "",
      contact_person: item.contact_person ?? "",
      email: item.email ?? "",
      phone: item.phone ?? "",
    });
  }, [form, query.data]);

  const mutation = useMutation({
    mutationFn: async (values: Values) => {
      if (!query.data?.etag) throw new Error("Reload before saving changes.");
      return updateManufacturer(
        id,
        {
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
        },
        query.data.etag,
      );
    },
  });

  if (query.isPending) return <LoadingState label="Loading manufacturer" />;
  if (query.isError) return <ErrorState error={query.error} />;
  if (!hasPermission("manufacturer:update")) {
    return (
      <div className="form-alert">
        You do not have permission to edit this manufacturer.
      </div>
    );
  }

  async function submit(values: Values) {
    setSubmitError(null);
    try {
      await mutation.mutateAsync(values);
      await queryClient.invalidateQueries({ queryKey: ["manufacturer", id] });
      await queryClient.invalidateQueries({ queryKey: ["manufacturers"] });
      router.push(`/manufacturers/${id}`);
    } catch (cause) {
      setSubmitError(friendlyApiMessage(cause));
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Manufacturer"
        title="Edit manufacturer"
        description="Changes affect current master data only; historical evaluation/report snapshots remain immutable."
      />
      <form className="form-card" onSubmit={form.handleSubmit(submit)}>
        <div className="form-grid">
          <label className="form-field form-span-2">
            <span>Name *</span>
            <input {...form.register("name")} />
          </label>
          <label className="form-field">
            <span>Registration number</span>
            <input {...form.register("registration_no")} />
          </label>
          <label className="form-field">
            <span>Country</span>
            <input {...form.register("country")} />
          </label>
          <label className="form-field form-span-2">
            <span>Address line 1 *</span>
            <input {...form.register("address_line1")} />
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
          <label className="form-field">
            <span>Contact person</span>
            <input {...form.register("contact_person")} />
          </label>
          <label className="form-field">
            <span>Email</span>
            <input type="email" {...form.register("email")} />
          </label>
          <label className="form-field">
            <span>Phone</span>
            <input {...form.register("phone")} />
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
