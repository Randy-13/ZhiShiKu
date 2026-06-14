import { requestJson, unwrapV2 } from "./apiCore";
import type {
  ApiSettingInput,
  ApiSettingsPayload,
  ApiTestResult,
  BilibiliCookieLoginResult,
  BilibiliCookieStatus,
  ImageApiSettingInput,
  ImageApiSettingsPayload,
  TrashStatus,
  WorkbenchSettings,
} from "./api";

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

  apiSettings() {
    return requestJson<ApiSettingsPayload>("/api/api-settings");
  },

  saveApiSetting(setting: ApiSettingInput) {
    return requestJson<ApiSettingsPayload>("/api/api-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    });
  },

  setActiveApiSetting(id: string) {
    return requestJson<ApiSettingsPayload>("/api/api-settings/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  },

  deleteApiSetting(id: string) {
    return requestJson<ApiSettingsPayload>(`/api/api-settings/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  testApiSetting(setting: ApiSettingInput) {
    return requestJson<ApiTestResult>("/api/api-settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting }),
    });
  },

  imageApiSettings() {
    return requestJson<ImageApiSettingsPayload>("/api/image-api-settings");
  },

  saveImageApiSetting(setting: ImageApiSettingInput) {
    return requestJson<ImageApiSettingsPayload>("/api/image-api-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setting),
    });
  },

  setActiveImageApiSetting(id: string) {
    return requestJson<ImageApiSettingsPayload>("/api/image-api-settings/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  },

  deleteImageApiSetting(id: string) {
    return requestJson<ImageApiSettingsPayload>(`/api/image-api-settings/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  testImageApiSetting(setting: ImageApiSettingInput, options?: { realTest?: boolean; prompt?: string }) {
    return requestJson<ApiTestResult>("/api/image-api-settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting, real_test: options?.realTest ?? false, prompt: options?.prompt }),
    });
  },

  async trashStatus(): Promise<TrashStatus> {
    return unwrapV2(await requestJson<import("./apiCore").V2Payload<TrashStatus>>("/api/v2/settings/trash"));
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
