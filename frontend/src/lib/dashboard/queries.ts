import { apiRequest } from "@/lib/api/client";

import type { DashboardSummary } from "./types";

export async function getDashboardSummary(
  laboratoryId: string,
): Promise<DashboardSummary> {
  const params = new URLSearchParams({
    laboratory_id: laboratoryId,
    page: "1",
    page_size: "8",
  });

  const response = await apiRequest<DashboardSummary>(
    `/api/v1/dashboard/summary?${params.toString()}`,
  );
  return response.data;
}
