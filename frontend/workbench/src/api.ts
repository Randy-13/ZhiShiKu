import type {
  CreationDraft,
  KnowledgeDraft,
  KnowledgeItem,
  MaterialType,
  PerspectiveDraft,
  PerspectiveProfile,
  SourceMaterial,
  TextExtractionMode,
  WriterProjectState,
} from "./domain";

const API_BASE = "";
const READABLE_DRAFT_TIMEOUT_MS = 120_000;
const DRAFT_META_TIMEOUT_MS = 30_000;

export type LibraryKind = "original" | "focus" | "perspective";

type V2Payload<T> = {
  data?: T;
  meta?: Record<string, unknown>;
};

type LibraryFilePayload = Record<string, unknown> & {
  id?: string;
  title?: string;
  library?: string;
  status?: string;
  source?: string;
  material_type?: string;
  markdown_path?: string;
  created_at?: string;
  updated_at?: string;
};

export type FocusDraftPayload = {
  ok: boolean;
  error?: string;
  source_files?: Array<Record<string, string>>;
  source_hash?: string;
  cluster_count?: number;
  markdown?: string;
  existing_item?: Record<string, unknown>;
};

export type RawLibraryResult = {
  item: KnowledgeItem;
  errors?: string[];
};

export type ReadableDraftInput = {
  title: string;
  note: string;
  body: string;
  sourceIds: string[];
  materialType: string;
  source: string;
};

type ReadableDraftPayload = {
  ok?: boolean;
  error?: string;
  title?: string;
  note?: string;
  markdown?: string;
  source?: string;
  errors?: string[];
};

async function requestJson<T>(path: string, init?: RequestInit, options?: { timeoutMs?: number }): Promise<T> {
  const timeoutMs = options?.timeoutMs;
  const controller = timeoutMs ? new AbortController() : undefined;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : undefined;
  const signal = controller?.signal ?? init?.signal;
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal });
    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(readError(text) || `${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Readable original generation timed out. For Douyin links, upload the local video/subtitle or configure ASR, then try again.");
    }
    throw error;
  } finally {
    if (timeoutId) window.clearTimeout(timeoutId);
  }
}

function readError(text: string) {
  if (!text) return "";
  try {
    const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
    const detail = payload.detail ?? payload.message;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      const record = detail as Record<string, unknown>;
      const message = record.message;
      if (typeof message === "string") return message;
      return JSON.stringify(detail);
    }
    return String(detail ?? text);
  } catch {
    return text;
  }
}

function joinUniqueMessages(messages: string[]) {
  const seen = new Set<string>();
  return messages
    .map((message) => message.trim())
    .filter((message) => {
      if (!message || seen.has(message)) return false;
      seen.add(message);
      return true;
    })
    .join("；");
}

function asFileList(files: File[]) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file, file.name));
  return form;
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function normalizeLibraryPath(value: unknown) {
  return firstString(value).replace(/\\/g, "/");
}

function numericId(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isInteger(parsed)) return parsed;
  }
  return undefined;
}

function assertV2Ok<T extends { ok?: boolean; error?: string }>(payload: V2Payload<T>): T {
  const data = (payload.data ?? {}) as T;
  if (data.ok === false) throw new Error(data.error || "API request failed");
  return data;
}

function libraryBucketFromV2(value: unknown): LibraryKind {
  if (value === "focus") return "focus";
  if (value === "perspective") return "perspective";
  return "original";
}

function libraryBucketToV2(value: LibraryKind) {
  return value === "original" ? "raw" : value;
}

function rawMaterialType(materials: SourceMaterial[]) {
  return rawMaterialGroupKey(materials[0] ?? { type: "text" } as SourceMaterial);
}

export function rawMaterialGroupKey(material: SourceMaterial) {
  if (material.type === "image") return "screenshot";
  if (material.type === "file") return "document";
  if (material.type === "media") return "media";
  if (material.type === "link") return "web_link";
  return "text";
}

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("读取粘贴图片失败"));
    reader.readAsDataURL(file);
  });
}

function normalizeClipboardImage(file: File, index: number) {
  const type = file.type && file.type.startsWith("image/") ? file.type : "image/png";
  const suffix = type === "image/jpeg" ? ".jpg" : type === "image/webp" ? ".webp" : type === "image/gif" ? ".gif" : ".png";
  const name = file.name && /\.[a-z0-9]+$/i.test(file.name) ? file.name : `clipboard-${Date.now()}-${index + 1}${suffix}`;
  if (file.name === name && file.type === type) return file;
  return new File([file], name, { type, lastModified: file.lastModified || Date.now() });
}

function localReadableDocument(materials: SourceMaterial[]): KnowledgeItem {
  if (materials.length === 1) {
    const material = materials[0];
    const title = material.title.trim() || "未命名原文";
    const body = material.source.trim()
      ? `# ${title}\n\n${material.source.trim()}`
      : `# ${title}\n\n${material.note ?? ""}`;
    return {
      id: `readable-${Date.now()}`,
      title,
      note: "本地文本原文草稿",
      body,
      sourceIds: [material.id],
      status: "draft",
      confidence: "medium",
    };
  }

  const title = `${materials[0]?.title || "组合素材"} 等 ${materials.length} 个原文文档`;
  const body = materials
    .map((material, index) => {
      const heading = material.title.trim() || `素材 ${index + 1}`;
      return `## ${index + 1}. ${heading}\n\n${material.source.trim() || material.note || ""}`;
    })
    .join("\n\n---\n\n");

  return {
    id: `readable-${Date.now()}`,
    title,
    note: "多素材本地原文草稿",
    body,
    sourceIds: materials.map((item) => item.id),
    status: "draft",
    confidence: "medium",
  };
}

