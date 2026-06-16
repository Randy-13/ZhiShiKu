import { Copy, RefreshCw, ShieldCheck, Ticket, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { authApi } from "../api";
import type { AuthAdminUser, AuthContext, AuthInvitation } from "../api";

export function UserAdminPanel({
  authContext,
  isOpen,
  onClose,
}: {
  authContext: AuthContext;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [users, setUsers] = useState<AuthAdminUser[]>([]);
  const [invitations, setInvitations] = useState<AuthInvitation[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCreatingInvite, setIsCreatingInvite] = useState(false);
  const [role, setRole] = useState("member");
  const [maxUses, setMaxUses] = useState(1);
  const [days, setDays] = useState(14);

  const currentUserId = authContext.user?.id;
  const activeUsers = useMemo(() => users.filter((user) => user.status === "active").length, [users]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const [userPayload, invitationPayload] = await Promise.all([
        authApi.listUsers(),
        authApi.listInvitations(),
      ]);
      setUsers(userPayload.items);
      setInvitations(invitationPayload.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "用户管理数据加载失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) refresh();
  }, [isOpen, refresh]);

  if (!isOpen) return null;

  async function createInvite() {
    setIsCreatingInvite(true);
    setError("");
    setMessage("");
    try {
      const invitation = await authApi.createInvitation({ role, maxUses, days });
      setInvitations((current) => [invitation, ...current]);
      setMessage(`已创建邀请码：${invitation.code}`);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "邀请码创建失败");
    } finally {
      setIsCreatingInvite(false);
    }
  }

  async function toggleUserStatus(user: AuthAdminUser) {
    const nextStatus = user.status === "active" ? "disabled" : "active";
    setError("");
    setMessage("");
    try {
      const payload = await authApi.updateUserStatus(user.id, nextStatus);
      setUsers((current) => current.map((item) => (item.id === user.id ? payload.item : item)));
      setMessage(`${user.username} 已${nextStatus === "active" ? "启用" : "停用"}`);
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "用户状态更新失败");
    }
  }

  async function copyInvite(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setMessage(`已复制邀请码：${code}`);
    } catch {
      setMessage(`邀请码：${code}`);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="modal-panel user-admin-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-admin-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-title-row">
          <div>
            <span>Cloud 管理</span>
            <h2 id="user-admin-title">用户与邀请码</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="user-admin-summary">
          <article>
            <ShieldCheck size={18} aria-hidden="true" />
            <span>活跃用户</span>
            <strong>{activeUsers}</strong>
          </article>
          <article>
            <Ticket size={18} aria-hidden="true" />
            <span>可用邀请码</span>
            <strong>{invitations.filter((item) => item.status === "active" && item.usedCount < item.maxUses).length}</strong>
          </article>
          <button className="secondary-button" type="button" onClick={refresh} disabled={isLoading}>
            <RefreshCw size={16} aria-hidden="true" />
            <span>{isLoading ? "刷新中" : "刷新"}</span>
          </button>
        </div>

        {error ? <p className="auth-error">{error}</p> : null}
        {message ? <p className="user-admin-message">{message}</p> : null}

        <div className="user-admin-grid">
          <section className="user-admin-section">
            <div className="section-heading">
              <h3>用户</h3>
              <span>{users.length} 个账号</span>
            </div>
            <div className="admin-user-list">
              {users.map((user) => (
                <article className="admin-user-row" key={user.id}>
                  <span className="user-avatar">{initials(user.username)}</span>
                  <div>
                    <strong>{user.username}</strong>
                    <span>{user.email}</span>
                    <small>{user.role === "admin" ? "管理员" : "成员"} · {user.status === "active" ? "启用" : "停用"}</small>
                  </div>
                  <button
                    className={user.status === "active" ? "secondary-button danger-button" : "secondary-button"}
                    type="button"
                    disabled={user.id === currentUserId && user.status === "active"}
                    onClick={() => toggleUserStatus(user)}
                    title={user.id === currentUserId ? "不能停用当前账号" : undefined}
                  >
                    {user.status === "active" ? "停用" : "启用"}
                  </button>
                </article>
              ))}
            </div>
          </section>

          <section className="user-admin-section">
            <div className="section-heading">
              <h3>邀请码</h3>
              <span>用于新增内测账号</span>
            </div>
            <div className="invite-create-form">
              <label>
                <span>角色</span>
                <select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="member">成员</option>
                  <option value="admin">管理员</option>
                </select>
              </label>
              <label>
                <span>可用次数</span>
                <input type="number" min={1} max={100} value={maxUses} onChange={(event) => setMaxUses(Number(event.target.value) || 1)} />
              </label>
              <label>
                <span>有效天数</span>
                <input type="number" min={1} max={365} value={days} onChange={(event) => setDays(Number(event.target.value) || 14)} />
              </label>
              <button className="primary-cta" type="button" onClick={createInvite} disabled={isCreatingInvite}>
                <Ticket size={16} aria-hidden="true" />
                <span>{isCreatingInvite ? "创建中" : "创建邀请码"}</span>
              </button>
            </div>
            <div className="admin-invite-list">
              {invitations.map((invitation) => (
                <article className="admin-invite-row" key={invitation.id}>
                  <div>
                    <strong>{invitation.code}</strong>
                    <span>
                      {invitation.role} · {invitation.usedCount}/{invitation.maxUses} · {invitation.status}
                    </span>
                  </div>
                  <button className="icon-button" type="button" onClick={() => copyInvite(invitation.code)} aria-label="复制邀请码">
                    <Copy size={15} aria-hidden="true" />
                  </button>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function initials(value: string) {
  return (value.trim().slice(0, 2) || "ZK").toUpperCase();
}
