"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import {
  createUser,
  listAdministrativeLaboratories,
  listRoles,
} from "@/lib/admin-users/api";
import {
  ROLE_CODES,
  ROLE_LABELS,
  type RoleCode,
} from "@/lib/admin-users/types";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";

const roleSchema = z.enum(ROLE_CODES);

const schema = z
  .object({
    full_name: z.string().trim().min(1, "Full name is required.").max(200),
    email: z.string().trim().email("Enter a valid email address."),
    password: z.string().min(12, "Use at least 12 characters.").max(128),
    confirm_password: z.string().min(1, "Confirm the password."),
    scope_type: z.enum(["GLOBAL", "LABORATORY"]),
    role_code: roleSchema,
    laboratory_id: z.string(),
  })
  .superRefine((value, context) => {
    if (value.password !== value.confirm_password) {
      context.addIssue({
        code: "custom",
        path: ["confirm_password"],
        message: "Passwords do not match.",
      });
    }

    if (value.scope_type === "GLOBAL" && value.role_code !== "ADMIN") {
      context.addIssue({
        code: "custom",
        path: ["role_code"],
        message: "Only ADMIN can be assigned globally.",
      });
    }

    if (value.scope_type === "LABORATORY" && !value.laboratory_id) {
      context.addIssue({
        code: "custom",
        path: ["laboratory_id"],
        message: "Select a laboratory.",
      });
    }
  });

type Values = z.infer<typeof schema>;

