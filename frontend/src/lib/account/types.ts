import type { AuthUser } from "@/lib/auth/types";

export type AccountResource = {
  item: AuthUser;
  etag: string;
};

export type SessionFamilyView = {
  family_id: string;
  created_at: string;
  expires_at: string;
  family_expires_at: string;
  is_active: boolean;
  client_ip: string | null;
  user_agent: string | null;
  etag: string;
};

export type SessionFamilyPage = {
  items: SessionFamilyView[];
  page: number;
  page_size: number;
  total: number;
};

export type PasswordChangeInput = {
  currentPassword: string;
  newPassword: string;
  etag: string;
};
