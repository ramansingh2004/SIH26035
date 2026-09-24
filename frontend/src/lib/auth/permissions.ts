import type { AuthUser } from "./types";

export function laboratoryGrant(
  user: AuthUser | null,
  laboratoryId: string | null,
) {
  if (!user || !laboratoryId) {
    return null;
  }
  return (
    user.laboratories.find((item) => item.laboratory_id === laboratoryId) ??
    null
  );
}

export function hasPermission(
  user: AuthUser | null,
  permission: string,
  laboratoryId: string | null,
): boolean {
  if (!user) {
    return false;
  }

  if (user.global_permissions.includes(permission)) {
    return true;
  }

  const grant = laboratoryGrant(user, laboratoryId);
  return grant?.permissions.includes(permission) ?? false;
}