export type UploadedItem = Record<string, unknown> & {
  id?: number;
  title?: string;
  original_name?: string;
  filename?: string;
  source_url?: string;
  canonical_url?: string;
  file_path?: string;
  image_path?: string;
  page_count?: number;
  default_range?: string;
};

export type InspectedLink = {
  url?: string;
  final_url?: string;
  title?: string;
  link_type?: string;
  extraction_strategy?: string;
  access_status?: string;
  source?: string;
  notes?: string;
  author?: string;
  published_at?: string;
};

export type WriterAdvanceResult = {
  draft: Partial<CreationDraft>;
  message: string;
};

export type WriterLibraryFileInput = {
  library: LibraryKind;
  markdown_path: string;
  title: string;
  knowledge_id?: number;
};

export type WorkbenchSettings = {
  text_extraction_mode: TextExtractionMode;
  storage_locations?: StorageLocations;
};

export type StorageLocations = {
  storage_root?: string;
  image_cache?: string;
  document_cache?: string;
  media_cache?: string;
  raw_library?: string;
  focus_library?: string;
  perspective_library?: string;
  writer_projects?: string;
  trash?: string;
  database?: string;
};

export type TrashStatus = {
  path: string;
  file_count: number;
  size_bytes: number;
  updated_at?: string;
  deleted_files?: number;
  deleted_bytes?: number;
  deleted?: string[];
  restored?: string[];
  errors?: Array<{ path?: string; error?: string }>;
  items?: TrashFileItem[];
  ok?: boolean;
};

export type TrashFileItem = {
  id: string;
  trash_path: string;
  title: string;
  library: LibraryKind | "raw" | "";
  source_path?: string;
  deleted_at?: string;
  size?: number;
};

export type BilibiliCookieStatus = {
  ok?: boolean;
  mode?: string;
  source?: string;
  path?: string;
  exists?: boolean;
  message?: string;
  missing?: string[];
  cookie_count?: number;
  last_modified?: string;
};

export type BilibiliCookieLoginResult = {
  ok?: boolean;
  message?: string;
  script?: string;
};

export type ApiSettingItem = {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model: string;
  api_key_masked?: string;
  timeout?: number;
  max_retries?: number;
  created_at?: string;
  updated_at?: string;
};

export type ApiSettingTemplate = {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model: string;
  api_key_placeholder?: string;
  size?: string;
  quality?: string;
};

export type ApiSettingsPayload = {
  active_id?: string | null;
  items?: ApiSettingItem[];
  templates?: ApiSettingTemplate[];
  item?: ApiSettingItem;
};

export type ApiSettingInput = {
  id?: string | null;
  name: string;
  provider: string;
  base_url: string;
  model: string;
  api_key?: string;
  timeout?: number;
  max_retries?: number;
  make_active?: boolean;
};

export type ImageApiSettingItem = ApiSettingItem & {
  size?: string;
  quality?: string;
  response_format?: string;
};

export type ImageApiSettingsPayload = {
  active_id?: string | null;
  items?: ImageApiSettingItem[];
  templates?: ApiSettingTemplate[];
  item?: ImageApiSettingItem;
};

export type ImageApiSettingInput = Omit<ApiSettingInput, "max_retries"> & {
  size?: string;
  quality?: string;
  response_format?: string;
};

