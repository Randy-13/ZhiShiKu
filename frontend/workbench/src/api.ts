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
import { requestJson, unwrapV2 } from "./apiCore";
import { authApi } from "./apiAuth";
import { collectApi } from "./apiCollect";
import { jobsApi } from "./apiJobs";
import { libraryApi } from "./apiLibrary";
import { mineApi } from "./apiMine";
import { quotaApi } from "./apiQuota";
import { settingsApi } from "./apiSettings";
import { writerApi } from "./apiWriter";
import type { V2Payload } from "./apiCore";

const READABLE_DRAFT_TIMEOUT_MS = 120_000;
const DRAFT_META_TIMEOUT_MS = 30_000;

export type LibraryKind = "original" | "focus" | "perspective";

export type DeploymentMode = "local" | "cloud";

export type AuthUser = {
  id: string;
  email: string;
  username: string;
  role: "admin" | "member" | string;
  status: string;
};

export type AuthWorkspace = {
  id: string;
  name: string;
  ownerUserId: string;
};

export type AuthContext = {
  deploymentMode: DeploymentMode;
  authenticated: boolean;
  user: AuthUser | null;
  workspace: AuthWorkspace | null;
};

export type AuthAdminUser = AuthUser & {
  createdAt: string;
  updatedAt: string;
  lastLoginAt?: string | null;
};

export type AuthInvitation = {
  id: string;
  code: string;
  role: string;
  maxUses: number;
  usedCount: number;
  expiresAt?: string | null;
  createdAt: string;
  status: string;
};

export type JobStatus = "queued" | "running" | "success" | "failed" | "cancelled";

export type JobEvent = {
  id: number;
  jobId: string;
  status: JobStatus | string;
  message: string;
  detail: Record<string, unknown>;
  createdAt: string;
};

export type JobItem = {
  id: string;
  ownerUserId: string;
  workspaceId: string;
  kind: string;
  status: JobStatus;
  payload: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  errorMessage: string;
  createdAt: string;
  updatedAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  events?: JobEvent[];
};

export type QuotaCounter = {
  allowed?: boolean;
  used?: number;
  projected?: number;
  limit: number;
  remaining?: number;
};

