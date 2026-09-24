"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { Breadcrumbs } from "./breadcrumbs";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function AppShell({ children }: { children: ReactNode }) {
  const [navigationOpen, setNavigationOpen] = useState(false);

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
