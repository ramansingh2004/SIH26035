import type { LaboratoryView } from "@/lib/laboratories/types";

export type LaboratoryCreate = {
  name: string;
  code: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
  email: string;
  accreditation_no: string;
  timezone: string;
};

export type LaboratoryPatch = {
  name?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  phone?: string;
  email?: string;
  accreditation_no?: string;
  timezone?: string;
  is_active?: boolean;
};

export type LaboratoryResource = {
  item: LaboratoryView;
  etag: string;
};
