import { CheckCircle2, ChevronLeft, ChevronRight, Eye, FolderPlus, Images, LogIn, Pencil, Save, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { WriterLibraryFileInput } from "../api";
import type { XhsImageRetryTask } from "../hooks/useXhsFlow";
import { xhsApi } from "../apiXhs";
import type { KnowledgeItem, XhsAccountProfile, XhsCarouselStrategy, XhsLoginStatus, XhsProject, XhsProjectState, XhsRunningTask, XhsStep } from "../domain";
import { EmptyState } from "../components/EmptyState";
import { Stepper } from "../components/Stepper";

const stages: Array<{ id: XhsStep; zh: string; en: string }> = [
  { id: "created", zh: "项目素材", en: "Sources" },
  { id: "topics", zh: "选题", en: "Topics" },
  { id: "draft", zh: "图文草稿", en: "Draft" },
  { id: "images", zh: "图片生成", en: "Image generation" },
  { id: "publish_check", zh: "发布预检", en: "Preflight" },
  { id: "publish_ready", zh: "确认发布", en: "Publish" },
];

type XhsWorkflowStage = XhsStep;

const stageIndex: Record<string, number> = {
  created: 0,
  knowledge_confirmed: 0,
  topics: 1,
  topic: 2,
  topic_configured: 2,
  draft: 2,
  images: 3,
  publish_check: 4,
  publish_ready: 5,
  published: 5,
};

const imageTextModes = [
  { id: "tutorial", zh: "教程轮播", en: "Tutorial carousel", slides: 6, structure: "封面承诺 -> 步骤拆解 -> 结果/CTA", body: "适合教学、方法论、流程拆解。每张图只讲一个步骤，标题用动词开头，封面必须给出明确承诺。" },
  { id: "listicle", zh: "清单轮播", en: "List carousel", slides: 6, structure: "封面清单 -> 分项价值 -> 总结收藏", body: "适合资料整理、工具/渠道/方法清单、避坑 checklist。强调可收藏价值，每个分项都要有一句为什么值得记。" },
  { id: "pitfall", zh: "避坑轮播", en: "Pitfall carousel", slides: 5, structure: "痛点/误区 -> 风险解释 -> 正确做法", body: "适合纠偏、风险提示、常见错误。语气像提醒朋友，不制造焦虑；风险判断必须回到材料依据。" },
  { id: "comparison", zh: "对比轮播", en: "Comparison carousel", slides: 5, structure: "对比对象 -> 维度拆解 -> 选择建议", body: "适合方案选择、政策/产品/路径对比。每页固定同一对比维度，最后给条件化建议。" },
  { id: "case_study", zh: "案例拆解", en: "Case breakdown", slides: 5, structure: "案例背景 -> 关键动作 -> 可复用结论", body: "适合热点案例、公司/个人/政策动作拆解。先讲故事，再提炼方法，把可复用结论单独拎出来。" },
  { id: "single_opinion", zh: "单图观点", en: "Single-image opinion", slides: 1, structure: "一个强观点 + 一个清晰理由", body: "适合一句话观点、轻量提醒、强钩子表达。只表达一个重点，画面干净，正文承担解释。" },
];

const coverTypes = [
  { id: "hook_text", zh: "大字钩子封面", en: "Bold hook cover" },
  { id: "problem_promise", zh: "痛点承诺封面", en: "Problem-promise cover" },
  { id: "before_after", zh: "前后对比封面", en: "Before-after cover" },
  { id: "checklist", zh: "清单数字封面", en: "Numbered checklist cover" },
];

const layoutStyles = [
  { id: "balanced", zh: "图文平衡", en: "Balanced" },
  { id: "text_first", zh: "文字优先", en: "Text-first" },
  { id: "visual_first", zh: "视觉优先", en: "Visual-first" },
  { id: "split", zh: "左右分栏", en: "Split layout" },
];

type Props = {
  language: "zh" | "en";
  rightRail: ReactNode;
  selectedKnowledgeFiles: KnowledgeItem[];
  projects: XhsProject[];
  state?: XhsProjectState;
  selectedProjectId?: string;
  accountProfiles: XhsAccountProfile[];
  carouselStrategies: XhsCarouselStrategy[];
  selectedAccountProfileId: string;
  isRunning: boolean;
  runningTask?: XhsRunningTask;
  isCloudMember?: boolean;
  loginStatus?: XhsLoginStatus;
  onSelectAccountProfile: (profileId: string) => void;
  onSaveAccountProfile: (profile: XhsAccountProfileInput, profileId?: string) => Promise<XhsAccountProfile | undefined>;
  onDeleteAccountProfile: (profileId: string) => void;
  onSaveCarouselStrategy: (strategy: { id?: string; name: string; description?: string; config: Record<string, unknown> }) => Promise<XhsCarouselStrategy | undefined>;
  onDeleteCarouselStrategy: (strategyId: string) => void;
  onCreateProject: (name: string, accountProfileId: string, libraryFiles: WriterLibraryFileInput[]) => void;
  onSelectProject: (projectId: string) => void;
  onImportKnowledge: (libraryFiles: WriterLibraryFileInput[]) => void;
  onGenerateTopics: () => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onConfigureImageText: (config: Record<string, unknown>) => void;
  onGenerateDraft: () => void;
  onConfirmDraft: () => void;
  onReviseDraft: (instruction: string, content?: string) => void;
  onSuggestImages: (content?: string) => void;
  onConfirmImageSuggestions: () => void;
  onGenerateImages: (coverPrompt?: string, contentImagePrompts?: string[], onProgress?: (done: number, total: number) => void) => void;
  onRetryImageItems: (tasks: XhsImageRetryTask[], onProgress?: (done: number, total: number) => void) => void;
  onEnterPreflight?: () => void;
  onRefreshLogin: () => void;
  onPreflight: () => void;
  onExportPackage: () => void;
  onFillPublish: () => void;
  onConfirmPublish: () => void;
  onSavePublishDraft: () => void;
};

type XhsAccountProfileInput = Omit<XhsAccountProfile, "id" | "created_at" | "updated_at">;
type XhsImageProgress = { done: number; total: number } | null;

function formatElapsedTime(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${pad(minutes)}:${pad(rest)}`;
}

function RunningButtonLabel({
  taskId,
  runningTask,
  children,
}: {
  taskId: string;
  runningTask?: XhsRunningTask;
  children: ReactNode;
}) {
  const [now, setNow] = useState(() => Date.now());
  const isActive = runningTask?.id === taskId;

  useEffect(() => {
    if (!isActive) return undefined;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isActive, runningTask?.startedAt]);

  if (!isActive || !runningTask) return <>{children}</>;

  const elapsedSeconds = (now - runningTask.startedAt) / 1000;
  return (
    <span className="xhs-running-label">
      <span>{runningTask.runningLabel}</span>
      <span className="xhs-running-time">{formatElapsedTime(elapsedSeconds)}</span>
    </span>
  );
}

export function XhsWorkspace({
  language,
  rightRail,
  selectedKnowledgeFiles,
  projects,
  state,
  selectedProjectId,
  accountProfiles,
  carouselStrategies,
  selectedAccountProfileId,
  isRunning,
  runningTask,
  isCloudMember = false,
  loginStatus,
  onSelectAccountProfile,
  onSaveAccountProfile,
  onDeleteAccountProfile,
  onSaveCarouselStrategy,
  onDeleteCarouselStrategy,
  onCreateProject,
  onSelectProject,
  onImportKnowledge,
  onGenerateTopics,
  onSelectTopic,
  onConfigureImageText,
  onGenerateDraft,
  onConfirmDraft,
  onReviseDraft,
  onSuggestImages,
  onConfirmImageSuggestions,
  onGenerateImages,
  onRetryImageItems,
  onRefreshLogin,
  onPreflight,
  onExportPackage,
  onFillPublish,
  onConfirmPublish,
  onSavePublishDraft,
}: Props) {
  const [createMode, setCreateMode] = useState(!state?.project);
  const [projectName, setProjectName] = useState("");
  const [projectNameTouched, setProjectNameTouched] = useState(false);
  const [pendingTopic, setPendingTopic] = useState<Record<string, unknown> | null>(null);
  const [imageTextConfig, setImageTextConfig] = useState<Record<string, unknown>>({});
  const [revision, setRevision] = useState("");
  const [profileDialogMode, setProfileDialogMode] = useState<"create" | "edit" | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [reviewStage, setReviewStage] = useState<XhsWorkflowStage | null>(null);
  const [imageProgress, setImageProgress] = useState<XhsImageProgress>(null);
  const [editingProfile, setEditingProfile] = useState<XhsAccountProfile | undefined>();
  const projectNameInputRef = useRef<HTMLInputElement>(null);
  const selectedFiles = useMemo(() => toWriterLibraryFiles(selectedKnowledgeFiles), [selectedKnowledgeFiles]);
  const selectedAccountProfile = useMemo(
    () => accountProfiles.find((item) => item.id === selectedAccountProfileId),
    [accountProfiles, selectedAccountProfileId],
  );
  const project = state?.project;
  const step = state?.step ?? "created";
  const nextAction = state?.next_action ?? "";
  const actualStage = xhsStageForStep(step, nextAction, project);
  const actualStageIndex = stageIndex[actualStage] ?? 0;
  const visibleStage = reviewStage && (stageIndex[reviewStage] ?? 0) <= actualStageIndex ? reviewStage : actualStage;
  const visibleStep = xhsStepForStage(visibleStage, step, project);
  const visibleNextAction = nextActionForVisibleXhsStep(visibleStep, step, nextAction, project);
  const visibleIndex = stageIndex[visibleStage] ?? 0;
  const isReviewingStep = visibleStage !== actualStage;
  const clearReviewStage = () => setReviewStage(null);
  const projectNameMissingReason = language === "zh" ? "请先填写项目名称" : "Enter a project name first.";
  const createDisabledReason = !selectedAccountProfileId
    ? language === "zh"
      ? "请先选择或新建账号定位"
      : "Select or create an account profile first."
    : "";
  const visibleCreateReason = createDisabledReason;
  const submitCreateProject = () => {
    const fallbackName = selectedFiles[0]?.title || selectedFiles[0]?.markdown_path || (language === "zh" ? "未命名小红书图文" : "Untitled XHS post");
    const name = projectNameInputRef.current?.value.trim() || projectName.trim() || fallbackName;
    if (createDisabledReason) return;
    onCreateProject(name, selectedAccountProfileId, selectedFiles);
    setProjectName("");
    setProjectNameTouched(false);
  };

  useEffect(() => {
    if (project?.id) setCreateMode(false);
    setPendingTopic(null);
    const savedConfig = recordValue(project?.image_text_config);
    setImageTextConfig(Object.keys(savedConfig).length ? savedConfig : defaultImageTextConfig(recordValue(project?.topic)));
    setRevision("");
    setReviewStage(null);
  }, [project?.id, project?.topic, project?.image_text_config]);

  useEffect(() => {
    setImageProgress(null);
  }, [project?.id]);

  useEffect(() => {
    if (reviewStage && (stageIndex[reviewStage] ?? 0) > actualStageIndex) setReviewStage(null);
  }, [actualStageIndex, reviewStage]);

  return (
    <section className="xhs-workspace create-project-layout">
      <aside className="content-panel project-list-panel">
        <div className="panel-heading">
          <h2>{language === "zh" ? "小红书项目" : "XHS Projects"}</h2>
          <button className="secondary-button" type="button" disabled={isRunning} onClick={() => setCreateMode(true)}>
            <FolderPlus size={16} />
            {language === "zh" ? "新建" : "New"}
          </button>
        </div>
        <div className="project-list">
          {projects.length ? (
            projects.map((item) => (
              <button
                key={item.id}
                type="button"
                className={item.id === selectedProjectId ? "project-row selected" : "project-row"}
                onClick={() => onSelectProject(item.id)}
              >
                <strong>{item.title || item.name || item.id}</strong>
                <span>{language === "zh" ? "小红书图文" : "XHS post"} · {item.workspace}</span>
              </button>
            ))
          ) : (
            <EmptyState
              title={language === "zh" ? "还没有小红书项目" : "No XHS projects yet"}
              body={language === "zh" ? "新建项目后，选题、图文、图片和发布记录都会保存在本地。" : "Create a project to keep drafts, images, and publish records locally."}
            />
          )}
        </div>
      </aside>

      <div className="workspace-main">
        {createMode || !project ? (
          <section className="content-panel project-setup-guide xhs-setup-panel">
            <div className="stage-panel-heading">
              <div>
                <span>{language === "zh" ? "小红书图文" : "XHS image-text"}</span>
                <h2>{language === "zh" ? "创建一个图文项目" : "Create an image-text project"}</h2>
              </div>
              {project ? (
                <button className="secondary-button" type="button" onClick={() => setCreateMode(false)}>
                  {language === "zh" ? "返回当前项目" : "Back"}
                </button>
              ) : null}
            </div>
            <label className="field-label">
              <span>{language === "zh" ? "项目名" : "Project name"}</span>
              <input
                ref={projectNameInputRef}
                value={projectName}
                onBlur={() => setProjectNameTouched(true)}
                onChange={(event) => {
                  setProjectName(event.target.value);
                  if (event.target.value.trim()) setProjectNameTouched(false);
                }}
                placeholder={language === "zh" ? "例如：AI 工具避坑图文" : "e.g. AI tools carousel"}
              />
            </label>
            <section className="project-section xhs-profile-picker">
              <div className="section-heading">
                <h2>{language === "zh" ? "账号定位" : "Account profile"}</h2>
                <span>{accountProfiles.length}</span>
              </div>
              {accountProfiles.length ? (
                <>
                  <label className="field-label">
                    <span>{language === "zh" ? "选择已有账号定位" : "Select an existing profile"}</span>
                    <select value={selectedAccountProfileId} onChange={(event) => onSelectAccountProfile(event.target.value)}>
                      {accountProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name} · {profile.positioning}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedAccountProfile ? <AccountProfileSummary profile={selectedAccountProfile} language={language} /> : null}
                  <div className="xhs-profile-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={isRunning}
                      onClick={() => {
                        setEditingProfile(undefined);
                        setProfileDialogMode("create");
                      }}
                    >
                      <FolderPlus size={16} />
                      {language === "zh" ? "新建定位" : "New profile"}
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={isRunning || !selectedAccountProfile}
                      onClick={() => {
                        setEditingProfile(selectedAccountProfile);
                        setProfileDialogMode("edit");
                      }}
                    >
                      <Pencil size={16} />
                      {language === "zh" ? "编辑" : "Edit"}
                    </button>
                    <button
                      className="secondary-button danger-button"
                      type="button"
                      disabled={isRunning || !selectedAccountProfile}
                      onClick={() => {
                        if (!selectedAccountProfile) return;
                        if (window.confirm(language === "zh" ? `确认删除账号定位「${selectedAccountProfile.name}」？` : `Delete account profile "${selectedAccountProfile.name}"?`)) {
                          onDeleteAccountProfile(selectedAccountProfile.id);
                        }
                      }}
                    >
                      <Trash2 size={16} />
                      {language === "zh" ? "删除" : "Delete"}
                    </button>
                  </div>
                </>
              ) : (
                <div className="xhs-profile-empty">
                  <EmptyState title={language === "zh" ? "还没有账号定位" : "No account profiles yet"} body={language === "zh" ? "先新建账号定位，后续选题、标题、正文、封面和标签都会参考它。" : "Create a profile first; topics, titles, captions, covers, and tags will follow it."} />
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isRunning}
                    onClick={() => {
                      setEditingProfile(undefined);
                      setProfileDialogMode("create");
                    }}
                  >
                    <FolderPlus size={16} />
                    {language === "zh" ? "新建账号定位" : "Create account profile"}
                  </button>
                </div>
              )}
            </section>
            <section className="project-section setup-selected-files">
              <div className="section-heading">
                <h2>{language === "zh" ? "选中文件列表" : "Selected files"}</h2>
                <span>{selectedFiles.length}</span>
              </div>
              {selectedFiles.length ? (
                <div className="reference-list compact">
                  {selectedFiles.map((item) => (
                    <article key={`${item.library}-${item.markdown_path}`} className="reference-row">
                      <strong>{item.title || item.markdown_path}</strong>
                      <span>{libraryLabel(item.library, language)} · {item.markdown_path}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState title={language === "zh" ? "右侧勾选文件后会显示在这里" : "Checked library files appear here"} />
              )}
            </section>
            <button
              className="primary-cta"
              type="button"
              disabled={isRunning || Boolean(createDisabledReason)}
              title={visibleCreateReason}
              onClick={submitCreateProject}
            >
              <strong>
                <RunningButtonLabel taskId="create_project" runningTask={runningTask}>
                  {language === "zh" ? "创建并进入工作流" : "Create and start"}
                </RunningButtonLabel>
              </strong>
            </button>
            {visibleCreateReason ? <p className="disabled-reason">{visibleCreateReason}</p> : null}
          </section>
        ) : (
          <>
            <div className="create-stepper-wrap">
              <Stepper
                steps={stages.map((item) => (language === "zh" ? item.zh : item.en))}
                activeIndex={visibleIndex}
                progressIndex={actualStageIndex}
                maxSelectableIndex={actualStageIndex}
                onSelect={(index) => setReviewStage(stages[index]?.id ?? null)}
              />
            </div>
            <section className="content-panel xhs-stage-panel">
              <XhsStage
                language={language}
                project={project}
                step={visibleStep}
                nextAction={visibleNextAction}
                selectedFiles={selectedFiles}
                pendingTopic={pendingTopic}
                imageTextConfig={imageTextConfig}
                carouselStrategies={carouselStrategies}
                revision={revision}
                loginStatus={loginStatus}
                imageProgress={imageProgress}
              isCloudMember={isCloudMember}
              isRunning={isRunning}
              runningTask={runningTask}
                onPendingTopicChange={setPendingTopic}
                onImportKnowledge={() => {
                  clearReviewStage();
                  onImportKnowledge(selectedFiles);
                }}
                onGenerateTopics={() => {
                  clearReviewStage();
                  onGenerateTopics();
                }}
                onSelectTopic={(topic) => {
                  clearReviewStage();
                  onSelectTopic(topic);
                }}
                onImageTextConfigChange={setImageTextConfig}
                onConfirmImageTextConfig={() => {
                  clearReviewStage();
                  onConfigureImageText(imageTextConfig);
                }}
                onGenerateDraft={() => {
                  clearReviewStage();
                  onGenerateDraft();
                }}
                onConfirmDraft={() => {
                  clearReviewStage();
                  onConfirmDraft();
                }}
                onSaveCarouselStrategy={onSaveCarouselStrategy}
                onDeleteCarouselStrategy={onDeleteCarouselStrategy}
                onRevisionChange={setRevision}
                onRevise={() => {
                  clearReviewStage();
                  onReviseDraft(revision, project.content);
                  setRevision("");
                }}
                onSuggestImages={() => {
                  clearReviewStage();
                  onSuggestImages(project.content);
                }}
                onConfirmImageSuggestions={() => {
                  clearReviewStage();
                  onConfirmImageSuggestions();
                }}
                onGenerateImages={() => {
                  clearReviewStage();
                  const contentPrompts = stringList(project.content_image_prompts);
                  const total = xhsImageTaskTotal(project.cover_prompt, contentPrompts);
                  setImageProgress({ done: 0, total });
                  onGenerateImages(project.cover_prompt, contentPrompts, (done, total) => setImageProgress({ done, total }));
                }}
                onRetryImageItems={(tasks) => {
                  clearReviewStage();
                  if (!tasks.length) return;
                  setImageProgress({ done: 0, total: tasks.length });
                  onRetryImageItems(tasks, (done, total) => setImageProgress({ done, total }));
                }}
                onEnterPreflight={() => setReviewStage("publish_check")}
                onPreview={() => setPreviewOpen(true)}
                onRefreshLogin={onRefreshLogin}
                onPreflight={() => {
                  clearReviewStage();
                  onPreflight();
                }}
                onExportPackage={() => {
                  clearReviewStage();
                  onExportPackage();
                }}
                onFillPublish={() => {
                  clearReviewStage();
                  onFillPublish();
                }}
                onConfirmPublish={() => {
                  clearReviewStage();
                  onConfirmPublish();
                }}
                onSavePublishDraft={onSavePublishDraft}
              />
            </section>
          </>
        )}
      </div>
      {rightRail}
      {profileDialogMode ? (
        <AccountProfileDialog
          language={language}
          mode={profileDialogMode}
          profile={editingProfile}
          isRunning={isRunning}
          onClose={() => {
            setProfileDialogMode(null);
            setEditingProfile(undefined);
          }}
          onSave={async (profile) => {
            await onSaveAccountProfile(profile, editingProfile?.id);
            setProfileDialogMode(null);
            setEditingProfile(undefined);
          }}
        />
      ) : null}
      {previewOpen && project ? <XhsPreviewDialog language={language} project={project} onClose={() => setPreviewOpen(false)} /> : null}
    </section>
  );
}

function AccountProfileSummary({ profile, language }: { profile: XhsAccountProfile; language: "zh" | "en" }) {
  return (
    <article className="xhs-profile-summary">
      <strong>{profile.positioning}</strong>
      <span>{language === "zh" ? "目标人群" : "Audience"}：{profile.target_audience}</span>
      <span>{language === "zh" ? "内容支柱" : "Pillars"}：{stringList(profile.content_pillars).join(" / ")}</span>
      {profile.tone ? <span>{language === "zh" ? "语气人设" : "Tone"}：{profile.tone}</span> : null}
    </article>
  );
}

function AccountProfileDialog({
  language,
  mode,
  profile,
  isRunning,
  onClose,
  onSave,
}: {
  language: "zh" | "en";
  mode: "create" | "edit";
  profile?: XhsAccountProfile;
  isRunning: boolean;
  onClose: () => void;
  onSave: (profile: XhsAccountProfileInput) => Promise<void>;
}) {
  const [draft, setDraft] = useState(() => profileToDraft(profile));
  const [error, setError] = useState("");
  const update = (key: keyof AccountProfileDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setError("");
  };
  const submit = () => {
    const payload = draftToProfile(draft);
    if (!payload.name.trim() || !payload.positioning.trim() || !payload.target_audience.trim() || !payload.content_pillars.length) {
      setError(language === "zh" ? "请填写定位名称、一句话定位、目标人群和至少一个内容支柱。" : "Fill name, positioning, audience, and at least one content pillar.");
      return;
    }
    onSave(payload).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  };
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={language === "zh" ? "账号定位" : "Account profile"}>
      <div className="modal-panel xhs-profile-modal">
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "小红书账号定位" : "XHS account profile"}</span>
            <h2>{mode === "edit" ? (language === "zh" ? "编辑账号定位" : "Edit account profile") : language === "zh" ? "新建账号定位" : "Create account profile"}</h2>
          </div>
          <button className="secondary-button" type="button" onClick={onClose} disabled={isRunning}>
            {language === "zh" ? "关闭" : "Close"}
          </button>
        </div>
        <div className="xhs-profile-form">
          <ProfileInput label={language === "zh" ? "定位名称" : "Profile name"} value={draft.name} onChange={(value) => update("name", value)} required />
          <ProfileInput label={language === "zh" ? "账号名/拟定账号名" : "Account name"} value={draft.account_name} onChange={(value) => update("account_name", value)} />
          <ProfileInput label={language === "zh" ? "一句话账号定位" : "One-line positioning"} value={draft.positioning} onChange={(value) => update("positioning", value)} required />
          <ProfileInput label={language === "zh" ? "目标人群" : "Target audience"} value={draft.target_audience} onChange={(value) => update("target_audience", value)} required />
          <ProfileTextArea label={language === "zh" ? "用户痛点" : "Audience pain points"} value={draft.audience_pain_points} onChange={(value) => update("audience_pain_points", value)} />
          <ProfileTextArea label={language === "zh" ? "内容支柱（3-5 个）" : "Content pillars"} value={draft.content_pillars} onChange={(value) => update("content_pillars", value)} required />
          <ProfileInput label={language === "zh" ? "账号语气/人设风格" : "Tone/persona"} value={draft.tone} onChange={(value) => update("tone", value)} />
          <ProfileInput label={language === "zh" ? "核心价值承诺" : "Value promise"} value={draft.value_promise} onChange={(value) => update("value_promise", value)} />
          <ProfileTextArea label={language === "zh" ? "常用内容形式" : "Content formats"} value={draft.content_formats} onChange={(value) => update("content_formats", value)} />
          <ProfileTextArea label={language === "zh" ? "大类标签" : "Broad tags"} value={draft.broad_tags} onChange={(value) => update("broad_tags", value)} />
          <ProfileTextArea label={language === "zh" ? "细分标签" : "Niche tags"} value={draft.niche_tags} onChange={(value) => update("niche_tags", value)} />
          <ProfileTextArea label={language === "zh" ? "场景/趋势标签" : "Trend/context tags"} value={draft.trend_tags} onChange={(value) => update("trend_tags", value)} />
          <ProfileTextArea label={language === "zh" ? "自有标签" : "Branded tags"} value={draft.branded_tags} onChange={(value) => update("branded_tags", value)} />
          <ProfileTextArea label={language === "zh" ? "不做/慎做内容边界" : "Avoid topics"} value={draft.avoid_topics} onChange={(value) => update("avoid_topics", value)} />
          <ProfileTextArea label={language === "zh" ? "补充说明" : "Notes"} value={draft.notes} onChange={(value) => update("notes", value)} />
        </div>
        {error ? <p className="form-error">{error}</p> : null}
        <div className="strategy-modal-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={isRunning}>
            {language === "zh" ? "取消" : "Cancel"}
          </button>
          <button className="primary-cta" type="button" onClick={submit} disabled={isRunning}>
            <strong>{language === "zh" ? "保存账号定位" : "Save profile"}</strong>
          </button>
        </div>
      </div>
    </div>
  );
}

function ProfileInput({ label, value, onChange, required }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return (
    <label className="field-label">
      <span>{label}{required ? " *" : ""}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ProfileTextArea({ label, value, onChange, required }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return (
    <label className="field-label">
      <span>{label}{required ? " *" : ""}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder="每行一个" />
    </label>
  );
}

type AccountProfileDraft = {
  name: string;
  account_name: string;
  positioning: string;
  target_audience: string;
  audience_pain_points: string;
  content_pillars: string;
  tone: string;
  value_promise: string;
  content_formats: string;
  broad_tags: string;
  niche_tags: string;
  trend_tags: string;
  branded_tags: string;
  avoid_topics: string;
  notes: string;
};

function profileToDraft(profile?: XhsAccountProfile): AccountProfileDraft {
  return {
    name: profile?.name ?? "",
    account_name: profile?.account_name ?? "",
    positioning: profile?.positioning ?? "",
    target_audience: profile?.target_audience ?? "",
    audience_pain_points: stringList(profile?.audience_pain_points).join("\n"),
    content_pillars: stringList(profile?.content_pillars).join("\n"),
    tone: profile?.tone ?? "",
    value_promise: profile?.value_promise ?? "",
    content_formats: stringList(profile?.content_formats).join("\n"),
    broad_tags: stringList(profile?.tag_strategy?.broad_tags).join("\n"),
    niche_tags: stringList(profile?.tag_strategy?.niche_tags).join("\n"),
    trend_tags: stringList(profile?.tag_strategy?.trend_tags).join("\n"),
    branded_tags: stringList(profile?.tag_strategy?.branded_tags).join("\n"),
    avoid_topics: stringList(profile?.avoid_topics).join("\n"),
    notes: profile?.notes ?? "",
  };
}

function draftToProfile(draft: AccountProfileDraft): XhsAccountProfileInput {
  return {
    name: draft.name.trim(),
    account_name: draft.account_name.trim(),
    positioning: draft.positioning.trim(),
    target_audience: draft.target_audience.trim(),
    audience_pain_points: lines(draft.audience_pain_points),
    content_pillars: lines(draft.content_pillars),
    tone: draft.tone.trim(),
    value_promise: draft.value_promise.trim(),
    content_formats: lines(draft.content_formats),
    tag_strategy: {
      broad_tags: lines(draft.broad_tags),
      niche_tags: lines(draft.niche_tags),
      trend_tags: lines(draft.trend_tags),
      branded_tags: lines(draft.branded_tags),
    },
    avoid_topics: lines(draft.avoid_topics),
    notes: draft.notes.trim(),
  };
}

function XhsStage({
  language,
  project,
  step,
  nextAction,
  selectedFiles,
  pendingTopic,
  imageTextConfig,
  carouselStrategies,
  revision,
  loginStatus,
  imageProgress,
  isCloudMember,
  isRunning,
  runningTask,
  onPendingTopicChange,
  onImportKnowledge,
  onGenerateTopics,
  onSelectTopic,
  onImageTextConfigChange,
  onConfirmImageTextConfig,
  onGenerateDraft,
  onConfirmDraft,
  onSaveCarouselStrategy,
  onDeleteCarouselStrategy,
  onRevisionChange,
  onRevise,
  onSuggestImages,
  onConfirmImageSuggestions,
  onGenerateImages,
  onRetryImageItems,
  onEnterPreflight,
  onPreview,
  onRefreshLogin,
  onPreflight,
  onExportPackage,
  onFillPublish,
  onConfirmPublish,
  onSavePublishDraft,
}: {
  language: "zh" | "en";
  project: XhsProject;
  step: XhsStep;
  nextAction: string;
  selectedFiles: WriterLibraryFileInput[];
  pendingTopic: Record<string, unknown> | null;
  imageTextConfig: Record<string, unknown>;
  carouselStrategies: XhsCarouselStrategy[];
  revision: string;
  loginStatus?: XhsLoginStatus;
  imageProgress: XhsImageProgress;
  isCloudMember?: boolean;
  isRunning: boolean;
  runningTask?: XhsRunningTask;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onImportKnowledge: () => void;
  onGenerateTopics: () => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onImageTextConfigChange: (config: Record<string, unknown>) => void;
  onConfirmImageTextConfig: () => void;
  onGenerateDraft: () => void;
  onConfirmDraft: () => void;
  onSaveCarouselStrategy: (strategy: { id?: string; name: string; description?: string; config: Record<string, unknown> }) => Promise<XhsCarouselStrategy | undefined>;
  onDeleteCarouselStrategy: (strategyId: string) => void;
  onRevisionChange: (value: string) => void;
  onRevise: () => void;
  onSuggestImages: () => void;
  onConfirmImageSuggestions: () => void;
  onGenerateImages: () => void;
  onRetryImageItems: (tasks: XhsImageRetryTask[]) => void;
  onEnterPreflight?: () => void;
  onPreview: () => void;
  onRefreshLogin: () => void;
  onPreflight: () => void;
  onExportPackage: () => void;
  onFillPublish: () => void;
  onConfirmPublish: () => void;
  onSavePublishDraft: () => void;
}) {
  if (step === "created") {
    return (
      <div className="xhs-two-column">
        <div>
          <h2>{language === "zh" ? "导入项目素材" : "Import sources"}</h2>
          <p className="muted-copy">{language === "zh" ? "小红书图文会基于右侧勾选的原文、重点或视角文件生成。" : "The post will be generated from checked library files."}</p>
          <button className="secondary-button" type="button" disabled={!selectedFiles.length || isRunning} onClick={onImportKnowledge}>
            <CheckCircle2 size={16} />
            <RunningButtonLabel taskId="import_knowledge" runningTask={runningTask}>{language === "zh" ? `导入 ${selectedFiles.length} 个文件` : `Import ${selectedFiles.length} files`}</RunningButtonLabel>
          </button>
        </div>
        <SourceList files={libraryFileItems(project)} language={language} />
      </div>
    );
  }

  if (step === "knowledge_confirmed" || step === "topics") {
    const topics = topicItems(project);
    const libraryFiles = libraryFileItems(project);
    const sourceCount = libraryFiles.length;
    return (
      <div className="xhs-topic-grid">
        <div className="xhs-topic-context">
          <div>
            <span>{language === "zh" ? "账号定位" : "Account profile"}</span>
            <strong>{project.account_profile?.positioning || project.account_profile?.name || (language === "zh" ? "未设置账号定位" : "No account profile")}</strong>
            {project.account_profile?.target_audience ? <p>{project.account_profile.target_audience}</p> : null}
          </div>
          <div>
            <span>{language === "zh" ? "项目素材" : "Project sources"}</span>
            <strong>{language === "zh" ? `${sourceCount} 个文件` : `${sourceCount} files`}</strong>
            <p>{libraryFiles.slice(0, 3).map((file) => file.title || file.markdown_path).join(" / ")}</p>
          </div>
          <button className="primary-cta" type="button" disabled={isRunning || sourceCount === 0} onClick={onGenerateTopics}>
            <Sparkles size={16} />
            <strong>
              <RunningButtonLabel taskId="generate_topics" runningTask={runningTask}>
                {topics.length ? (language === "zh" ? "重新生成选题" : "Regenerate topics") : language === "zh" ? "智能生成选题" : "Generate topics"}
              </RunningButtonLabel>
            </strong>
          </button>
        </div>
        {topics.length ? (
          topics.map((topic, index) => {
            const selected = pendingTopic === topic;
            return (
              <button
                key={index}
                type="button"
                className={selected ? "xhs-topic-card selected" : "xhs-topic-card"}
                onClick={() => onPendingTopicChange(topic)}
                onDoubleClick={() => onSelectTopic(topic)}
              >
                <strong>{text(topic.title_hook, topic.cover_hook, topic.title, topic.name, language === "zh" ? `选题 ${index + 1}` : `Topic ${index + 1}`)}</strong>
                <span>{xhsTopicSummary(topic, language)}</span>
              </button>
            );
          })
        ) : (
          <EmptyState title={language === "zh" ? "等待生成选题" : "Ready for topics"} body={language === "zh" ? "点击智能生成选题，会根据账号定位和已导入素材调用 API 生成小红书图文建议。" : "Generate topic ideas from the account profile and imported project sources."} />
        )}
        <div className="xhs-stage-actions">
          <button className="primary-cta" type="button" disabled={isRunning || !pendingTopic} onClick={() => pendingTopic ? onSelectTopic(pendingTopic) : undefined}>
            <CheckCircle2 size={16} />
            <strong>
              <RunningButtonLabel taskId="select_topic" runningTask={runningTask}>
                {language === "zh" ? "确认选题" : "Confirm topic"}
              </RunningButtonLabel>
            </strong>
          </button>
          {!pendingTopic && topics.length ? <span>{language === "zh" ? "请先点选一个选题。" : "Select a topic first."}</span> : null}
        </div>
      </div>
    );
  }

  if (step === "topic" || step === "topic_configured") {
    return (
      <ImageTextConfigPanel
        language={language}
        topic={project.topic ?? {}}
        config={imageTextConfig}
        strategies={carouselStrategies}
        isConfigured={step === "topic_configured"}
        isRunning={isRunning}
        runningTask={runningTask}
        onGenerateDraft={onGenerateDraft}
        onChange={onImageTextConfigChange}
        onConfirm={onConfirmImageTextConfig}
        onSaveStrategy={onSaveCarouselStrategy}
        onDeleteStrategy={onDeleteCarouselStrategy}
      />
    );
  }

  if (step === "draft") {
    return (
      <div className="xhs-editor-main">
        <div className="xhs-title-row">
          <div>
            <span>{language === "zh" ? "图文草稿" : "Draft"}</span>
            <h2>{project.title || project.name}</h2>
          </div>
          <strong>{titleUnits(project.title || "").toFixed(1)}/20</strong>
        </div>
        <SlidePlan project={project} language={language} />
        {project.content ? (
          <textarea className="xhs-content-editor" value={project.content} readOnly />
        ) : (
          <div className="xhs-draft-empty">
            <strong>{language === "zh" ? "还没有图文正文" : "No draft content yet"}</strong>
            <span>{language === "zh" ? "请先生成图文草稿，完成内容写作后再进入图片生成。" : "Generate the draft before moving into image generation."}</span>
          </div>
        )}
        <div className="xhs-tag-row">
          {tagItems(project).map((tag) => (
            <span key={tag}>#{tag}</span>
          ))}
        </div>
        <label className="field-label">
          <span>{language === "zh" ? "修订要求" : "Revision"}</span>
          <textarea value={revision} onChange={(event) => onRevisionChange(event.target.value)} placeholder={language === "zh" ? "例如：标题更像小红书，正文更短，CTA 更明确" : "e.g. tighten the caption and CTA"} />
        </label>
        <div className="xhs-stage-actions">
          <button className="secondary-button" type="button" disabled={!revision.trim() || isRunning} onClick={onRevise}>
            <Save size={16} />
            <RunningButtonLabel taskId="revise_draft" runningTask={runningTask}>{language === "zh" ? "按要求修订" : "Revise"}</RunningButtonLabel>
          </button>
          <button className="primary-cta" type="button" disabled={isRunning || !project.content} onClick={onConfirmDraft}>
            <CheckCircle2 size={16} />
            <strong>
              <RunningButtonLabel taskId="confirm_draft" runningTask={runningTask}>
                {language === "zh" ? "确认草稿，进入图片生成" : "Confirm draft and continue"}
              </RunningButtonLabel>
            </strong>
          </button>
          <span>{language === "zh" ? "草稿确认后，下一步才会生成配图建议。" : "After confirmation, image suggestions become available."}</span>
        </div>
      </div>
    );
  }

  if (step === "images") {
    return (
      <div className="xhs-editor-main">
        <div className="xhs-title-row">
          <div>
            <span>{language === "zh" ? "图片生成" : "Image generation"}</span>
            <h2>{project.title || project.name}</h2>
          </div>
          <strong>{imageItems(project).length} {language === "zh" ? "张图" : "images"}</strong>
        </div>
        <ImageGenerationPanel
          language={language}
          project={project}
          nextAction={nextAction}
          progress={imageProgress}
          isRunning={isRunning}
          runningTask={runningTask}
          onSuggestImages={onSuggestImages}
          onConfirmImageSuggestions={onConfirmImageSuggestions}
          onGenerateImages={onGenerateImages}
          onRetryImageItems={onRetryImageItems}
          onEnterPreflight={onEnterPreflight}
          onPreview={onPreview}
        />
      </div>
    );
  }

  return (
    <div className="xhs-editor-main">
      <div className="xhs-title-row">
        <div>
          <span>{language === "zh" ? "发布预检" : "Publish preflight"}</span>
          <h2>{project.title || project.name}</h2>
        </div>
        <strong>{project.preflight?.ok ? (language === "zh" ? "已通过" : "Passed") : language === "zh" ? "待处理" : "Needs review"}</strong>
      </div>
      <PublishTools
        language={language}
        step={step}
        nextAction={nextAction}
        project={project}
        loginStatus={loginStatus}
        isCloudMember={Boolean(isCloudMember)}
        isRunning={isRunning}
        runningTask={runningTask}
        onRefreshLogin={onRefreshLogin}
        onPreflight={onPreflight}
        onExportPackage={onExportPackage}
        onFillPublish={onFillPublish}
        onConfirmPublish={onConfirmPublish}
        onSavePublishDraft={onSavePublishDraft}
      />
    </div>
  );
}

function ImageTextConfigPanel({
  language,
  topic,
  config,
  strategies,
  isConfigured,
  isRunning,
  runningTask,
  onGenerateDraft,
  onChange,
  onConfirm,
  onSaveStrategy,
  onDeleteStrategy,
}: {
  language: "zh" | "en";
  topic: Record<string, unknown>;
  config: Record<string, unknown>;
  strategies: XhsCarouselStrategy[];
  isConfigured: boolean;
  isRunning: boolean;
  runningTask?: XhsRunningTask;
  onGenerateDraft: () => void;
  onChange: (config: Record<string, unknown>) => void;
  onConfirm: () => void;
  onSaveStrategy: (strategy: { id?: string; name: string; description?: string; config: Record<string, unknown> }) => Promise<XhsCarouselStrategy | undefined>;
  onDeleteStrategy: (strategyId: string) => void;
}) {
  const draft = Object.keys(config).length ? config : defaultImageTextConfig(topic);
  const mode = text(draft.mode, "listicle");
  const activeMode = imageTextModes.find((item) => item.id === mode) ?? imageTextModes[1];
  const slideCount = mode === "single_opinion" ? 1 : Number(draft.slide_count || activeMode.slides);
  const selectedStrategy = strategies.find((item) => item.id === text(draft.strategy_id));
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [strategyName, setStrategyName] = useState("");
  const [strategyDescription, setStrategyDescription] = useState("");
  const update = (patch: Record<string, unknown>) => onChange({ ...draft, ...patch });
  const applyStrategy = (strategyId: string) => {
    const strategy = strategies.find((item) => item.id === strategyId);
    if (!strategy) return;
    onChange({ ...strategy.config, strategy_id: strategy.id, strategy_name: strategy.name });
    setStrategyName(strategy.name);
    setStrategyDescription(strategy.description ?? "");
  };
  const saveStrategy = () => {
    const name = strategyName.trim() || text(draft.strategy_name, selectedStrategy?.name, language === "zh" ? "新轮播策略" : "New carousel strategy");
    onSaveStrategy({
      id: selectedStrategy?.readonly ? undefined : selectedStrategy?.id,
      name,
      description: strategyDescription,
      config: draft,
    }).then((saved) => {
      if (saved) onChange({ ...saved.config, strategy_id: saved.id, strategy_name: saved.name });
    });
  };
  return (
    <div className="xhs-config-panel">
      <div className="stage-panel-heading">
        <div>
          <span>{language === "zh" ? "图文配置" : "Image-text config"}</span>
          <h2>{language === "zh" ? "选择小红书图文结构和模式" : "Choose the XHS post structure"}</h2>
        </div>
      </div>
      <article className="xhs-selected-topic">
        <span>{language === "zh" ? "已选选题" : "Selected topic"}</span>
        <strong>{text(topic.title_hook, topic.cover_hook, topic.title, topic.name, language === "zh" ? "小红书图文选题" : "XHS topic")}</strong>
        <p>{xhsTopicSummary(topic, language)}</p>
      </article>
      <div className="xhs-strategy-row">
        <label className="field-label">
          <span>{language === "zh" ? "轮播策略" : "Carousel strategy"}</span>
          <select value={text(draft.strategy_id)} onChange={(event) => applyStrategy(event.target.value)}>
            <option value="">{language === "zh" ? "按当前选题自动配置" : "Auto from topic"}</option>
            {strategies.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name}
              </option>
            ))}
          </select>
        </label>
        <div className="xhs-strategy-actions">
          <button className="secondary-button" type="button" onClick={() => setStrategyOpen((value) => !value)}>
            <Pencil size={16} />
            {language === "zh" ? "管理策略" : "Manage"}
          </button>
        </div>
      </div>
      {strategyOpen ? (
        <div className="xhs-strategy-editor">
          <label className="field-label">
            <span>{language === "zh" ? "策略名称" : "Strategy name"}</span>
            <input value={strategyName || text(draft.strategy_name, selectedStrategy?.name)} onChange={(event) => setStrategyName(event.target.value)} />
          </label>
          <label className="field-label">
            <span>{language === "zh" ? "策略说明" : "Description"}</span>
            <input value={strategyDescription || selectedStrategy?.description || activeMode.structure} onChange={(event) => setStrategyDescription(event.target.value)} />
          </label>
          <label className="field-label xhs-strategy-body-field">
            <span>{language === "zh" ? "策略正文" : "Strategy body"}</span>
            <textarea value={text(draft.strategy_body, activeMode.body)} onChange={(event) => update({ strategy_body: event.target.value })} />
          </label>
          <div className="xhs-strategy-actions">
            <button className="secondary-button" type="button" onClick={() => {
              setStrategyName(language === "zh" ? "新轮播策略" : "New carousel strategy");
              setStrategyDescription(activeMode.structure);
              onChange({ ...draft, strategy_id: "", strategy_name: "" });
            }}>
              <FolderPlus size={16} />
              {language === "zh" ? "新建" : "New"}
            </button>
            <button className="secondary-button" type="button" onClick={saveStrategy}>
              <Save size={16} />
              {language === "zh" ? "保存策略" : "Save strategy"}
            </button>
            <button
              className="secondary-button danger-button"
              type="button"
              disabled={!selectedStrategy || selectedStrategy.readonly}
              onClick={() => selectedStrategy ? onDeleteStrategy(selectedStrategy.id) : undefined}
              title={selectedStrategy?.readonly ? (language === "zh" ? "默认策略不能删除" : "Default strategies cannot be deleted") : ""}
            >
              <Trash2 size={16} />
              {language === "zh" ? "删除" : "Delete"}
            </button>
          </div>
        </div>
      ) : null}
      <div className="xhs-config-grid">
        <label className="field-label">
          <span>{language === "zh" ? "图文结构" : "Structure"}</span>
          <select value={mode} onChange={(event) => {
            const item = imageTextModes.find((candidate) => candidate.id === event.target.value) ?? imageTextModes[1];
            update({ mode: item.id, mode_label: item.zh, slide_count: item.slides, strategy_body: item.body });
          }}>
            {imageTextModes.map((item) => (
              <option key={item.id} value={item.id}>
                {language === "zh" ? item.zh : item.en}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "封面模式" : "Cover mode"}</span>
          <select value={text(draft.cover_type, "hook_text")} onChange={(event) => update({ cover_type: event.target.value })}>
            {coverTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {language === "zh" ? item.zh : item.en}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "版式模式" : "Layout"}</span>
          <select value={text(draft.layout_style, "balanced")} onChange={(event) => update({ layout_style: event.target.value })}>
            {layoutStyles.map((item) => (
              <option key={item.id} value={item.id}>
                {language === "zh" ? item.zh : item.en}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "轮播张数" : "Slides"}</span>
          <input
            type="number"
            min={1}
            max={7}
            value={slideCount}
            disabled={mode === "single_opinion"}
            onChange={(event) => update({ slide_count: Number(event.target.value) })}
          />
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "文字密度" : "Text density"}</span>
          <select value={text(draft.text_density, "medium")} onChange={(event) => update({ text_density: event.target.value })}>
            <option value="low">{language === "zh" ? "低：少字强视觉" : "Low"}</option>
            <option value="medium">{language === "zh" ? "中：图文平衡" : "Medium"}</option>
            <option value="high">{language === "zh" ? "高：信息清单" : "High"}</option>
          </select>
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "封面钩子" : "Cover hook"}</span>
          <input value={text(draft.cover_hook, topic.cover_hook, topic.title_hook)} onChange={(event) => update({ cover_hook: event.target.value })} />
        </label>
        <label className="field-label">
          <span>{language === "zh" ? "补充要求" : "Notes"}</span>
          <input value={text(draft.notes)} onChange={(event) => update({ notes: event.target.value })} placeholder={language === "zh" ? "例如：更适合收藏、少用大段解释" : "e.g. make it save-worthy"} />
        </label>
      </div>
      <div className="xhs-stage-actions">
        <button className="primary-cta" type="button" disabled={isRunning} onClick={isConfigured ? onGenerateDraft : onConfirm}>
          <CheckCircle2 size={16} />
          <strong>
            <RunningButtonLabel taskId={isConfigured ? "generate_draft" : "configure_image_text"} runningTask={runningTask}>
              {isConfigured ? (language === "zh" ? "生成图文草稿" : "Generate draft") : language === "zh" ? "确认图文配置" : "Confirm config"}
            </RunningButtonLabel>
          </strong>
        </button>
        {isConfigured ? <span>{language === "zh" ? "图文配置已确认，下一步先生成正文，再生成配图建议。" : "Config is confirmed. Generate the draft before image suggestions."}</span> : null}
      </div>
    </div>
  );
}

function SourceList({ files, language }: { files: NonNullable<XhsProject["library_files"]>; language: "zh" | "en" }) {
  if (!files.length) return <EmptyState title={language === "zh" ? "项目还没有素材" : "No sources imported"} />;
  return (
    <div className="xhs-source-list">
      {files.map((file) => (
        <div key={`${file.library}:${file.markdown_path}`} className="xhs-source-row">
          <strong>{file.title || file.markdown_path}</strong>
          <span>{file.library} · {file.markdown_path}</span>
        </div>
      ))}
    </div>
  );
}

function ImageGenerationPanel({
  language,
  project,
  nextAction,
  progress,
  isRunning,
  runningTask,
  onSuggestImages,
  onConfirmImageSuggestions,
  onGenerateImages,
  onRetryImageItems,
  onEnterPreflight,
  onPreview,
}: {
  language: "zh" | "en";
  project: XhsProject;
  nextAction: string;
  progress: XhsImageProgress;
  isRunning: boolean;
  runningTask?: XhsRunningTask;
  onSuggestImages: () => void;
  onConfirmImageSuggestions: () => void;
  onGenerateImages: () => void;
  onRetryImageItems: (tasks: XhsImageRetryTask[]) => void;
  onEnterPreflight?: () => void;
  onPreview: () => void;
}) {
  const contentPrompts = stringList(project.content_image_prompts);
  const prompts = [project.cover_prompt, ...contentPrompts].filter(Boolean);
  const images = imageItems(project);
  const errors = imageErrorItems(project);
  const retryTasks = xhsImageRetryTasks(project);
  return (
    <div className="xhs-image-generation">
      <div className="xhs-stage-actions xhs-draft-actions">
        {nextAction === "suggest_images" ? (
          <button className="primary-cta" type="button" disabled={isRunning || !project.content} onClick={onSuggestImages}>
            <Sparkles size={16} />
            <strong>
              <RunningButtonLabel taskId="suggest_images" runningTask={runningTask}>
                {language === "zh" ? "生成配图建议" : "Suggest images"}
              </RunningButtonLabel>
            </strong>
          </button>
        ) : null}
        {nextAction === "confirm_image_suggestions" ? (
          <button className="primary-cta" type="button" disabled={isRunning || !prompts.length} onClick={onConfirmImageSuggestions}>
            <CheckCircle2 size={16} />
            <strong>
              <RunningButtonLabel taskId="confirm_image_suggestions" runningTask={runningTask}>
                {language === "zh" ? "确认配图建议" : "Confirm suggestions"}
              </RunningButtonLabel>
            </strong>
          </button>
        ) : null}
        {nextAction === "generate_images" ? (
          <button className="primary-cta" type="button" disabled={isRunning || !prompts.length} onClick={onGenerateImages}>
            <Images size={16} />
            <strong>
              <RunningButtonLabel taskId="generate_images" runningTask={runningTask}>
                {language === "zh" ? "生成图片" : "Generate images"}
              </RunningButtonLabel>
            </strong>
          </button>
        ) : null}
        {nextAction === "retry_failed_images" || retryTasks.length ? (
          <button className="secondary-button" type="button" disabled={isRunning || !retryTasks.length} onClick={() => onRetryImageItems(retryTasks)}>
            <Images size={16} />
            <strong>
              <RunningButtonLabel taskId="retry_failed_images" runningTask={runningTask}>
                {language === "zh" ? `重新生成失败图片（${retryTasks.length}）` : `Retry failed images (${retryTasks.length})`}
              </RunningButtonLabel>
            </strong>
          </button>
        ) : null}
        {nextAction === "run_preflight" ? (
          <button className="primary-cta" type="button" disabled={isRunning || !xhsImagesComplete(project) || !onEnterPreflight} onClick={onEnterPreflight}>
            <CheckCircle2 size={16} />
            <strong>{language === "zh" ? "进入预检" : "Go to preflight"}</strong>
          </button>
        ) : null}
        <span>{imageGenerationHint(language, nextAction, project)}</span>
      </div>
      <div className="xhs-preview-inline">
        <button className="secondary-button" type="button" disabled={!project.content && !images.length} onClick={onPreview}>
          <Eye size={16} />
          {language === "zh" ? "预览" : "Preview"}
        </button>
      </div>
      {progress ? (
        <div className="xhs-image-progress">
          <span>{language === "zh" ? "生成进度" : "Generation progress"}</span>
          <strong>{progress.done} / {progress.total}</strong>
        </div>
      ) : null}
      {project.image_suggestion_rationale ? (
        <article className="xhs-image-suggestion xhs-image-suggestion-main">
          <strong>{language === "zh" ? "配图建议" : "Image suggestion"}</strong>
          <p>{project.image_suggestion_rationale}</p>
          <span>
            {prompts.length} {language === "zh" ? "条提示词" : "prompts"}
            {project.image_suggestions_confirmed ? ` · ${language === "zh" ? "已确认" : "confirmed"}` : ""}
          </span>
        </article>
      ) : (
        <div className="xhs-draft-empty">
          <strong>{language === "zh" ? "等待生成配图建议" : "Waiting for image suggestions"}</strong>
          <span>{language === "zh" ? "系统会先根据草稿规划生成封面和轮播图提示词，经确认后再生成图片。" : "Suggestions are generated first, then confirmed before actual image generation."}</span>
        </div>
      )}
      {prompts.length ? (
        <div className="xhs-prompt-list">
          {prompts.map((prompt, index) => (
            <article key={`${prompt}-${index}`} className="xhs-prompt-row">
              <strong>{index === 0 ? (language === "zh" ? "封面图" : "Cover") : `${language === "zh" ? "轮播图" : "Slide"} ${index + 1}`}</strong>
              <span>{prompt}</span>
            </article>
          ))}
        </div>
      ) : null}
      {images.length ? (
        <div className="xhs-generated-grid">
          {images.map((image, index) => (
            <article key={`${image.path}-${index}`} className="xhs-generated-card">
              <img src={xhsApi.fileUrl(image.path || "")} alt={image.prompt || `slide ${index + 1}`} />
              <span>{index === 0 ? (language === "zh" ? "封面" : "Cover") : `${language === "zh" ? "轮播" : "Slide"} ${index + 1}`}</span>
            </article>
          ))}
        </div>
      ) : null}
      {errors.length ? (
        <div className="xhs-image-errors">
          {errors.map((error, index) => (
            <span key={index}>{error.message || JSON.stringify(error)}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function XhsPreviewDialog({ language, project, onClose }: { language: "zh" | "en"; project: XhsProject; onClose: () => void }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const images = imageItems(project);
  const slides = slidePlanItems(project);
  const activeSlide = slides[activeIndex] ?? slides[0];
  const activeImage = images[activeIndex] ?? images[0];
  const total = Math.max(images.length, slides.length, 1);
  const contentFallback = (project.content || "").split(/\n+/).filter(Boolean).slice(0, 4).join("\n");
  const slideBody = text(activeSlide?.body, activeSlide?.caption, activeSlide?.text, activeSlide?.description, contentFallback);
  const slideTitle = text(activeSlide?.title, activeSlide?.role, activeIndex === 0 ? project.title || project.name : "");
  const goTo = (index: number) => setActiveIndex((index + total) % total);
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={language === "zh" ? "小红书预览" : "XHS preview"}>
      <div className="modal-panel xhs-preview-modal">
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "手机预览" : "Phone preview"}</span>
            <h2>{project.title || project.name}</h2>
          </div>
          <button className="secondary-button" type="button" onClick={onClose}>
            {language === "zh" ? "关闭" : "Close"}
          </button>
        </div>
        <div className="xhs-preview-modal-body">
          <div className="xhs-phone-preview">
            <div className="xhs-phone-frame xhs-phone-note">
              <div className="xhs-note-media">
                {activeImage ? (
                  <img src={xhsApi.fileUrl(activeImage.path || "")} alt={activeImage.prompt || slideTitle || `slide ${activeIndex + 1}`} />
                ) : (
                  <div className="xhs-image-empty">
                    <Images size={24} />
                  </div>
                )}
                {total > 1 ? (
                  <>
                    <button className="xhs-carousel-button previous" type="button" aria-label={language === "zh" ? "上一张" : "Previous"} onClick={() => goTo(activeIndex - 1)}>
                      <ChevronLeft size={18} />
                    </button>
                    <button className="xhs-carousel-button next" type="button" aria-label={language === "zh" ? "下一张" : "Next"} onClick={() => goTo(activeIndex + 1)}>
                      <ChevronRight size={18} />
                    </button>
                  </>
                ) : null}
                <span className="xhs-carousel-count">{activeIndex + 1}/{total}</span>
              </div>
              {total > 1 ? (
                <div className="xhs-carousel-dots" aria-label={language === "zh" ? "轮播页码" : "Carousel pages"}>
                  {Array.from({ length: total }).map((_, index) => (
                    <button
                      key={index}
                      className={index === activeIndex ? "active" : ""}
                      type="button"
                      aria-label={`${language === "zh" ? "第" : "Slide"} ${index + 1}`}
                      onClick={() => goTo(index)}
                    />
                  ))}
                </div>
              ) : null}
              <div className="xhs-note-copy">
                <h3>{project.title || project.name}</h3>
                {slideTitle ? <strong>{slideTitle}</strong> : null}
                <p>{slideBody}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SlidePlan({ project, language }: { project: XhsProject; language: "zh" | "en" }) {
  const slides = slidePlanItems(project);
  return (
    <div className="xhs-slide-plan">
      <h3>{language === "zh" ? "轮播脚本" : "Carousel plan"}</h3>
      {slides.length ? (
        slides.map((slide, index) => (
          <div key={index} className="xhs-slide-row">
            <strong>{slide.index || index + 1}. {slide.title || slide.role}</strong>
            <span>{slide.body || slide.visual_prompt}</span>
          </div>
        ))
      ) : (
        <span className="muted-copy">{language === "zh" ? "生成草稿后会出现每张图的脚本。" : "Slide copy appears after draft generation."}</span>
      )}
    </div>
  );
}

function PublishTools({
  language,
  step,
  nextAction,
  project,
  loginStatus,
  isCloudMember,
  isRunning,
  runningTask,
  onRefreshLogin,
  onPreflight,
  onExportPackage,
  onFillPublish,
  onConfirmPublish,
  onSavePublishDraft,
}: {
  language: "zh" | "en";
  step: XhsStep;
  nextAction: string;
  project: XhsProject;
  loginStatus?: XhsLoginStatus;
  isCloudMember: boolean;
  isRunning: boolean;
  runningTask?: XhsRunningTask;
  onRefreshLogin: () => void;
  onPreflight: () => void;
  onExportPackage: () => void;
  onFillPublish: () => void;
  onConfirmPublish: () => void;
  onSavePublishDraft: () => void;
}) {
  const preflight = preflightValue(project);
  const checks = preflightCheckItems(project);
  const hasPreflight = Boolean(preflight && checks.length);
  const blocking = preflightBlockingItems(project, checks);
  const canFillPublish = step === "publish_check" && Boolean(preflight?.ok) && !isCloudMember;
  const imagePaths = preflightImagePaths(project);
  const canRunPreflight = canRunXhsPreflight(project, nextAction);
  const exportPackage = project.export_package;
  const canExport = Boolean(imagePaths.length);
  if (isCloudMember) {
    return (
      <div className="xhs-publish-tools">
        <div className="xhs-cloud-export-notice">
          <strong>{language === "zh" ? "云端发布方式：导出图文包" : "Cloud publishing: export a package"}</strong>
          <p>{language === "zh" ? "云端不会代替你登录或发布小红书。完成预检后下载压缩包，按图片顺序上传，并粘贴标题、正文和标签。" : "Cloud mode does not log in or publish for you. Run checks, download the ZIP, then upload the images and paste the title, caption, and tags yourself."}</p>
        </div>
        <div className={preflight?.ok ? "xhs-preflight-summary ok" : hasPreflight ? "xhs-preflight-summary blocked" : "xhs-preflight-summary"}>
          <div>
            <span>{language === "zh" ? "导出检查" : "Export checks"}</span>
            <strong>
              {preflight?.ok
                ? language === "zh" ? "可以导出图文包" : "Ready to export"
                : hasPreflight
                  ? language === "zh" ? `${blocking.length} 项需要处理` : `${blocking.length} blocking checks`
                  : language === "zh" ? "尚未执行发布预检" : "Preflight not run yet"}
            </strong>
          </div>
          <p>{preflight?.ok ? (language === "zh" ? "标题、正文和图片已通过导出检查，可以生成小红书图文压缩包。" : "Title, caption, and images passed export checks. You can create the ZIP package.") : (language === "zh" ? "导出前需要先确认标题、正文和图片文件都可用。" : "Before exporting, confirm the title, caption, and image files are ready.")}</p>
        </div>
        <div className="xhs-publish-actions">
          <button className="secondary-button" type="button" disabled={isRunning || !canRunPreflight} onClick={onPreflight}>
            <CheckCircle2 size={16} />
            <strong>
              <RunningButtonLabel taskId="run_preflight" runningTask={runningTask}>
                {hasPreflight ? (language === "zh" ? "重新预检" : "Run again") : language === "zh" ? "执行发布预检" : "Run preflight"}
              </RunningButtonLabel>
            </strong>
          </button>
          <button className="primary-cta" type="button" disabled={isRunning || !canExport} title={!canExport ? (language === "zh" ? "需要先生成图片" : "Generate images first.") : ""} onClick={onExportPackage}>
            <Save size={16} />
            <strong>
              <RunningButtonLabel taskId="export_package" runningTask={runningTask}>
                {language === "zh" ? "导出图文压缩包" : "Export ZIP"}
              </RunningButtonLabel>
            </strong>
          </button>
        </div>
        {exportPackage?.package_path ? (
          <div className="xhs-export-package-card">
            <div>
              <span>{language === "zh" ? "导出包已生成" : "Export package ready"}</span>
              <strong>{exportPackage.filename || "xhs_publish_package.zip"}</strong>
              <p>{language === "zh" ? `包含 ${exportPackage.image_count ?? imagePaths.length} 张图片、标题、正文、标签和发布说明。` : `Includes ${exportPackage.image_count ?? imagePaths.length} images, title, caption, tags, and a publishing guide.`}</p>
            </div>
            <a className="primary-cta" href={xhsApi.fileUrl(exportPackage.package_path)} download>
              <Save size={16} />
              <strong>{language === "zh" ? "下载压缩包" : "Download ZIP"}</strong>
            </a>
          </div>
        ) : null}
        <div className="xhs-publish-guide">
          <strong>{language === "zh" ? "自行上传步骤" : "Manual upload steps"}</strong>
          <p>{language === "zh" ? "下载 ZIP 后解压，按 images 文件夹顺序上传图片，再复制 title.txt、content.txt 和 tags.txt 到小红书发布页。" : "Download and unzip the package, upload images in order, then copy title.txt, content.txt, and tags.txt into XHS."}</p>
        </div>
        {exportPackage?.package_path ? (
        <div className="xhs-export-package-card">
          <div>
            <span>{language === "zh" ? "导出包已生成" : "Export package ready"}</span>
            <strong>{exportPackage.filename || "xhs_publish_package.zip"}</strong>
            <p>{language === "zh" ? `包含 ${exportPackage.image_count ?? imagePaths.length} 张图片、标题、正文、标签和发布说明。` : `Includes ${exportPackage.image_count ?? imagePaths.length} images, title, caption, tags, and a publishing guide.`}</p>
          </div>
          <a className="primary-cta" href={xhsApi.fileUrl(exportPackage.package_path)} download>
            <Save size={16} />
            <strong>{language === "zh" ? "下载 ZIP" : "Download ZIP"}</strong>
          </a>
        </div>
      ) : null}
      <div className="xhs-publish-guide">
        <strong>{language === "zh" ? "本地填入流程" : "Local fill workflow"}</strong>
        <p>{language === "zh" ? "本地用户登录后可用 XHS Bridge 自动填入发布页，也可以导出 ZIP 作为备份。" : "Local users can use XHS Bridge to fill the publish page after logging in, or export a ZIP as backup."}</p>
      </div>
      <div className="xhs-preflight-files">
          <div>
            <span>{language === "zh" ? "标题" : "Title"}</span>
            <strong>{preflight?.title || project.title || project.name}</strong>
          </div>
          <div>
            <span>{language === "zh" ? "图片" : "Images"}</span>
            <strong>{imagePaths.length} {language === "zh" ? "张" : "images"}</strong>
          </div>
          <div>
            <span>{language === "zh" ? "标签" : "Tags"}</span>
            <strong>{preflightTags(project).map((tag) => `#${tag}`).join(" ") || "-"}</strong>
          </div>
        </div>
        {hasPreflight ? (
          <div className="xhs-check-list">
            {checks.map((check) => (
              <div key={check.key} className={check.ok ? "xhs-check ok" : "xhs-check blocked"}>
                <span>{check.label || check.key}</span>
                <strong>{check.detail || (check.ok ? "OK" : "Blocked")}</strong>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div className="xhs-publish-tools">
      <div className={preflight?.ok ? "xhs-preflight-summary ok" : hasPreflight ? "xhs-preflight-summary blocked" : "xhs-preflight-summary"}>
        <div>
          <span>{language === "zh" ? "预检结果" : "Preflight result"}</span>
          <strong>
            {preflight?.ok
              ? language === "zh" ? "可以填入发布页" : "Ready to fill"
              : hasPreflight
                ? language === "zh" ? `${blocking.length} 项需要处理` : `${blocking.length} blocking checks`
                : language === "zh" ? "尚未执行发布预检" : "Preflight not run yet"}
          </strong>
        </div>
        <p>
          {preflight?.ok
            ? language === "zh" ? "标题、正文、图片和登录状态已通过检查。" : "Title, content, images, and login status passed."
            : language === "zh" ? "发布前需要先确认标题、正文、图片文件和小红书登录状态。" : "Check title, content, image files, and XHS login before publishing."}
        </p>
      </div>
      <div className="xhs-publish-actions">
        <button className="secondary-button" type="button" disabled={isRunning} onClick={onRefreshLogin}>
          <LogIn size={16} />
          <RunningButtonLabel taskId="refresh_login" runningTask={runningTask}>{loginStatus?.logged_in ? (language === "zh" ? "已登录" : "Logged in") : language === "zh" ? "检查登录" : "Check login"}</RunningButtonLabel>
        </button>
        <button className="secondary-button" type="button" disabled={isRunning || !canRunPreflight} onClick={onPreflight}>
          <CheckCircle2 size={16} />
          <RunningButtonLabel taskId="run_preflight" runningTask={runningTask}>{hasPreflight ? (language === "zh" ? "重新预检" : "Run again") : language === "zh" ? "执行发布预检" : "Run preflight"}</RunningButtonLabel>
        </button>
        <button className="secondary-button" type="button" disabled={isRunning || !canExport} title={!canExport ? (language === "zh" ? "请先生成图片" : "Generate images first.") : ""} onClick={onExportPackage}>
          <Save size={16} />
          <RunningButtonLabel taskId="export_package" runningTask={runningTask}>{language === "zh" ? "导出 ZIP" : "Export ZIP"}</RunningButtonLabel>
        </button>
        <button className="primary-cta" type="button" disabled={isRunning || !canFillPublish} title={!canFillPublish ? (language === "zh" ? "预检通过后才能填入发布页" : "Pass preflight before filling the publish page.") : ""} onClick={onFillPublish}>
          <Send size={16} />
          <strong>
              <RunningButtonLabel taskId="fill_publish" runningTask={runningTask}>
                {language === "zh" ? "填入发布页" : "Fill publish page"}
              </RunningButtonLabel>
            </strong>
        </button>
        {step === "publish_ready" ? (
          <>
            <button className="primary-cta" type="button" disabled={isRunning} onClick={onConfirmPublish}>
              <Send size={16} />
              <strong>
              <RunningButtonLabel taskId="confirm_publish" runningTask={runningTask}>
                {language === "zh" ? "确认发布" : "Publish"}
              </RunningButtonLabel>
            </strong>
            </button>
            <button className="secondary-button" type="button" disabled={isRunning} onClick={onSavePublishDraft}>
              <RunningButtonLabel taskId="save_publish_draft" runningTask={runningTask}>{language === "zh" ? "保存草稿" : "Save draft"}</RunningButtonLabel>
            </button>
          </>
        ) : null}
      </div>
      <div className="xhs-preflight-files">
        <div>
          <span>{language === "zh" ? "标题" : "Title"}</span>
          <strong>{preflight?.title || project.title || project.name}</strong>
        </div>
        <div>
          <span>{language === "zh" ? "图片" : "Images"}</span>
          <strong>{imagePaths.length} {language === "zh" ? "张" : "images"}</strong>
        </div>
        <div>
          <span>{language === "zh" ? "标签" : "Tags"}</span>
          <strong>{preflightTags(project).map((tag) => `#${tag}`).join(" ") || "-"}</strong>
        </div>
      </div>
      {hasPreflight ? (
        <div className="xhs-check-list">
          {checks.map((check) => (
            <div key={check.key} className={check.ok ? "xhs-check ok" : "xhs-check blocked"}>
              <span>{check.label || check.key}</span>
              <strong>{check.detail || (check.ok ? "OK" : "Blocked")}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function xhsStageForStep(step: XhsStep, nextAction: string, project: XhsProject | undefined): XhsWorkflowStage {
  if (step === "published") return "published";
  if (step === "publish_ready") return "publish_ready";
  if (step === "publish_check") return "publish_check";
  if (step === "images" && canRunXhsPreflight(project, nextAction)) return "publish_check";
  if (step === "images") return "images";
  if (step === "draft") return "draft";
  if (step === "topic" || step === "topic_configured") return "draft";
  if (step === "knowledge_confirmed" || step === "topics") return "topics";
  if (topicItems(project).length) return "topics";
  if (nextAction === "generate_topics") return "topics";
  return "created";
}

function xhsStepForStage(stage: XhsWorkflowStage, actualStep: XhsStep, project: XhsProject | undefined): XhsStep {
  if (stage === "created") return "created";
  if (stage === "topics") return topicItems(project).length ? "topics" : "knowledge_confirmed";
  if (stage === "draft") {
    if (project?.content) return "draft";
    if (Object.keys(recordValue(project?.image_text_config)).length) return "topic_configured";
    return Object.keys(recordValue(project?.topic)).length ? "topic" : "topics";
  }
  if (stage === "images") return "images";
  if (stage === "publish_check") return "publish_check";
  if (stage === "publish_ready") return actualStep === "published" ? "published" : "publish_ready";
  if (stage === "published") return "published";
  return actualStep;
}

function nextActionForVisibleXhsStep(
  visibleStep: XhsStep,
  actualStep: XhsStep,
  backendNextAction: string,
  project: XhsProject | undefined,
) {
  if (visibleStep === actualStep) return backendNextAction;
  if (visibleStep === "created") return "confirm_knowledge";
  if (visibleStep === "knowledge_confirmed") return "generate_topics";
  if (visibleStep === "topics") return "select_topic";
  if (visibleStep === "topic") return "configure_image_text";
  if (visibleStep === "topic_configured") return "generate_draft";
  if (visibleStep === "draft") return "confirm_draft";
  if (visibleStep === "images") {
    if (canRunXhsPreflight(project, backendNextAction)) return "run_preflight";
    if (!project?.image_suggestion_rationale && !hasImagePrompts(project)) return "suggest_images";
    if (!project?.image_suggestions_confirmed) return "confirm_image_suggestions";
    return "generate_images";
  }
  if (visibleStep === "publish_check") return project?.preflight?.ok ? "fill_publish" : "run_preflight";
  if (visibleStep === "publish_ready") return "confirm_publish";
  return backendNextAction;
}

function canRunXhsPreflight(project: XhsProject | undefined, nextAction?: string): boolean {
  if (nextAction === "run_preflight" && xhsImagesComplete(project)) return true;
  return xhsImagesComplete(project);
}

function imageGenerationHint(language: "zh" | "en", nextAction: string, project: XhsProject) {
  if (nextAction === "retry_failed_images" || xhsImageRetryTasks(project).length) {
    return language === "zh" ? "有图片生成失败，可以只重新生成失败项；已成功的图片会保留。" : "Some images failed. Retry only failed items; successful images are kept.";
  }
  if (nextAction === "suggest_images") {
    return language === "zh" ? "先生成配图建议，不会立即消耗生图。" : "Generate suggestions first. No images are created yet.";
  }
  if (nextAction === "confirm_image_suggestions") {
    return language === "zh" ? "确认这些提示词后，下一步才会生成图片。" : "Confirm these prompts before generating images.";
  }
  if (nextAction === "generate_images") {
    return language === "zh" ? "配图建议已确认，可以开始生成封面和轮播图。" : "Suggestions are confirmed. Image generation is ready.";
  }
  if (xhsImagesComplete(project)) {
    return language === "zh" ? "图片已生成，进入发布预检工作区后再执行检查。" : "Images are ready. Open the preflight workspace to run checks.";
  }
  return language === "zh" ? "请按顺序完成配图建议和图片生成。" : "Complete suggestions and generation in order.";
}

function hasImagePrompts(project: XhsProject | undefined): boolean {
  return Boolean(text(project?.cover_prompt) || stringList(project?.content_image_prompts).length);
}

function xhsImagesComplete(project: XhsProject | undefined): boolean {
  if (!project?.image_suggestions_confirmed) return false;
  const coverPrompt = text(project.cover_prompt);
  const contentPrompts = stringList(project.content_image_prompts);
  if (!coverPrompt) return false;
  const images = recordValue(project.images);
  if (imageErrorItems(project).length) return false;
  const cover = recordValue(images.cover);
  if (!text(cover.path)) return false;
  const contentImages = recordList(images.content_images);
  const existingIndexes = new Set(
    contentImages
      .filter((item) => text(item.path))
      .map((item) => Number(item.index || 0))
      .filter(Boolean),
  );
  return contentPrompts.every((_, index) => existingIndexes.has(index + 1));
}

function toWriterLibraryFiles(items: KnowledgeItem[]): WriterLibraryFileInput[] {
  const files: WriterLibraryFileInput[] = [];
  const seen = new Set<string>();
  items.forEach((item) => {
    if (!item.markdownPath || !item.library) return;
    const key = `${item.library}:${item.markdownPath}`;
    if (seen.has(key)) return;
    seen.add(key);
    files.push({
      library: item.library,
      markdown_path: item.markdownPath,
      title: item.title,
      knowledge_id: item.backendId,
    });
  });
  return files;
}

function imageItems(project: XhsProject | undefined): Array<{ path?: string; prompt?: string }> {
  const images = project?.images;
  if (!images || typeof images !== "object" || Array.isArray(images)) return [];
  const cover = recordValue(images.cover);
  const coverItems = Object.keys(cover).length ? [cover] : [];
  const contentImages = recordList(images.content_images);
  const extraItems = recordList(images.items);
  return [...coverItems, ...contentImages, ...extraItems].filter((item, index, all) => {
    const path = text(item.path);
    return path && all.findIndex((candidate) => candidate.path === path) === index;
  });
}

function xhsImageRetryTasks(project: XhsProject | undefined): XhsImageRetryTask[] {
  const tasks: XhsImageRetryTask[] = [];
  const images = recordValue(project?.images);
  const cover = recordValue(images.cover);
  const coverPrompt = text(project?.cover_prompt);
  const contentPrompts = stringList(project?.content_image_prompts).map((prompt) => text(prompt));
  const hasCover = Boolean(cover.path);
  const existingContent = new Set(
    recordList(images.content_images)
      .filter((item) => item.path)
      .map((item) => Number(item.index || 0))
      .filter(Boolean),
  );
  const pushTask = (task: XhsImageRetryTask) => {
    const key = `${task.kind}:${task.index ?? 0}`;
    if (!task.prompt.trim() || tasks.some((item) => `${item.kind}:${item.index ?? 0}` === key)) return;
    tasks.push({ ...task, aspectRatio: task.aspectRatio || "3:4" });
  };
  for (const error of imageErrorItems(project)) {
    const kind = error.kind === "cover" ? "cover" : error.kind === "content" ? "content" : "";
    if (kind === "cover" && coverPrompt && !hasCover) pushTask({ kind, prompt: coverPrompt });
    if (kind === "content") {
      const index = Number(error.index || 0);
      const prompt = contentPrompts[index - 1] || "";
      if (index > 0 && prompt && !existingContent.has(index)) pushTask({ kind, prompt, index });
    }
  }
  if (images.partial || images.ok === false) {
    if (coverPrompt && !hasCover) pushTask({ kind: "cover", prompt: coverPrompt });
    contentPrompts.forEach((prompt, index) => {
      const contentIndex = index + 1;
      if (prompt && !existingContent.has(contentIndex)) pushTask({ kind: "content", prompt, index: contentIndex });
    });
  }
  return tasks;
}

function xhsImageTaskTotal(coverPrompt?: string, contentImagePrompts: string[] = []) {
  const coverCount = coverPrompt?.trim() ? 1 : 0;
  const contentCount = contentImagePrompts.filter((prompt) => prompt.trim()).length;
  return Math.max(1, coverCount + contentCount);
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function recordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return lines(value);
  return [];
}

function libraryFileItems(project: XhsProject | undefined): NonNullable<XhsProject["library_files"]> {
  return recordList(project?.library_files) as NonNullable<XhsProject["library_files"]>;
}

function topicItems(project: XhsProject | undefined): Array<Record<string, unknown>> {
  return recordList(project?.topics);
}

function tagItems(project: XhsProject | undefined): string[] {
  return stringList(project?.tags);
}

function slidePlanItems(project: XhsProject | undefined): NonNullable<XhsProject["slide_plan"]> {
  return recordList(project?.slide_plan) as NonNullable<XhsProject["slide_plan"]>;
}

function imageErrorItems(project: XhsProject | undefined): NonNullable<NonNullable<XhsProject["images"]>["errors"]> {
  return recordList(recordValue(project?.images).errors) as NonNullable<NonNullable<XhsProject["images"]>["errors"]>;
}

function preflightValue(project: XhsProject | undefined): XhsProject["preflight"] | undefined {
  const preflight = project?.preflight;
  return preflight && typeof preflight === "object" && !Array.isArray(preflight) ? preflight : undefined;
}

function preflightCheckItems(project: XhsProject): NonNullable<NonNullable<XhsProject["preflight"]>["checks"]> {
  return recordList(preflightValue(project)?.checks) as NonNullable<NonNullable<XhsProject["preflight"]>["checks"]>;
}

function preflightBlockingItems(
  project: XhsProject,
  checks: NonNullable<NonNullable<XhsProject["preflight"]>["checks"]>,
): NonNullable<NonNullable<XhsProject["preflight"]>["checks"]> {
  const blocking = preflightValue(project)?.blocking;
  return Array.isArray(blocking) ? (recordList(blocking) as NonNullable<NonNullable<XhsProject["preflight"]>["checks"]>) : checks.filter((check) => !check.ok);
}

function preflightImagePaths(project: XhsProject): string[] {
  const paths = preflightValue(project)?.image_paths;
  return stringList(paths).length ? stringList(paths) : imageItems(project).map((item) => item.path || "").filter(Boolean);
}

function preflightTags(project: XhsProject): string[] {
  const tags = preflightValue(project)?.tags;
  return stringList(tags).length ? stringList(tags) : tagItems(project);
}

function text(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function xhsTopicSummary(topic: Record<string, unknown>, language: "zh" | "en") {
  const format = text(topic.note_format, topic.format);
  const pillar = text(topic.content_pillar);
  const pain = text(topic.user_pain_point, topic.reader_pain_point, topic.reader_pain);
  const values = Array.isArray(topic.value_points) ? topic.value_points.map((item) => String(item).trim()).filter(Boolean).slice(0, 2).join(" / ") : "";
  const count = typeof topic.carousel_count === "number" ? (language === "zh" ? `${topic.carousel_count} 张` : `${topic.carousel_count} slides`) : "";
  const legacy = text(topic.topic_angle, topic.angle, topic.reason, topic.value, "");
  return [format, count, pillar, pain, values || legacy].filter(Boolean).join(" · ");
}

function defaultImageTextConfig(topic: Record<string, unknown> | null | undefined) {
  const source = topic ?? {};
  const noteFormat = text(source.note_format);
  let mode = "listicle";
  if (noteFormat.includes("教程")) mode = "tutorial";
  else if (noteFormat.includes("避坑")) mode = "pitfall";
  else if (noteFormat.includes("对比")) mode = "comparison";
  else if (noteFormat.includes("案例")) mode = "case_study";
  else if (noteFormat.includes("单图")) mode = "single_opinion";
  const modeMeta = imageTextModes.find((item) => item.id === mode) ?? imageTextModes[1];
  const count = typeof source.carousel_count === "number" ? source.carousel_count : modeMeta.slides;
  return {
    mode,
    mode_label: modeMeta.zh,
    slide_count: mode === "single_opinion" ? 1 : count,
    cover_type: "hook_text",
    layout_style: "balanced",
    text_density: "medium",
    visual_balance: "balanced",
    aspect_ratio: "3:4",
    cover_hook: text(source.cover_hook, source.title_hook),
    slide_flow: Array.isArray(source.slide_flow) ? source.slide_flow : [],
    notes: "",
    strategy_body: modeMeta.body,
  };
}

function lines(value: string) {
  return value
    .split(/\r?\n|,|，|、/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function libraryLabel(value: unknown, language: "zh" | "en") {
  const labels: Record<string, { zh: string; en: string }> = {
    original: { zh: "原文库", en: "Originals" },
    focus: { zh: "重点库", en: "Focus" },
    perspective: { zh: "视角库", en: "Perspectives" },
    knowledge: { zh: "旧知识库", en: "Legacy" },
  };
  const key = String(value || "original");
  return labels[key] ? (language === "zh" ? labels[key].zh : labels[key].en) : key;
}

function titleUnits(value: string) {
  return Array.from(value || "").reduce((sum, char) => sum + (char.charCodeAt(0) < 128 ? 0.5 : 1), 0);
}
