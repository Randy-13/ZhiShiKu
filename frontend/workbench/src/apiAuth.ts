import { requestJson, unwrapV2 } from "./apiCore";
import type { AuthAdminUser, AuthContext, AuthInvitation } from "./api";
import type { V2Payload } from "./apiCore";

export const authApi = {
  async me() {
    return unwrapV2(await requestJson<V2Payload<AuthContext>>("/api/auth/me"));
  },

  async login(identifier: string, password: string) {
    return unwrapV2(
      await requestJson<V2Payload<AuthContext>>("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      }),
    );
  },

  async registerWithInvite(input: { inviteCode: string; email: string; username: string; password: string }) {
    return unwrapV2(
      await requestJson<V2Payload<AuthContext>>("/api/auth/register-with-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          invite_code: input.inviteCode,
          email: input.email,
          username: input.username,
          password: input.password,
        }),
      }),
    );
  },

  async logout() {
    return unwrapV2(await requestJson<V2Payload<{ ok: boolean }>>("/api/auth/logout", { method: "POST" }));
  },

  async listUsers() {
    return unwrapV2(await requestJson<V2Payload<{ items: AuthAdminUser[] }>>("/api/auth/admin/users"));
  },

  async listInvitations() {
    return unwrapV2(await requestJson<V2Payload<{ items: AuthInvitation[] }>>("/api/auth/admin/invitations"));
  },

  async createInvitation(input: { role: string; maxUses: number; days: number }) {
    return unwrapV2(
      await requestJson<V2Payload<AuthInvitation>>("/api/auth/admin/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: input.role,
          max_uses: input.maxUses,
          days: input.days,
        }),
      }),
    );
  },

  async updateUserStatus(userId: string, status: "active" | "disabled") {
    return unwrapV2(
      await requestJson<V2Payload<{ item: AuthAdminUser }>>(`/api/auth/admin/users/${encodeURIComponent(userId)}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    );
  },
};
