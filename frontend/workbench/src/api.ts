import type { CreationDraft, KnowledgeDraft, KnowledgeItem, MaterialType, SourceMaterial, TextExtractionMode, WriterProjectState } from "./domain";

const API_BASE = "";

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

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(readError(text) || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
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

export type WriterAdvanceResult = {
  draft: Partial<CreationDraft>;
  message: string;
};

export type WorkbenchSettings = {
  text_extraction_mode: TextExtractionMode;
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

  knowledgeDraftMeta(materials: SourceMaterial[], body: string, language: string) {
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
    });
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

  createWriterProject(name: string, knowledgeIds: number[] = [], projectType = "article") {
    return requestJson<WriterProjectState>("/api/writer/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, project_type: projectType, knowledge_ids: knowledgeIds }),
    });
  },

  confirmWriterKnowledge(projectId: string, knowledgeIds: number[]) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds }),
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

  formatWriterProject(projectId: string, markdown?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, theme: "tech" }),
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
  const markdownPath = firstString(raw.markdown_path, raw.id);
  return {
    id: markdownPath || `${library}-${fallbackIndex}`,
    title: firstString(raw.title, raw.id, `File ${fallbackIndex + 1}`),
    body: firstString(raw.source, raw.status, raw.material_type),
    note: firstString(raw.source, raw.material_type, raw.status),
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

function toKnowledge(raw: Record<string, unknown>, material?: SourceMaterial, fallbackIndex = 0, library: LibraryKind = "focus"): KnowledgeItem {
  const backendId = numericId(raw.id);
  const body = firstString(raw.markdown, raw.content, raw.body, raw.summary);
  const markdownPath = firstString(raw.markdown_path);
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