export type ApiTestResult = Record<string, string | boolean | number | null | undefined>;

type PerspectivePayload = Record<string, unknown> & {
  id?: string;
  name?: string;
  positioning?: string;
  core_goal?: string;
  coreGoal?: string;
  stance?: string;
  role?: string;
  target_subject?: string;
  purpose?: string;
  readonly?: boolean;
  origin?: string;
  created_at?: string;
  updated_at?: string;
};

type MineSourcePayload = {
  library: string;
  markdown_path: string;
  title?: string;
};

type MineInterpretPayload = {
  ok: boolean;
  error?: string;
  title?: string;
  markdown?: string;
  source_files?: Array<Record<string, string>>;
  perspective?: PerspectivePayload;
};

export const api = {
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

  async uploadMaterial(type: MaterialType, files: File[]): Promise<UploadedItem[]> {
    const path = type === "image" ? "/api/images" : type === "media" ? "/api/media/upload" : "/api/files";
    const payload = await requestJson<{ items?: UploadedItem[]; item?: UploadedItem }>(path, {
      method: "POST",
      body: asFileList(files),
    });
    return payload.items ?? (payload.item ? [payload.item] : []);
  },

  async uploadPastedImages(files: File[]): Promise<UploadedItem[]> {
    const normalizedFiles = files.map((file, index) => normalizeClipboardImage(file, index));
    try {
      return await this.uploadMaterial("image", normalizedFiles);
    } catch (multipartError) {
      const images = await Promise.all(
        normalizedFiles.map(async (file, index) => ({
          filename: file.name || `clipboard-${Date.now()}-${index + 1}.png`,
          content_type: file.type || "image/png",
          data_url: await fileToDataUrl(file),
        })),
      );
      try {
        const payload = await requestJson<{ items?: UploadedItem[] }>("/api/images/paste", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ images }),
        });
        return payload.items ?? [];
      } catch (pasteError) {
        const first = multipartError instanceof Error ? multipartError.message : "";
        const second = pasteError instanceof Error ? pasteError.message : "";
        throw new Error(joinUniqueMessages([first, second]) || "粘贴截图上传失败");
      }
    }
  },

  async loadFilePageInfo(fileIds: number[]): Promise<UploadedItem[]> {
    if (!fileIds.length) return [];
    const payload = await requestJson<{ items?: UploadedItem[] }>("/api/files/page-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: fileIds }),
    });
    return payload.items ?? [];
  },

  async resolveMediaUrl(url: string): Promise<UploadedItem | null> {
    const payload = await requestJson<{ item?: UploadedItem }>("/api/media/resolve-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return payload.item ?? null;
  },

  async inspectLink(url: string): Promise<InspectedLink | null> {
    const payload = await requestJson<V2Payload<{ ok?: boolean; item?: InspectedLink }>>("/api/v2/collect/inspect-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return payload.data?.item ?? null;
  },

  transcribeMedia(mediaIds: number[]) {
    return requestJson<{ items?: Array<Record<string, unknown>> }>("/api/media/transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_ids: mediaIds }),
    });
  },

  async listKnowledge(): Promise<KnowledgeItem[]> {
    const payload = await requestJson<{ items?: Array<Record<string, unknown>> }>("/api/knowledge");
    return (payload.items ?? []).map((item, index) => toKnowledge(item, undefined, index));
  },

  async listLibraryFiles(library: LibraryKind, pendingFocus = false): Promise<KnowledgeItem[]> {
    const query = library === "original" && pendingFocus ? "?pending_focus=true" : "";
    const payload = await requestJson<V2Payload<{ items?: LibraryFilePayload[] }>>(
      `/api/v2/libraries/${libraryBucketToV2(library)}/files${query}`,
    );
    return (payload.data?.items ?? []).map((item, index) => toLibraryKnowledge(item, index));
  },

  async readLibraryFile(library: LibraryKind, markdownPath: string): Promise<KnowledgeItem> {
    const payload = await requestJson<V2Payload<{ item?: LibraryFilePayload; markdown?: string }>>(
      `/api/v2/libraries/${libraryBucketToV2(library)}/file?markdown_path=${encodeURIComponent(markdownPath)}`,
    );
    return toLibraryKnowledge({ ...(payload.data?.item ?? {}), markdown: payload.data?.markdown }, Date.now());
  },

  async updateLibraryFile(
    library: LibraryKind,
    markdownPath: string,
    payload: { title: string; note: string; body: string },
  ): Promise<KnowledgeItem> {
    const response = await requestJson<V2Payload<{ ok: boolean; error?: string; item?: LibraryFilePayload; markdown?: string }>>(
      `/api/v2/libraries/${libraryBucketToV2(library)}/file?markdown_path=${encodeURIComponent(markdownPath)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: payload.title, note: payload.note, markdown: payload.body }),
      },
    );
    const data = assertV2Ok(response);
    return toLibraryKnowledge({ ...(data.item ?? {}), markdown: data.markdown }, Date.now());
  },

  async deleteLibraryFile(library: LibraryKind, markdownPath: string): Promise<TrashStatus> {
    const response = await requestJson<V2Payload<{ ok: boolean; error?: string; trash?: TrashStatus }>>(
      `/api/v2/libraries/${libraryBucketToV2(library)}/file?markdown_path=${encodeURIComponent(markdownPath)}`,
      { method: "DELETE" },
    );
    const data = assertV2Ok(response);
    return data.trash ?? { path: "", file_count: 0, size_bytes: 0 };
  },

  async trashStatus(): Promise<TrashStatus> {
    const response = await requestJson<V2Payload<TrashStatus>>("/api/v2/settings/trash");
    return response.data ?? { path: "", file_count: 0, size_bytes: 0 };
  },

  async clearTrash(): Promise<TrashStatus> {
    const response = await requestJson<V2Payload<TrashStatus>>("/api/v2/settings/trash", { method: "DELETE" });
    return response.data ?? { path: "", file_count: 0, size_bytes: 0 };
  },

  async deleteTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    const response = await requestJson<V2Payload<TrashStatus>>("/api/v2/settings/trash/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trash_paths: trashPaths }),
    });
    return response.data ?? { path: "", file_count: 0, size_bytes: 0 };
  },

  async restoreTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    const response = await requestJson<V2Payload<TrashStatus>>("/api/v2/settings/trash/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trash_paths: trashPaths }),
    });
    return response.data ?? { path: "", file_count: 0, size_bytes: 0 };
  },

  async createRawLibraryFile(materials: SourceMaterial[], title = ""): Promise<RawLibraryResult> {
    if (!materials.length) throw new Error("No material selected for raw library file.");
    const materialType = rawMaterialType(materials);
    const items = materials.map((material) => ({
      id: material.backendId,
      content: material.type === "text" ? material.source : "",
      url: material.type === "link" || material.type === "media" ? material.source : "",
      title: material.title,
      link_type: "",
      extraction_strategy: "",
      access_status: material.status,
    }));
    const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; item?: Record<string, unknown>; errors?: string[] }>>(
      "/api/v2/collect/raw-markdown",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_type: materialType, title, items }),
      },
    );
    const data = assertV2Ok(payload);
    return {
      item: toLibraryKnowledge({ ...(data.item ?? {}), library: "raw" }, Date.now()),
      errors: data.errors ?? [],
    };
  },

  async createReadableDraft(materials: SourceMaterial[], parserMode: TextExtractionMode): Promise<ReadableDraftInput> {
    if (!materials.length) throw new Error("No material selected for readable draft.");
    let readable: KnowledgeItem;
    const textOnly = materials.every((material) => material.type === "text" && !material.backendId);
    const backendReady = materials.every(
      (material) => material.type === "text" || material.type === "link" || typeof material.backendId === "number",
    );
    if (textOnly) {
      readable = localReadableDocument(materials);
    } else if (backendReady) {
      const payload = await requestJson<V2Payload<ReadableDraftPayload>>("/api/v2/collect/readable-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material_type: rawMaterialType(materials),
          title: materials.length === 1 ? materials[0]?.title ?? "" : "",
          parser_mode: parserMode,
          items: materials.map((material) => ({
            id: material.backendId,
            content: material.type === "text" ? material.source : "",
            url: material.type === "link" || material.type === "media" ? material.source : "",
            title: material.title,
            link_type: "",
            extraction_strategy: "",
            access_status: material.status,
          })),
        }),
      }, { timeoutMs: READABLE_DRAFT_TIMEOUT_MS });
      const data = assertV2Ok(payload);
      readable = {
        id: `readable-${Date.now()}`,
        title: firstString(data.title, materials[0]?.title, "Readable document"),
        note: firstString(data.note),
        body: firstString(data.markdown),
        sourceIds: materials.map((material) => material.id),
        status: "draft",
        confidence: "needsReview",
      };
    } else {
      readable = await this.readableDocument(materials, parserMode);
    }
    const meta = await this
      .knowledgeDraftMeta(materials, readable.body, "zh", DRAFT_META_TIMEOUT_MS)
      .catch(() => ({ title: readable.title, note: readable.note ?? "" }));
    return {
      title: meta.title?.trim() || readable.title || materials[0]?.title || "未命名原文",
      note: meta.note?.trim() || readable.note || `来源素材：${materials.map((item) => item.title).join("、")}`,
      body: readable.body,
      sourceIds: materials.map((material) => material.id),
      materialType: rawMaterialType(materials),
      source: materials.map((material) => material.source || material.title).filter(Boolean).join("; "),
    };
  },

  async saveRawDraft(draft: ReadableDraftInput): Promise<KnowledgeItem> {
    const requestBody = {
      material_type: draft.materialType,
      title: draft.title,
      note: draft.note,
      markdown: draft.body,
      source: draft.source,
    };
    try {
      const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; item?: Record<string, unknown> }>>(
        "/api/v2/collect/raw-file",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        },
      );
      const data = assertV2Ok(payload);
      return toLibraryKnowledge({ ...(data.item ?? {}), library: "raw" }, Date.now());
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("Not Found") && !message.includes("404")) throw error;
      const fallback = await this.createRawLibraryFile(
        [
          {
            id: `draft-${Date.now()}`,
            type: draft.materialType === "screenshot" ? "image" : draft.materialType === "document" ? "file" : draft.materialType === "web_link" ? "link" : draft.materialType === "media" ? "media" : "text",
            title: draft.title,
            source: draft.body,
            status: "ready",
            note: draft.note,
          },
        ],
        draft.title,
      );
      return {
        ...fallback.item,
        title: draft.title || fallback.item.title,
        note: draft.note || fallback.item.note,
        body: draft.body,
      };
    }
  },

  async refineKnowledgeCluster(rawPaths: string[], title = ""): Promise<FocusDraftPayload> {
    const payload = await requestJson<V2Payload<FocusDraftPayload>>("/api/v2/learn/refine-knowledge-cluster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_paths: rawPaths, title }),
    });
    return assertV2Ok(payload);
  },

  async saveFocusFile(rawPaths: string[], markdown: string, title = ""): Promise<KnowledgeItem> {
    const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; item?: Record<string, unknown> }>>(
      "/api/v2/learn/focus-file",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_paths: rawPaths, markdown, title }),
      },
    );
    const data = assertV2Ok(payload);
    return toLibraryKnowledge({ ...(data.item ?? {}), library: "focus" }, Date.now());
  },

  async listPerspectiveProfiles(): Promise<PerspectiveProfile[]> {
    const payload = await requestJson<V2Payload<{ items?: PerspectivePayload[] }>>("/api/v2/mine/perspectives");
    return (payload.data?.items ?? []).map((item, index) => toPerspectiveProfile(item, index));
  },

  async savePerspectiveProfile(profile: PerspectiveProfile): Promise<PerspectiveProfile[]> {
    const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; items?: PerspectivePayload[] }>>(
      "/api/v2/mine/perspectives",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPerspectivePayload(profile)),
      },
    );
    const data = assertV2Ok(payload);
    return (data.items ?? []).map((item, index) => toPerspectiveProfile(item, index));
  },

  async deletePerspectiveProfile(profileId: string): Promise<PerspectiveProfile[]> {
    const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; items?: PerspectivePayload[] }>>(
      `/api/v2/mine/perspectives/${encodeURIComponent(profileId)}`,
      { method: "DELETE" },
    );
    const data = assertV2Ok(payload);
    return (data.items ?? []).map((item, index) => toPerspectiveProfile(item, index));
  },

  async interpretPerspective(sources: KnowledgeItem[], perspective: PerspectiveProfile): Promise<PerspectiveDraft> {
    const payload = await requestJson<V2Payload<MineInterpretPayload>>("/api/v2/mine/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sources: sources.map(toMineSource),
        perspective: toPerspectivePayload(perspective),
      }),
    });
    const data = assertV2Ok(payload);
    return {
      title: firstString(data.title, `${perspective.name}视角解读`),
      markdown: firstString(data.markdown),
      sourceFiles: data.source_files ?? [],
      perspective: toPerspectiveProfile(data.perspective ?? toPerspectivePayload(perspective)),
    };
  },

  async savePerspectiveFile(
    sources: KnowledgeItem[],
    perspective: PerspectiveProfile,
    markdown: string,
    title = "",
  ): Promise<KnowledgeItem> {
    const payload = await requestJson<V2Payload<{ ok: boolean; error?: string; item?: Record<string, unknown> }>>(
      "/api/v2/mine/perspective-file",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sources: sources.map(toMineSource),
          perspective: toPerspectivePayload(perspective),
          markdown,
          title,
        }),
      },
    );
    const data = assertV2Ok(payload);
    return toLibraryKnowledge({ ...(data.item ?? {}), library: "perspective" }, Date.now());
  },

  async readKnowledge(knowledgeId: number): Promise<KnowledgeItem> {
    const payload = await requestJson<{ item?: Record<string, unknown>; content?: string }>(`/api/knowledge/${knowledgeId}`);
    return toKnowledge({ ...(payload.item ?? {}), markdown: payload.content }, undefined, knowledgeId);
  },

  async updateKnowledge(knowledgeId: number, payload: { title: string; note: string; body: string }): Promise<KnowledgeItem> {
    const response = await requestJson<{ item?: Record<string, unknown>; content?: string }>(
      `/api/knowledge/${knowledgeId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    ).catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("Method Not Allowed") && !message.includes("405")) throw error;
      return requestJson<{ item?: Record<string, unknown>; content?: string }>("/api/knowledge/commit-draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          backend_id: knowledgeId,
          title: payload.title,
          note: "",
          body: payload.body,
          source_ids: [],
        }),
      });
    });
    return toKnowledge({ ...(response.item ?? {}), markdown: response.content }, undefined, knowledgeId);
  },

  async deleteKnowledge(knowledgeIds: number[]): Promise<{ items: KnowledgeItem[]; deleted: Array<Record<string, unknown>>; skipped: Array<Record<string, unknown>> }> {
    const payload = await requestJson<{
      items?: Array<Record<string, unknown>>;
      deleted?: Array<Record<string, unknown>>;
      skipped?: Array<Record<string, unknown>>;
    }>("/api/knowledge/delete-not-ingested", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds }),
    });
    return {
      items: (payload.items ?? []).map((item, index) => toKnowledge(item, undefined, index)),
      deleted: payload.deleted ?? [],
      skipped: payload.skipped ?? [],
    };
  },

  knowledgeDraftMeta(materials: SourceMaterial[], body: string, language: string, timeoutMs?: number) {
    return requestJson<{ title?: string; note?: string }>("/api/knowledge/draft-meta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        materials: materials.map((material) => ({
          title: material.title,
          type: material.type,
          source: material.source,
        })),
        body,
        language,
      }),
    }, timeoutMs ? { timeoutMs } : undefined);
  },

  async commitKnowledgeDraft(draft: KnowledgeDraft): Promise<KnowledgeItem> {
    const payload = await requestJson<{ item?: Record<string, unknown>; content?: string }>("/api/knowledge/commit-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backend_id: draft.backendId,
        title: draft.title,
        note: draft.note,
        body: draft.body,
        source_ids: draft.sourceIds,
      }),
    });
    return toKnowledge({ ...(payload.item ?? {}), markdown: payload.content }, undefined, Number(payload.item?.id ?? Date.now()));
  },

  async readableDocument(materials: SourceMaterial[], parserMode: TextExtractionMode): Promise<KnowledgeItem> {
    const imageIds = materials.filter((material) => material.type === "image" && material.backendId).map((material) => material.backendId!);
    const fileIds = materials.filter((material) => material.type === "file" && material.backendId).map((material) => material.backendId!);
    const mediaIds = materials
      .filter((material) => (material.type === "media" || material.type === "link") && material.backendId)
      .map((material) => material.backendId!);
    if (!imageIds.length && !fileIds.length && !mediaIds.length) {
      throw new Error("Selected materials do not have backend records for text extraction.");
    }
    const payload = await requestJson<{ title?: string; note?: string; markdown?: string; raw_text?: string; cleaned_by?: string }>(
      "/api/materials/readable-document",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_ids: imageIds, file_ids: fileIds, media_ids: mediaIds, parser_mode: parserMode }),
      },
    ).catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("Not Found") || message.includes("404")) {
        throw new Error("后端还没有加载可读原文接口。请重启知识酷后端后刷新页面，再点击生成知识。");
      }
      throw error;
    });
    return {
      id: `readable-${Date.now()}`,
      title: firstString(payload.title, materials[0]?.title, "Readable document"),
      note: firstString(payload.note, payload.cleaned_by ? `cleaned by ${payload.cleaned_by}` : ""),
      body: firstString(payload.markdown, payload.raw_text),
      sourceIds: materials.map((material) => material.id),
      status: "draft",
      confidence: payload.cleaned_by === "llm" ? "high" : "needsReview",
    };
  },

  async generateKnowledge(material: SourceMaterial, parserMode: TextExtractionMode = "local_ocr"): Promise<KnowledgeItem> {
    if (!material.backendId) {
      throw new Error("该素材还没有后端记录，请先上传或解析到旧后端。");
    }

    if (material.type === "image") {
      const payload = await requestJson<{ item?: Record<string, unknown> }>("/api/knowledge/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_ids: [material.backendId], parser_mode: parserMode }),
      });
      return toKnowledge(payload.item ?? {}, material);
    }

    if (material.type === "file") {
      const payload = await requestJson<{ item?: Record<string, unknown>; items?: Array<Record<string, unknown>> }>(
        "/api/knowledge/generate-from-files",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_ids: [material.backendId] }),
        },
      );
      return toKnowledge(payload.item ?? payload.items?.[0] ?? {}, material);
    }

    if (material.type === "media" || material.type === "link") {
      const payload = await requestJson<{ item?: Record<string, unknown>; items?: Array<Record<string, unknown>> }>(
        "/api/knowledge/generate-from-media",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ media_ids: [material.backendId] }),
        },
      );
      return toKnowledge(payload.item ?? payload.items?.[0] ?? {}, material);
    }

    throw new Error("文本素材没有旧后端生成接口，将使用本地知识草稿。");
  },

  ingestKnowledge(knowledgeIds: number[]) {
    return requestJson("/api/knowledge/ingest-to-graph", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds }),
    });
  },

  writerSession(knowledgeIds: number[]) {
    const query = knowledgeIds.length ? `?ids=${knowledgeIds.join(",")}` : "";
    return requestJson<Record<string, unknown>>(`/api/writer/session${query}`);
  },

  writerTopics(knowledgeIds: number[]) {
    return requestJson<Record<string, unknown>>("/api/writer/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds }),
    });
  },

  writerArticle(knowledgeIds: number[], topic: Record<string, unknown>) {
    return requestJson<Record<string, unknown>>("/api/writer/article", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds, topic }),
    });
  },

  writerRevise(knowledgeIds: number[], markdown: string, workspace?: string) {
    return requestJson<Record<string, unknown>>("/api/writer/revise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_ids: knowledgeIds,
        markdown,
        workspace,
        instruction: "请保留核心观点，压缩铺垫，增强结构和发布可读性。",
      }),
    });
  },

  writerPreflight(workspace: string, title: string, digest?: string) {
    return requestJson<Record<string, unknown>>("/api/writer/publish/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace, title, digest }),
    });
  },

  writerProjects() {
    return requestJson<{ items?: WriterProjectState["project"][] }>("/api/writer/projects");
  },

  writerProject(projectId: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}`);
  },

  createWriterProject(
    name: string,
    knowledgeIds: number[] = [],
    projectType = "article",
    libraryFiles: WriterLibraryFileInput[] = [],
    writingStrategy = "",
    designStrategy = "",
  ) {
    return requestJson<WriterProjectState>("/api/writer/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        project_type: projectType,
        knowledge_ids: knowledgeIds,
        library_files: libraryFiles,
        writing_strategy: writingStrategy,
        design_strategy: designStrategy,
      }),
    });
  },

  confirmWriterKnowledge(projectId: string, knowledgeIds: number[], libraryFiles: WriterLibraryFileInput[] = []) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds, library_files: libraryFiles }),
    });
  },

  generateWriterProjectTopics(projectId: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/topics`, {
      method: "POST",
    });
  },

  selectWriterProjectTopic(projectId: string, topic: Record<string, unknown>) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/topic`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
  },

  generateWriterProjectDraft(projectId: string, topic?: Record<string, unknown>) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
  },

  reviseWriterProject(projectId: string, instruction: string, markdown?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/revise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instruction, markdown }),
    });
  },

  suggestWriterProjectImages(projectId: string, markdown?: string, topic?: Record<string, unknown>) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/image-suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, topic }),
    });
  },

  generateWriterProjectImages(projectId: string, coverPrompt?: string, contentImagePrompts: string[] = []) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cover_prompt: coverPrompt, content_image_prompts: contentImagePrompts }),
    });
  },

  formatWriterProject(projectId: string, markdown?: string, designStrategy?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, theme: "tech", design_strategy: designStrategy }),
    });
  },

  preflightWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/publish/preflight`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, author: "Bobo", digest, cover_path: coverPath }),
    });
  },

  publishWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, author: "Bobo", digest, cover_path: coverPath }),
    });
  },
};