export default function NewAdminUserPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, selectedLaboratoryId, hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [scopeType, setScopeType] = useState<"GLOBAL" | "LABORATORY">(
    "LABORATORY",
  );

  const canCreate = hasPermission("user:create");
  const canManageGlobal = Boolean(
    user?.global_permissions.includes("user:create") &&
      user.global_permissions.includes("user:manage_roles"),
  );

  const manageableLaboratoryIds = useMemo(
    () =>
      new Set(
        user?.laboratories
          .filter(
            (grant) =>
              grant.permissions.includes("user:create") &&
              grant.permissions.includes("user:manage_roles"),
          )
          .map((grant) => grant.laboratory_id) ?? [],
      ),
    [user],
  );

  const laboratories = useQuery({
    queryKey: ["admin-laboratories", "for-user-create"],
    queryFn: listAdministrativeLaboratories,
    enabled: canCreate,
    staleTime: 5 * 60_000,
  });

  const roles = useQuery({
    queryKey: ["admin-roles"],
    queryFn: listRoles,
    enabled: canCreate,
    staleTime: 5 * 60_000,
  });

  const availableLaboratories = useMemo(() => {
    const active = (laboratories.data ?? []).filter((item) => item.is_active);
    if (canManageGlobal) return active;
    return active.filter((item) => manageableLaboratoryIds.has(item.id));
  }, [canManageGlobal, laboratories.data, manageableLaboratoryIds]);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: "",
      email: "",
      password: "",
      confirm_password: "",
      scope_type: "LABORATORY",
      role_code: "LAB_TECHNICIAN",
      laboratory_id: selectedLaboratoryId ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: createUser,
  });

  if (!canCreate) {
    return (
      <div className="page-stack">
        <PageHeader title="Add user" eyebrow="Administration" />
        <div className="form-alert">
          You do not have permission to create users in the current scope.
        </div>
      </div>
    );
  }

  if (laboratories.isPending || roles.isPending) {
    return <LoadingState label="Preparing user administration" />;
  }
  if (laboratories.isError) return <ErrorState error={laboratories.error} />;
  if (roles.isError) return <ErrorState error={roles.error} />;

  async function submit(values: Values) {
    setSubmitError(null);
    try {
      const result = await mutation.mutateAsync({
        full_name: values.full_name.trim(),
        email: values.email.trim(),
        password: values.password,
        initial_assignment: {
          scope_type: values.scope_type,
          role_code:
            values.scope_type === "GLOBAL" ? "ADMIN" : values.role_code,
          laboratory_id:
            values.scope_type === "GLOBAL" ? null : values.laboratory_id,
        },
      });

      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      router.push(`/admin/users/${result.item.id}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  const errors = form.formState.errors;
  const availableRoleCodes = (roles.data ?? [])
    .map((role) => role.code)
    .filter((code): code is RoleCode => ROLE_CODES.includes(code));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Administration"
        title="Add user"
        description="Provision an authorized account and its first role assignment. This is not public registration."
      />

      <form
        className="form-card"
        onSubmit={form.handleSubmit(submit)}
        noValidate
      >
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Account</h2>
            <p>
              The password is stored only as a backend password hash. It is
              never shown again by the administration UI.
            </p>
          </div>

          <div className="form-grid">
            <label className="form-field">
              <span>Full name *</span>
              <input
                autoComplete="name"
                {...form.register("full_name")}
                aria-invalid={Boolean(errors.full_name)}
              />
              {errors.full_name ? (
                <small className="field-error">
                  {errors.full_name.message}
                </small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Email *</span>
              <input
                type="email"
                autoComplete="off"
                {...form.register("email")}
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email ? (
                <small className="field-error">{errors.email.message}</small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Initial password *</span>
              <input
                type="password"
                autoComplete="new-password"
                {...form.register("password")}
                aria-invalid={Boolean(errors.password)}
              />
              {errors.password ? (
                <small className="field-error">
                  {errors.password.message}
                </small>
              ) : null}
            </label>

            <label className="form-field">
              <span>Confirm password *</span>
              <input
                type="password"
                autoComplete="new-password"
                {...form.register("confirm_password")}
                aria-invalid={Boolean(errors.confirm_password)}
              />
              {errors.confirm_password ? (
                <small className="field-error">
                  {errors.confirm_password.message}
                </small>
              ) : null}
            </label>
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Initial authorization</h2>
            <p>
              Roles are explicit. ADMIN does not automatically act as a
              reviewer or approving officer in the regulatory workflow.
            </p>
          </div>

          <div className="form-grid">
            {canManageGlobal ? (
              <label className="form-field">
                <span>Assignment scope *</span>
                <select
                  value={scopeType}
                  onChange={(event) => {
                    const next = event.target.value as
                      | "GLOBAL"
                      | "LABORATORY";
                    setScopeType(next);
                    form.setValue("scope_type", next, {
                      shouldValidate: true,
                    });
                    if (next === "GLOBAL") {
                      form.setValue("role_code", "ADMIN", {
                        shouldValidate: true,
                      });
                      form.setValue("laboratory_id", "");
                    } else {
                      form.setValue("role_code", "LAB_TECHNICIAN", {
                        shouldValidate: true,
                      });
                      form.setValue(
                        "laboratory_id",
                        selectedLaboratoryId ?? "",
                        { shouldValidate: true },
                      );
                    }
                  }}
                >
                  <option value="LABORATORY">Laboratory</option>
                  <option value="GLOBAL">Global administration</option>
                </select>
              </label>
            ) : (
              <input
                type="hidden"
                value="LABORATORY"
                {...form.register("scope_type")}
              />
            )}

            <label className="form-field">
              <span>Role *</span>
              <select
                {...form.register("role_code")}
                disabled={scopeType === "GLOBAL"}
              >
                {(scopeType === "GLOBAL"
                  ? ["ADMIN" as RoleCode]
                  : availableRoleCodes
                ).map((code) => (
                  <option key={code} value={code}>
                    {ROLE_LABELS[code]}
                  </option>
                ))}
              </select>
              {errors.role_code ? (
                <small className="field-error">
                  {errors.role_code.message}
                </small>
              ) : null}
            </label>

            {scopeType === "LABORATORY" ? (
              <label className="form-field form-span-2">
                <span>Laboratory *</span>
                <select
                  {...form.register("laboratory_id")}
                  aria-invalid={Boolean(errors.laboratory_id)}
                >
                  <option value="">Select laboratory</option>
                  {availableLaboratories.map((laboratory) => (
                    <option key={laboratory.id} value={laboratory.id}>
                      {laboratory.name} ({laboratory.code})
                    </option>
                  ))}
                </select>
                {errors.laboratory_id ? (
                  <small className="field-error">
                    {errors.laboratory_id.message}
                  </small>
                ) : null}
              </label>
            ) : null}
          </div>
        </section>

        <div className="information-banner">
          <strong>Least privilege.</strong>
          <span>
            Create the account with only the role required for the person’s
            current duties. Additional assignments can be granted later from
            the user detail screen and are recorded by the backend audit trail.
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
            disabled={
              mutation.isPending ||
              (scopeType === "LABORATORY" &&
                availableLaboratories.length === 0)
            }
          >
            {mutation.isPending ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </div>
  );
}
