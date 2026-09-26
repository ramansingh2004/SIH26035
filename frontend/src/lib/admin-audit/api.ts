import { apiRequest } from "@/lib/api/client";
import type {
  LaboratoryPage,
  LaboratoryView,
} from "@/lib/laboratories/types";

import type {
  AuditEventPage,
  AuditFilters,
  AuditLaboratory,
} from "./types";

function awareDateTime(value: string): string | undefined {
  if (!value) return undefined;
  return new Date(value).toISOString();
}

function queryString(
  values: Record<string, string | number | undefined>,
): string {
  const params = new URLSearchParams();

  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });

  return params.toString();
}

export async function listAuditEvents(input: {
  page: number;
  pageSize?: number;
  filters: AuditFilters;
}): Promise<AuditEventPage> {
  const query = queryString({
    page: input.page,
    page_size: input.pageSize ?? 20,
    laboratory_id: input.filters.laboratoryId || undefined,
    entity_type: input.filters.entityType.trim() || undefined,
    entity_id: input.filters.entityId.trim() || undefined,
    since: awareDateTime(input.filters.since),
    until: awareDateTime(input.filters.until),
  });

  return (
    await apiRequest<AuditEventPage>(`/api/v1/audit-events?${query}`)
  ).data;
}

export async function listAuditLaboratories(): Promise<AuditLaboratory[]> {
  const laboratories: LaboratoryView[] = [];
  let page = 1;

  while (true) {
    const response = await apiRequest<LaboratoryPage>(
      `/api/v1/laboratories?page=${page}&page_size=100`,
    );

    laboratories.push(...response.data.items);

    if (page * response.data.page_size >= response.data.total) {
      break;
    }
    page += 1;
  }

  return laboratories
    .map(({ id, name, code, is_active }) => ({
      id,
      name,
      code,
      is_active,
    }))
    .sort((left, right) => left.code.localeCompare(right.code));
}
