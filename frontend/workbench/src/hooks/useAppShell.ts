import { BookOpen, Boxes, Cog, Feather, Inbox, Pickaxe } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { appShellApi } from "../apiAppShell";
import type { AppShellPayload, AppShellSection } from "../apiAppShell";
import type { WorkspaceId, WorkspaceNavItem } from "../domain";
import type { Translator } from "../i18n";

const workspaceOrder: WorkspaceId[] = ["collect", "learn", "mine", "create", "library", "settings"];
const workspaceIds = new Set<string>(workspaceOrder);
const workspaceIcons = {
  collect: Inbox,
  learn: BookOpen,
  mine: Pickaxe,
  create: Feather,
  library: Boxes,
  settings: Cog,
};

export function useAppShell(t: Translator) {
  const [payload, setPayload] = useState<AppShellPayload>();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    appShellApi
      .get()
      .then((next) => {
        if (cancelled) return;
        setPayload(next);
        setError("");
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(caught instanceof Error ? caught.message : "App shell load failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const navItems = useMemo<WorkspaceNavItem[]>(() => {
    const fallback = fallbackNavItems(t);
    const sections = payload?.primarySections ?? [];
    if (!sections.length) return fallback;

    const byId = new Map(fallback.map((item) => [item.id, item]));
    for (const section of sections) {
      const id = normalizeWorkspaceId(section.id);
      if (!id) continue;
      byId.set(id, toNavItem(section, byId.get(id) ?? fallbackNavItem(id, t)));
    }

    return workspaceOrder
      .map((id) => byId.get(id))
      .filter((item): item is WorkspaceNavItem => Boolean(item));
  }, [payload?.primarySections, t]);

  return {
    appShell: payload,
    appShellError: error,
    navItems,
  };
}

function fallbackNavItems(t: Translator): WorkspaceNavItem[] {
  return workspaceOrder.map((id) => fallbackNavItem(id, t));
}

function fallbackNavItem(id: WorkspaceId, t: Translator): WorkspaceNavItem {
  return {
    id,
    label: t(`workspace.${id}`),
    description: t(`workspace.${id}.desc`),
    icon: workspaceIcons[id],
  };
}

function toNavItem(section: AppShellSection, fallback: WorkspaceNavItem): WorkspaceNavItem {
  return {
    id: fallback.id,
    label: section.navLabel || fallback.label,
    description: section.navDescription || fallback.description,
    icon: fallback.icon,
  };
}

function normalizeWorkspaceId(value: string): WorkspaceId | undefined {
  return workspaceIds.has(value) ? (value as WorkspaceId) : undefined;
}
