export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type Address = {
  schema_version: 1;
  address_line1: string;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
};

export type ManufacturerCreate = {
  laboratory_id: string;
  name: string;
  registration_no: string | null;
  address: Address;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  country: string | null;
};

export type ManufacturerPatch = Omit<ManufacturerCreate, "laboratory_id">;

export type ManufacturerView = ManufacturerCreate & {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  is_active: boolean;
};

export type InstrumentMetadata = {
  is_direct_sales?: boolean | null;
  is_price_computing?: boolean | null;
  is_labeling?: boolean | null;
  data_storage_device_present?: boolean | null;
  battery_charging_during_operation?: boolean | null;
  vehicle_powered?: boolean | null;
  vehicle_power_details?: string | null;
  declared_operating_conditions?: string | null;
  declared_installation?: string | null;
};

export type AccuracyClass = "I" | "II" | "III" | "IIII";

export type InstrumentCreate = {
  laboratory_id: string;
  manufacturer_id: string;
  model_name: string;
  type_designation?: string | null;
  serial_number?: string | null;
  accuracy_class: AccuracyClass;
  min_capacity_g?: string | null;
  max_capacity_g: string;
  scale_interval_d_g: string;
  verification_interval_e_g: string;
  range_type?: string | null;
  indication_type?: string | null;
  is_self_indicating?: boolean | null;
  is_electronic?: boolean | null;
  is_software_controlled?: boolean | null;
  is_portable?: boolean | null;
  is_mobile?: boolean | null;
  load_receptor_type?: string | null;
  support_point_count?: number | null;
  tare_type?: string | null;
  maximum_tare_g?: string | null;
  zero_setting_type?: string | null;
  zero_tracking_available?: boolean | null;
  level_indicator_available?: boolean | null;
  automatic_tilt_sensor?: boolean | null;
  power_supply_type?: string | null;
  nominal_voltage?: string | null;
  min_voltage?: string | null;
  max_voltage?: string | null;
  declared_temp_min_c?: string | null;
  declared_temp_max_c?: string | null;
  software_identifier?: string | null;
  metadata_schema_version?: 1;
  metadata_json?: InstrumentMetadata;
};

export type InstrumentPatch = Partial<Omit<InstrumentCreate, "laboratory_id">>;

export type InstrumentView = InstrumentCreate & {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  verification_intervals_n: string;
  instrument_status: "ACTIVE" | "ARCHIVED";
};

export type ConfigurationValidation = {
  structural_valid: boolean;
  verification_intervals_n: string | null;
  errors: Array<{
    code: string;
    message: string;
    details: Record<string, unknown>;
  }>;
  warnings: string[];
  regulatory_validation_status: "TODO_REGULATORY_VALIDATION";
  unresolved_rule_ids: string[];
  regulatory_validation_performed: false;
};

export type RangeData = {
  range_no: number;
  min_capacity_g?: string | null;
  max_capacity_g: string;
  scale_interval_d_g: string;
  verification_interval_e_g: string;
};

export type RangeView = RangeData & {
  id: string;
  instrument_id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  is_active: boolean;
};

export type ComponentSpecifications = {
  schema_version?: 1;
  description?: string | null;
  rated_capacity_g?: string | null;
  nominal_voltage?: string | null;
  interface_type?: string | null;
  software_identifier?: string | null;
};

export type ComponentData = {
  component_type: string;
  manufacturer_name?: string | null;
  model?: string | null;
  serial_or_type?: string | null;
  certificate_reference?: string | null;
  technical_specifications?: ComponentSpecifications;
  notes?: string | null;
};

export type ComponentView = ComponentData & {
  id: string;
  instrument_id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  is_active: boolean;
};

export type EquipmentCreate = {
  laboratory_id: string;
  category: string;
  manufacturer?: string | null;
  model?: string | null;
  serial_number?: string | null;
  reference_number?: string | null;
  calibration_certificate_no?: string | null;
  calibration_date?: string | null;
  calibration_due_date?: string | null;
  accuracy_or_class?: string | null;
  metadata_schema_version?: 1;
  metadata_json?: {
    notes?: string | null;
    nominal_mass_g?: string | null;
    certificate_reference?: string | null;
  };
};

export type EquipmentPatch = Omit<EquipmentCreate, "laboratory_id">;

export type EquipmentView = EquipmentCreate & {
  id: string;
  lock_version: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  is_active: boolean;
};

export type Resource<T> = {
  item: T;
  etag: string | null;
  instrumentEtag?: string | null;
};

export function etagFromVersion(version: number): string {
  return `"${version}"`;
}
