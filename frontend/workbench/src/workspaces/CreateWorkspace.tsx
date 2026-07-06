import { ExternalLink, Eye, FolderPlus, ImageIcon, Save, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LibraryKind, WriterLibraryFileInput } from "../api";
import { writerApi } from "../apiWriter";
import type { WriterImageRetryTask } from "../hooks/useWriterFlow";
import type { KnowledgeItem, WriterProject, WriterProjectState, WriterStep, WriterStrategyPreset } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { Stepper } from "../components/Stepper";

const designStrategyPresets = [
  {
    id: "wechat",
    zh: "公众号长文",
    en: "WeChat longform",
    value: `微信公众号文章默认美编策略
- 生成适合公众号粘贴发布的 HTML，层级清楚，阅读节奏舒展。
- 保留标题、摘要、正文小标题、重点句和图片，不增加无来源的新内容。
- 重点句可以适度强调，但不要把全文做成花哨海报。
- 图片使用项目内生成的本地路径，由发布预检再转换为公众号可用资源。
- 整体风格偏科技/财经：克制、清晰、专业，适合长文阅读。`,
  },
  {
    id: "pm_research",
    zh: "PM研究型",
    en: "PM research",
    value: `PM 研究型美编策略
- 本策略只参考 pm-search、pm-fulltext、pm-paper-detail、pm-export 等 PM skills 的资料组织方式，不把它们当作 HTML formatter。
- 页面目标是把文章整理成可复盘的研究笔记：结论先行、证据链清晰、来源可追踪、适合反复查阅。
- 结构建议：核心结论 -> 关键证据 -> 对比表格/变量拆解 -> 风险与反例 -> 后续检索问题 -> 来源附录。
- 版式保持工作台风格：信息密度高但分区清楚，使用小标题、编号列表、引用块、表格和少量强调句，不做营销海报式装饰。
- 对来自 PM 检索或论文详情的内容，保留题名、作者/机构、时间、链接或本地引用路径；没有来源的判断必须标成推断。
- 图片只作为解释结构和关系的辅助，不替代证据；不要让配图压过结论和来源。
- 导出时优先保证 Markdown/HTML 可复制、可二次编辑、可追溯，而不是追求视觉复杂度。`,
  },
];

const designThemeOptions = [
  { id: "tech", zh: "科技长文", en: "Tech longform" },
  { id: "research", zh: "研究笔记", en: "Research note" },
  { id: "column", zh: "观点专栏", en: "Opinion column" },
  { id: "xiumi", zh: "秀米装饰增强", en: "Xiumi-like rich" },
];

const imageStylePresets = [
  {
    id: "tech_clean",
    zh: "科技信息图",
    en: "Tech infographic",
    prompt: "科技信息图风格，蓝绿灰配色，结构清晰，简体中文少量文字，适合公众号科技文章。",
  },
  {
    id: "finance_brief",
    zh: "财经简报",
    en: "Finance brief",
    prompt: "财经简报风格，白底深色文字，少量高亮色块，简体中文少量文字，强调数据和结论。",
  },
  {
    id: "warm_lifestyle",
    zh: "清新生活方式",
    en: "Warm lifestyle",
    prompt: "清新生活方式插画风格，柔和配色，轻松留白，简体中文少量文字，适合观点表达和读者共鸣。",
  },
  {
    id: "guochao_editorial",
    zh: "国潮视觉",
    en: "Guochao editorial",
    prompt: "国潮编辑视觉风格，东方构图，克制装饰，简体中文少量文字，适合文化与品牌主题。",
  },
];

type WorkflowStage = "project" | "topic" | "draft" | "images" | "design" | "publish";

const workflowStages: Array<{ id: WorkflowStage; zh: string; en: string }> = [
  { id: "project", zh: "项目创建", en: "Project" },
  { id: "topic", zh: "选题", en: "Topic" },
  { id: "draft", zh: "初稿", en: "Draft" },
  { id: "images", zh: "配图", en: "Images" },
  { id: "design", zh: "美编", en: "Design" },
  { id: "publish", zh: "发布", en: "Publish" },
];

const workflowStageIndex: Record<WorkflowStage, number> = {
  project: 0,
  topic: 1,
  draft: 2,
  images: 3,
  design: 4,
  publish: 5,
};

type Props = {
  t: Translator;
  language: "zh" | "en";
  rightRail: ReactNode;
  writerProjects: WriterProject[];
  writerState?: WriterProjectState;
  selectedProjectId?: string;
  selectedKnowledgeFiles: KnowledgeItem[];
  isRunning: boolean;
  onCreateProject: (
    name: string,
    projectType: string,
    libraryFiles: WriterLibraryFileInput[],
    writingStrategy: string,
    designStrategy: string,
  ) => void;
  onSelectProject: (projectId: string) => void;
  onImportKnowledge: (libraryFiles: WriterLibraryFileInput[]) => void;
  onGenerateTopics: () => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onSaveStrategies: (writingStrategy?: string, designStrategy?: string) => void;
  onGenerateDraft: (writingStrategy?: string, designStrategy?: string) => void;
  onRevise: (instruction: string, markdown?: string) => void;
  onSuggestImages: (markdown?: string, contentImageCount?: number, imageStylePreset?: string) => void;
  onGenerateImages: (
    coverPrompt?: string,
    contentPrompts?: string[],
    onProgress?: (done: number, total: number) => void,
    aspectRatios?: { cover?: string; content?: string },
  ) => void;
  onRetryImageItems: (tasks: WriterImageRetryTask[], onProgress?: (done: number, total: number) => void) => void;
  onFormat: (markdown?: string, designStrategy?: string, writingStrategy?: string, theme?: string) => void;
  onConfirmDesign: () => void;
  onPreflight: () => void;
  onPublish: () => void;
};

type ImageProgress = {
  done: number;
  total: number;
} | null;

