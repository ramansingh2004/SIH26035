export type LaboratoryGrant = {
  laboratory_id: string;
  roles: string[];
  permissions: string[];
};

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  lock_version: number;
  last_login_at: string | null;
  global_roles: string[];
  global_permissions: string[];
  laboratories: LaboratoryGrant[];
};

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";
