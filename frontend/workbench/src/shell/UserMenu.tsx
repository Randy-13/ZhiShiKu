import { LogOut, Shield, UserRound, UsersRound } from "lucide-react";
import { useState } from "react";
import type { AuthContext } from "../api";

export function UserMenu({
  authContext,
  onLogout,
  onOpenAdmin,
}: {
  authContext: AuthContext;
  onLogout: () => void;
  onOpenAdmin: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const user = authContext.user;
  const workspace = authContext.workspace;
  const isAdmin = user?.role === "admin";
  const modeLabel = authContext.deploymentMode === "cloud" ? "Cloud" : "Local";

  if (!user) return null;

  return (
    <div className="user-menu">
      <button
        className="user-menu-trigger"
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
        title={`${user.username} · ${modeLabel}`}
      >
        <UserRound size={16} aria-hidden="true" />
        <span>
          <strong>{user.username}</strong>
          <small>{modeLabel}</small>
        </span>
      </button>
      {isOpen ? (
        <div className="user-menu-popover">
          <div className="user-menu-card">
            <span className="user-avatar">{initials(user.username)}</span>
            <div>
              <strong>{user.username}</strong>
              <span>{user.email}</span>
            </div>
          </div>
          <div className="user-menu-meta">
            <span>
              <Shield size={14} aria-hidden="true" />
              {isAdmin ? "管理员" : "成员"}
            </span>
            <span>{workspace?.name || "默认工作台"}</span>
          </div>
          {isAdmin ? (
            <button
              className="user-menu-action"
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenAdmin();
              }}
            >
              <UsersRound size={15} aria-hidden="true" />
              <span>用户管理</span>
            </button>
          ) : null}
          <button
            className="user-menu-action danger"
            type="button"
            onClick={() => {
              setIsOpen(false);
              onLogout();
            }}
          >
            <LogOut size={15} aria-hidden="true" />
            <span>{authContext.deploymentMode === "cloud" ? "退出登录" : "结束本地会话"}</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}

function initials(value: string) {
  return (value.trim().slice(0, 2) || "ZK").toUpperCase();
}
