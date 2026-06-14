import { requestJson, unwrapV2 } from "./apiCore";
import type { V2Payload } from "./apiCore";

export type AppShellSection = {
  id: string;
  label?: string;
  navLabel?: string;
  navDescription?: string;
  route?: string;
  priority?: string;
  purpose?: string;
};

export type AppShellPayload = {
  auth?: Record<string, unknown>;
  primarySections?: AppShellSection[];
  workspaceEntries?: Array<Record<string, unknown>>;
  globalLibraries?: Array<Record<string, unknown>>;
};

export const appShellApi = {
  async get(): Promise<AppShellPayload> {
    const payload = await requestJson<V2Payload<AppShellPayload>>("/api/v2/app-shell");
    return unwrapV2(payload);
  },
};
