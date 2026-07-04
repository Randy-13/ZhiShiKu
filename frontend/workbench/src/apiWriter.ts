import { requestJson } from "./apiCore";
import type { WriterProjectState, WriterStrategyPreset } from "./domain";
import type { WriterLibraryFileInput } from "./api";

export const writerApi = {
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

  writerWritingStrategies() {
    return requestJson<{ default_id: string; items: WriterStrategyPreset[] }>("/api/writer/writing-strategies");
  },

  saveWriterWritingStrategy(name: string, body: string, id?: string) {
    return requestJson<{ default_id: string; items: WriterStrategyPreset[]; item: WriterStrategyPreset }>("/api/writer/writing-strategies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, body }),
    });
  },

  deleteWriterWritingStrategy(id: string) {
    return requestJson<{ default_id: string; items: WriterStrategyPreset[] }>(`/api/writer/writing-strategies/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
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

  updateWriterProjectStrategies(projectId: string, writingStrategy?: string, designStrategy?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/strategies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ writing_strategy: writingStrategy, design_strategy: designStrategy }),
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

  suggestWriterProjectImages(projectId: string, markdown?: string, topic?: Record<string, unknown>, contentImageCount = 1, imageStylePreset?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/image-suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, topic, content_image_count: contentImageCount, image_style_preset: imageStylePreset }),
    });
  },

  generateWriterProjectImages(projectId: string, coverPrompt?: string, contentImagePrompts: string[] = [], coverAspectRatio?: string, contentAspectRatio?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cover_prompt: coverPrompt, content_image_prompts: contentImagePrompts, cover_aspect_ratio: coverAspectRatio, content_aspect_ratio: contentAspectRatio }),
    });
  },

  generateWriterProjectImageItem(projectId: string, kind: "cover" | "content", prompt: string, index?: number, aspectRatio?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/images/item`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, prompt, index, aspect_ratio: aspectRatio }),
    });
  },

  formatWriterProject(projectId: string, markdown?: string, designStrategy?: string, theme = "tech") {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown, theme, design_strategy: designStrategy }),
    });
  },

  confirmWriterProjectDesign(projectId: string, confirmed = true) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/confirm-design`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed }),
    });
  },

  preflightWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/publish/preflight`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, digest, cover_path: coverPath }),
    });
  },

  publishWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return requestJson<WriterProjectState>(`/api/writer/projects/${encodeURIComponent(projectId)}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, digest, cover_path: coverPath }),
    });
  },

  writerFileUrl(path: string) {
    return `/api/writer/file?path=${encodeURIComponent(path)}`;
  },
};
