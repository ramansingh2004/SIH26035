import { apiRequest } from "@/lib/api/client";
import type { AuthUser } from "@/lib/auth/types";

import type {
  AccountResource,
  PasswordChangeInput,
  SessionFamilyPage,
} from "./types";

function lockVersionEtag(lockVersion: number): string {
  return `"${lockVersion}"`;
}

export async function accountMe(): Promise<AccountResource> {
  const response = await apiRequest<AuthUser>("/api/v1/auth/me");

  return {
    item: response.data,
    etag: response.etag ?? lockVersionEtag(response.data.lock_version),
  };
}

export async function listAccountSessions(
  page: number,
  pageSize = 20,
): Promise<SessionFamilyPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return (
    await apiRequest<SessionFamilyPage>(
      `/api/v1/auth/sessions?${params.toString()}`,
    )
  ).data;
}

export async function revokeAccountSession(
  familyId: string,
  etag: string,
): Promise<void> {
  await apiRequest<void>(`/api/v1/auth/sessions/${familyId}`, {
    method: "DELETE",
    etag,
  });
}

export async function changeOwnPassword(
  input: PasswordChangeInput,
): Promise<void> {
  await apiRequest<void>("/api/v1/auth/password", {
    method: "POST",
    body: {
      current_password: input.currentPassword,
      new_password: input.newPassword,
    },
    etag: input.etag,
  });
}