function CreateSummaryBar({
  eyebrow,
  title,
  status,
  action,
  disabled,
  disabledReason,
  onAction,
}: {
  eyebrow: string;
  title: string;
  status?: ReactNode;
  action?: string;
  disabled?: boolean;
  disabledReason?: string;
  onAction?: () => void;
}) {
  return (
    <section className="create-summary-bar">
      <div className="create-summary-main">
        <div className="create-summary-copy">
          <span>{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        {action && onAction ? (
          <div className="create-summary-actions">
            <button className="primary-cta" type="button" disabled={disabled} onClick={onAction}>
              <strong>{action}</strong>
            </button>
            {disabled && disabledReason ? <p className="disabled-reason create-summary-reason">{disabledReason}</p> : null}
          </div>
        ) : null}
      </div>
      {status ? <div className="create-summary-status">{status}</div> : null}
    </section>
  );
}

export function CreateWorkspace({
  language,
  rightRail,
  writerProjects,
  writerState,
  selectedProjectId,
  selectedKnowledgeFiles,
  isRunning,
  onCreateProject,
  onSelectProject,
  onImportKnowledge,
  onGenerateTopics,
  onSelectTopic,
  onSaveStrategies,
  onGenerateDraft,
  onRevise,
  onSuggestImages,
  onGenerateImages,
  onRetryImageItems,
  onFormat,
  onConfirmDesign,
  onPreflight,
  onPublish,
}: Props) {
  const [projectName, setProjectName] = useState("");
  const [createMode, setCreateMode] = useState(!writerState?.project);
  const [writingStrategy, setWritingStrategy] = useState("");
  const [designStrategy, setDesignStrategy] = useState("");
  const [designTheme, setDesignTheme] = useState("tech");
  const [revision, setRevision] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [coverPrompt, setCoverPrompt] = useState("");
  const [contentPromptsText, setContentPromptsText] = useState("");
  const [contentImageCount, setContentImageCount] = useState(1);
  const [imageStylePreset, setImageStylePreset] = useState(imageStylePresets[0].prompt);
  const [coverImageAspectRatio, setCoverImageAspectRatio] = useState("2.35:1");
  const [contentImageAspectRatio, setContentImageAspectRatio] = useState("");
  const [imageProgress, setImageProgress] = useState<ImageProgress>(null);
  const [imagePromptsTouched, setImagePromptsTouched] = useState(false);
  const [imageSuggestionsVisible, setImageSuggestionsVisible] = useState(false);
  const [imagesConfirmedProjectId, setImagesConfirmedProjectId] = useState("");
  const [pendingTopic, setPendingTopic] = useState<Record<string, unknown> | null>(null);
  const [reviewStage, setReviewStage] = useState<WorkflowStage | null>(null);
  const [draftConfirmedProjectId, setDraftConfirmedProjectId] = useState("");
  const [writingStrategyPresets, setWritingStrategyPresets] = useState<WriterStrategyPreset[]>([]);
  const [defaultWritingStrategyId, setDefaultWritingStrategyId] = useState("");
  const [writingStrategyLibraryError, setWritingStrategyLibraryError] = useState("");

  const project = normalizeWriterProject(writerState?.project);
  const step = writerState?.step ?? "created";
  const nextAction = writerState?.next_action ?? "";
  const actualVisibleStep = visibleWriterStep(step, nextAction);
  const draftConfirmed = Boolean(project?.id && project.article_markdown && draftConfirmedProjectId === project.id);
  const articleMarkdown = markdownDraft || project?.article_markdown || "";
  const images = imageItems(project);
  const imagePromptDirty =
    imagePromptsTouched &&
    (coverPrompt !== (project?.cover_prompt ?? "") ||
      contentPromptsText !== (project?.content_image_prompts ?? []).join("\n"));
  const imagesConfirmed = Boolean(project?.id && images.length && imagesConfirmedProjectId === project.id && !imagePromptDirty);
  const actualStage = workflowStageForStep(actualVisibleStep, nextAction, draftConfirmed, imagesConfirmed);
  const actualStageIndex = workflowStageIndex[actualStage] ?? 0;
  const visibleStage = reviewStage && (workflowStageIndex[reviewStage] ?? 0) <= actualStageIndex ? reviewStage : actualStage;
  const visibleStep = stepForWorkflowStage(visibleStage, actualVisibleStep, nextAction, project);
  const strategyDirty =
    writingStrategy !== (project?.writing_strategy ?? "") || designStrategy !== (project?.design_strategy ?? "");
  const hasImageSuggestions = Boolean(
    imageSuggestionsVisible ||
      project?.image_suggestion_rationale ||
      project?.cover_prompt ||
      project?.content_image_prompts?.length ||
      images.length,
  );
  const viewNextAction = nextActionForVisibleStep(visibleStep, actualVisibleStep, nextAction, project, imagePromptDirty, hasImageSuggestions);
  const labels = workflowStages.map((item) => (language === "zh" ? item.zh : item.en));
  const selectedLibraryFiles = useMemo(() => toWriterLibraryFiles(selectedKnowledgeFiles), [selectedKnowledgeFiles]);
  const guide = guideForState(language, project, visibleStep, viewNextAction);
  const primary = primaryAction(language, project, visibleStep, viewNextAction, isRunning, selectedLibraryFiles.length, pendingTopic);
  const clearReviewStage = () => setReviewStage(null);
  const runRetryFailedImages = (
    tasks = imageRetryTasks(project, coverPrompt, contentPromptsText, contentImageCount, {
      cover: coverImageAspectRatio,
      content: contentImageAspectRatio,
    }),
  ) => {
    clearReviewStage();
    if (!tasks.length) return;
    setImageProgress({ done: 0, total: tasks.length });
    onRetryImageItems(tasks, (done, total) => setImageProgress({ done, total }));
  };
  const runPrimaryAction = () =>
    runPrimary(visibleStep, viewNextAction, {
      onImportKnowledge: () => {
        clearReviewStage();
        onImportKnowledge(selectedLibraryFiles);
      },
      onGenerateTopics: () => {
        clearReviewStage();
        onGenerateTopics();
      },
      onConfirmTopic: () => {
        if (!pendingTopic) return;
        clearReviewStage();
        onSelectTopic(pendingTopic);
        setPendingTopic(null);
      },
      onConfirmDraft: () => {
        if (!project?.id || !articleMarkdown.trim()) return;
        setDraftConfirmedProjectId(project.id);
        setReviewStage(null);
      },
      onGenerateDraft: () => {
        clearReviewStage();
        onGenerateDraft(writingStrategy, designStrategy);
      },
      onSuggestImages: () => {
        clearReviewStage();
        onSuggestImages(articleMarkdown, contentImageCount, imageStylePreset);
      },
      onGenerateImages: () => {
        clearReviewStage();
        setImagesConfirmedProjectId("");
        setImageProgress({ done: 0, total: Math.max(1, 1 + promptLines(contentPromptsText).length) });
        onGenerateImages(coverPrompt || project?.cover_prompt, promptLines(contentPromptsText), (done, total) =>
          setImageProgress({ done, total }),
          { cover: coverImageAspectRatio, content: contentImageAspectRatio },
        );
      },
      onRetryFailedImages: () => runRetryFailedImages(),
      onConfirmImages: () => {
        if (!project?.id) return;
        setImagesConfirmedProjectId(project.id);
        setReviewStage(null);
      },
      onFormat: () => {
        clearReviewStage();
        onFormat(articleMarkdown, designStrategy, writingStrategy, designTheme);
      },
      onConfirmDesign: () => {
        clearReviewStage();
        onConfirmDesign();
      },
      onPreflight: () => {
        clearReviewStage();
        onPreflight();
      },
      onPublish: () => {
        clearReviewStage();
        onPublish();
      },
    });

  useEffect(() => {
    setMarkdownDraft("");
    setRevision("");
    setImageProgress(null);
    setImagePromptsTouched(false);
    setPendingTopic(null);
    setReviewStage(null);
    setDraftConfirmedProjectId("");
    setImagesConfirmedProjectId("");
  }, [project?.id, project?.article_markdown]);

  useEffect(() => {
    if (reviewStage && (workflowStageIndex[reviewStage] ?? 0) > actualStageIndex) setReviewStage(null);
  }, [actualStageIndex, reviewStage]);

  useEffect(() => {
    if (project?.id) setCreateMode(false);
  }, [project?.id]);

  useEffect(() => {
    let active = true;
    writerApi
      .writerWritingStrategies()
      .then((payload) => {
        if (!active) return;
        setWritingStrategyPresets(payload.items ?? []);
        setDefaultWritingStrategyId(payload.default_id ?? "");
        setWritingStrategyLibraryError("");
      })
      .catch((error) => {
        if (!active) return;
        setWritingStrategyLibraryError(error instanceof Error ? error.message : String(error));
      });
    return () => {
      active = false;
    };
  }, []);

  const projectContentPromptsKey = (project?.content_image_prompts ?? []).join("\n");

  useEffect(() => {
    setWritingStrategy(project?.writing_strategy ?? "");
    setDesignStrategy(project?.design_strategy ?? "");
    setDesignTheme(project?.html_theme ?? project?.design_intent?.theme ?? "tech");
    setCoverPrompt(project?.cover_prompt ?? "");
    setContentPromptsText(projectContentPromptsKey);
    setImageStylePreset(project?.image_style_preset ?? imageStylePresets[0].prompt);
    setImageSuggestionsVisible(false);
    const promptCount = project?.content_image_prompts?.length ?? 0;
    setContentImageCount(promptCount >= 1 && promptCount <= 3 ? promptCount : 1);
  }, [project?.id]);

  useEffect(() => {
    setCoverPrompt(project?.cover_prompt ?? "");
    setContentPromptsText(projectContentPromptsKey);
    setImagePromptsTouched(false);
    const promptCount = project?.content_image_prompts?.length ?? 0;
    if (promptCount >= 1 && promptCount <= 3) setContentImageCount(promptCount);
  }, [project?.cover_prompt, projectContentPromptsKey]);

  useEffect(() => {
    setWritingStrategy(project?.writing_strategy ?? "");
    setDesignStrategy(project?.design_strategy ?? "");
    setDesignTheme(project?.html_theme ?? project?.design_intent?.theme ?? "tech");
  }, [project?.writing_strategy, project?.design_strategy, project?.html_theme, project?.design_intent?.theme]);

  return (
    <section className="create-project-layout">
      <aside className="content-panel project-list-panel">
        <div className="panel-heading">
          <h2>{language === "zh" ? "公众号" : "WeChat article writing"}</h2>
          <button className="secondary-button" type="button" disabled={isRunning} onClick={() => setCreateMode(true)}>
            <FolderPlus size={16} />
            {language === "zh" ? "新建" : "New"}
          </button>
        </div>
        <div className="project-list">
          {writerProjects.length ? (
            writerProjects.map((item) => (
              <button
                key={item.id}
                type="button"
                className={item.id === selectedProjectId ? "project-row selected" : "project-row"}
                onClick={() => onSelectProject(item.id)}
              >
                <strong>{item.name || item.id}</strong>
                <span>{projectTypeLabel(item.type, language)} · {item.workspace}</span>
              </button>
            ))
          ) : (
            <EmptyState
              title={language === "zh" ? "还没有公众号文章项目" : "No WeChat article projects yet"}
              body={language === "zh" ? "先创建一个公众号文章项目，后续素材和产物都会保存在项目目录里。" : "Create a WeChat article project first."}
            />
          )}
        </div>
      </aside>

      <div className="workspace-main">
        {createMode || !project ? (
          <ProjectSetup
            language={language}
            name={projectName}
            selectedFiles={selectedLibraryFiles}
            isRunning={isRunning}
            hasOpenProject={Boolean(project)}
            onNameChange={setProjectName}
            onCancel={() => setCreateMode(false)}
            onCreate={() => {
              onCreateProject(projectName.trim(), "article", selectedLibraryFiles, "", "");
              setProjectName("");
            }}
          />
        ) : (
          <CreateSummaryBar
            eyebrow={language === "zh" ? "当前项目下一步" : "Next in project"}
            title={guide.title}
            status={
              <div className="project-status-strip">
                <div className="project-status-card">
                  <span>{language === "zh" ? "项目类型" : "Project type"}</span>
                  <strong>{projectTypeLabel(project.type, language)}</strong>
                </div>
                <div className="project-status-card">
                  <span>{language === "zh" ? "当前步骤" : "Current step"}</span>
                  <strong>{workflowStageLabel(actualStage, language)}</strong>
                </div>
              </div>
            }
          />
        )}

        {project ? (
          <div className="create-stepper-wrap">
            <Stepper
              steps={labels}
              activeIndex={workflowStageIndex[visibleStage] ?? 0}
              progressIndex={actualStageIndex}
              maxSelectableIndex={actualStageIndex}
              activeLabel={guide.checkpoints?.[0]}
              onSelect={(index) => setReviewStage(workflowStages[index]?.id ?? null)}
            />
          </div>
        ) : null}

        <section className="content-panel project-work-panel">
          {!project ? (
            <EmptyState
              title={language === "zh" ? "先创建项目" : "Create a project first"}
            />
          ) : (
          <ProjectStageWorkspace
              language={language}
              project={project}
              visibleStage={visibleStage}
              actualStage={actualStage}
              visibleStep={visibleStep}
              nextAction={viewNextAction}
              backendNextAction={nextAction}
              isReviewingStep={visibleStage !== actualStage}
              strategyDirty={strategyDirty}
              selectedLibraryFiles={selectedLibraryFiles}
              isRunning={isRunning}
              writingStrategy={writingStrategy}
              designStrategy={designStrategy}
              designTheme={designTheme}
              articleMarkdown={articleMarkdown}
              revision={revision}
              coverPrompt={coverPrompt}
                contentPromptsText={contentPromptsText}
                contentImageCount={contentImageCount}
                imageStylePreset={imageStylePreset}
                coverImageAspectRatio={coverImageAspectRatio}
                contentImageAspectRatio={contentImageAspectRatio}
                imageProgress={imageProgress}
              images={images}
              imageErrors={project.images?.errors ?? []}
              hasSuggestions={hasImageSuggestions}
              pendingTopic={pendingTopic}
              primaryAction={primary}
              guideTitle={guide.title}
              onPendingTopicChange={setPendingTopic}
              onPrimaryAction={runPrimaryAction}
              onSuggestImages={() => {
                clearReviewStage();
                setImageSuggestionsVisible(true);
                onSuggestImages(articleMarkdown, contentImageCount, imageStylePreset);
              }}
              onContinueFormat={() => onFormat(articleMarkdown, designStrategy, writingStrategy, designTheme)}
              onRetryImageTasks={runRetryFailedImages}
              onImportKnowledge={() => onImportKnowledge(selectedLibraryFiles)}
              onSaveStrategies={onSaveStrategies}
              onSelectTopic={(topic) => {
                onSelectTopic(topic);
                setPendingTopic(null);
              }}
              onMarkdownChange={setMarkdownDraft}
              onRevisionChange={setRevision}
              onRevise={() => {
                onRevise(revision, articleMarkdown);
                setRevision("");
              }}
              onCoverPromptChange={(value) => {
                setImagePromptsTouched(true);
                setCoverPrompt(value);
              }}
                onContentPromptsTextChange={(value) => {
                  setImagePromptsTouched(true);
                  setContentPromptsText(value);
                }}
                onContentImageCountChange={setContentImageCount}
                onImageStylePresetChange={setImageStylePreset}
                onCoverImageAspectRatioChange={setCoverImageAspectRatio}
                onContentImageAspectRatioChange={setContentImageAspectRatio}
                onWritingStrategyChange={setWritingStrategy}
              onDesignStrategyChange={setDesignStrategy}
              onDesignThemeChange={setDesignTheme}
              writingStrategyPresets={writingStrategyPresets}
              defaultWritingStrategyId={defaultWritingStrategyId}
              writingStrategyLibraryError={writingStrategyLibraryError}
              onWritingStrategyPresetsChange={setWritingStrategyPresets}
            />
          )}
        </section>
      </div>

      {rightRail}
    </section>
  );
}

function ProjectStageWorkspace({
  language,
  project,
  visibleStage,
  actualStage,
  visibleStep,
  nextAction,
  backendNextAction,
  isReviewingStep,
  strategyDirty,
  selectedLibraryFiles,
  isRunning,
  writingStrategy,
  designStrategy,
  designTheme,
  articleMarkdown,
  revision,
  coverPrompt,
  contentPromptsText,
  contentImageCount,
  imageStylePreset,
  coverImageAspectRatio,
  contentImageAspectRatio,
  imageProgress,
  images,
  imageErrors,
  hasSuggestions,
  pendingTopic,
  primaryAction,
  guideTitle,
  onPendingTopicChange,
  onPrimaryAction,
  onSuggestImages,
  onContinueFormat,
  onRetryImageTasks,
  onImportKnowledge,
  onSaveStrategies,
  onSelectTopic,
  onMarkdownChange,
  onRevisionChange,
  onRevise,
  onCoverPromptChange,
  onContentPromptsTextChange,
  onContentImageCountChange,
  onImageStylePresetChange,
  onCoverImageAspectRatioChange,
  onContentImageAspectRatioChange,
  onWritingStrategyChange,
  onDesignStrategyChange,
  onDesignThemeChange,
  writingStrategyPresets,
  defaultWritingStrategyId,
  writingStrategyLibraryError,
  onWritingStrategyPresetsChange,
}: {
  language: "zh" | "en";
  project: WriterProject;
  visibleStage: WorkflowStage;
  actualStage: WorkflowStage;
  visibleStep: WriterStep;
  nextAction: string;
  backendNextAction: string;
  isReviewingStep: boolean;
  strategyDirty: boolean;
  selectedLibraryFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  writingStrategy: string;
  designStrategy: string;
  designTheme: string;
  articleMarkdown: string;
  revision: string;
  coverPrompt: string;
  contentPromptsText: string;
  contentImageCount: number;
  imageStylePreset: string;
  coverImageAspectRatio: string;
  contentImageAspectRatio: string;
  imageProgress: ImageProgress;
  images: Array<{ path?: string; prompt?: string }>;
  imageErrors: Array<{ kind?: string; index?: number; message?: string }>;
  hasSuggestions: boolean;
  pendingTopic: Record<string, unknown> | null;
  primaryAction: { label: string; disabled: boolean; reason?: string };
  guideTitle: string;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onPrimaryAction: () => void;
  onSuggestImages: () => void;
  onContinueFormat: () => void;
  onRetryImageTasks: (tasks?: WriterImageRetryTask[]) => void;
  onImportKnowledge: () => void;
  onSaveStrategies: (writingStrategy: string, designStrategy: string) => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onMarkdownChange: (value: string) => void;
  onRevisionChange: (value: string) => void;
  onRevise: () => void;
  onCoverPromptChange: (value: string) => void;
  onContentPromptsTextChange: (value: string) => void;
  onContentImageCountChange: (value: number) => void;
  onImageStylePresetChange: (value: string) => void;
  onCoverImageAspectRatioChange: (value: string) => void;
  onContentImageAspectRatioChange: (value: string) => void;
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
  onDesignThemeChange: (value: string) => void;
  writingStrategyPresets: WriterStrategyPreset[];
  defaultWritingStrategyId: string;
  writingStrategyLibraryError: string;
  onWritingStrategyPresetsChange: (items: WriterStrategyPreset[]) => void;
}) {
  const stageTitle = workflowStageLabel(visibleStage, language);
  return (
    <div className="stage-workspace">
      <div className="stage-panel-heading">
        <div>
          <span>{language === "zh" ? "当前工作区" : "Current workspace"}</span>
          <h2>{stageTitle}</h2>
          {isReviewingStep ? (
            <small className="stage-review-note">
              {language === "zh"
                ? `正在回看：真实进度在「${workflowStageLabel(actualStage, language)}」。如果在这里继续，将从此阶段重新生成后续流程。`
                : `Reviewing this stage. The real progress is ${workflowStageLabel(actualStage, language)}. Continuing here will regenerate the downstream flow.`}
            </small>
          ) : null}
        </div>
        <div className="stage-heading-tools">
          <button
            className="primary-cta stage-primary-action"
            type="button"
            disabled={primaryAction.disabled}
            title={primaryAction.disabled ? primaryAction.reason || guideTitle : guideTitle}
            onClick={onPrimaryAction}
          >
            <Sparkles size={16} />
            <strong>{primaryAction.label}</strong>
          </button>
          {visibleStage === actualStage && visibleStep === "images" && backendNextAction === "retry_failed_images" ? (
            <button className="secondary-button" type="button" disabled={isRunning} onClick={onContinueFormat}>
              {language === "zh" ? "继续美编" : "Continue to HTML"}
            </button>
          ) : null}
          {primaryAction.disabled && primaryAction.reason ? (
            <p className="disabled-reason stage-primary-reason">{primaryAction.reason}</p>
          ) : null}
        </div>
      </div>

      {visibleStage === "draft" || visibleStage === "design" ? (
          <ProjectStrategyPanel
            language={language}
            kind={visibleStage === "draft" ? "writing" : "design"}
            writingStrategy={writingStrategy}
            designStrategy={designStrategy}
            designTheme={designTheme}
            onWritingStrategyChange={onWritingStrategyChange}
            onDesignStrategyChange={onDesignStrategyChange}
            onDesignThemeChange={onDesignThemeChange}
          onSave={onSaveStrategies}
          saveDisabled={isRunning}
          writingStrategyPresets={writingStrategyPresets}
          defaultWritingStrategyId={defaultWritingStrategyId}
          writingStrategyLibraryError={writingStrategyLibraryError}
          onWritingStrategyPresetsChange={onWritingStrategyPresetsChange}
          saveLabel={strategyDirty ? (language === "zh" ? "保存并应用到项目" : "Save to project") : (language === "zh" ? "当前策略已生效" : "Strategies are up to date")}
          hint={
            visibleStage === "draft"
              ? language === "zh"
                ? "写文策略只用于生成初稿。保存后会立刻成为当前项目默认写文策略。"
                : "Writing strategy only drives draft generation. Save to make it the active project default."
              : language === "zh"
                ? "美编策略只用于生成 HTML。保存后会立刻成为当前项目默认美编策略。"
                : "Design strategy only drives HTML formatting. Save to make it the active project default."
          }
        />
      ) : null}

      {visibleStage === "project" ? (
        <ProjectKnowledge
          language={language}
          files={project.library_files ?? []}
          selectedFiles={selectedLibraryFiles}
          isRunning={isRunning}
          onImport={onImportKnowledge}
        />
      ) : null}

      {visibleStage === "topic" ? (
        <TopicStagePanel
          language={language}
          project={project}
          pendingTopic={pendingTopic}
          disabled={isRunning}
          onPendingTopicChange={onPendingTopicChange}
          onSelectTopic={onSelectTopic}
        />
      ) : null}

      {visibleStage === "draft" ? (
        <ArticleEditor
          language={language}
          title={project.title}
          digest={project.digest}
          markdown={articleMarkdown}
          revision={revision}
          disabled={!articleMarkdown.trim() || !revision.trim() || isRunning}
          onMarkdownChange={onMarkdownChange}
          onRevisionChange={onRevisionChange}
          onRevise={onRevise}
        />
      ) : null}

      {visibleStage === "images" ? (
        <ImageSuggestionOptions
          language={language}
          value={contentImageCount}
          imageStylePreset={imageStylePreset}
          coverAspectRatio={coverImageAspectRatio}
          contentAspectRatio={contentImageAspectRatio}
          isRunning={isRunning}
          hasSuggestions={hasSuggestions}
          onChange={onContentImageCountChange}
          onImageStylePresetChange={onImageStylePresetChange}
          onCoverAspectRatioChange={onCoverImageAspectRatioChange}
          onContentAspectRatioChange={onContentImageAspectRatioChange}
          onSuggest={onSuggestImages}
        />
      ) : null}

      {visibleStage === "images" && hasSuggestions ? (
        <ImageSection
          language={language}
          coverPrompt={coverPrompt}
          contentPromptsText={contentPromptsText}
          contentImageCount={contentImageCount}
          coverAspectRatio={coverImageAspectRatio}
          contentAspectRatio={contentImageAspectRatio}
          rationale={project.image_suggestion_rationale ?? ""}
          progress={imageProgress}
          imageState={project.images}
          images={images}
          errors={imageErrors}
          hasSuggestions={hasSuggestions}
          isRunning={isRunning}
          onCoverPromptChange={onCoverPromptChange}
          onContentPromptsTextChange={onContentPromptsTextChange}
          onRetryTasks={onRetryImageTasks}
        />
      ) : null}

      {visibleStage === "design" && project.html_path ? (
        <div className="stage-stack">
          <DesignStagePanel
            language={language}
            project={project}
            nextAction={nextAction}
            designTheme={designTheme}
            onDesignThemeChange={onDesignThemeChange}
            onReformat={() => onContinueFormat()}
            disabled={isRunning}
          />
        </div>
      ) : null}

      {visibleStage === "publish" ? (
        <PublishSection language={language} project={project} />
      ) : null}
    </div>
  );
}

function ReferenceReadyPanel({ language, project }: { language: "zh" | "en"; project: WriterProject }) {
  const files = project.library_files ?? [];
  return (
    <section className="project-section stage-focus-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "已导入知识" : "Imported knowledge"}</h2>
        <span>{files.length}</span>
      </div>
      <div className="reference-list compact">
        {files.slice(0, 6).map((item) => (
          <article key={`${item.library}-${item.markdown_path}`} className="reference-row">
            <strong>{item.title || item.markdown_path}</strong>
            <span>{libraryLabel(item.library, language)} · {item.markdown_path}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function TopicSummaryPanel({ language, topic }: { language: "zh" | "en"; topic?: Record<string, unknown> | null }) {
  return (
    <section className="project-section stage-focus-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "已确认选题" : "Confirmed topic"}</h2>
      </div>
      {topic ? (
        <article className="topic-card selected static">
          <strong>{text(topic.title, topic.topic, language === "zh" ? "未命名选题" : "Untitled topic")}</strong>
          <span>{text(topic.angle, topic.reason, topic.summary, topic.reader_pain)}</span>
        </article>
      ) : (
        <EmptyState title={language === "zh" ? "还没有确认选题" : "No topic confirmed"} />
      )}
    </section>
  );
}

function TopicStagePanel({
  language,
  project,
  pendingTopic,
  disabled,
  onPendingTopicChange,
  onSelectTopic,
}: {
  language: "zh" | "en";
  project: WriterProject;
  pendingTopic: Record<string, unknown> | null;
  disabled: boolean;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
}) {
  const hasTopics = Boolean(project.topics?.length);
  return (
    <div className="stage-stack topic-stage-stack">
      <ReferenceReadyPanel language={language} project={project} />
      <section className="project-section stage-focus-panel topic-strategy-strip">
        <div className="section-heading">
          <h2>{language === "zh" ? "选题策略" : "Topic strategy"}</h2>
          <span>{language === "zh" ? "真实生成规则" : "Real generation rule"}</span>
        </div>
        <p className="hint">
          {language === "zh"
            ? "选题会严格基于已导入知识生成，不引入未选中的历史内容或外部事实。需要调整方向时，先回到项目创建阶段更换导入文件。"
            : "Topics are generated strictly from imported knowledge. To change direction, return to the project stage and adjust imported files."}
        </p>
      </section>
      {hasTopics ? (
        <TopicCards
          language={language}
          topics={project.topics ?? []}
          selected={project.topic}
          pendingTopic={pendingTopic}
          disabled={disabled}
          onPendingTopicChange={onPendingTopicChange}
          onSelectTopic={onSelectTopic}
        />
      ) : (
        <section className="project-section stage-focus-panel">
          <EmptyState title={language === "zh" ? "还没有选题建议" : "No topic suggestions yet"} />
        </section>
      )}
      {project.topic ? <TopicSummaryPanel language={language} topic={project.topic} /> : null}
    </div>
  );
}

function DesignStagePanel({
  language,
  project,
  nextAction,
  designTheme,
  onDesignThemeChange,
  onReformat,
  disabled,
}: {
  language: "zh" | "en";
  project: WriterProject;
  nextAction: string;
  designTheme: string;
  onDesignThemeChange: (value: string) => void;
  onReformat: () => void;
  disabled?: boolean;
}) {
  return (
    <section className="project-section design-stage-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "美编输出" : "Design output"}</h2>
        <span>
          {project.html_path
            ? project.design_confirmed
              ? language === "zh"
                ? "已确认"
                : "Confirmed"
              : language === "zh"
                ? "待确认"
                : "Pending confirmation"
            : language === "zh"
              ? "待生成"
              : "Pending"}
        </span>
      </div>
      <div className="design-theme-picker" role="group" aria-label={language === "zh" ? "美编主题" : "Design theme"}>
        {designThemeOptions.map((item) => (
          <button
            key={item.id}
            type="button"
            className={designTheme === item.id ? "theme-chip active" : "theme-chip"}
            disabled={disabled}
            onClick={() => onDesignThemeChange(item.id)}
          >
            {language === "zh" ? item.zh : item.en}
          </button>
        ))}
      </div>
      {project.html_path ? (
        <>
          <HtmlPreviewControls language={language} htmlPath={project.html_path} />
          <DesignCompatibilityPanel language={language} project={project} />
          <div className="design-action-row">
            <button className="secondary-button" type="button" disabled={disabled} onClick={onReformat}>
              <Sparkles size={16} />
              {language === "zh" ? "重新美编但保留图片位置" : "Reformat, keep images"}
            </button>
          </div>
        </>
      ) : (
        <EmptyState title={language === "zh" ? "还没有生成 HTML" : "No HTML yet"} />
      )}
    </section>
  );
}

function DesignCompatibilityPanel({ language, project }: { language: "zh" | "en"; project: WriterProject }) {
  const checks = project.preflight?.checks ?? [];
  const intent = project.design_intent ?? {};
  const inspection = (project.publish_inspection ?? project.publish_sanitize?.publish_inspection ?? {}) as Record<string, unknown>;
  const sanitizeReport = project.format_sanitize_report ?? {};
  const compactChecks = checks.length
    ? checks.filter((item) => ["content_images", "missing_images", "data_images", "remote_images", "wechat_html_sanitize", "html_size", "digest", "cover"].includes(String(item.key)))
    : [
        {
          key: "images",
          label: language === "zh" ? "图片" : "Images",
          ok: !inspection.missing_images && !inspection.data_images && !inspection.remote_images,
          detail: language === "zh" ? "等待预检或清洗报告" : "Waiting for sanitize or preflight report",
          optional: true,
        },
        {
          key: "sanitize",
          label: language === "zh" ? "禁用标签" : "Forbidden tags",
          ok: !inspection.forbidden_tags && !sanitizeReport.removed_forbidden_tags,
          detail: language === "zh" ? "模板渲染器会在发布前清洗" : "The renderer sanitizes before publishing",
          optional: true,
        },
      ];
  const intentItems = [
    ["theme", language === "zh" ? "主题" : "Theme"],
    ["emphasis_density", language === "zh" ? "强调密度" : "Emphasis"],
    ["decoration_level", language === "zh" ? "装饰强度" : "Decoration"],
    ["paragraph_rhythm", language === "zh" ? "段落节奏" : "Rhythm"],
    ["quote_style", language === "zh" ? "引用样式" : "Quote"],
    ["image_style", language === "zh" ? "图片样式" : "Images"],
  ] as const;
  const components = Array.isArray(intent.components) ? intent.components.map(String) : [];
  return (
    <div className="design-compatibility-panel">
      <div className="compatibility-header">
        <strong>{language === "zh" ? "发布兼容性状态" : "Publish compatibility"}</strong>
        <span>{project.preflight?.ok ? (language === "zh" ? "预检通过" : "Preflight passed") : language === "zh" ? "待预检" : "Pending preflight"}</span>
      </div>
      <div className="compatibility-grid">
        {compactChecks.map((item) => (
          <article key={item.key || item.label} className={item.ok ? "compatibility-item ok" : item.optional ? "compatibility-item warn" : "compatibility-item failed"}>
            <strong>{item.label || item.key}</strong>
            <span>{item.detail}</span>
          </article>
        ))}
      </div>
      <div className="design-intent-grid">
        {intentItems.map(([key, label]) => (
          <span key={key}>
            <b>{label}</b>
            {String(intent[key] ?? "-")}
          </span>
        ))}
      </div>
      {components.length ? <p className="design-components">{components.slice(0, 10).join(" / ")}</p> : null}
    </div>
  );
}

function ProjectSetup({
  language,
  name,
  selectedFiles,
  isRunning,
  hasOpenProject,
  onNameChange,
  onCancel,
  onCreate,
}: {
  language: "zh" | "en";
  name: string;
  selectedFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  hasOpenProject: boolean;
  onNameChange: (value: string) => void;
  onCancel: () => void;
  onCreate: () => void;
}) {
  return (
    <section className="content-panel project-setup-guide">
      <div className="setup-copy">
        <span>{language === "zh" ? "公众号" : "WeChat article writing"}</span>
        <h2>{language === "zh" ? "创建专用公众号文章项目" : "Create a dedicated WeChat article project"}</h2>
      </div>
      <div className="setup-form-grid">
        <label>
          <span>{language === "zh" ? "项目名称" : "Project name"}</span>
          <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder={language === "zh" ? "例如：AI 芯片公众号文章" : "Example: AI chip article"} />
        </label>
      </div>
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
      <div className="setup-actions">
        <button className="primary-cta" type="button" disabled={isRunning || !name.trim()} onClick={onCreate}>
          <strong>{language === "zh" ? "创建并进入工作流" : "Create and start"}</strong>
        </button>
        {hasOpenProject ? (
          <button className="secondary-button" type="button" disabled={isRunning} onClick={onCancel}>
            {language === "zh" ? "返回当前项目" : "Back to project"}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function ProjectStrategyPanel({
  language,
  kind,
  writingStrategy,
  designStrategy,
  designTheme = "tech",
  onWritingStrategyChange,
  onDesignStrategyChange,
  onDesignThemeChange,
  onSave,
  saveDisabled,
  writingStrategyPresets,
  defaultWritingStrategyId,
  writingStrategyLibraryError,
  onWritingStrategyPresetsChange,
  saveLabel,
  hint,
}: {
  language: "zh" | "en";
  kind: "writing" | "design";
  writingStrategy: string;
  designStrategy: string;
  designTheme?: string;
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
  onDesignThemeChange?: (value: string) => void;
  onSave?: (writingStrategy: string, designStrategy: string) => void;
  saveDisabled?: boolean;
  writingStrategyPresets?: WriterStrategyPreset[];
  defaultWritingStrategyId?: string;
  writingStrategyLibraryError?: string;
  onWritingStrategyPresetsChange?: (items: WriterStrategyPreset[]) => void;
  saveLabel?: string;
  hint?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [draftWritingStrategy, setDraftWritingStrategy] = useState(writingStrategy);
  const [draftDesignStrategy, setDraftDesignStrategy] = useState(designStrategy);
  const [selectedWritingPresetId, setSelectedWritingPresetId] = useState("");
  const [draftWritingPresetName, setDraftWritingPresetName] = useState("");
  const [strategyLibraryError, setStrategyLibraryError] = useState("");
  const [strategyLibrarySaving, setStrategyLibrarySaving] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setDraftWritingStrategy(writingStrategy);
      setDraftDesignStrategy(designStrategy);
      setStrategyLibraryError("");
    }
  }, [writingStrategy, designStrategy, isOpen]);

  useEffect(() => {
    if (!isOpen || kind !== "writing") return;
    const presets = writingStrategyPresets ?? [];
    const matched = presets.find((item) => item.body.trim() === writingStrategy.trim());
    const fallback = matched ?? presets.find((item) => item.id === defaultWritingStrategyId) ?? presets[0];
    setSelectedWritingPresetId(fallback?.id ?? "");
    setDraftWritingPresetName(matched ? matched.name : fallback?.name ?? "");
    setDraftWritingStrategy(writingStrategy.trim() ? writingStrategy : fallback?.body ?? "");
  }, [defaultWritingStrategyId, isOpen, kind, writingStrategy, writingStrategyPresets]);

  const currentStrategy = kind === "writing" ? writingStrategy : designStrategy;
  const currentDraftStrategy = kind === "writing" ? draftWritingStrategy : draftDesignStrategy;
  const dirty = currentDraftStrategy !== currentStrategy;
  const summary = summarizeStrategy(currentStrategy, language, kind);
  const writingPresets = writingStrategyPresets ?? [];
  const selectedWritingPreset = writingPresets.find((item) => item.id === selectedWritingPresetId);
  const selectedWritingPresetReadonly = Boolean(selectedWritingPreset?.readonly);
  const cleanWritingPresetName = draftWritingPresetName.trim();
  const cleanWritingPresetBody = draftWritingStrategy.trim();
  const canSaveWritingPreset = kind === "writing" && Boolean(cleanWritingPresetName && cleanWritingPresetBody && !selectedWritingPresetReadonly && !strategyLibrarySaving);
  const canDeleteWritingPreset = kind === "writing" && Boolean(selectedWritingPreset && !selectedWritingPresetReadonly && !strategyLibrarySaving);
  const applyDisabledReason =
    kind === "writing" && !cleanWritingPresetBody
      ? language === "zh"
        ? "写文策略正文不能为空"
        : "Writing strategy body is required"
      : "";
  const strategyTitle =
    kind === "writing"
      ? language === "zh"
        ? "写文策略"
        : "Writing strategy"
      : language === "zh"
        ? "美编策略"
        : "Design strategy";
  const strategyEditorTitle =
    kind === "writing"
      ? language === "zh"
        ? "编辑写文策略"
        : "Edit writing strategy"
      : language === "zh"
        ? "编辑美编策略"
        : "Edit design strategy";
  const strategyToolbarTitle =
    kind === "writing"
      ? language === "zh"
        ? "只调整初稿生成策略"
        : "Only tune draft generation"
      : language === "zh"
        ? "只调整 HTML 美编策略"
        : "Only tune HTML design";

  const closePanel = () => {
    setDraftWritingStrategy(writingStrategy);
    setDraftDesignStrategy(designStrategy);
    setStrategyLibraryError("");
    setIsOpen(false);
  };

  const applyStrategies = () => {
    const nextWritingStrategy = kind === "writing" ? draftWritingStrategy : writingStrategy;
    const nextDesignStrategy = kind === "design" ? draftDesignStrategy : designStrategy;
    if (kind === "writing" && !nextWritingStrategy.trim()) {
      setStrategyLibraryError(applyDisabledReason);
      return;
    }
    onWritingStrategyChange(nextWritingStrategy);
    onDesignStrategyChange(nextDesignStrategy);
    onSave?.(nextWritingStrategy, nextDesignStrategy);
    setIsOpen(false);
  };

  const selectWritingPreset = (presetId: string) => {
    const preset = writingPresets.find((item) => item.id === presetId);
    setSelectedWritingPresetId(presetId);
    setDraftWritingPresetName(preset?.name ?? "");
    setDraftWritingStrategy(preset?.body ?? "");
    setStrategyLibraryError("");
  };

  const newWritingPreset = () => {
    setSelectedWritingPresetId("");
    setDraftWritingPresetName(nextWritingPresetName(writingPresets, language));
    setDraftWritingStrategy("");
    setStrategyLibraryError("");
  };

  const copyWritingPreset = () => {
    setSelectedWritingPresetId("");
    setDraftWritingPresetName(
      cleanWritingPresetName
        ? language === "zh"
          ? `${cleanWritingPresetName}副本`
          : `${cleanWritingPresetName} copy`
        : language === "zh"
          ? "新写文策略"
          : "New writing strategy",
    );
    setStrategyLibraryError("");
  };

  const saveWritingPreset = async () => {
    if (!cleanWritingPresetName) {
      setStrategyLibraryError(language === "zh" ? "策略名称不能为空" : "Strategy name is required");
      return;
    }
    if (!cleanWritingPresetBody) {
      setStrategyLibraryError(language === "zh" ? "策略正文不能为空" : "Strategy body is required");
      return;
    }
    if (selectedWritingPresetReadonly) {
      setStrategyLibraryError(language === "zh" ? "默认策略不能覆盖，请先复制为新策略" : "The default strategy is read-only. Copy it first.");
      return;
    }
    setStrategyLibrarySaving(true);
    setStrategyLibraryError("");
    try {
      const payload = await writerApi.saveWriterWritingStrategy(
        cleanWritingPresetName,
        cleanWritingPresetBody,
        selectedWritingPresetId || undefined,
      );
      onWritingStrategyPresetsChange?.(payload.items ?? []);
      setSelectedWritingPresetId(payload.item.id);
      setDraftWritingPresetName(payload.item.name);
      setDraftWritingStrategy(payload.item.body);
    } catch (error) {
      setStrategyLibraryError(error instanceof Error ? error.message : String(error));
    } finally {
      setStrategyLibrarySaving(false);
    }
  };

  const deleteWritingPreset = async () => {
    if (!selectedWritingPreset || selectedWritingPresetReadonly) {
      setStrategyLibraryError(language === "zh" ? "默认策略不能删除" : "The default strategy cannot be deleted");
      return;
    }
    setStrategyLibrarySaving(true);
    setStrategyLibraryError("");
    try {
      const payload = await writerApi.deleteWriterWritingStrategy(selectedWritingPreset.id);
      onWritingStrategyPresetsChange?.(payload.items ?? []);
      const fallback = payload.items.find((item) => item.id === payload.default_id) ?? payload.items[0];
      setSelectedWritingPresetId(fallback?.id ?? "");
      setDraftWritingPresetName(fallback?.name ?? "");
      setDraftWritingStrategy(fallback?.body ?? "");
    } catch (error) {
      setStrategyLibraryError(error instanceof Error ? error.message : String(error));
    } finally {
      setStrategyLibrarySaving(false);
    }
  };

  return (
    <section className="project-section strategy-overview-panel">
      <div className="strategy-panel-toolbar">
        <div>
          <span>{language === "zh" ? "策略面板" : "Strategy panel"}</span>
          <strong>{strategyToolbarTitle}</strong>
        </div>
        <button className="secondary-button" type="button" disabled={saveDisabled} onClick={() => setIsOpen(true)}>
          <Sparkles size={16} />
          {language === "zh" ? "打开策略面板" : "Open strategy panel"}
        </button>
      </div>
      <div className="strategy-summary-grid">
        <article className="strategy-summary-card">
          <span>{strategyTitle}</span>
          <strong>{currentStrategy.trim() ? (language === "zh" ? "已自定义" : "Custom strategy") : (language === "zh" ? "系统默认" : "System default")}</strong>
          <p>{summary}</p>
        </article>
      </div>
      {kind === "design" ? (
        <div className="design-theme-picker" role="group" aria-label={language === "zh" ? "美编主题" : "Design theme"}>
          {designThemeOptions.map((item) => (
            <button
              key={item.id}
              type="button"
              className={designTheme === item.id ? "theme-chip active" : "theme-chip"}
              onClick={() => onDesignThemeChange?.(item.id)}
            >
              {language === "zh" ? item.zh : item.en}
            </button>
          ))}
        </div>
      ) : null}
      {hint ? <p className="hint strategy-panel-hint">{hint}</p> : null}
      {isOpen ? (
        <div className="modal-backdrop" onClick={closePanel}>
          <div className="modal-panel strategy-modal-panel" onClick={(event) => event.stopPropagation()}>
            <div className="modal-title-row">
              <div>
                <span>{language === "zh" ? "策略编辑" : "Strategy editor"}</span>
                <h2>{strategyEditorTitle}</h2>
              </div>
              <button className="secondary-button" type="button" onClick={closePanel}>
                {language === "zh" ? "关闭" : "Close"}
              </button>
            </div>
            <div className="strategy-grid">
              {kind === "writing" ? (
                <>
                  <div className="strategy-library-layout">
                    <aside className="strategy-library-list" aria-label={language === "zh" ? "写文策略库" : "Writing strategy library"}>
                      {writingPresets.length ? (
                        writingPresets.map((preset) => (
                          <button
                            key={preset.id}
                            type="button"
                            className={preset.id === selectedWritingPresetId ? "strategy-library-item selected" : "strategy-library-item"}
                            onClick={() => selectWritingPreset(preset.id)}
                          >
                            <strong>{preset.name}</strong>
                            <span>{preset.readonly ? (language === "zh" ? "默认只读" : "Default") : language === "zh" ? "自定义" : "Custom"}</span>
                          </button>
                        ))
                      ) : (
                        <p className="hint">{language === "zh" ? "策略库加载中或暂无策略。" : "Strategy library is loading or empty."}</p>
                      )}
                    </aside>
                    <div className="strategy-library-editor">
                      <label>
                        <span>{language === "zh" ? "策略名称" : "Strategy name"}</span>
                        <input
                          value={draftWritingPresetName}
                          disabled={selectedWritingPresetReadonly}
                          onChange={(event) => setDraftWritingPresetName(event.target.value)}
                          placeholder={language === "zh" ? "例如：证据优先写法" : "For example: Evidence-first style"}
                        />
                      </label>
                      <div className="strategy-library-actions">
                        <button className="secondary-button" type="button" disabled={strategyLibrarySaving} onClick={newWritingPreset}>
                          {language === "zh" ? "新建" : "New"}
                        </button>
                        <button className="secondary-button" type="button" disabled={strategyLibrarySaving || !cleanWritingPresetBody} onClick={copyWritingPreset}>
                          {language === "zh" ? "复制为新策略" : "Copy as new"}
                        </button>
                        <button className="secondary-button" type="button" disabled={!canSaveWritingPreset} onClick={saveWritingPreset}>
                          <Save size={16} />
                          {language === "zh" ? "保存策略" : "Save strategy"}
                        </button>
                        <button
                          className="secondary-button danger"
                          type="button"
                          disabled={!canDeleteWritingPreset}
                          title={selectedWritingPresetReadonly ? (language === "zh" ? "默认策略不能删除" : "The default strategy cannot be deleted") : ""}
                          onClick={deleteWritingPreset}
                        >
                          {language === "zh" ? "删除" : "Delete"}
                        </button>
                      </div>
                    </div>
                  </div>
                <label>
                  <span>{strategyTitle}</span>
                  <textarea
                    value={draftWritingStrategy}
                    onChange={(event) => setDraftWritingStrategy(event.target.value)}
                    placeholder={language === "zh" ? "留空则使用系统默认写文策略" : "Leave empty to use the default writing strategy"}
                  />
                </label>
                </>
              ) : (
                <label>
                  <span>{strategyTitle}</span>
                  <div className="strategy-preset-row">
                    {designStrategyPresets.map((preset) => (
                      <button
                        key={preset.id}
                        className="secondary-button"
                        type="button"
                        onClick={() => setDraftDesignStrategy(preset.value)}
                      >
                        {language === "zh" ? preset.zh : preset.en}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={draftDesignStrategy}
                    onChange={(event) => setDraftDesignStrategy(event.target.value)}
                    placeholder={language === "zh" ? "留空则使用系统默认美编策略" : "Leave empty to use the default design strategy"}
                  />
                </label>
              )}
            </div>
            {kind === "writing" && (writingStrategyLibraryError || strategyLibraryError) ? (
              <p className="disabled-reason">{strategyLibraryError || writingStrategyLibraryError}</p>
            ) : null}
            {hint ? <p className="hint strategy-panel-hint">{hint}</p> : null}
            <div className="strategy-modal-actions">
              <button className="secondary-button" type="button" onClick={closePanel}>
                {language === "zh" ? "取消" : "Cancel"}
              </button>
              <button
                className="primary-cta"
                type="button"
                disabled={saveDisabled || (kind === "writing" ? !cleanWritingPresetBody : !dirty)}
                title={applyDisabledReason}
                onClick={applyStrategies}
              >
                <Save size={16} />
                {onSave ? (language === "zh" ? "保存并应用到项目" : "Save to project") : (language === "zh" ? "应用到当前创建" : "Apply to setup")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ProjectKnowledge({
  language,
  files,
  selectedFiles,
  isRunning,
  onImport,
}: {
  language: "zh" | "en";
  files: WriterProject["library_files"];
  selectedFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  onImport: () => void;
}) {
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "导入知识" : "Imported knowledge"}</h2>
        <span>{files?.length || 0} {language === "zh" ? "个" : "items"}</span>
      </div>
      <div className="knowledge-import-bar">
        <span className="hint">
          {language === "zh" ? `已勾选 ${selectedFiles.length} 个` : `${selectedFiles.length} checked`}
        </span>
        <button className="secondary-button" type="button" disabled={isRunning || !selectedFiles.length} onClick={onImport}>
          <Save size={16} />
          {language === "zh" ? "导入勾选文件" : "Import checked"}
        </button>
      </div>
      {files?.length ? (
        <div className="reference-list">
          {files.map((item) => (
            <article key={`${item.library}-${item.markdown_path}`} className="reference-row">
              <strong>{item.title || item.markdown_path}</strong>
              <span>{libraryLabel(item.library, language)} · {item.markdown_path}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title={language === "zh" ? "还没有导入知识" : "No imported knowledge"}
        />
      )}
    </section>
  );
}

function TopicCards({
  language,
  topics,
  selected,
  pendingTopic,
  disabled,
  onPendingTopicChange,
  onSelectTopic,
}: {
  language: "zh" | "en";
  topics: Array<Record<string, unknown>>;
  selected?: Record<string, unknown> | null;
  pendingTopic?: Record<string, unknown> | null;
  disabled: boolean;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
}) {
  const pendingTitle = pendingTopic ? text(pendingTopic.title, pendingTopic.topic) : "";
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "选题建议" : "Topic suggestions"}</h2>
        <span>{topics.length}</span>
      </div>
      {topics.length ? (
        <div className="topic-card-grid">
          {topics.map((topic, index) => {
            const title = text(topic.title, topic.topic, language === "zh" ? "未命名选题" : "Untitled topic");
            const active = selected && text(selected.title, selected.topic) === title;
            const pending = pendingTitle === title;
            return (
              <button key={`${title}-${index}`} className={active || pending ? "topic-card selected" : "topic-card"} type="button" disabled={disabled} onClick={() => onPendingTopicChange(topic)}>
                <strong>{title}</strong>
                <span>{text(topic.angle, topic.reason, topic.summary, topic.reader_pain)}</span>
                {pending ? <em>{language === "zh" ? "待确认" : "Pending confirmation"}</em> : null}
              </button>
            );
          })}
        </div>
      ) : (
        <EmptyState title={language === "zh" ? "还没有选题建议" : "No topic suggestions"} />
      )}
    </section>
  );
}

function ArticleEditor({
  language,
  title,
  digest,
  markdown,
  revision,
  disabled,
  onMarkdownChange,
  onRevisionChange,
  onRevise,
}: {
  language: "zh" | "en";
  title?: string;
  digest?: string;
  markdown: string;
  revision: string;
  disabled: boolean;
  onMarkdownChange: (value: string) => void;
  onRevisionChange: (value: string) => void;
  onRevise: () => void;
}) {
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "初稿与编辑" : "Draft and editing"}</h2>
        <span>{markdown ? `${markdown.length} chars` : language === "zh" ? "未生成" : "Not generated"}</span>
      </div>
      {title ? <h3 className="article-title">{title}</h3> : null}
      {digest ? <p className="hint">{digest}</p> : null}
      <textarea
        className="article-editor-large"
        value={markdown}
        onChange={(event) => onMarkdownChange(event.target.value)}
        placeholder={language === "zh" ? "确认选题后生成的初稿会显示在这里，也可以手动编辑后再进入配图和美编。" : "The generated draft appears here. You can edit it before images and design."}
      />
      <div className="revision-row">
        <input value={revision} onChange={(event) => onRevisionChange(event.target.value)} placeholder={language === "zh" ? "修订指令，例如：压缩开头，增强结论" : "Revision instruction"} />
        <button className="secondary-button" type="button" disabled={disabled} onClick={onRevise}>
          <Sparkles size={16} />
          {language === "zh" ? "修订" : "Revise"}
        </button>
      </div>
    </section>
  );
}

function ImageSuggestionOptions({
  language,
  value,
  imageStylePreset,
  coverAspectRatio,
  contentAspectRatio,
  isRunning,
  hasSuggestions,
  onChange,
  onImageStylePresetChange,
  onCoverAspectRatioChange,
  onContentAspectRatioChange,
  onSuggest,
}: {
  language: "zh" | "en";
  value: number;
  imageStylePreset: string;
  coverAspectRatio: string;
  contentAspectRatio: string;
  isRunning: boolean;
  hasSuggestions: boolean;
  onChange: (value: number) => void;
  onImageStylePresetChange: (value: string) => void;
  onCoverAspectRatioChange: (value: string) => void;
  onContentAspectRatioChange: (value: string) => void;
  onSuggest: () => void;
}) {
  return (
    <section className="project-section image-options-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图建议设置" : "Image suggestion settings"}</h2>
        <span>{language === "zh" ? "生成前" : "Before suggestions"}</span>
      </div>
      <div className="image-options-layout">
        <article className="image-options-copy">
          <strong>{language === "zh" ? "先选择正文图片数量" : "Choose how many content images you want first"}</strong>
          <p>
            {language === "zh"
              ? "这里会决定下一步生成多少条正文配图建议；确认建议后再规划配图任务。"
              : "This directly controls how many content image prompts will be suggested next."}
          </p>
        </article>
        <ImageCountSelect language={language} value={value} disabled={isRunning} onChange={onChange} />
      </div>
      <label className="image-style-select">
        <div className="image-count-copy">
          <span>{language === "zh" ? "配图风格" : "Image style preset"}</span>
          <small>
            {language === "zh"
              ? "风格会写入真实配图建议提示词。"
              : "This style is injected into the real image suggestion prompts."}
          </small>
        </div>
        <div className="image-count-control">
          <select
            value={imageStylePreset}
            disabled={isRunning}
            aria-label={language === "zh" ? "配图风格" : "Image style preset"}
            onChange={(event) => onImageStylePresetChange(event.target.value)}
          >
            {imageStylePresets.map((preset) => (
              <option key={preset.id} value={preset.prompt}>
                {language === "zh" ? preset.zh : preset.en}
              </option>
            ))}
          </select>
        </div>
      </label>
        <div className="image-ratio-grid">
          <label className="image-ratio-field">
            <span>{language === "zh" ? "封面图比例" : "Cover ratio"}</span>
            <input
              value={coverAspectRatio}
              disabled={isRunning}
              placeholder="2.35:1"
              aria-label={language === "zh" ? "封面图比例" : "Cover image aspect ratio"}
              onChange={(event) => onCoverAspectRatioChange(event.target.value)}
            />
          </label>
          <label className="image-ratio-field">
            <span>{language === "zh" ? "正文图比例" : "Content ratio"}</span>
            <input
              value={contentAspectRatio}
              disabled={isRunning}
              placeholder={language === "zh" ? "留空沿用建议" : "Auto"}
              aria-label={language === "zh" ? "正文图比例" : "Content image aspect ratio"}
              onChange={(event) => onContentAspectRatioChange(event.target.value)}
            />
          </label>
        </div>
        <p className="hint image-ratio-hint">
          {language === "zh" ? "封面默认 2.35:1；正文留空时按当前图片 API 设置或配图建议适配。" : "Cover defaults to 2.35:1; leave content blank to use the current image API setting."}
        </p>
        <div className="image-options-actions">
        <button className="secondary-button" type="button" disabled={isRunning} onClick={onSuggest}>
          <Sparkles size={16} />
          {hasSuggestions
            ? language === "zh"
              ? "重新生成建议"
              : "Refresh image suggestions"
            : language === "zh"
              ? "生成配图建议"
              : "Suggest images"}
        </button>
      </div>
    </section>
  );
}

function ImageCountSelect({
  language,
  value,
  disabled,
  onChange,
}: {
  language: "zh" | "en";
  value: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <label className="image-count-select">
      <div className="image-count-copy">
        <span>{language === "zh" ? "正文图片数量" : "Content image count"}</span>
        <small>
          {language === "zh"
            ? "建议先少量生成，便于确认节奏。"
            : "Start small so layout and pacing are easier to confirm."}
        </small>
      </div>
      <div className="image-count-control">
        <select
          value={value}
          disabled={disabled}
          aria-label={language === "zh" ? "正文图片数量" : "Content image count"}
          onChange={(event) => onChange(Number(event.target.value))}
        >
          {[1, 2, 3].map((count) => (
            <option key={count} value={count}>
              {language === "zh" ? `${count} 张` : `${count} image${count > 1 ? "s" : ""}`}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}

function ImageSection({
  language,
  coverPrompt,
  contentPromptsText,
  contentImageCount,
  coverAspectRatio,
  contentAspectRatio,
  rationale,
  progress,
  imageState,
  images,
  errors,
  hasSuggestions,
  isRunning,
  onCoverPromptChange,
  onContentPromptsTextChange,
  onRetryTasks,
}: {
  language: "zh" | "en";
  coverPrompt: string;
  contentPromptsText: string;
  contentImageCount: number;
  coverAspectRatio: string;
  contentAspectRatio: string;
  rationale: string;
  progress: ImageProgress;
  imageState?: WriterProject["images"];
  images: Array<{ path?: string; prompt?: string; index?: number }>;
  errors?: Array<{ kind?: string; index?: number; message?: string }>;
  hasSuggestions: boolean;
  isRunning: boolean;
  onCoverPromptChange: (value: string) => void;
  onContentPromptsTextChange: (value: string) => void;
  onRetryTasks: (tasks?: WriterImageRetryTask[]) => void;
}) {
  const tasks = imageTaskList(language, coverPrompt, contentPromptsText, contentImageCount, imageState, errors);
  const failedTasks = tasks.filter((task) => task.status === "failed");
  const updateContentPrompt = (index: number, value: string) => {
    const lines = promptLines(contentPromptsText);
    while (lines.length < index) lines.push("");
    lines[index - 1] = value;
    onContentPromptsTextChange(lines.join("\n"));
  };

  return (
    <section className="project-section image-stage-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图任务" : "Image tasks"}</h2>
        <span>
          {images.length} / {tasks.length}
        </span>
      </div>

      {failedTasks.length ? (
        <div className="image-recovery-banner">
          <div>
            <strong>{language === "zh" ? "图片生成未完成" : "Image generation needs attention"}</strong>
            <span>
              {language === "zh"
                ? "已成功的图片会保留。可以修改失败项提示词后，只重试失败图片。"
                : "Successful images are kept. Edit failed prompts and retry only failed items."}
            </span>
          </div>
          <button className="secondary-button" type="button" disabled={isRunning} onClick={() => onRetryTasks(failedTasks.map(taskToRetryInput))}>
            {language === "zh" ? "重试失败图片" : "Retry failed"}
          </button>
        </div>
      ) : null}

      <p className="hint">
        {language === "zh"
          ? "这里展示配图建议生成后的任务清单。失败后可只重试失败图片，不会抹掉已成功图片。"
          : "This shows the task list after image suggestions. Failed items can be retried without removing successful images."}
      </p>

      {hasSuggestions && rationale.trim() ? (
        <article className="image-rationale-panel">
          <div className="image-rationale-heading">
            <strong>{language === "zh" ? "配图建议" : "Detailed image direction"}</strong>
            <span>{language === "zh" ? "建议" : "Suggestion"}</span>
          </div>
          <p>{rationale}</p>
        </article>
      ) : null}

      <div className="prompt-grid">
        <label>
          <span>{language === "zh" ? "封面图提示词" : "Cover prompt"}</span>
          <textarea value={coverPrompt} onChange={(event) => onCoverPromptChange(event.target.value)} />
        </label>
        <label>
          <span>{language === "zh" ? "正文配图提示词" : "Content prompts"}</span>
          <textarea value={contentPromptsText} onChange={(event) => onContentPromptsTextChange(event.target.value)} />
        </label>
      </div>

      {progress ? (
        <div className="image-progress">
          <span>{language === "zh" ? "生成进度" : "Generation progress"}</span>
          <strong>{progress.done} / {progress.total}</strong>
        </div>
      ) : null}

      <div className="image-task-list">
        {tasks.map((task) => (
          <article key={task.id} className={`image-task-card ${task.status}`}>
            <div className="image-task-preview">
              {task.path ? <img src={writerApi.writerFileUrl(task.path)} alt={task.label} /> : <ImageIcon size={28} />}
            </div>
            <div className="image-task-body">
              <div className="image-task-title">
                <strong>{task.label}</strong>
                <span>{imageTaskStatusLabel(task.status, language)}</span>
              </div>
              {task.status === "failed" ? (
                <label className="image-task-prompt">
                  <span>{language === "zh" ? "重试提示词" : "Retry prompt"}</span>
                  <textarea
                    value={task.prompt}
                    onChange={(event) =>
                      task.kind === "cover"
                        ? onCoverPromptChange(event.target.value)
                        : updateContentPrompt(task.index ?? 1, event.target.value)
                    }
                  />
                </label>
              ) : (
                <p>{task.prompt || (language === "zh" ? "暂无提示词" : "No prompt yet")}</p>
              )}
              {task.message ? <small>{task.message}</small> : null}
            </div>
            <div className="image-task-actions">
              {task.status === "failed" ? (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isRunning || !task.prompt.trim()}
                    onClick={() => onRetryTasks([taskToRetryInput(task, { cover: coverAspectRatio, content: contentAspectRatio })])}
                  >
                  {language === "zh" ? "重试这张" : "Retry"}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function PublishSection({
  language,
  project,
}: {
  language: "zh" | "en";
  project: WriterProject;
}) {
  const checks = project.preflight?.checks ?? [];
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "美编、预检与发布" : "Design, preflight, publish"}</h2>
        <span>{project.preflight?.ok ? (language === "zh" ? "预检通过" : "Passed") : language === "zh" ? "待检查" : "Pending"}</span>
      </div>
      {project.html_path ? <HtmlPreviewControls language={language} htmlPath={project.html_path} /> : null}
      {checks.length ? (
        <div className="preflight-list">
          {checks.map((item) => (
            <article key={item.key || item.label} className={item.ok ? "preflight-row ok" : item.optional ? "preflight-row warn" : "preflight-row failed"}>
              <strong>{item.label || item.key}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title={language === "zh" ? "还没有预检结果" : "No preflight results"} />
      )}
    </section>
  );
}

function HtmlPreviewControls({ language, htmlPath }: { language: "zh" | "en"; htmlPath: string }) {
  const [showPreview, setShowPreview] = useState(false);
  const url = writerApi.writerFileUrl(htmlPath);
  return (
    <div className="html-preview-panel">
      <div className="html-preview-actions">
        <div>
          <strong>{language === "zh" ? "美编 HTML" : "Designed HTML"}</strong>
          <span>{htmlPath}</span>
        </div>
        <button className="secondary-button" type="button" onClick={() => setShowPreview((current) => !current)}>
          <Eye size={16} />
          {showPreview ? (language === "zh" ? "收起预览" : "Hide preview") : language === "zh" ? "预览" : "Preview"}
        </button>
        <a className="secondary-button" href={url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} />
          {language === "zh" ? "打开" : "Open"}
        </a>
      </div>
      {showPreview ? <iframe className="html-preview-frame" title={language === "zh" ? "美编 HTML 预览" : "Designed HTML preview"} src={url} /> : null}
    </div>
  );
}

function guideForState(language: "zh" | "en", project: WriterProject | undefined, step: WriterStep, nextAction: string) {
  if (!project) {
    return {
      title: language === "zh" ? "创建公众号文章项目" : "Create a WeChat article project",
      body: language === "zh" ? "填写项目名称和策略，可同时导入右侧三库勾选的知识文件。" : "Name the project, set strategies, and optionally import checked library files.",
      checkpoints: [
        language === "zh" ? "选择项目类型" : "Choose project type",
        language === "zh" ? "确认写文和美编策略" : "Confirm strategies",
        language === "zh" ? "创建项目" : "Create project",
      ],
    };
  }
  if (step === "draft" && nextAction === "suggest_images") {
    return {
      title: language === "zh" ? "确认初稿" : "Confirm draft",
      body: language === "zh" ? "先检查正文是否已经能进入配图阶段。确认后不会立刻生成配图建议。" : "Review the article before moving to image planning. Confirmation will not generate suggestions yet.",
      checkpoints: [language === "zh" ? "检查标题和正文" : "Review title and body", language === "zh" ? "必要时智能修订" : "Revise if needed", language === "zh" ? "确认初稿" : "Confirm draft"],
    };
  }
  if (step === "images" && nextAction === "suggest_images") {
    return {
      title: language === "zh" ? "生成配图建议" : "Suggest images",
      body: language === "zh" ? "确认正文图片数量和配图风格后，再生成封面图与正文配图提示词。" : "Choose the image count and style before generating cover and content image prompts.",
      checkpoints: [language === "zh" ? "确认图片数量" : "Confirm image count", language === "zh" ? "选择配图风格" : "Choose image style", language === "zh" ? "生成配图建议" : "Suggest images"],
    };
  }
  const map: Record<WriterStep, ReturnType<typeof guideForState>> = {
    created: {
      title: language === "zh" ? "导入项目知识" : "Import project knowledge",
      body: language === "zh" ? "从右侧原文库、重点库、视角库勾选文件，导入后才能生成选题。" : "Check files in any library on the right, then import them before generating topics.",
      checkpoints: [language === "zh" ? "右侧切换三库" : "Switch library bucket", language === "zh" ? "勾选来源文件" : "Check files", language === "zh" ? "导入项目" : "Import into project"],
    },
    knowledge_confirmed: {
      title: language === "zh" ? "生成多个选题" : "Generate topic options",
      body: language === "zh" ? "系统会基于导入知识智能生成多个差异化选题。" : "The API will generate differentiated topic ideas from imported knowledge.",
      checkpoints: [language === "zh" ? "检查导入知识" : "Check references", language === "zh" ? "点击生成选题" : "Generate topics", language === "zh" ? "等待模型返回" : "Wait for the model"],
    },
    topics: {
      title: language === "zh" ? "确认意向选题" : "Confirm a topic",
      body: language === "zh" ? "从选题卡片中勾选一个意向选题，确认后进入初稿生成。" : "Pick one topic card before generating the draft.",
      checkpoints: [language === "zh" ? "比较标题和切入点" : "Compare title and angle", language === "zh" ? "点击一个选题" : "Click one topic", language === "zh" ? "进入初稿" : "Move to draft"],
    },
    topic: {
      title: language === "zh" ? "生成公众号初稿" : "Generate the article draft",
      body: language === "zh" ? "初稿会结合已确认选题、导入知识和写文策略生成。" : "The draft uses the selected topic, imported knowledge, and writing strategy.",
      checkpoints: [language === "zh" ? "确认选题" : "Confirm topic", language === "zh" ? "应用写文策略" : "Apply writing strategy", language === "zh" ? "生成初稿" : "Generate draft"],
    },
    draft: {
      title: nextAction === "generate_images" ? (language === "zh" ? "生成配图" : "Generate images") : (language === "zh" ? "生成配图建议" : "Suggest images"),
      body: language === "zh" ? "根据已确认初稿生成封面图和正文配图提示词，再调用配图 API。" : "Create cover and content image prompts from the confirmed draft, then call the image API.",
      checkpoints: [language === "zh" ? "生成配图建议" : "Suggest images", language === "zh" ? "检查提示词" : "Review prompts", language === "zh" ? "调用配图 API" : "Call image API"],
    },
    images: {
      title: language === "zh" ? "生成美编 HTML" : "Generate designed HTML",
      body: language === "zh" ? "美编会把文章和项目图片排成可发布 HTML。" : "Design turns the draft and images into publishable HTML.",
      checkpoints: [language === "zh" ? "确认图片" : "Confirm images", language === "zh" ? "应用美编策略" : "Apply design strategy", language === "zh" ? "生成 HTML" : "Generate HTML"],
    },
    designed: {
      title: language === "zh" ? "执行发布预检" : "Run publish preflight",
      body: language === "zh" ? "检查 HTML、封面、摘要、公众号配置和发布条件。" : "Check HTML, cover, digest, WeChat config, and publish readiness.",
      checkpoints: [language === "zh" ? "检查 HTML" : "Check HTML", language === "zh" ? "检查封面" : "Check cover", language === "zh" ? "检查公众号配置" : "Check WeChat config"],
    },
    publish_check: {
      title: language === "zh" ? "发布到草稿箱" : "Publish to draft box",
      body: language === "zh" ? "预检通过后调用旧发布流程写入公众号草稿箱。" : "After preflight passes, use the existing publish flow.",
      checkpoints: [language === "zh" ? "确认预检结果" : "Confirm preflight", language === "zh" ? "调用发布流程" : "Run publisher", language === "zh" ? "保存发布结果" : "Save result"],
    },
    published: {
      title: language === "zh" ? "项目已发布" : "Project published",
      body: language === "zh" ? "发布结果已保存到项目目录。" : "The publish result is saved in the project folder.",
      checkpoints: [language === "zh" ? "查看发布结果" : "Review result", language === "zh" ? "继续新项目" : "Start another project", language === "zh" ? "保留项目产物" : "Keep artifacts"],
    },
  };
  return map[step];
}

function workflowStageLabel(stage: WorkflowStage, language: "zh" | "en") {
  const match = workflowStages.find((item) => item.id === stage);
  return match ? (language === "zh" ? match.zh : match.en) : stage;
}

function visibleWriterStep(step: WriterStep, nextAction: string): WriterStep {
  if (step === "published") return "published";
  if (step === "draft" && nextAction === "generate_images") return "images";
  return step;
}

function workflowStageForStep(step: WriterStep, nextAction: string, draftConfirmed = false, imagesConfirmed = false): WorkflowStage {
  if (step === "created") return "project";
  if (step === "knowledge_confirmed" || step === "topics") return "topic";
  if (step === "topic") return "draft";
  if (step === "draft" && nextAction === "generate_images") return "images";
  if (step === "draft" && nextAction === "suggest_images" && draftConfirmed) return "images";
  if (step === "draft") return "draft";
  if (step === "images") return imagesConfirmed ? "design" : "images";
  if (step === "designed") return "design";
  return "publish";
}

function stepForWorkflowStage(
  stage: WorkflowStage,
  actualStep: WriterStep,
  nextAction: string,
  project: WriterProject | undefined,
): WriterStep {
  if (stage === "project") return "created";
  if (stage === "topic") {
    if (project?.topics?.length) return "topics";
    return "knowledge_confirmed";
  }
  if (stage === "draft") {
    if (project?.article_markdown) return "draft";
    return "topic";
  }
  if (stage === "images") {
    if (actualStep === "images" || (actualStep === "draft" && nextAction === "generate_images")) return "images";
    if (actualStep === "draft" && nextAction === "suggest_images" && project?.article_markdown) return "images";
    return project?.image_suggestion_rationale || project?.cover_prompt || project?.content_image_prompts?.length ? "images" : "draft";
  }
  if (stage === "design") return "designed";
  if (stage === "publish") return actualStep === "published" ? "published" : "publish_check";
  return actualStep;
}

function nextActionForVisibleStep(
  visibleStep: WriterStep,
  actualVisibleStep: WriterStep,
  backendNextAction: string,
  project: WriterProject | undefined,
  imagePromptDirty: boolean,
  hasSuggestions = false,
) {
  if (visibleStep === "images" && !hasSuggestions) return "suggest_images";
  if (visibleStep === "images") {
    if (!project?.image_suggestion_rationale && !project?.cover_prompt && !project?.content_image_prompts?.length) return "suggest_images";
    if (imagePromptDirty || !hasGeneratedProjectImages(project)) return "generate_images";
    return "confirm_images";
  }
  if (visibleStep === actualVisibleStep) return backendNextAction;
  if (visibleStep === "created") return "confirm_knowledge";
  if (visibleStep === "knowledge_confirmed") return "generate_topics";
  if (visibleStep === "topics") return "select_topic";
  if (visibleStep === "topic") return "generate_draft";
  if (visibleStep === "draft") return "suggest_images";
  if (visibleStep === "designed") {
    if (!project?.html_path) return "format_article";
    return project.design_confirmed ? "run_preflight" : "confirm_design";
  }
  if (visibleStep === "publish_check") return "run_preflight";
  if (visibleStep === "published") return "publish";
  return backendNextAction;
}

function primaryAction(
  language: "zh" | "en",
  project: WriterProject | undefined,
  step: WriterStep,
  nextAction: string,
  isRunning: boolean,
  selectedFileCount = 0,
  pendingTopic: Record<string, unknown> | null = null,
) {
  if (isRunning) return { label: language === "zh" ? "处理中..." : "Working...", disabled: true, reason: "" };
  if (!project) return { label: language === "zh" ? "先创建项目" : "Create project first", disabled: true, reason: "" };
  if (project.type && project.type !== "article") {
    return {
      label: language === "zh" ? "暂未实现" : "Not implemented",
      disabled: true,
      reason: language === "zh" ? "目前先实现公众号文章项目。" : "Only WeChat article projects are implemented first.",
    };
  }
  if (step === "created") {
    return {
      label: language === "zh" ? "导入勾选文件" : "Import checked files",
      disabled: selectedFileCount === 0,
      reason: selectedFileCount === 0 ? (language === "zh" ? "请先在右侧三库勾选文件。" : "Check files in the right library rail first.") : "",
    };
  }
  if (step === "images" && nextAction === "retry_failed_images") {
    return {
      label: language === "zh" ? "重试失败图片" : "Retry failed images",
      disabled: false,
      reason: "",
    };
  }
  if (step === "draft" && nextAction === "suggest_images") {
    return { label: language === "zh" ? "确认初稿" : "Confirm draft", disabled: false, reason: "" };
  }
  if (step === "images" && nextAction === "suggest_images") {
    return { label: language === "zh" ? "生成配图建议" : "Suggest images", disabled: false, reason: "" };
  }
  if (step === "images" && nextAction === "generate_images") {
    return { label: language === "zh" ? "生成图片" : "Generate images", disabled: false, reason: "" };
  }
  if (step === "images" && nextAction === "confirm_images") {
    return { label: language === "zh" ? "\u786e\u8ba4\u914d\u56fe" : "Confirm images", disabled: false, reason: "" };
  }
  if (step === "designed" && nextAction === "format_article") {
    return { label: language === "zh" ? "\u751f\u6210\u7f8e\u7f16 HTML" : "Generate designed HTML", disabled: false, reason: "" };
  }
  const labelMap: Partial<Record<WriterStep, string>> = {
    knowledge_confirmed: language === "zh" ? "生成选题" : "Generate topics",
    topics: language === "zh" ? "确认选题" : "Confirm topic",
    topic: language === "zh" ? "生成初稿" : "Generate draft",
    draft: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "确认初稿并生成配图建议" : "Confirm draft and suggest images"),
    images: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "确认配图" : "Confirm images"),
    designed: nextAction === "format_article" ? (language === "zh" ? "\u751f\u6210\u7f8e\u7f16 HTML" : "Generate designed HTML") : nextAction === "confirm_design" ? (language === "zh" ? "\u786e\u8ba4\u7f8e\u7f16" : "Confirm design") : (language === "zh" ? "\u6267\u884c\u9884\u68c0" : "Run preflight"),
    publish_check: nextAction === "publish" ? (language === "zh" ? "发布" : "Publish") : (language === "zh" ? "执行预检" : "Run preflight"),
    published: language === "zh" ? "已发布" : "Published",
  };
  return {
    label: labelMap[step] ?? (language === "zh" ? "继续" : "Continue"),
    disabled: (step === "topics" && !pendingTopic) || step === "published",
    reason: step === "topics" && !pendingTopic ? (language === "zh" ? "请先点击下方一个选题卡片。" : "Click one topic card below first.") : "",
  };
}

function runPrimary(
  step: WriterStep,
  nextAction: string,
  actions: {
    onImportKnowledge: () => void;
    onGenerateTopics: () => void;
    onConfirmTopic: () => void;
    onConfirmDraft: () => void;
    onGenerateDraft: () => void;
    onSuggestImages: () => void;
    onGenerateImages: () => void;
    onRetryFailedImages: () => void;
    onConfirmImages: () => void;
    onFormat: () => void;
    onConfirmDesign: () => void;
    onPreflight: () => void;
    onPublish: () => void;
  },
) {
  if (step === "created") actions.onImportKnowledge();
  else if (step === "knowledge_confirmed") actions.onGenerateTopics();
  else if (step === "topics") actions.onConfirmTopic();
  else if (step === "topic") actions.onGenerateDraft();
  else if (step === "draft" && nextAction === "suggest_images") actions.onConfirmDraft();
  else if (step === "draft" && nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "draft") actions.onConfirmDraft();
  else if (step === "images" && nextAction === "suggest_images") actions.onSuggestImages();
  else if (step === "images" && nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "images" && nextAction === "retry_failed_images") actions.onRetryFailedImages();
  else if (step === "images" && nextAction === "confirm_images") actions.onConfirmImages();
  else if (step === "images") actions.onFormat();
  else if (step === "designed" && nextAction === "format_article") actions.onFormat();
  else if (step === "designed" && nextAction === "confirm_design") actions.onConfirmDesign();
  else if (step === "designed") actions.onPreflight();
  else if (step === "publish_check" && nextAction === "publish") actions.onPublish();
  else if (step === "publish_check") actions.onPreflight();
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

type ImageTask = WriterImageRetryTask & {
  id: string;
  label: string;
  status: "success" | "failed" | "pending";
  path?: string;
  message?: string;
};

function imageTaskList(
  language: "zh" | "en",
  coverPrompt: string,
  contentPromptsText: string,
  contentImageCount: number,
  imageState?: WriterProject["images"],
  errors: Array<{ kind?: string; index?: number; message?: string }> = [],
): ImageTask[] {
  const contentPrompts = promptLines(contentPromptsText);
  const contentImages = imageState?.content_images ?? [];
  const maxContentIndex = Math.max(
    contentImageCount,
    contentPrompts.length,
    ...contentImages.map((item) => Number(item.index || 0)),
    ...errors.filter((item) => item.kind === "content").map((item) => Number(item.index || 0)),
  );
  const coverError = errors.find((item) => item.kind === "cover");
  const tasks: ImageTask[] = [];
  if (coverPrompt.trim() || imageState?.cover || coverError) {
    tasks.push({
      id: "cover",
      kind: "cover",
      label: language === "zh" ? "封面图" : "Cover",
      prompt: coverPrompt || imageState?.cover?.prompt || "",
      path: imageState?.cover?.path,
      status: coverError ? "failed" : imageState?.cover?.path ? "success" : "pending",
      message: coverError?.message,
    });
  }
  for (let index = 1; index <= maxContentIndex; index += 1) {
    const image = contentImages.find((item) => Number(item.index || 0) === index);
    const error = errors.find((item) => item.kind === "content" && Number(item.index || 0) === index);
    tasks.push({
      id: `content-${index}`,
      kind: "content",
      index,
      label: language === "zh" ? `正文配图 ${index}` : `Content image ${index}`,
      prompt: contentPrompts[index - 1] || image?.prompt || "",
      path: image?.path,
      status: error ? "failed" : image?.path ? "success" : "pending",
      message: error?.message,
    });
  }
  return tasks;
}

function imageRetryTasks(
  project: WriterProject | undefined,
  coverPrompt: string,
  contentPromptsText: string,
  contentImageCount: number,
  aspectRatios: { cover?: string; content?: string } = {},
): WriterImageRetryTask[] {
  if (!project) return [];
  return imageTaskList("zh", coverPrompt, contentPromptsText, contentImageCount, project.images, project.images?.errors ?? [])
    .filter((task) => task.status === "failed" || task.status === "pending")
    .map((task) => taskToRetryInput(task, aspectRatios))
    .filter((task) => task.prompt.trim());
}

function taskToRetryInput(task: ImageTask, aspectRatios: { cover?: string; content?: string } = {}): WriterImageRetryTask {
  return {
    kind: task.kind,
    index: task.index,
    prompt: task.prompt,
    aspectRatio: task.kind === "cover" ? aspectRatios.cover : aspectRatios.content,
  };
}

function imageTaskStatusLabel(status: ImageTask["status"], language: "zh" | "en") {
  if (status === "success") return language === "zh" ? "已生成" : "Generated";
  if (status === "failed") return language === "zh" ? "失败" : "Failed";
  return language === "zh" ? "待生成" : "Pending";
}

function imageItems(project?: WriterProject): Array<{ path?: string; prompt?: string; index?: number }> {
  if (!project?.images) return [];
  const items = project.images.items ?? [];
  const cover = project.images.cover ? [project.images.cover] : [];
  return [...cover, ...(project.images.content_images ?? []), ...items].filter((item, index, all) => {
    const path = item.path || "";
    return path && all.findIndex((candidate) => candidate.path === path) === index;
  });
}

function hasGeneratedProjectImages(project?: WriterProject) {
  if (!project?.images) return false;
  return Boolean(
    project.images.cover?.path ||
      project.images.content_images?.some((item) => item.path) ||
      project.images.items?.some((item) => item.path),
  );
}


function promptLines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function summarizeStrategy(value: string, language: "zh" | "en", kind: "writing" | "design") {
  const summary = value
    .split(/\r?\n/)
    .map((item) => item.replace(/^[-*#\d.\s、)]+/, "").trim())
    .find(Boolean);
  if (summary) return summary;
  if (kind === "writing") {
    return language === "zh" ? "留空时会使用系统默认写文策略。" : "If left empty, the default writing strategy will be used.";
  }
  return language === "zh" ? "留空时会使用系统默认美编策略。" : "If left empty, the default design strategy will be used.";
}

function nextWritingPresetName(presets: WriterStrategyPreset[], language: "zh" | "en") {
  const base = language === "zh" ? "新写文策略" : "New writing strategy";
  const existingNames = new Set(presets.map((item) => item.name.trim()).filter(Boolean));
  if (!existingNames.has(base)) return base;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${base} ${index}`;
    if (!existingNames.has(candidate)) return candidate;
  }
  return `${base} ${Date.now()}`;
}

function text(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function projectTypeLabel(value: unknown, language: "zh" | "en") {
  if (!value || value === "article") return language === "zh" ? "公众号" : "WeChat article writing";
  return language === "zh" ? "公众号" : "WeChat article writing";
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

function normalizeWriterProject(project?: WriterProject): WriterProject | undefined {
  if (!project) return undefined;
  return {
    ...project,
    library_files: Array.isArray(project.library_files) ? project.library_files.filter(isRecord) : [],
    topics: Array.isArray(project.topics) ? project.topics.filter(isRecord) : [],
    topic: isRecord(project.topic) ? project.topic : null,
    content_image_prompts: normalizeStringArray(project.content_image_prompts),
    images: normalizeImages(project.images),
    preflight: normalizePreflight(project.preflight),
  };
}

function normalizeStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  if (typeof value === "string" && value.trim()) return [value];
  return [];
}

function normalizeImages(value: WriterProject["images"] | unknown): WriterProject["images"] | undefined {
  if (!isRecord(value)) return undefined;
  const cover = isRecord(value.cover) ? value.cover : undefined;
  const items = Array.isArray(value.items) ? value.items.filter(isRecord) : [];
  const contentImages = Array.isArray(value.content_images) ? value.content_images.filter(isRecord) : [];
  const errors = Array.isArray(value.errors) ? value.errors.filter(isRecord) : [];
  return {
    cover,
    items,
    content_images: contentImages,
    errors,
    partial: Boolean(value.partial),
    ok: typeof value.ok === "boolean" ? value.ok : undefined,
  };
}

function normalizePreflight(value: WriterProject["preflight"] | unknown): WriterProject["preflight"] | undefined {
  if (!isRecord(value)) return undefined;
  return {
    ...value,
    checks: Array.isArray(value.checks) ? value.checks.filter(isRecord) : [],
    blocking: Array.isArray(value.blocking) ? value.blocking.filter(isRecord) : [],
  };
}

function isRecord(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
