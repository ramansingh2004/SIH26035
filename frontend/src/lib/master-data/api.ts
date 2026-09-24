import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";

import type {
  ComponentData,
  ComponentView,
  ConfigurationValidation,
  EquipmentCreate,
  EquipmentPatch,
  EquipmentView,
  InstrumentCreate,
  InstrumentPatch,
  InstrumentView,
  ManufacturerCreate,
  ManufacturerPatch,
  ManufacturerView,
  Page,
  RangeData,
  RangeView,
  Resource,
} from "./types";

function queryString(
  values: Record<string, string | number | boolean | null | undefined>,
) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export async function listManufacturers(input: {
  laboratoryId: string;
  page: number;
  pageSize?: number;
  search?: string;
  active?: boolean | null;
}): Promise<Page<ManufacturerView>> {
  const query = queryString({
    laboratory_id: input.laboratoryId,
    page: input.page,
    page_size: input.pageSize ?? 20,
    search: input.search,
    is_active: input.active,
  });
  return (
    await apiRequest<Page<ManufacturerView>>(`/api/v1/manufacturers?${query}`)
  ).data;
}

export async function allManufacturers(
  laboratoryId: string,
): Promise<ManufacturerView[]> {
  const items: ManufacturerView[] = [];
  let page = 1;
  while (true) {
    const result = await listManufacturers({
      laboratoryId,
      page,
      pageSize: 100,
      active: true,
    });
    items.push(...result.items);
    if (page * result.page_size >= result.total) break;
    page += 1;
  }
  return items;
}

export async function manufacturerDetail(
  id: string,
): Promise<Resource<ManufacturerView>> {
  const response = await apiRequest<ManufacturerView>(
    `/api/v1/manufacturers/${id}`,
  );
  return { item: response.data, etag: response.etag };
}

export async function createManufacturer(
  payload: ManufacturerCreate,
): Promise<Resource<ManufacturerView>> {
  const response = await apiRequest<ManufacturerView>("/api/v1/manufacturers", {
    method: "POST",
    body: payload,
    idempotencyKey: createIdempotencyKey(),
  });
  return { item: response.data, etag: response.etag };
}

