import { ListChecks } from "lucide-react";
import type { AuthContext } from "../api";
import { UserMenu } from "./UserMenu";

export function Topbar({
  title,
  description,
  queueLabel,
  queueStatus,
  onOpenQueue,
  authContext,
  onLogout,
  onOpenUserAdmin,
}: {
  title: string;
  description: string;
  queueLabel: string;
  queueStatus: string;
  onOpenQueue: () => void;
  authContext: AuthContext;
  onLogout: () => void;
  onOpenUserAdmin: () => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="topbar-actions">
        <button className="queue-chip" type="button" onClick={onOpenQueue}>
        <ListChecks size={15} aria-hidden="true" />
        <span>{queueLabel}</span>
        <strong>{queueStatus}</strong>
        </button>
        <UserMenu authContext={authContext} onLogout={onLogout} onOpenAdmin={onOpenUserAdmin} />
      </div>
    </header>
  );
}
