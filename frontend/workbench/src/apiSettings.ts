import { requestJson, unwrapV2 } from "./apiCore";
import type {
  ApiSettingInput,
  ApiSettingsPayload,
  ApiTestResult,
  AsrSettingInput,
  AsrSettingsPayload,
  BilibiliCookieLoginResult,
  BilibiliCookieStatus,
  DatabaseStatus,
  HtmlGrabCheckStatus,
  ImageApiSettingInput,
  ImageApiSettingsPayload,
  MediaDependencyStatus,
  TrashStatus,
  WorkbenchSettings,
} from "./api";

type SettingsResult = { ok?: boolean; error?: string; message?: string };

function ensureSettingsOk<T extends SettingsResult>(payload: T): T {
  if (payload.ok === false) throw new Error(payload.error || payload.message || "API settings request failed");
  return payload;
}

export const settingsApi = {
  health() {
    return requestJson<{ status: string }>("/api/health");
  },

  workbenchSettings() {
    return requestJson<WorkbenchSettings>("/api/workbench-settings");
  },

  saveWorkbenchSettings(settings: WorkbenchSettings) {
    return requestJson<WorkbenchSettings>("/api/workbench-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
  },

  bilibiliCookieStatus() {
    return requestJson<BilibiliCookieStatus>("/api/media/bilibili-cookies");
  },

  openBilibiliCookieLogin(url = "https://space.bilibili.com/520819684") {
    return requestJson<BilibiliCookieLoginResult>("/api/media/bilibili-cookies/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  },

  mediaDependencies() {
    return requestJson<MediaDependencyStatus>("/api/media/dependencies");
  },

  async htmlGrabCheck(url = "") {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<HtmlGrabCheckStatus>>("/api/v2/settings/html-grab-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }));
  },

  async htmlGrabAuthorize(url = "about:blank") {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<{ ok?: boolean; message?: string; target_url?: string; error?: string }>>("/api/v2/settings/html-grab-authorize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }));
  },

  async asrSettings(): Promise<AsrSettingsPayload> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<AsrSettingsPayload>>("/api/v2/settings/asr"));
  },

  async saveAsrSetting(setting: AsrSettingInput): Promise<AsrSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<AsrSettingsPayload>>("/api/v2/settings/asr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    })));
  },

  async testAsrSetting(setting: AsrSettingInput): Promise<AsrSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<AsrSettingsPayload>>("/api/v2/settings/asr/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    })));
  },

  async apiSettings(): Promise<ApiSettingsPayload> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiSettingsPayload>>("/api/v2/settings/api"));
  },

  async saveApiSetting(setting: ApiSettingInput): Promise<ApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiSettingsPayload>>("/api/v2/settings/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    })));
  },

  async setActiveApiSetting(id: string): Promise<ApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiSettingsPayload>>("/api/v2/settings/api/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    })));
  },

  async deleteApiSetting(id: string): Promise<ApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiSettingsPayload>>(`/api/v2/settings/api/${encodeURIComponent(id)}`, {
      method: "DELETE",
    })));
  },

  async testApiSetting(setting: ApiSettingInput): Promise<ApiTestResult> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiTestResult>>("/api/v2/settings/api/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting }),
    })));
  },

  async imageApiSettings(): Promise<ImageApiSettingsPayload> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<ImageApiSettingsPayload>>("/api/v2/settings/image"));
  },

  async saveImageApiSetting(setting: ImageApiSettingInput): Promise<ImageApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ImageApiSettingsPayload>>("/api/v2/settings/image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    })));
  },

  async setActiveImageApiSetting(id: string): Promise<ImageApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ImageApiSettingsPayload>>("/api/v2/settings/image/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    })));
  },

  async deleteImageApiSetting(id: string): Promise<ImageApiSettingsPayload> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ImageApiSettingsPayload>>(`/api/v2/settings/image/${encodeURIComponent(id)}`, {
      method: "DELETE",
    })));
  },

  async testImageApiSetting(setting: ImageApiSettingInput, options?: { realTest?: boolean; prompt?: string }): Promise<ApiTestResult> {
    return ensureSettingsOk(unwrapV2(await requestJson<import("./apiCore").V2Payload<ApiTestResult>>("/api/v2/settings/image/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting, real_test: options?.realTest ?? false, prompt: options?.prompt }),
    })));
  },

  async trashStatus(): Promise<TrashStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<TrashStatus>>("/api/v2/settings/trash"));
  },

  async databaseStatus(): Promise<DatabaseStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<DatabaseStatus>>("/api/v2/admin/database/status"));
  },

  async clearTrash(): Promise<TrashStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<TrashStatus>>("/api/v2/settings/trash", { method: "DELETE" }));
  },

  async deleteTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<TrashStatus>>("/api/v2/settings/trash/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trash_paths: trashPaths }),
    }));
  },

  async restoreTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<TrashStatus>>("/api/v2/settings/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trash_paths: trashPaths }),
    }));
  },
};
