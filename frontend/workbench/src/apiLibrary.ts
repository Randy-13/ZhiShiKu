import { requestJson, unwrapV2 } from "./apiCore";
import type { V2Payload } from "./apiCore";
import type { KnowledgeDraft, KnowledgeItem, SourceMaterial } from "./domain";
import type { LibraryKind, TrashStatus } from "./api";

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

type LegacyKnowledgePayload = {
  item?: Record<string, unknown>;
  items?: Array<Record<string, unknown>>;
  content?: string;
  deleted?: Array<Record<string, unknown>>;
  skipped?: Array<Record<string, unknown>>;
};

export const libraryApi = {
  async listKnowledge(): Promise<KnowledgeItem[]> {
    const payload = await legacyKnowledgeApi.list();
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

  async readKnowledge(knowledgeId: number): Promise<KnowledgeItem> {
    const payload = await legacyKnowledgeApi.read(knowledgeId);
    return toKnowledge({ ...(payload.item ?? {}), markdown: payload.content }, undefined, knowledgeId);
  },

  async updateKnowledge(knowledgeId: number, payload: { title: string; note: string; body: string }): Promise<KnowledgeItem> {
    const response = await legacyKnowledgeApi.update(knowledgeId, payload);
    return toKnowledge({ ...(response.item ?? {}), markdown: response.content }, undefined, knowledgeId);
  },

  async deleteKnowledge(knowledgeIds: number[]): Promise<{ items: KnowledgeItem[]; deleted: Array<Record<string, unknown>>; skipped: Array<Record<string, unknown>> }> {
    const payload = await legacyKnowledgeApi.deleteNotIngested(knowledgeIds);
    return {
      items: (payload.items ?? []).map((item, index) => toKnowledge(item, undefined, index)),
      deleted: payload.deleted ?? [],
      skipped: payload.skipped ?? [],
    };
  },

  async commitKnowledgeDraft(draft: KnowledgeDraft): Promise<KnowledgeItem> {
    const payload = await legacyKnowledgeApi.commitDraft(draft);
    return toKnowledge({ ...(payload.item ?? {}), markdown: payload.content }, undefined, Number(payload.item?.id ?? Date.now()));
  },
};

const legacyKnowledgeApi = {
  list() {
    return requestJson<LegacyKnowledgePayload>("/api/knowledge");
  },

  read(knowledgeId: number) {
    return requestJson<LegacyKnowledgePayload>(`/api/knowledge/${knowledgeId}`);
  },

  async update(knowledgeId: number, payload: { title: string; note: string; body: string }) {
    try {
      return await requestJson<LegacyKnowledgePayload>(`/api/knowledge/${knowledgeId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("Method Not Allowed") && !message.includes("405")) throw error;
      return this.commitDraft({
        backendId: knowledgeId,
        title: payload.title,
        note: payload.note,
        body: payload.body,
        sourceIds: [],
      });
    }
  },

  deleteNotIngested(knowledgeIds: number[]) {
    return requestJson<LegacyKnowledgePayload>("/api/knowledge/delete-not-ingested", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: knowledgeIds }),
    });
  },

  commitDraft(draft: Pick<KnowledgeDraft, "backendId" | "title" | "note" | "body" | "sourceIds">) {
    return requestJson<LegacyKnowledgePayload>("/api/knowledge/commit-draft", {
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
  },
};

function assertV2Ok<T extends { ok?: boolean; error?: string }>(payload: V2Payload<T>): T {
  const data = unwrapV2(payload);
  if (data.ok === false) throw new Error(data.error || "API request failed");
  return data;
}

function libraryBucketFromV2(value: unknown): LibraryKind {
  if (value === "focus") return "focus";
  if (value === "perspective") return "perspective";
  return "original";
}

function libraryBucketToV2(library: LibraryKind) {
  if (library === "original") return "raw";
  return library;
}

function normalizeLibraryPath(value: unknown) {
  return firstString(value).replace(/\\/g, "/");
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return "";
}

function numericId(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && /^\d+$/.test(value)) return Number(value);
  return undefined;
}

export function toLibraryKnowledge(raw: LibraryFilePayload, fallbackIndex = 0): KnowledgeItem {
  const library = libraryBucketFromV2(raw.library);
  const markdownPath = normalizeLibraryPath(raw.markdown_path || raw.id);
  const title = firstString(raw.title, raw.id, `File ${fallbackIndex + 1}`);
  return {
    id: markdownPath || `${library}-${fallbackIndex}`,
    title,
    body: firstString(raw.markdown),
    note: firstString(raw.note, raw.source, raw.material_type),
    library,
    markdownPath,
    createdAt: firstString(raw.created_at),
    updatedAt: firstString(raw.updated_at),
    sourceIds: markdownPath ? [markdownPath] : [],
    status: raw.status === "archived" ? "archived" : "saved",
    confidence: "medium",
  };
}

export function toKnowledge(raw: Record<string, unknown>, material?: SourceMaterial, fallbackIndex = 0, library: LibraryKind = "focus"): KnowledgeItem {
  const backendId = numericId(raw.id);
  const body = firstString(raw.markdown, raw.content, raw.body, raw.summary);
  const markdownPath = normalizeLibraryPath(raw.markdown_path);
  return {
    id: String(raw.id ?? (markdownPath || `knowledge-${Date.now()}-${fallbackIndex}`)),
    backendId,
    title: firstString(raw.title, raw.name, material ? `${material.title} knowledge` : `Knowledge ${fallbackIndex + 1}`),
    body,
    note: firstString(raw.note, raw.topic),
    library,
    markdownPath,
    createdAt: firstString(raw.created_at, raw.createdAt),
    updatedAt: firstString(raw.updated_at, raw.updatedAt),
    sourceIds: material ? [material.id] : markdownPath ? [markdownPath] : [],
    status: "saved",
    confidence: raw.status === "ready" || body ? "medium" : "needsReview",
  };
}