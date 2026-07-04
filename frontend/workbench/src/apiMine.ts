import { requestJson, unwrapV2 } from "./apiCore";
import { toLibraryKnowledge } from "./apiLibrary";
import type { V2Payload } from "./apiCore";
import type { LibraryKind } from "./api";
import type { KnowledgeItem, PerspectiveDraft, PerspectiveProfile } from "./domain";

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
  external_sources?: ExpansionExternalSource[];
  search_report?: ExpansionSearchReport;
  warning?: string;
};

export type ExpansionExternalSource = {
  library: string;
  title: string;
  relative_path: string;
  url: string;
  authority: string;
  query: string;
  text: string;
  snippet: string;
  read_status: string;
};

export type ExpansionSearchReport = {
  queries?: string[];
  errors?: string[];
  candidates?: number;
  readable?: number;
};

export type PerspectiveExpansionPreview = {
  title: string;
  externalSources: ExpansionExternalSource[];
  sourceFiles: Array<Record<string, string>>;
  searchReport: ExpansionSearchReport;
  warning: string;
};

export const mineApi = {
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

  async expandPerspective(
    sources: KnowledgeItem[],
    perspective: PerspectiveProfile,
    currentMarkdown: string,
    expansionInstruction = "",
  ): Promise<PerspectiveDraft> {
    const payload = await requestJson<V2Payload<MineInterpretPayload>>("/api/v2/mine/expand-interpretation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sources: sources.map(toMineSource),
        perspective: toPerspectivePayload(perspective),
        current_markdown: currentMarkdown,
        expansion_instruction: expansionInstruction,
        official_scope: "official_first",
      }),
    });
    const data = assertV2Ok(payload);
    return {
      title: firstString(data.title, `${perspective.name}拓展解读`),
      markdown: firstString(data.markdown),
      sourceFiles: data.source_files ?? [],
      perspective: toPerspectiveProfile(data.perspective ?? toPerspectivePayload(perspective)),
    };
  },

  async previewPerspectiveExpansion(
    sources: KnowledgeItem[],
    perspective: PerspectiveProfile,
    currentMarkdown: string,
    expansionInstruction = "",
  ): Promise<PerspectiveExpansionPreview> {
    const payload = await requestJson<V2Payload<MineInterpretPayload>>("/api/v2/mine/expand-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sources: sources.map(toMineSource),
        perspective: toPerspectivePayload(perspective),
        current_markdown: currentMarkdown,
        expansion_instruction: expansionInstruction,
        official_scope: "official_first",
      }),
    });
    const data = assertV2Ok(payload);
    return {
      title: firstString(data.title, `${perspective.name}拓展来源预览`),
      externalSources: (data.external_sources ?? []).map(toExpansionExternalSource),
      sourceFiles: data.source_files ?? [],
      searchReport: normalizeSearchReport(data.search_report),
      warning: firstString(data.warning),
    };
  },

  async mergePerspectiveExpansion(
    sources: KnowledgeItem[],
    perspective: PerspectiveProfile,
    currentMarkdown: string,
    externalSources: ExpansionExternalSource[],
    expansionInstruction = "",
  ): Promise<PerspectiveDraft> {
    const payload = await requestJson<V2Payload<MineInterpretPayload>>("/api/v2/mine/expand-merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sources: sources.map(toMineSource),
        perspective: toPerspectivePayload(perspective),
        current_markdown: currentMarkdown,
        external_sources: externalSources,
        expansion_instruction: expansionInstruction,
      }),
    });
    const data = assertV2Ok(payload);
    return {
      title: firstString(data.title, `${perspective.name}拓展解读`),
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
};

function assertV2Ok<T extends { ok?: boolean; error?: string }>(payload: V2Payload<T>): T {
  const data = unwrapV2(payload);
  if (data.ok === false) throw new Error(data.error || "API request failed");
  return data;
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

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return "";
}

function toExpansionExternalSource(raw: Record<string, unknown>): ExpansionExternalSource {
  return {
    library: firstString(raw.library, "external"),
    title: firstString(raw.title, raw.url, raw.relative_path),
    relative_path: firstString(raw.relative_path, raw.url),
    url: firstString(raw.url, raw.relative_path),
    authority: firstString(raw.authority, "supplemental"),
    query: firstString(raw.query),
    text: firstString(raw.text),
    snippet: firstString(raw.snippet, raw.text).slice(0, 600),
    read_status: firstString(raw.read_status, raw.text ? "readable" : "unreadable"),
  };
}

function normalizeSearchReport(raw: unknown): ExpansionSearchReport {
  if (!raw || typeof raw !== "object") return {};
  const value = raw as Record<string, unknown>;
  return {
    queries: Array.isArray(value.queries) ? value.queries.map(String) : [],
    errors: Array.isArray(value.errors) ? value.errors.map(String) : [],
    candidates: typeof value.candidates === "number" ? value.candidates : undefined,
    readable: typeof value.readable === "number" ? value.readable : undefined,
  };
}
