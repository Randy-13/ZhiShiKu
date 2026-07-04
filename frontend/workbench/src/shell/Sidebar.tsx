import type { WorkspaceId, WorkspaceNavItem } from "../domain";

export function Sidebar({
  appName,
  appSubtitle,
  items,
  activeId,
  onSelect,
}: {
  appName: string;
  appSubtitle: string;
  items: WorkspaceNavItem[];
  activeId: WorkspaceId;
  onSelect: (id: WorkspaceId) => void;
}) {
  const primaryItems = items.filter((item) => item.id !== "docs");
  const utilityItems = items.filter((item) => item.id === "docs");

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">ZK</div>
        <div>
          <strong>{appName}</strong>
          <span>{appSubtitle}</span>
        </div>
      </div>
      <nav className="sidebar-primary-nav" aria-label="Primary workspaces">
        {primaryItems.map((item) => (
          <SidebarNavButton
            item={item}
            activeId={activeId}
            key={item.id}
            onSelect={onSelect}
          />
        ))}
      </nav>
      {utilityItems.length ? (
        <nav className="sidebar-bottom-nav" aria-label="Documentation">
          {utilityItems.map((item) => (
            <SidebarNavButton
              item={item}
              activeId={activeId}
              key={item.id}
              onSelect={onSelect}
            />
          ))}
        </nav>
      ) : null}
    </aside>
  );
}

function SidebarNavButton({
  item,
  activeId,
  onSelect,
}: {
  item: WorkspaceNavItem;
  activeId: WorkspaceId;
  onSelect: (id: WorkspaceId) => void;
}) {
  const Icon = item.icon;
  return (
    <button
      className={item.id === activeId ? "nav-item active" : "nav-item"}
      type="button"
      onClick={() => onSelect(item.id)}
    >
      <Icon size={18} />
      <span>{item.label}</span>
    </button>
  );
}
