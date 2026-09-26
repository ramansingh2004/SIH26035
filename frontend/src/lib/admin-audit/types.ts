import type { LaboratoryView } from "@/lib/laboratories/types";

export type AuditActorType = "USER" | "SYSTEM" | "ANONYMOUS";

export type AuditEventView = {
  id: string;
  actor_id: string | null;
  actor_type: AuditActorType;
  laboratory_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  source_revision: number | null;
  target_revision: number | null;
  request_id: string;
  correlation_id: string;
  reason: string | null;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
};

export type AuditEventPage = {
  items: AuditEventView[];
  page: number;
  page_size: number;
  total: number;
};

export type AuditFilters = {
  laboratoryId: string;
  entityType: string;
  entityId: string;
  since: string;
  until: string;
};

export type AuditLaboratory = Pick<
  LaboratoryView,
  "id" | "name" | "code" | "is_active"
>;