export function materialFromUpload(type: MaterialType, upload: UploadedItem, fallbackTitle: string): SourceMaterial {
  return {
    id: `material-${type}-${upload.id ?? Date.now()}`,
    type,
    title: firstString(upload.title, upload.original_name, upload.filename, fallbackTitle, `${type} material`),
    source: firstString(upload.canonical_url, upload.source_url, upload.file_path, upload.image_path, upload.original_name, fallbackTitle),
    status: "captured",
    backendId: typeof upload.id === "number" ? upload.id : undefined,
  };
}

function toLibraryKnowledge(raw: LibraryFilePayload, fallbackIndex = 0): KnowledgeItem {
  const library = libraryBucketFromV2(raw.library);
  const markdownPath = normalizeLibraryPath(raw.markdown_path || raw.id);
  return {
    id: markdownPath || `${library}-${fallbackIndex}`,
    title: firstString(raw.title, raw.id, `File ${fallbackIndex + 1}`),
    body: firstString(raw.markdown),
    note: firstString(raw.note, raw.source, raw.material_type, raw.status),
    library,
    markdownPath,
    createdAt: firstString(raw.created_at),
    updatedAt: firstString(raw.updated_at),
    sourceIds: markdownPath ? [markdownPath] : [],
    status: "saved",
    confidence: "medium",
    backendId: numericId(raw.id),
  };
}

