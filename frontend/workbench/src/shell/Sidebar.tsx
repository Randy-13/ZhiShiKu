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
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">ZK</div>
        <div>
          <strong>{appName}</strong>
          <span>{appSubtitle}</span>
        </div>
      </div>
      <nav aria-label="Primary workspaces">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={item.id === activeId ? "nav-item active" : "nav-item"}
              type="button"
              key={item.id}
              onClick={() => onSelect(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
