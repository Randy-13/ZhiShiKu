import { useCallback, useEffect, useState } from "react";
import type { LegacyStageId, WorkspaceId } from "../domain";

const legacyMap: Record<LegacyStageId, WorkspaceId> = {
  overview: "collect",
  inbox: "collect",
  packs: "library",
  processing: "learn",
  perspectives: "mine",
  review: "create",
};

const workspaceOrder: WorkspaceId[] = ["collect", "learn", "mine", "create", "library", "settings"];

function resolveWorkspaceRoute(route: string): WorkspaceId | undefined {
  if (workspaceOrder.includes(route as WorkspaceId)) return route as WorkspaceId;
  return legacyMap[route as LegacyStageId];
}

function currentBrowserRoute() {
  const hashRoute = window.location.hash.replace("#/", "").replace("#", "");
  const pathRoute = window.location.pathname.replace(/^\/+/, "").split("/")[0];
  return hashRoute || pathRoute;
}

export function useWorkspaceRoute(initialWorkspace: WorkspaceId = "collect") {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(initialWorkspace);

  useEffect(() => {
    const applyRoute = () => {
      const next = resolveWorkspaceRoute(currentBrowserRoute());
      if (next) setActiveWorkspace(next);
    };

    applyRoute();
    window.addEventListener("hashchange", applyRoute);
    window.addEventListener("popstate", applyRoute);
    return () => {
      window.removeEventListener("hashchange", applyRoute);
      window.removeEventListener("popstate", applyRoute);
    };
  }, []);

  const selectWorkspace = useCallback((id: WorkspaceId) => {
    setActiveWorkspace(id);
    window.history.replaceState(null, "", `#/${id}`);
  }, []);

  return { activeWorkspace, selectWorkspace };
}
