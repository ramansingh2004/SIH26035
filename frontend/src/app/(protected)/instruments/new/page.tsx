"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { RegulatoryBlocker } from "@/components/ui/regulatory-blocker";
import { PageHeader } from "@/components/ui/page-header";
import { friendlyApiMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import {
  allManufacturers,
  createInstrument,
  validateInstrumentConfiguration,
} from "@/lib/master-data/api";
import type {
  ConfigurationValidation,
  InstrumentCreate,
} from "@/lib/master-data/types";

const decimal = z
  .string()
  .trim()
  .regex(/^[+-]?(?:\d+)(?:\.\d+)?$/, "Enter a decimal value as text.");

const optionalDecimal = z.union([z.literal(""), decimal]);
const triState = z.enum(["unknown", "yes", "no"]);

const schema = z.object({
  manufacturer_id: z.string().min(1, "Select a manufacturer."),
  model_name: z.string().trim().min(1, "Model name is required.").max(200),
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
  load_receptor_type: z.string().trim().max(200),
  support_point_count: z.string().trim(),
  power_supply_type: z.string().trim().max(200),
  nominal_voltage: optionalDecimal,
  min_voltage: optionalDecimal,
  max_voltage: optionalDecimal,
  declared_temp_min_c: optionalDecimal,
  declared_temp_max_c: optionalDecimal,
  software_identifier: z.string().trim().max(200),
});

type Values = z.infer<typeof schema>;

const nullable = (value: string) => value.trim() || null;
const boolOrNull = (value: "unknown" | "yes" | "no") =>
  value === "unknown" ? null : value === "yes";

function toPayload(values: Values, laboratoryId: string): InstrumentCreate {
  return {
    laboratory_id: laboratoryId,
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
    load_receptor_type: nullable(values.load_receptor_type),
    support_point_count: values.support_point_count
      ? Number.parseInt(values.support_point_count, 10)
      : null,
    power_supply_type: nullable(values.power_supply_type),
    nominal_voltage: nullable(values.nominal_voltage),
    min_voltage: nullable(values.min_voltage),
    max_voltage: nullable(values.max_voltage),
    declared_temp_min_c: nullable(values.declared_temp_min_c),
    declared_temp_max_c: nullable(values.declared_temp_max_c),
    software_identifier: nullable(values.software_identifier),
    metadata_schema_version: 1,
    metadata_json: {
      is_direct_sales: boolOrNull(values.is_direct_sales),
    },
  };
}

function TriStateField({
  label,
  registration,
}: {
  label: string;
  registration: ReturnType<ReturnType<typeof useForm<Values>>["register"]>;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      <select {...registration}>
        <option value="unknown">Unknown / not established</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    </label>
  );
}

export default function NewInstrumentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { selectedLaboratoryId, hasPermission } = useAuth();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ConfigurationValidation | null>(
    null,
  );

  const manufacturers = useQuery({
    queryKey: ["manufacturers", "all", selectedLaboratoryId],
    queryFn: () => allManufacturers(selectedLaboratoryId!),
    enabled: Boolean(
      selectedLaboratoryId && hasPermission("manufacturer:read"),
    ),
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
      load_receptor_type: "",
      support_point_count: "",
      power_supply_type: "",
      nominal_voltage: "",
      min_voltage: "",
      max_voltage: "",
      declared_temp_min_c: "",
      declared_temp_max_c: "",
      software_identifier: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (payload: InstrumentCreate) => {
      const result = await validateInstrumentConfiguration(payload);
      setValidation(result);
      if (!result.structural_valid) {
        throw new Error(
          "Instrument configuration failed structural validation.",
        );
      }
      return createInstrument(payload);
    },
  });

  if (!selectedLaboratoryId || !hasPermission("instrument:create")) {
    return (
      <div className="page-stack">
        <PageHeader title="Register instrument" eyebrow="Master data" />
        <div className="form-alert">
          You do not have permission to create instruments in this laboratory.
        </div>
      </div>
    );
  }

  const laboratoryId = selectedLaboratoryId;

  async function submit(values: Values) {
    setSubmitError(null);
    setValidation(null);
    try {
      const result = await mutation.mutateAsync(
        toPayload(values, laboratoryId),
      );
      await queryClient.invalidateQueries({ queryKey: ["instruments"] });
      router.push(`/instruments/${result.item.id}`);
    } catch (error) {
      setSubmitError(friendlyApiMessage(error));
    }
  }

  const errors = form.formState.errors;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Master data"
        title="Register instrument"
        description="Record declared NAWI characteristics. Unknown applicability facts remain explicit and are not converted to N/A."
      />

      <div className="information-banner">
        <strong>Master-data registration is not regulatory compliance.</strong>
        <span>
          Structural validation can succeed while OIML rule verification remains
          blocked. Applicability is established later from the pinned ruleset.
        </span>
      </div>

      <form
        className="form-card"
        onSubmit={form.handleSubmit(submit)}
        noValidate
      >
        <section className="form-section">
          <div className="form-section-heading">
            <h2>Identification</h2>
          </div>
          <div className="form-grid">
            <label className="form-field form-span-2">
              <span>Manufacturer *</span>
              <select
                {...form.register("manufacturer_id")}
                aria-invalid={Boolean(errors.manufacturer_id)}
              >
                <option value="">Select manufacturer</option>
                {(manufacturers.data ?? []).map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {errors.manufacturer_id ? (
                <small className="field-error">
                  {errors.manufacturer_id.message}
                </small>
              ) : null}
            </label>
            <label className="form-field">
              <span>Model name *</span>
              <input
                {...form.register("model_name")}
                aria-invalid={Boolean(errors.model_name)}
              />
              {errors.model_name ? (
                <small className="field-error">
                  {errors.model_name.message}
                </small>
              ) : null}
            </label>
            <label className="form-field">
              <span>Accuracy class *</span>
              <select {...form.register("accuracy_class")}>
                <option value="I">I</option>
                <option value="II">II</option>
                <option value="III">III</option>
                <option value="IIII">IIII</option>
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
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Capacity and intervals</h2>
            <p>
              Values are retained and sent to the API as decimal strings; the
              browser does not calculate regulatory limits.
            </p>
          </div>
          <div className="form-grid">
            <label className="form-field">
              <span>Minimum capacity (g)</span>
              <input inputMode="decimal" {...form.register("min_capacity_g")} />
            </label>
            <label className="form-field">
              <span>Maximum capacity (g) *</span>
              <input
                inputMode="decimal"
                {...form.register("max_capacity_g")}
                aria-invalid={Boolean(errors.max_capacity_g)}
              />
              {errors.max_capacity_g ? (
                <small className="field-error">
                  {errors.max_capacity_g.message}
                </small>
              ) : null}
            </label>
            <label className="form-field">
              <span>Scale interval d (g) *</span>
              <input
                inputMode="decimal"
                {...form.register("scale_interval_d_g")}
              />
            </label>
            <label className="form-field">
              <span>Verification interval e (g) *</span>
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
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Applicability facts</h2>
            <p>
              Choose Unknown when a fact has not been established. The frontend
              never turns unknown into false or not-applicable.
            </p>
          </div>
          <div className="form-grid form-grid-3">
            <TriStateField
              label="Self-indicating"
              registration={form.register("is_self_indicating")}
            />
            <TriStateField
              label="Electronic"
              registration={form.register("is_electronic")}
            />
            <TriStateField
              label="Software controlled"
              registration={form.register("is_software_controlled")}
            />
            <TriStateField
              label="Portable"
              registration={form.register("is_portable")}
            />
            <TriStateField
              label="Mobile"
              registration={form.register("is_mobile")}
            />
            <TriStateField
              label="Direct sales"
              registration={form.register("is_direct_sales")}
            />
          </div>
        </section>

        <section className="form-section">
          <div className="form-section-heading">
            <h2>Technical declarations</h2>
          </div>
          <div className="form-grid">
            <label className="form-field">
              <span>Load receptor type</span>
              <input {...form.register("load_receptor_type")} />
            </label>
            <label className="form-field">
              <span>Support point count</span>
              <input
                inputMode="numeric"
                {...form.register("support_point_count")}
              />
            </label>
            <label className="form-field">
              <span>Power supply type</span>
              <input {...form.register("power_supply_type")} />
            </label>
            <label className="form-field">
              <span>Nominal voltage</span>
              <input
                inputMode="decimal"
                {...form.register("nominal_voltage")}
              />
            </label>
            <label className="form-field">
              <span>Minimum voltage</span>
              <input inputMode="decimal" {...form.register("min_voltage")} />
            </label>
            <label className="form-field">
              <span>Maximum voltage</span>
              <input inputMode="decimal" {...form.register("max_voltage")} />
            </label>
            <label className="form-field">
              <span>Declared temperature min (°C)</span>
              <input
                inputMode="decimal"
                {...form.register("declared_temp_min_c")}
              />
            </label>
            <label className="form-field">
              <span>Declared temperature max (°C)</span>
              <input
                inputMode="decimal"
                {...form.register("declared_temp_max_c")}
              />
            </label>
            <label className="form-field">
              <span>Software identifier</span>
              <input {...form.register("software_identifier")} />
            </label>
          </div>
        </section>

        {validation?.warnings.length ? (
          <div className="validation-panel">
            <strong>Configuration warnings</strong>
            <ul>
              {validation.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {validation?.regulatory_validation_status ===
        "TODO_REGULATORY_VALIDATION" ? (
          <RegulatoryBlocker ruleIds={validation.unresolved_rule_ids} />
        ) : null}

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
            {mutation.isPending
              ? "Validating & saving…"
              : "Validate & register"}
          </button>
        </div>
      </form>
    </div>
  );
}