function libraryBucketToSource(value: LibraryKind) {
  return value === "original" ? "raw" : value;
}

function toMineSource(item: KnowledgeItem): MineSourcePayload {
  if (!item.markdownPath) throw new Error("所选原文缺少 Markdown 路径。");
  return {
    library: libraryBucketToSource(item.library ?? "original"),
    markdown_path: item.markdownPath,
    title: item.title,
  };
}

function toPerspectivePayload(profile: PerspectiveProfile): PerspectivePayload {
  return {
    id: profile.id,
    name: profile.name,
    positioning: profile.positioning,
    core_goal: profile.coreGoal,
    stance: profile.stance,
    role: profile.positioning,
    target_subject: profile.positioning,
    purpose: profile.coreGoal,
    focus_dimensions: splitPerspectiveLines(profile.stance),
    analysis_questions: [profile.coreGoal].filter(Boolean),
    output_style: "严格按照 RTFC 框架和固定五段式结构输出。",
    evidence_rule: "所有判断必须锚定原文事实，使用 S1/S2 等来源编号，不脑补、不编造。",
  };
}

function toPerspectiveProfile(raw: PerspectivePayload, fallbackIndex = 0): PerspectiveProfile {
  return {
    id: firstString(raw.id, `perspective-${fallbackIndex}`),
    name: firstString(raw.name, "未命名视角"),
    positioning: firstString(raw.positioning, raw.role, raw.target_subject),
    coreGoal: firstString(raw.coreGoal, raw.core_goal, raw.purpose),
    stance: firstString(raw.stance, Array.isArray(raw.focus_dimensions) ? raw.focus_dimensions.join("；") : "", raw.evidence_rule),
    readonly: Boolean(raw.readonly),
    origin: firstString(raw.origin),
    createdAt: firstString(raw.created_at),
    updatedAt: firstString(raw.updated_at),
  };
}

function splitPerspectiveLines(value: string) {
  return value
    .split(/[\n；;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toKnowledge(raw: Record<string, unknown>, material?: SourceMaterial, fallbackIndex = 0, library: LibraryKind = "focus"): KnowledgeItem {
  const backendId = numericId(raw.id);
  const body = firstString(raw.markdown, raw.content, raw.body, raw.summary);
  const markdownPath = normalizeLibraryPath(raw.markdown_path);
  return {
    id: String(raw.id ?? `knowledge-${Date.now()}-${fallbackIndex}`),
    backendId,
    title: firstString(raw.title, raw.name, material ? `${material.title} 知识稿` : `Knowledge ${fallbackIndex + 1}`),
    body,
    note: firstString(raw.note, raw.topic),
    library,
    markdownPath,
    createdAt: firstString(raw.created_at, raw.createdAt),
    updatedAt: firstString(raw.updated_at, raw.updatedAt),
    sourceIds: material ? [material.id] : [],
    status: raw.graph_status === "ingested" ? "ingested" : "saved",
    confidence: raw.status === "ready" || body ? "medium" : "needsReview",
  };
}
