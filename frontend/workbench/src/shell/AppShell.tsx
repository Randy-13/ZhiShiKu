import type { ReactNode } from "react";
import type { AuthContext } from "../api";
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
  queueLabel,
  queueStatus,
  children,
  onOpenQueue,
  authContext,
  onLogout,
  onOpenUserAdmin,
  onSelect,
}: {
  appName: string;
  appSubtitle: string;
  navItems: WorkspaceNavItem[];
  activeId: WorkspaceId;
  activeTitle: string;
  activeDescription: string;
  queueLabel: string;
  queueStatus: string;
  children: ReactNode;
  onOpenQueue: () => void;
  authContext: AuthContext;
  onLogout: () => void;
  onOpenUserAdmin: () => void;
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
          queueLabel={queueLabel}
          queueStatus={queueStatus}
          onOpenQueue={onOpenQueue}
          authContext={authContext}
          onLogout={onLogout}
          onOpenUserAdmin={onOpenUserAdmin}
        />
        {children}
      </main>
    </div>
  );
}
