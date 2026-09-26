import { apiRequest } from "@/lib/api/client";
import type { LaboratoryPage, LaboratoryView } from "@/lib/laboratories/types";

import type {
  AdminUserResource,
  AssignmentCreate,
  AssignmentPage,
  AssignmentView,
  RolePage,
  RoleView,
  UserCreate,
  UserPage,
  UserPatch,
  UserView,
} from "./types";

function queryString(
  values: Record<string, string | number | boolean | null | undefined>,
): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export function lockVersionEtag(lockVersion: number): string {
  return `"${lockVersion}"`;
}

export async function listUsers(input: {
  page: number;
  pageSize?: number;
  laboratoryId?: string | null;
  role?: string;
  active?: boolean | null;
  search?: string;
}): Promise<UserPage> {
  const query = queryString({
    page: input.page,
    page_size: input.pageSize ?? 20,
    laboratory_id: input.laboratoryId,
    role: input.role,
    active: input.active,
    search: input.search,
  });

  return (await apiRequest<UserPage>(`/api/v1/users?${query}`)).data;
}

export async function adminUser(userId: string): Promise<AdminUserResource> {
  let page = 1;

  while (true) {
    const result = await listUsers({ page, pageSize: 100 });
    const item = result.items.find((candidate) => candidate.id === userId);
    if (item) {
      return { item, etag: lockVersionEtag(item.lock_version) };
    }

    if (page * result.page_size >= result.total) {
      throw new Error("The requested user is not visible in your administrative scope.");
    }
    page += 1;
  }
}

export async function createUser(
  payload: UserCreate,
): Promise<AdminUserResource> {
  const response = await apiRequest<UserView>("/api/v1/users", {
    method: "POST",
    body: payload,
  });
  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}

export async function updateUser(
  userId: string,
  payload: UserPatch,
  etag: string,
): Promise<AdminUserResource> {
  const response = await apiRequest<UserView>(`/api/v1/users/${userId}`, {
    method: "PATCH",
    body: payload,
    etag,
  });
  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}

export async function resetUserPassword(
  userId: string,
  newPassword: string,
  etag: string,
): Promise<void> {
  await apiRequest<void>(`/api/v1/users/${userId}/reset-password`, {
    method: "POST",
    body: { new_password: newPassword },
    etag,
  });
}

export async function listAssignments(
  userId: string,
): Promise<AssignmentView[]> {
  const items: AssignmentView[] = [];
  let page = 1;

  while (true) {
    const response = await apiRequest<AssignmentPage>(
      `/api/v1/users/${userId}/role-assignments?page=${page}&page_size=100`,
    );
    items.push(...response.data.items);

    if (page * response.data.page_size >= response.data.total) {
      break;
    }
    page += 1;
  }

  return items;
}

export async function grantAssignment(
  userId: string,
  payload: AssignmentCreate,
  userEtag: string,
): Promise<AssignmentView> {
  const response = await apiRequest<AssignmentView>(
    `/api/v1/users/${userId}/role-assignments`,
    {
      method: "POST",
      body: payload,
      etag: userEtag,
    },
  );
  return response.data;
}

export async function revokeAssignment(
  userId: string,
  assignmentId: string,
  assignmentLockVersion: number,
  reason: string,
): Promise<void> {
  const query = queryString({ reason });
  await apiRequest<void>(
    `/api/v1/users/${userId}/role-assignments/${assignmentId}?${query}`,
    {
      method: "DELETE",
      etag: lockVersionEtag(assignmentLockVersion),
    },
  );
}

export async function listRoles(): Promise<RoleView[]> {
  const response = await apiRequest<RolePage>(
    "/api/v1/roles?page=1&page_size=100",
  );
  return response.data.items;
}

export async function listAdministrativeLaboratories(): Promise<
  LaboratoryView[]
> {
  const items: LaboratoryView[] = [];
  let page = 1;

  while (true) {
    const response = await apiRequest<LaboratoryPage>(
      `/api/v1/laboratories?page=${page}&page_size=100`,
    );
    items.push(...response.data.items);

    if (page * response.data.page_size >= response.data.total) {
      break;
    }
    page += 1;
  }

  return items.sort((left, right) => left.code.localeCompare(right.code));
}
