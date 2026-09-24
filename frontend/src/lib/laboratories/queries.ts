import { apiRequest } from "@/lib/api/client";

import type { LaboratoryPage, LaboratoryView } from "./types";

const PAGE_SIZE = 100;

export async function getAccessibleLaboratories(
  grantedLaboratoryIds: string[],
): Promise<LaboratoryView[]> {
  if (grantedLaboratoryIds.length === 0) {
    return [];
  }

  const granted = new Set(grantedLaboratoryIds);
  const laboratories: LaboratoryView[] = [];
  let page = 1;

  while (true) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });

    const response = await apiRequest<LaboratoryPage>(
      `/api/v1/laboratories?${params.toString()}`,
    );

    laboratories.push(
      ...response.data.items.filter((laboratory) => granted.has(laboratory.id)),
    );

    if (page * response.data.page_size >= response.data.total) {
      break;
    }
    page += 1;
  }

  return laboratories.sort((left, right) =>
    left.code.localeCompare(right.code),
  );
}
