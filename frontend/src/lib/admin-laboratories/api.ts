import { apiRequest } from "@/lib/api/client";
import type {
  LaboratoryPage,
  LaboratoryView,
} from "@/lib/laboratories/types";

import type {
  LaboratoryCreate,
  LaboratoryPatch,
  LaboratoryResource,
} from "./types";

function lockVersionEtag(lockVersion: number): string {
  return `"${lockVersion}"`;
}

export async function listLaboratories(input: {
  page: number;
  pageSize?: number;
}): Promise<LaboratoryPage> {
  const params = new URLSearchParams({
    page: String(input.page),
    page_size: String(input.pageSize ?? 20),
  });

  return (
    await apiRequest<LaboratoryPage>(
      `/api/v1/laboratories?${params.toString()}`,
    )
  ).data;
}

export async function laboratoryDetail(
  laboratoryId: string,
): Promise<LaboratoryResource> {
  const response = await apiRequest<LaboratoryView>(
    `/api/v1/laboratories/${laboratoryId}`,
  );

  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}

export async function createLaboratory(
  payload: LaboratoryCreate,
): Promise<LaboratoryResource> {
  const response = await apiRequest<LaboratoryView>("/api/v1/laboratories", {
    method: "POST",
    body: payload,
  });

  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}

export async function updateLaboratory(
  laboratoryId: string,
  payload: LaboratoryPatch,
  etag: string,
): Promise<LaboratoryResource> {
  const response = await apiRequest<LaboratoryView>(
    `/api/v1/laboratories/${laboratoryId}`,
    {
      method: "PATCH",
      body: payload,
      etag,
    },
  );

  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}
