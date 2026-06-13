import type { LucideIcon } from "lucide-react";

export type WorkspaceId = "collect" | "learn" | "mine" | "create" | "library" | "settings";
export type LegacyStageId =
  | "overview"
  | "inbox"
  | "packs"
  | "processing"
  | "perspectives"
  | "review";
export type RouteId = WorkspaceId | LegacyStageId;

export type MaterialType = "image" | "file" | "media" | "link" | "text";
export type MaterialStatus = "captured" | "queued" | "learning" | "ready" | "error";
export type KnowledgeStatus = "draft" | "saved" | "ingested";
export type TaskStatus = "idle" | "running" | "done" | "error";
export type Language = "zh" | "en";
export type TextExtractionMode = "local_ocr" | "ai_vision";

export type SourceMaterial = {
  id: string;
  type: MaterialType;
  title: string;
  source: string;
  status: MaterialStatus;
  backendId?: number;
  error?: string;
  note?: string;
  linkType?: string;
  extractionStrategy?: string;
  accessStatus?: string;
};

export type KnowledgeItem = {
  id: string;
  title: string;
  body: string;
  note?: string;
  library?: "original" | "focus" | "perspective";
  markdownPath?: string;
  createdAt?: string;
  updatedAt?: string;
  sourceIds: string[];
  status: KnowledgeStatus;
  confidence: "high" | "medium" | "needsReview";
  backendId?: number;
};

export type MiningResult = {
  id: string;
  role: string;
  claim: string;
  evidence: string;
  counterpoint: string;
  knowledgeId?: string;
};

export type PerspectiveProfile = {
  id: string;
  name: string;
  positioning: string;
  coreGoal: string;
  stance: string;
  readonly?: boolean;
  origin?: "preset" | "custom" | string;
  createdAt?: string;
  updatedAt?: string;
};

export type PerspectiveDraft = {
  title: string;
  markdown: string;
  sourceFiles: Array<Record<string, string>>;
  perspective: PerspectiveProfile;
};

export type CreationDraft = {
  id: string;
  title: string;
  channel: string;
  step: number;
  body: string;
  status: "draft" | "review" | "ready";
  topic?: Record<string, unknown>;
  workspace?: string;
  articlePath?: string;
};

export type WriterStep =
  | "created"
  | "knowledge_confirmed"
  | "topics"
  | "topic"
  | "draft"
  | "images"
  | "designed"
  | "publish_check"
  | "published";

export type WriterProject = {
  id: string;
  name: string;
  type?: "article" | "image_text" | "short_video" | "long_video" | string;
  status?: string;
  workspace: string;
  created_at?: string;
  updated_at?: string;
  library_files?: Array<{
    library?: "original" | "focus" | "perspective" | string;
    title?: string;
    knowledge_id?: number;
    markdown_path?: string;
  }>;
  writing_strategy?: string;
  design_strategy?: string;
  topics?: Array<Record<string, unknown>>;
  topic?: Record<string, unknown> | null;
  title?: string;
  digest?: string;
  cover_prompt?: string;
  content_image_prompts?: string[];
  image_suggestion_rationale?: string;
  article_markdown?: string;
  html?: string;
  html_path?: string;
  images?: {
    cover?: { path?: string; prompt?: string };
    content_images?: Array<{ path?: string; prompt?: string }>;
    items?: Array<{ path?: string; prompt?: string }>;
    errors?: Array<{ kind?: string; index?: number; message?: string }>;
    partial?: boolean;
    ok?: boolean;
  };
  preflight?: {
    ok?: boolean;
    checks?: Array<{
      key?: string;
      label?: string;
      ok?: boolean;
      detail?: string;
      optional?: boolean;
      fixed?: boolean;
      ip?: string;
      raw?: string;
    }>;
    blocking?: Array<Record<string, unknown>>;
  };
  publish_result?: Record<string, unknown>;
};

export type WriterProjectState = {
  project: WriterProject;
  status?: Record<string, unknown>;
  step: WriterStep;
  next_action: string;
};

export type KnowledgeDraft = {
  id: string;
  title: string;
  note: string;
  body: string;
  sourceIds: string[];
  backendId?: number;
  status: "draft" | "ready" | "saved";
};

export type ActivityEvent = {
  id: string;
  title: string;
  detail: string;
  workspace: WorkspaceId;
  status: TaskStatus;
  time: string;
};

export type WorkspaceNavItem = {
  id: WorkspaceId;
  label: string;
  description: string;
  icon: LucideIcon;
};
