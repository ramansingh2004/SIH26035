export type LaboratoryView = {
  id: string;
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
  is_active: boolean;
  lock_version: number;
  logo_attachment_id: string | null;
};

export type LaboratoryPage = {
  items: LaboratoryView[];
  page: number;
  page_size: number;
  total: number;
};
