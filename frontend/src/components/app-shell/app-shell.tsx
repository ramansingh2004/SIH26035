"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { Breadcrumbs } from "./breadcrumbs";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: "auto",
    });
  }, [pathname]);

  return (
    <div className="app-layout">
      <Sidebar open={navigationOpen} onClose={() => setNavigationOpen(false)} />
      <div className="app-main">
        <Topbar onMenu={() => setNavigationOpen(true)} />
        <main className="content-area">
          <Breadcrumbs />
          {children}
        </main>
      </div>
    </div>
  );
}
