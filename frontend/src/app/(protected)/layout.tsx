import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell/app-shell";
import { AuthGate } from "@/components/auth/auth-gate";

export default function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
