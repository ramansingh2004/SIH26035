import { EmptyState } from "@/components/ui/empty-state";

export function MasterPermissionState({ resource }: { resource: string }) {
  return (
    <EmptyState
      title={`No ${resource} access`}
      description="Your current laboratory assignment does not grant access to this master-data area."
    />
  );
}
