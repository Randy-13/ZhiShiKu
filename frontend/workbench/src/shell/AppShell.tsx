import type { ReactNode } from "react";
import type { WorkspaceId, WorkspaceNavItem } from "../domain";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({
  appName,
  appSubtitle,
  navItems,
  activeId,
  activeTitle,
  activeDescription,
  searchPlaceholder,
  importLabel,
  queueLabel,
  queueStatus,
  search,
  children,
  onSearchChange,
  onImport,
  onSelect,
}: {
  appName: string;
  appSubtitle: string;
  navItems: WorkspaceNavItem[];
  activeId: WorkspaceId;
  activeTitle: string;
  activeDescription: string;
  searchPlaceholder: string;
  importLabel: string;
  queueLabel: string;
  queueStatus: string;
  search: string;
  children: ReactNode;
  onSearchChange: (value: string) => void;
  onImport: () => void;
  onSelect: (id: WorkspaceId) => void;
}) {
  return (
    <div className="app-shell">
      <Sidebar
        appName={appName}
        appSubtitle={appSubtitle}
        items={navItems}
        activeId={activeId}
        onSelect={onSelect}
      />
      <main className="main-shell">
        <Topbar
          title={activeTitle}
          description={activeDescription}
          searchPlaceholder={searchPlaceholder}
          importLabel={importLabel}
          queueLabel={queueLabel}
          queueStatus={queueStatus}
          search={search}
          onSearchChange={onSearchChange}
          onImport={onImport}
        />
        {children}
      </main>
    </div>
  );
}