export type QuotaStatus = {
  deploymentMode: DeploymentMode;
  enforced: boolean;
  daily: {
    link_parse_daily: QuotaCounter;
    llm_generate_daily: QuotaCounter;
  };
  jobs: {
    concurrent_jobs: QuotaCounter;
  };
  uploads: {
    single_upload_bytes: Pick<QuotaCounter, "limit">;
    storage_bytes: QuotaCounter;
  };
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

export type BrowserExtractLinkResult = {
  ok?: boolean;
  error?: string;
  title?: string;
  note?: string;
  markdown?: string;
  source?: string;
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

export type MediaDependencyItem = {
  label?: string;
  available?: boolean;
  purpose?: string;
  detail?: string;
  auth?: string;
  message?: string;
  provider?: string;
  base_url?: string;
  model?: string;
  configured?: boolean;
  verified?: boolean;
};

export type MediaDependencyStatus = Record<string, MediaDependencyItem>;

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

export type AsrSettingItem = {
  provider: string;
  base_url: string;
  model: string;
  timeout?: number;
  source?: string;
  api_key_masked?: string;
  configured?: boolean;
  last_test_ok?: boolean;
  last_test_at?: string;
  last_test_message?: string;
};

export type AsrSettingTemplate = {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model: string;
  api_key_placeholder?: string;
};

export type AsrSettingsPayload = {
  ok?: boolean;
  item?: AsrSettingItem;
  templates?: AsrSettingTemplate[];
  message?: string;
  error?: string;
};

export type AsrSettingInput = {
  provider: string;
  base_url: string;
  model: string;
  api_key?: string;
  timeout?: number;
};

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
    return settingsApi.health();
  },

  workbenchSettings() {
    return settingsApi.workbenchSettings();
  },

  async quotaStatus(): Promise<QuotaStatus> {
    return quotaApi.me();
  },

  saveWorkbenchSettings(settings: WorkbenchSettings) {
    return settingsApi.saveWorkbenchSettings(settings);
  },

  bilibiliCookieStatus() {
    return settingsApi.bilibiliCookieStatus();
  },

  openBilibiliCookieLogin(url = "https://space.bilibili.com/520819684") {
    return settingsApi.openBilibiliCookieLogin(url);
  },

  apiSettings() {
    return settingsApi.apiSettings();
  },

  saveApiSetting(setting: ApiSettingInput) {
    return settingsApi.saveApiSetting(setting);
  },

  setActiveApiSetting(id: string) {
    return settingsApi.setActiveApiSetting(id);
  },

  deleteApiSetting(id: string) {
    return settingsApi.deleteApiSetting(id);
  },

  testApiSetting(setting: ApiSettingInput) {
    return settingsApi.testApiSetting(setting);
  },

  imageApiSettings() {
    return settingsApi.imageApiSettings();
  },

  saveImageApiSetting(setting: ImageApiSettingInput) {
    return settingsApi.saveImageApiSetting(setting);
  },

  setActiveImageApiSetting(id: string) {
    return settingsApi.setActiveImageApiSetting(id);
  },

  deleteImageApiSetting(id: string) {
    return settingsApi.deleteImageApiSetting(id);
  },

  testImageApiSetting(setting: ImageApiSettingInput, options?: { realTest?: boolean; prompt?: string }) {
    return settingsApi.testImageApiSetting(setting, options);
  },

  async uploadMaterial(type: MaterialType, files: File[]): Promise<UploadedItem[]> {
    return collectApi.uploadMaterial(type, files);
  },

  async uploadPastedImages(files: File[]): Promise<UploadedItem[]> {
    return collectApi.uploadPastedImages(files);
  },

  async loadFilePageInfo(fileIds: number[]): Promise<UploadedItem[]> {
    return collectApi.loadFilePageInfo(fileIds);
  },

  async resolveMediaUrl(url: string): Promise<UploadedItem | null> {
    return collectApi.resolveMediaUrl(url);
  },

  async inspectLink(url: string): Promise<InspectedLink | null> {
    return collectApi.inspectLink(url);
  },

  async browserExtractLink(material: SourceMaterial): Promise<ReadableDraftInput> {
    return collectApi.browserExtractLink(material);
  },

  transcribeMedia(mediaIds: number[]) {
    return collectApi.transcribeMedia(mediaIds);
  },

  async listKnowledge(): Promise<KnowledgeItem[]> {
    return libraryApi.listKnowledge();
  },

  async listLibraryFiles(library: LibraryKind, pendingFocus = false): Promise<KnowledgeItem[]> {
    return libraryApi.listLibraryFiles(library, pendingFocus);
  },

  async readLibraryFile(library: LibraryKind, markdownPath: string): Promise<KnowledgeItem> {
    return libraryApi.readLibraryFile(library, markdownPath);
  },

  async updateLibraryFile(
    library: LibraryKind,
    markdownPath: string,
    payload: { title: string; note: string; body: string },
  ): Promise<KnowledgeItem> {
    return libraryApi.updateLibraryFile(library, markdownPath, payload);
  },

  async deleteLibraryFile(library: LibraryKind, markdownPath: string): Promise<TrashStatus> {
    return libraryApi.deleteLibraryFile(library, markdownPath);
  },

  async trashStatus(): Promise<TrashStatus> {
    return settingsApi.trashStatus();
  },

  async clearTrash(): Promise<TrashStatus> {
    return settingsApi.clearTrash();
  },

  async deleteTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    return settingsApi.deleteTrashFiles(trashPaths);
  },

  async restoreTrashFiles(trashPaths: string[]): Promise<TrashStatus> {
    return settingsApi.restoreTrashFiles(trashPaths);
  },

  async createRawLibraryFile(materials: SourceMaterial[], title = ""): Promise<RawLibraryResult> {
    return collectApi.createRawLibraryFile(materials, title);
  },

  async createReadableDraft(materials: SourceMaterial[], parserMode: TextExtractionMode): Promise<ReadableDraftInput> {
    return collectApi.createReadableDraft(materials, parserMode);
  },

  async saveRawDraft(draft: ReadableDraftInput): Promise<KnowledgeItem> {
    return collectApi.saveRawDraft(draft);
  },

  async refineKnowledgeCluster(rawPaths: string[], title = ""): Promise<FocusDraftPayload> {
    return collectApi.refineKnowledgeCluster(rawPaths, title);
  },

  async saveFocusFile(rawPaths: string[], markdown: string, title = ""): Promise<KnowledgeItem> {
    return collectApi.saveFocusFile(rawPaths, markdown, title);
  },

  async listPerspectiveProfiles(): Promise<PerspectiveProfile[]> {
    return mineApi.listPerspectiveProfiles();
  },

  async savePerspectiveProfile(profile: PerspectiveProfile): Promise<PerspectiveProfile[]> {
    return mineApi.savePerspectiveProfile(profile);
  },

  async deletePerspectiveProfile(profileId: string): Promise<PerspectiveProfile[]> {
    return mineApi.deletePerspectiveProfile(profileId);
  },

  async interpretPerspective(sources: KnowledgeItem[], perspective: PerspectiveProfile): Promise<PerspectiveDraft> {
    return mineApi.interpretPerspective(sources, perspective);
  },

  async savePerspectiveFile(
    sources: KnowledgeItem[],
    perspective: PerspectiveProfile,
    markdown: string,
    title = "",
  ): Promise<KnowledgeItem> {
    return mineApi.savePerspectiveFile(sources, perspective, markdown, title);
  },

  async readKnowledge(knowledgeId: number): Promise<KnowledgeItem> {
    return libraryApi.readKnowledge(knowledgeId);
  },

  async updateKnowledge(knowledgeId: number, payload: { title: string; note: string; body: string }): Promise<KnowledgeItem> {
    return libraryApi.updateKnowledge(knowledgeId, payload);
  },

  async deleteKnowledge(knowledgeIds: number[]): Promise<{ items: KnowledgeItem[]; deleted: Array<Record<string, unknown>>; skipped: Array<Record<string, unknown>> }> {
    return libraryApi.deleteKnowledge(knowledgeIds);
  },

  knowledgeDraftMeta(materials: SourceMaterial[], body: string, language: string, timeoutMs?: number) {
    return collectApi.knowledgeDraftMeta(materials, body, language, timeoutMs);
  },

  async commitKnowledgeDraft(draft: KnowledgeDraft): Promise<KnowledgeItem> {
    return libraryApi.commitKnowledgeDraft(draft);
  },

  async readableDocument(materials: SourceMaterial[], parserMode: TextExtractionMode): Promise<KnowledgeItem> {
    return collectApi.readableDocument(materials, parserMode);
  },

  async generateKnowledge(material: SourceMaterial, parserMode: TextExtractionMode = "local_ocr"): Promise<KnowledgeItem> {
    return collectApi.generateKnowledge(material, parserMode);
  },

  writerSession(knowledgeIds: number[]) {
    return writerApi.writerSession(knowledgeIds);
  },

  writerTopics(knowledgeIds: number[]) {
    return writerApi.writerTopics(knowledgeIds);
  },

  writerArticle(knowledgeIds: number[], topic: Record<string, unknown>) {
    return writerApi.writerArticle(knowledgeIds, topic);
  },

  writerRevise(knowledgeIds: number[], markdown: string, workspace?: string) {
    return writerApi.writerRevise(knowledgeIds, markdown, workspace);
  },

  writerPreflight(workspace: string, title: string, digest?: string) {
    return writerApi.writerPreflight(workspace, title, digest);
  },

  writerProjects() {
    return writerApi.writerProjects();
  },

  writerProject(projectId: string) {
    return writerApi.writerProject(projectId);
  },

  createWriterProject(
    name: string,
    knowledgeIds: number[] = [],
    projectType = "article",
    libraryFiles: WriterLibraryFileInput[] = [],
    writingStrategy = "",
    designStrategy = "",
  ) {
    return writerApi.createWriterProject(name, knowledgeIds, projectType, libraryFiles, writingStrategy, designStrategy);
  },

  confirmWriterKnowledge(projectId: string, knowledgeIds: number[], libraryFiles: WriterLibraryFileInput[] = []) {
    return writerApi.confirmWriterKnowledge(projectId, knowledgeIds, libraryFiles);
  },

  generateWriterProjectTopics(projectId: string) {
    return writerApi.generateWriterProjectTopics(projectId);
  },

  selectWriterProjectTopic(projectId: string, topic: Record<string, unknown>) {
    return writerApi.selectWriterProjectTopic(projectId, topic);
  },

  generateWriterProjectDraft(projectId: string, topic?: Record<string, unknown>) {
    return writerApi.generateWriterProjectDraft(projectId, topic);
  },

  reviseWriterProject(projectId: string, instruction: string, markdown?: string) {
    return writerApi.reviseWriterProject(projectId, instruction, markdown);
  },

  suggestWriterProjectImages(projectId: string, markdown?: string, topic?: Record<string, unknown>, contentImageCount = 1) {
    return writerApi.suggestWriterProjectImages(projectId, markdown, topic, contentImageCount);
  },

  generateWriterProjectImages(projectId: string, coverPrompt?: string, contentImagePrompts: string[] = []) {
    return writerApi.generateWriterProjectImages(projectId, coverPrompt, contentImagePrompts);
  },

  generateWriterProjectImageItem(projectId: string, kind: "cover" | "content", prompt: string, index?: number) {
    return writerApi.generateWriterProjectImageItem(projectId, kind, prompt, index);
  },

  formatWriterProject(projectId: string, markdown?: string, designStrategy?: string) {
    return writerApi.formatWriterProject(projectId, markdown, designStrategy);
  },

  preflightWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return writerApi.preflightWriterProject(projectId, title, digest, coverPath);
  },

  publishWriterProject(projectId: string, title: string, digest?: string, coverPath?: string) {
    return writerApi.publishWriterProject(projectId, title, digest, coverPath);
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
    status: "saved",
    confidence: raw.status === "ready" || body ? "medium" : "needsReview",
  };
}

export { authApi } from "./apiAuth";
export { appShellApi } from "./apiAppShell";
export { collectApi } from "./apiCollect";
export { jobsApi } from "./apiJobs";
export { libraryApi } from "./apiLibrary";
export { mineApi } from "./apiMine";
export { quotaApi } from "./apiQuota";
export { settingsApi } from "./apiSettings";
export { writerApi } from "./apiWriter";
