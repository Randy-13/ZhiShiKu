import { requestJson } from "./apiCore";
import type { XhsAccountProfile, XhsCarouselStrategy, XhsLoginStatus, XhsProjectState } from "./domain";
import type { WriterLibraryFileInput } from "./api";

export const xhsApi = {
  accountProfiles() {
    return requestJson<{ items?: XhsAccountProfile[] }>("/api/xhs/account-profiles");
  },

  createAccountProfile(profile: Omit<XhsAccountProfile, "id" | "created_at" | "updated_at">) {
    return requestJson<{ profile?: XhsAccountProfile; items?: XhsAccountProfile[] }>("/api/xhs/account-profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
  },

  updateAccountProfile(profileId: string, profile: Omit<XhsAccountProfile, "id" | "created_at" | "updated_at">) {
    return requestJson<{ profile?: XhsAccountProfile; items?: XhsAccountProfile[] }>(`/api/xhs/account-profiles/${encodeURIComponent(profileId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
  },

  deleteAccountProfile(profileId: string) {
    return requestJson<{ ok?: boolean; items?: XhsAccountProfile[] }>(`/api/xhs/account-profiles/${encodeURIComponent(profileId)}`, {
      method: "DELETE",
    });
  },

  carouselStrategies() {
    return requestJson<{ default_id?: string; items?: XhsCarouselStrategy[] }>("/api/xhs/carousel-strategies");
  },

  saveCarouselStrategy(strategy: { id?: string; name: string; description?: string; config: Record<string, unknown> }) {
    return requestJson<{ default_id?: string; items?: XhsCarouselStrategy[]; item?: XhsCarouselStrategy }>("/api/xhs/carousel-strategies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(strategy),
    });
  },

  deleteCarouselStrategy(strategyId: string) {
    return requestJson<{ default_id?: string; items?: XhsCarouselStrategy[] }>(`/api/xhs/carousel-strategies/${encodeURIComponent(strategyId)}`, {
      method: "DELETE",
    });
  },

  projects() {
    return requestJson<{ items?: XhsProjectState["project"][] }>("/api/xhs/projects");
  },

  project(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}`);
  },

  createProject(name: string, accountProfileId: string, libraryFiles: WriterLibraryFileInput[] = []) {
    return requestJson<XhsProjectState>("/api/xhs/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, account_profile_id: accountProfileId, library_files: libraryFiles }),
    });
  },

  confirmKnowledge(projectId: string, libraryFiles: WriterLibraryFileInput[]) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ library_files: libraryFiles }),
    });
  },

  generateTopics(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/topics`, {
      method: "POST",
    });
  },

  selectTopic(projectId: string, topic: Record<string, unknown>) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/topic`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
  },

  configureImageText(projectId: string, config: Record<string, unknown>) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    });
  },

  generateDraft(projectId: string, topic?: Record<string, unknown>, config?: Record<string, unknown>) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, config }),
    });
  },

  confirmDraft(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/draft/confirm`, {
      method: "POST",
    });
  },

  revise(projectId: string, instruction: string, content?: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, content }),
    });
  },

  suggestImages(projectId: string, content?: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/image-suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
  },

  confirmImageSuggestions(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/image-suggestions/confirm`, {
      method: "POST",
    });
  },

  generateImages(projectId: string, coverPrompt?: string, contentImagePrompts: string[] = []) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cover_prompt: coverPrompt,
        content_image_prompts: contentImagePrompts,
        cover_aspect_ratio: "3:4",
        content_aspect_ratio: "3:4",
      }),
    });
  },

  generateImageItem(projectId: string, kind: "cover" | "content", prompt: string, index?: number, aspectRatio = "3:4") {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/images/item`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, prompt, index, aspect_ratio: aspectRatio }),
    });
  },

  loginStatus() {
    return requestJson<XhsLoginStatus>("/api/xhs/auth/status");
  },

  preflight(projectId: string) {
    return requestJson<XhsProjectState>("/api/xhs/publish/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId }),
    });
  },

  exportPackage(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/export-package`, {
      method: "POST",
    });
  },

  fillPublish(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/publish/fill`, {
      method: "POST",
    });
  },

  confirmPublish(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/publish/confirm`, {
      method: "POST",
    });
  },

  saveDraft(projectId: string) {
    return requestJson<XhsProjectState>(`/api/xhs/projects/${encodeURIComponent(projectId)}/publish/save-draft`, {
      method: "POST",
    });
  },

  fileUrl(path: string) {
    return `/api/xhs/file?path=${encodeURIComponent(path)}`;
  },
};
