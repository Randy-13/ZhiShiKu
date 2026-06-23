import { requestJson, unwrapV2 } from "./apiCore";
import type { V2Payload } from "./apiCore";
import { toKnowledge, toLibraryKnowledge } from "./apiLibrary";
import type {
  BrowserExtractLinkResult,
  FocusDraftPayload,
  InspectedLink,
  RawLibraryResult,
  ReadableDraftInput,
  UploadedItem,
} from "./api";
import type { KnowledgeItem, MaterialType, SourceMaterial, TextExtractionMode } from "./domain";

const READABLE_DRAFT_TIMEOUT_MS = 120_000;
const DRAFT_META_TIMEOUT_MS = 30_000;

type ReadableDraftPayload = {
  ok?: boolean;
  error?: string;
  title?: string;
  note?: string;
  markdown?: string;
  source?: string;
  errors?: string[];
};

export const collectApi = {
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

  async browserExtractLink(material: SourceMaterial): Promise<ReadableDraftInput> {
    const payload = await requestJson<V2Payload<BrowserExtractLinkResult>>(
      "/api/v2/collect/browser-extract-link",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: material.source,
          title: material.title,
          wait_ms: 3000,
          scroll_times: 5,
          scroll_pause_ms: 800,
        }),
      },
      { timeoutMs: READABLE_DRAFT_TIMEOUT_MS },
    );
    const data = assertV2Ok(payload);
    return {
      title: firstString(data.title, material.title, "浏览器提取原文"),
      note: firstString(data.note, material.note),
      body: firstString(data.markdown),
      sourceIds: [material.id],
      materialType: "web_link",
      source: firstString(data.source, material.source),
    };
  },

  transcribeMedia(mediaIds: number[]) {
    return requestJson<{ items?: Array<Record<string, unknown>> }>("/api/media/transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_ids: mediaIds }),
    });
  },

  async createRawLibraryFile(materials: SourceMaterial[], title = ""): Promise<RawLibraryResult> {
    if (!materials.length) throw new Error("No material selected for raw library file.");
    const materialType = rawMaterialType(materials);
    const items = materials.map((material) => ({
      id: material.backendId,
      content: material.type === "text" ? material.source : "",
      url: material.type === "link" || material.type === "media" ? material.source : "",
      title: material.title,
      link_type: material.linkType ?? "",
      extraction_strategy: material.extractionStrategy ?? "",
      access_status: material.accessStatus ?? material.status,
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
            link_type: material.linkType ?? "",
            extraction_strategy: material.extractionStrategy ?? "",
            access_status: material.accessStatus ?? material.status,
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
};

function assertV2Ok<T extends { ok?: boolean; error?: string }>(payload: V2Payload<T>): T {
  const data = unwrapV2(payload);
  if (data.ok === false) throw new Error(data.error || "API request failed");
  return data;
}

function asFileList(files: File[]) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file, file.name));
  return form;
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return "";
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

function rawMaterialType(materials: SourceMaterial[]) {
  return rawMaterialGroupKey(materials[0] ?? { type: "text" } as SourceMaterial);
}

function rawMaterialGroupKey(material: SourceMaterial) {
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
  const title = `合并原文 ${new Date().toLocaleString()}`;
  return {
    id: `readable-${Date.now()}`,
    title,
    note: `合并 ${materials.length} 条文本素材`,
    body: [`# ${title}`, ...materials.map((material, index) => `\n\n## ${index + 1}. ${material.title}\n\n${material.source || material.note || ""}`)].join(""),
    sourceIds: materials.map((material) => material.id),
    status: "draft",
    confidence: "medium",
  };
}