export async function updateManufacturer(
  id: string,
  payload: ManufacturerPatch,
  etag: string,
): Promise<Resource<ManufacturerView>> {
  const response = await apiRequest<ManufacturerView>(
    `/api/v1/manufacturers/${id}`,
    { method: "PATCH", body: payload, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function archiveManufacturer(
  id: string,
  reason: string,
  etag: string,
): Promise<Resource<ManufacturerView>> {
  const response = await apiRequest<ManufacturerView>(
    `/api/v1/manufacturers/${id}/archive`,
    {
      method: "POST",
      body: { reason },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function listInstruments(input: {
  laboratoryId: string;
  page: number;
  pageSize?: number;
  search?: string;
  status?: "ACTIVE" | "ARCHIVED" | "";
}): Promise<Page<InstrumentView>> {
  const query = queryString({
    laboratory_id: input.laboratoryId,
    page: input.page,
    page_size: input.pageSize ?? 20,
    search: input.search,
    instrument_status: input.status,
  });
  return (
    await apiRequest<Page<InstrumentView>>(`/api/v1/instruments?${query}`)
  ).data;
}

export async function instrumentDetail(
  id: string,
): Promise<Resource<InstrumentView>> {
  const response = await apiRequest<InstrumentView>(
    `/api/v1/instruments/${id}`,
  );
  return { item: response.data, etag: response.etag };
}

export async function validateInstrumentConfiguration(
  payload: InstrumentCreate,
): Promise<ConfigurationValidation> {
  return (
    await apiRequest<ConfigurationValidation>(
      "/api/v1/instruments/validate-configuration",
      {
        method: "POST",
        body: { ...payload, ranges: [], components: [] },
        idempotencyKey: createIdempotencyKey(),
      },
    )
  ).data;
}

export async function createInstrument(
  payload: InstrumentCreate,
): Promise<Resource<InstrumentView>> {
  const response = await apiRequest<InstrumentView>("/api/v1/instruments", {
    method: "POST",
    body: payload,
    idempotencyKey: createIdempotencyKey(),
  });
  return { item: response.data, etag: response.etag };
}

export async function updateInstrument(
  id: string,
  payload: InstrumentPatch,
  etag: string,
): Promise<Resource<InstrumentView>> {
  const response = await apiRequest<InstrumentView>(
    `/api/v1/instruments/${id}`,
    { method: "PATCH", body: payload, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function archiveInstrument(
  id: string,
  reason: string,
  etag: string,
): Promise<Resource<InstrumentView>> {
  const response = await apiRequest<InstrumentView>(
    `/api/v1/instruments/${id}/archive`,
    {
      method: "POST",
      body: { reason },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}

export async function listRanges(
  instrumentId: string,
  includeArchived = false,
): Promise<{ page: Page<RangeView>; etag: string | null }> {
  const query = queryString({
    page: 1,
    page_size: 100,
    include_archived: includeArchived,
  });
  const response = await apiRequest<Page<RangeView>>(
    `/api/v1/instruments/${instrumentId}/ranges?${query}`,
  );
  return { page: response.data, etag: response.etag };
}

export async function createRange(
  instrumentId: string,
  payload: RangeData,
  parentEtag: string,
): Promise<Resource<RangeView>> {
  const response = await apiRequest<RangeView>(
    `/api/v1/instruments/${instrumentId}/ranges`,
    { method: "POST", body: payload, etag: parentEtag },
  );
  return {
    item: response.data,
    etag: response.etag,
    instrumentEtag: response.instrumentEtag,
  };
}

export async function updateRange(
  instrumentId: string,
  rangeId: string,
  payload: Partial<RangeData>,
  childEtag: string,
): Promise<Resource<RangeView>> {
  const response = await apiRequest<RangeView>(
    `/api/v1/instruments/${instrumentId}/ranges/${rangeId}`,
    { method: "PATCH", body: payload, etag: childEtag },
  );
  return {
    item: response.data,
    etag: response.etag,
    instrumentEtag: response.instrumentEtag,
  };
}

export async function archiveRange(
  instrumentId: string,
  rangeId: string,
  reason: string,
  childEtag: string,
): Promise<string | null> {
  const query = queryString({ reason });
  const response = await apiRequest<void>(
    `/api/v1/instruments/${instrumentId}/ranges/${rangeId}?${query}`,
    { method: "DELETE", etag: childEtag },
  );
  return response.instrumentEtag;
}

export async function listComponents(
  instrumentId: string,
  includeArchived = false,
): Promise<{ page: Page<ComponentView>; etag: string | null }> {
  const query = queryString({
    page: 1,
    page_size: 100,
    include_archived: includeArchived,
  });
  const response = await apiRequest<Page<ComponentView>>(
    `/api/v1/instruments/${instrumentId}/components?${query}`,
  );
  return { page: response.data, etag: response.etag };
}

export async function createComponent(
  instrumentId: string,
  payload: ComponentData,
  parentEtag: string,
): Promise<Resource<ComponentView>> {
  const response = await apiRequest<ComponentView>(
    `/api/v1/instruments/${instrumentId}/components`,
    { method: "POST", body: payload, etag: parentEtag },
  );
  return {
    item: response.data,
    etag: response.etag,
    instrumentEtag: response.instrumentEtag,
  };
}

export async function updateComponent(
  instrumentId: string,
  componentId: string,
  payload: Partial<ComponentData>,
  childEtag: string,
): Promise<Resource<ComponentView>> {
  const response = await apiRequest<ComponentView>(
    `/api/v1/instruments/${instrumentId}/components/${componentId}`,
    { method: "PATCH", body: payload, etag: childEtag },
  );
  return {
    item: response.data,
    etag: response.etag,
    instrumentEtag: response.instrumentEtag,
  };
}

export async function archiveComponent(
  instrumentId: string,
  componentId: string,
  reason: string,
  childEtag: string,
): Promise<string | null> {
  const query = queryString({ reason });
  const response = await apiRequest<void>(
    `/api/v1/instruments/${instrumentId}/components/${componentId}?${query}`,
    { method: "DELETE", etag: childEtag },
  );
  return response.instrumentEtag;
}

export async function listEquipment(input: {
  laboratoryId: string;
  page: number;
  pageSize?: number;
  active?: boolean | null;
}): Promise<Page<EquipmentView>> {
  const query = queryString({
    laboratory_id: input.laboratoryId,
    page: input.page,
    page_size: input.pageSize ?? 20,
    is_active: input.active,
  });
  return (
    await apiRequest<Page<EquipmentView>>(`/api/v1/test-equipment?${query}`)
  ).data;
}

export async function equipmentDetail(
  id: string,
): Promise<Resource<EquipmentView>> {
  const response = await apiRequest<EquipmentView>(
    `/api/v1/test-equipment/${id}`,
  );
  return { item: response.data, etag: response.etag };
}

export async function createEquipment(
  payload: EquipmentCreate,
): Promise<Resource<EquipmentView>> {
  const response = await apiRequest<EquipmentView>("/api/v1/test-equipment", {
    method: "POST",
    body: payload,
    idempotencyKey: createIdempotencyKey(),
  });
  return { item: response.data, etag: response.etag };
}

export async function updateEquipment(
  id: string,
  payload: EquipmentPatch,
  etag: string,
): Promise<Resource<EquipmentView>> {
  const response = await apiRequest<EquipmentView>(
    `/api/v1/test-equipment/${id}`,
    { method: "PATCH", body: payload, etag },
  );
  return { item: response.data, etag: response.etag };
}

export async function archiveEquipment(
  id: string,
  reason: string,
  etag: string,
): Promise<Resource<EquipmentView>> {
  const response = await apiRequest<EquipmentView>(
    `/api/v1/test-equipment/${id}/archive`,
    {
      method: "POST",
      body: { reason },
      etag,
      idempotencyKey: createIdempotencyKey(),
    },
  );
  return { item: response.data, etag: response.etag };
}
