export const ROLE_CODES = [
  "ADMIN",
  "LAB_TECHNICIAN",
  "LAB_ENGINEER",
  "REVIEWER",
  "APPROVING_OFFICER",
  "VIEWER",
] as const;

export type RoleCode = (typeof ROLE_CODES)[number];
export type AssignmentScope = "GLOBAL" | "LABORATORY";

export const ROLE_LABELS: Record<RoleCode, string> = {
  ADMIN: "Administrator",
  LAB_TECHNICIAN: "Lab technician",
  LAB_ENGINEER: "Lab engineer",
  REVIEWER: "Reviewer",
  APPROVING_OFFICER: "Approving officer",
  VIEWER: "Viewer",
};

export type UserView = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  lock_version: number;
  last_login_at: string | null;
};

export type UserPage = {
  items: UserView[];
  page: number;
  page_size: number;
  total: number;
};

export type UserCreate = {
  email: string;
  full_name: string;
  password: string;
  initial_assignment: AssignmentCreate;
};

export type UserPatch = {
  full_name?: string;
  is_active?: boolean;
};

export type AssignmentCreate = {
  role_code: RoleCode;
  scope_type: AssignmentScope;
  laboratory_id: string | null;
};

export type AssignmentView = {
  id: string;
  user_id: string;
  role_id: string;
  scope_type: AssignmentScope;
  laboratory_id: string | null;
  assigned_by: string;
  assigned_at: string;
  revoked_by: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
  lock_version: number;
};

export type AssignmentPage = {
  items: AssignmentView[];
  page: number;
  page_size: number;
  total: number;
};

export type RoleView = {
  id: string;
  code: RoleCode;
  name: string;
  global_permissions: string[];
  laboratory_permissions: string[];
};

export type RolePage = {
  items: RoleView[];
  page: number;
  page_size: number;
  total: number;
};

export type AdminUserResource = {
  item: UserView;
  etag: string;
};
