import { ExternalLink, Eye, FolderPlus, ImageIcon, Save, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LibraryKind, WriterLibraryFileInput } from "../api";
import { writerApi } from "../apiWriter";
import type { WriterImageRetryTask } from "../hooks/useWriterFlow";
import type { KnowledgeItem, WriterProject, WriterProjectState, WriterStep } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { Stepper } from "../components/Stepper";

const projectTypes = [
  { id: "article", zh: "公众号文章", en: "WeChat article" },
  { id: "image_text", zh: "小红书图文", en: "Xiaohongshu post" },
  { id: "short_video", zh: "抖音短视频", en: "Douyin short video" },
  { id: "long_video", zh: "哔站长视频", en: "Bilibili long video" },
];

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

const steps: Array<{ id: WriterStep; zh: string; en: string }> = [
  { id: "created", zh: "项目", en: "Project" },
  { id: "knowledge_confirmed", zh: "知识", en: "Knowledge" },
  { id: "topics", zh: "选题", en: "Topics" },
  { id: "topic", zh: "确认", en: "Confirm" },
  { id: "draft", zh: "初稿", en: "Draft" },
  { id: "images", zh: "配图", en: "Images" },
  { id: "designed", zh: "美编", en: "Design" },
  { id: "publish_check", zh: "预检", en: "Preflight" },
  { id: "published", zh: "发布", en: "Publish" },
];

const stepIndex: Record<WriterStep, number> = {
  created: 0,
  knowledge_confirmed: 1,
  topics: 2,
  topic: 3,
  draft: 4,
  images: 5,
  designed: 6,
  publish_check: 7,
  published: 8,
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
  onGenerateImages: (coverPrompt?: string, contentPrompts?: string[], onProgress?: (done: number, total: number) => void) => void;
  onRetryImageItems: (tasks: WriterImageRetryTask[], onProgress?: (done: number, total: number) => void) => void;
  onFormat: (markdown?: string, designStrategy?: string, writingStrategy?: string) => void;
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
  const [projectType, setProjectType] = useState("article");
  const [createMode, setCreateMode] = useState(!writerState?.project);
  const [writingStrategy, setWritingStrategy] = useState("");
  const [designStrategy, setDesignStrategy] = useState("");
  const [revision, setRevision] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [coverPrompt, setCoverPrompt] = useState("");
  const [contentPromptsText, setContentPromptsText] = useState("");
  const [contentImageCount, setContentImageCount] = useState(1);
  const [imageStylePreset, setImageStylePreset] = useState(imageStylePresets[0].prompt);
  const [imageProgress, setImageProgress] = useState<ImageProgress>(null);
  const [pendingTopic, setPendingTopic] = useState<Record<string, unknown> | null>(null);
  const [reviewStep, setReviewStep] = useState<WriterStep | null>(null);

  const project = normalizeWriterProject(writerState?.project);
  const step = writerState?.step ?? "created";
  const nextAction = writerState?.next_action ?? "";
  const actualVisibleStep = visibleWriterStep(step, nextAction);
  const actualStepIndex = stepIndex[actualVisibleStep] ?? 0;
  const visibleStep = reviewStep && (stepIndex[reviewStep] ?? 0) <= actualStepIndex ? reviewStep : actualVisibleStep;
  const articleMarkdown = markdownDraft || project?.article_markdown || "";
  const strategyDirty =
    writingStrategy !== (project?.writing_strategy ?? "") || designStrategy !== (project?.design_strategy ?? "");
  const imagePromptDirty =
    coverPrompt !== (project?.cover_prompt ?? "") ||
    contentPromptsText !== (project?.content_image_prompts ?? []).join("\n");
  const viewNextAction = nextActionForVisibleStep(visibleStep, actualVisibleStep, nextAction, project, imagePromptDirty);
  const labels = steps.map((item) => (language === "zh" ? item.zh : item.en));
  const selectedLibraryFiles = useMemo(() => toWriterLibraryFiles(selectedKnowledgeFiles), [selectedKnowledgeFiles]);
  const images = imageItems(project);
  const guide = guideForState(language, project, visibleStep, viewNextAction);
  const primary = primaryAction(language, project, visibleStep, viewNextAction, isRunning);
  const clearReviewStep = () => setReviewStep(null);
  const runRetryFailedImages = (tasks = imageRetryTasks(project, coverPrompt, contentPromptsText, contentImageCount)) => {
    clearReviewStep();
    if (!tasks.length) return;
    setImageProgress({ done: 0, total: tasks.length });
    onRetryImageItems(tasks, (done, total) => setImageProgress({ done, total }));
  };
  const runPrimaryAction = () =>
    runPrimary(visibleStep, viewNextAction, {
      onGenerateTopics: () => {
        clearReviewStep();
        onGenerateTopics();
      },
      onGenerateDraft: () => {
        clearReviewStep();
        onGenerateDraft(writingStrategy, designStrategy);
      },
      onSuggestImages: () => {
        clearReviewStep();
        onSuggestImages(articleMarkdown, contentImageCount, imageStylePreset);
      },
      onGenerateImages: () => {
        clearReviewStep();
        setImageProgress({ done: 0, total: Math.max(1, 1 + promptLines(contentPromptsText).length) });
        onGenerateImages(coverPrompt || project?.cover_prompt, promptLines(contentPromptsText), (done, total) =>
          setImageProgress({ done, total }),
        );
      },
      onRetryFailedImages: () => runRetryFailedImages(),
      onFormat: () => {
        clearReviewStep();
        onFormat(articleMarkdown, designStrategy, writingStrategy);
      },
      onConfirmDesign: () => {
        clearReviewStep();
        onConfirmDesign();
      },
      onPreflight: () => {
        clearReviewStep();
        onPreflight();
      },
      onPublish: () => {
        clearReviewStep();
        onPublish();
      },
    });

  useEffect(() => {
    setMarkdownDraft("");
    setRevision("");
    setImageProgress(null);
    setPendingTopic(null);
    setReviewStep(null);
  }, [project?.id, project?.article_markdown]);

  useEffect(() => {
    if (reviewStep && (stepIndex[reviewStep] ?? 0) > actualStepIndex) setReviewStep(null);
  }, [actualStepIndex, reviewStep]);

  useEffect(() => {
    if (project?.id) setCreateMode(false);
    setWritingStrategy(project?.writing_strategy ?? "");
    setDesignStrategy(project?.design_strategy ?? "");
    setCoverPrompt(project?.cover_prompt ?? "");
    setContentPromptsText((project?.content_image_prompts ?? []).join("\n"));
    setImageStylePreset(project?.image_style_preset ?? imageStylePresets[0].prompt);
    const promptCount = project?.content_image_prompts?.length ?? 0;
    if (promptCount >= 1 && promptCount <= 3) setContentImageCount(promptCount);
  }, [project?.id, project?.writing_strategy, project?.design_strategy, project?.cover_prompt, project?.content_image_prompts, project?.image_style_preset]);

  return (
    <section className="create-project-layout">
      <aside className="content-panel project-list-panel">
        <div className="panel-heading">
          <h2>{language === "zh" ? "创作项目" : "Projects"}</h2>
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
              title={language === "zh" ? "还没有创作项目" : "No projects yet"}
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
            projectType={projectType}
            writingStrategy={writingStrategy}
            designStrategy={designStrategy}
            selectedFiles={selectedLibraryFiles}
            isRunning={isRunning}
            hasOpenProject={Boolean(project)}
            onNameChange={setProjectName}
            onTypeChange={setProjectType}
            onWritingStrategyChange={setWritingStrategy}
            onDesignStrategyChange={setDesignStrategy}
            onCancel={() => setCreateMode(false)}
            onCreate={() => {
              onCreateProject(projectName.trim(), projectType, selectedLibraryFiles, writingStrategy, designStrategy);
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
                  <strong>{stageLabel(actualVisibleStep, language)}</strong>
                </div>
              </div>
            }
            action={primary.label}
            disabled={primary.disabled}
            disabledReason={primary.reason}
            onAction={() =>
              runPrimary(visibleStep, viewNextAction, {
                onGenerateTopics: () => {
                  clearReviewStep();
                  onGenerateTopics();
                },
                onGenerateDraft: () => {
                  clearReviewStep();
                  onGenerateDraft(writingStrategy, designStrategy);
                },
                onSuggestImages: () => {
                  clearReviewStep();
                  onSuggestImages(articleMarkdown, contentImageCount, imageStylePreset);
                },
                onGenerateImages: () => {
                  clearReviewStep();
                  setImageProgress({ done: 0, total: Math.max(1, 1 + promptLines(contentPromptsText).length) });
                  onGenerateImages(coverPrompt || project.cover_prompt, promptLines(contentPromptsText), (done, total) => setImageProgress({ done, total }));
                },
                onRetryFailedImages: () => runRetryFailedImages(),
                onFormat: () => {
                  clearReviewStep();
                  onFormat(articleMarkdown, designStrategy, writingStrategy);
                },
                onConfirmDesign: () => {
                  clearReviewStep();
                  onConfirmDesign();
                },
                onPreflight: () => {
                  clearReviewStep();
                  onPreflight();
                },
                onPublish: () => {
                  clearReviewStep();
                  onPublish();
                },
              })
            }
          />
        )}

        {project ? (
          <div className="create-stepper-wrap">
            <Stepper
              steps={labels}
              activeIndex={stepIndex[visibleStep] ?? 0}
              progressIndex={actualStepIndex}
              maxSelectableIndex={actualStepIndex}
              activeLabel={guide.checkpoints?.[0]}
              onSelect={(index) => setReviewStep(steps[index]?.id ?? null)}
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
              step={step}
              visibleStep={visibleStep}
              actualVisibleStep={actualVisibleStep}
              nextAction={viewNextAction}
              backendNextAction={nextAction}
              isReviewingStep={visibleStep !== actualVisibleStep}
              strategyDirty={strategyDirty}
              selectedLibraryFiles={selectedLibraryFiles}
              isRunning={isRunning}
              writingStrategy={writingStrategy}
              designStrategy={designStrategy}
              articleMarkdown={articleMarkdown}
              revision={revision}
              coverPrompt={coverPrompt}
              contentPromptsText={contentPromptsText}
              contentImageCount={contentImageCount}
              imageStylePreset={imageStylePreset}
              imageProgress={imageProgress}
              images={images}
              imageErrors={project.images?.errors ?? []}
              pendingTopic={pendingTopic}
              primaryAction={primary}
              guideTitle={guide.title}
              onPendingTopicChange={setPendingTopic}
              onPrimaryAction={runPrimaryAction}
              onContinueFormat={() => onFormat(articleMarkdown, designStrategy, writingStrategy)}
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
              onCoverPromptChange={setCoverPrompt}
              onContentPromptsTextChange={setContentPromptsText}
              onContentImageCountChange={setContentImageCount}
              onImageStylePresetChange={setImageStylePreset}
              onWritingStrategyChange={setWritingStrategy}
              onDesignStrategyChange={setDesignStrategy}
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
  step,
  visibleStep,
  actualVisibleStep,
  nextAction,
  backendNextAction,
  isReviewingStep,
  strategyDirty,
  selectedLibraryFiles,
  isRunning,
  writingStrategy,
  designStrategy,
  articleMarkdown,
  revision,
  coverPrompt,
  contentPromptsText,
  contentImageCount,
  imageStylePreset,
  imageProgress,
  images,
  imageErrors,
  pendingTopic,
  primaryAction,
  guideTitle,
  onPendingTopicChange,
  onPrimaryAction,
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
  onWritingStrategyChange,
  onDesignStrategyChange,
}: {
  language: "zh" | "en";
  project: WriterProject;
  step: WriterStep;
  visibleStep: WriterStep;
  actualVisibleStep: WriterStep;
  nextAction: string;
  backendNextAction: string;
  isReviewingStep: boolean;
  strategyDirty: boolean;
  selectedLibraryFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  writingStrategy: string;
  designStrategy: string;
  articleMarkdown: string;
  revision: string;
  coverPrompt: string;
  contentPromptsText: string;
  contentImageCount: number;
  imageStylePreset: string;
  imageProgress: ImageProgress;
  images: Array<{ path?: string; prompt?: string }>;
  imageErrors: Array<{ kind?: string; index?: number; message?: string }>;
  pendingTopic: Record<string, unknown> | null;
  primaryAction: { label: string; disabled: boolean; reason?: string };
  guideTitle: string;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onPrimaryAction: () => void;
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
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
}) {
  const stageTitle = stageLabel(visibleStep, language);
  return (
    <div className="stage-workspace">
      <div className="stage-panel-heading">
        <div>
          <span>{language === "zh" ? "当前工作区" : "Current workspace"}</span>
          <h2>{stageTitle}</h2>
          {isReviewingStep ? (
            <small className="stage-review-note">
              {language === "zh"
                ? `正在回看：真实进度在「${stageLabel(actualVisibleStep, language)}」。如果在这里继续，将从此步骤重新生成后续流程。`
                : `Reviewing this step. The real progress is ${stageLabel(actualVisibleStep, language)}. Continuing here will regenerate the downstream flow.`}
            </small>
          ) : null}
        </div>
        <div className="stage-heading-tools">
          {visibleStep === "designed" ? (
            <DesignStrategySelect language={language} value={designStrategy} onChange={onDesignStrategyChange} />
          ) : null}
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
          {visibleStep === actualVisibleStep && visibleStep === "images" && backendNextAction === "retry_failed_images" ? (
            <button className="secondary-button" type="button" disabled={isRunning} onClick={onContinueFormat}>
              {language === "zh" ? "继续美编" : "Continue to HTML"}
            </button>
          ) : null}
          {primaryAction.disabled && primaryAction.reason ? (
            <p className="disabled-reason stage-primary-reason">{primaryAction.reason}</p>
          ) : null}
        </div>
      </div>

      <ProjectStrategyPanel
        language={language}
        writingStrategy={writingStrategy}
        designStrategy={designStrategy}
        onWritingStrategyChange={onWritingStrategyChange}
        onDesignStrategyChange={onDesignStrategyChange}
        onSave={onSaveStrategies}
        saveDisabled={isRunning}
        saveLabel={strategyDirty ? (language === "zh" ? "保存并应用到项目" : "Save to project") : (language === "zh" ? "当前策略已生效" : "Strategies are up to date")}
        hint={
          language === "zh"
            ? "写文策略会用于生成初稿，美编策略会用于生成 HTML。保存后会立刻成为当前项目的默认策略。"
            : "Writing strategy drives draft generation, and design strategy drives HTML formatting. Save to make them the project's active defaults."
        }
      />

      {visibleStep === "created" ? (
        <ProjectKnowledge
          language={language}
          files={project.library_files ?? []}
          selectedFiles={selectedLibraryFiles}
          isRunning={isRunning}
          onImport={onImportKnowledge}
        />
      ) : null}

      {visibleStep === "knowledge_confirmed" ? (
        <ReferenceReadyPanel language={language} project={project} />
      ) : null}

      {visibleStep === "topics" ? (
        <TopicCards
          language={language}
          topics={project.topics ?? []}
          selected={project.topic}
          pendingTopic={pendingTopic}
          disabled={isRunning}
          onPendingTopicChange={onPendingTopicChange}
          onSelectTopic={onSelectTopic}
        />
      ) : null}

      {visibleStep === "topic" ? <TopicSummaryPanel language={language} topic={project.topic} /> : null}

      {visibleStep === "draft" ? (
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

      {visibleStep === "draft" && nextAction === "suggest_images" ? (
        <ImageSuggestionOptions
          language={language}
          value={contentImageCount}
          imageStylePreset={imageStylePreset}
          onChange={onContentImageCountChange}
          onImageStylePresetChange={onImageStylePresetChange}
        />
      ) : null}

      {visibleStep === "images" ? (
        <ImageSection
          language={language}
          coverPrompt={coverPrompt}
          contentPromptsText={contentPromptsText}
          contentImageCount={contentImageCount}
          progress={imageProgress}
          imageState={project.images}
          images={images}
          errors={imageErrors}
          isRunning={isRunning}
          onCoverPromptChange={onCoverPromptChange}
          onContentPromptsTextChange={onContentPromptsTextChange}
          onRetryTasks={onRetryImageTasks}
        />
      ) : null}

      {visibleStep === "designed" ? (
        <div className="stage-stack">
          <DesignStagePanel
            language={language}
            project={project}
            nextAction={nextAction}
          />
        </div>
      ) : null}

      {visibleStep === "publish_check" || visibleStep === "published" ? (
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

function DesignStrategySelect({
  language,
  value,
  onChange,
}: {
  language: "zh" | "en";
  value: string;
  onChange: (value: string) => void;
}) {
  const selectedId = designStrategyPresets.find((preset) => preset.value === value)?.id ?? designStrategyPresets[0].id;
  return (
    <label className="design-strategy-select">
      <span>{language === "zh" ? "美编策略" : "Design strategy"}</span>
      <select
        value={selectedId}
        onChange={(event) => {
          const preset = designStrategyPresets.find((item) => item.id === event.target.value);
          if (preset) onChange(preset.value);
        }}
      >
        {designStrategyPresets.map((preset) => (
          <option key={preset.id} value={preset.id}>
            {language === "zh" ? preset.zh : preset.en}
          </option>
        ))}
      </select>
    </label>
  );
}

function DesignStagePanel({
  language,
  project,
  nextAction,
}: {
  language: "zh" | "en";
  project: WriterProject;
  nextAction: string;
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
      {project.html_path ? (
        <>
          <HtmlPreviewControls language={language} htmlPath={project.html_path} />
        </>
      ) : (
        <EmptyState title={language === "zh" ? "还没有生成 HTML" : "No HTML yet"} />
      )}
    </section>
  );
}

function ProjectSetup({
  language,
  name,
  projectType,
  writingStrategy,
  designStrategy,
  selectedFiles,
  isRunning,
  hasOpenProject,
  onNameChange,
  onTypeChange,
  onWritingStrategyChange,
  onDesignStrategyChange,
  onCancel,
  onCreate,
}: {
  language: "zh" | "en";
  name: string;
  projectType: string;
  writingStrategy: string;
  designStrategy: string;
  selectedFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  hasOpenProject: boolean;
  onNameChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
  onCancel: () => void;
  onCreate: () => void;
}) {
  const unsupported = projectType !== "article";
  return (
    <section className="content-panel project-setup-guide">
      <div className="setup-copy">
        <span>{language === "zh" ? "创建项目" : "Create project"}</span>
        <h2>{language === "zh" ? "先从公众号文章项目开始" : "Start with a WeChat article project"}</h2>
      </div>
      <div className="setup-form-grid">
        <label>
          <span>{language === "zh" ? "项目名称" : "Project name"}</span>
          <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder={language === "zh" ? "例如：AI 芯片公众号文章" : "Example: AI chip article"} />
        </label>
        <label>
          <span>{language === "zh" ? "项目类型" : "Project type"}</span>
          <select value={projectType} onChange={(event) => onTypeChange(event.target.value)}>
            {projectTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {language === "zh" ? item.zh : item.en}
              </option>
            ))}
          </select>
        </label>
      </div>
      {unsupported ? (
        <p className="disabled-reason">
          {language === "zh" ? "目前先实现公众号文章项目，其他类型会保留为后续扩展。" : "Only WeChat article projects are implemented first; other types are reserved."}
        </p>
      ) : null}
      <ProjectStrategyPanel
        language={language}
        writingStrategy={writingStrategy}
        designStrategy={designStrategy}
        onWritingStrategyChange={onWritingStrategyChange}
        onDesignStrategyChange={onDesignStrategyChange}
      />
      <div className="setup-actions">
        <button className="primary-cta" type="button" disabled={isRunning || !name.trim() || unsupported} onClick={onCreate}>
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
  writingStrategy,
  designStrategy,
  onWritingStrategyChange,
  onDesignStrategyChange,
  onSave,
  saveDisabled,
  saveLabel,
  hint,
}: {
  language: "zh" | "en";
  writingStrategy: string;
  designStrategy: string;
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
  onSave?: (writingStrategy: string, designStrategy: string) => void;
  saveDisabled?: boolean;
  saveLabel?: string;
  hint?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [draftWritingStrategy, setDraftWritingStrategy] = useState(writingStrategy);
  const [draftDesignStrategy, setDraftDesignStrategy] = useState(designStrategy);

  useEffect(() => {
    if (!isOpen) {
      setDraftWritingStrategy(writingStrategy);
      setDraftDesignStrategy(designStrategy);
    }
  }, [writingStrategy, designStrategy, isOpen]);

  const dirty = draftWritingStrategy !== writingStrategy || draftDesignStrategy !== designStrategy;
  const writingSummary = summarizeStrategy(writingStrategy, language, "writing");
  const designSummary = summarizeStrategy(designStrategy, language, "design");

  const closePanel = () => {
    setDraftWritingStrategy(writingStrategy);
    setDraftDesignStrategy(designStrategy);
    setIsOpen(false);
  };

  const applyStrategies = () => {
    onWritingStrategyChange(draftWritingStrategy);
    onDesignStrategyChange(draftDesignStrategy);
    onSave?.(draftWritingStrategy, draftDesignStrategy);
    setIsOpen(false);
  };

  return (
    <section className="project-section strategy-overview-panel">
      <div className="strategy-panel-toolbar">
        <div>
          <span>{language === "zh" ? "策略面板" : "Strategy panel"}</span>
          <strong>{language === "zh" ? "主页面先看摘要，需要时再进入编辑" : "Keep the page focused, edit only when needed"}</strong>
        </div>
        <button className="secondary-button" type="button" disabled={saveDisabled} onClick={() => setIsOpen(true)}>
          <Sparkles size={16} />
          {language === "zh" ? "打开策略面板" : "Open strategy panel"}
        </button>
      </div>
      <div className="strategy-summary-grid">
        <article className="strategy-summary-card">
          <span>{language === "zh" ? "写文策略" : "Writing strategy"}</span>
          <strong>{writingStrategy.trim() ? (language === "zh" ? "已自定义" : "Custom strategy") : (language === "zh" ? "系统默认" : "System default")}</strong>
          <p>{writingSummary}</p>
        </article>
        <article className="strategy-summary-card">
          <span>{language === "zh" ? "美编策略" : "Design strategy"}</span>
          <strong>{designStrategy.trim() ? (language === "zh" ? "已自定义" : "Custom strategy") : (language === "zh" ? "系统默认" : "System default")}</strong>
          <p>{designSummary}</p>
        </article>
      </div>
      {hint ? <p className="hint strategy-panel-hint">{hint}</p> : null}
      {isOpen ? (
        <div className="modal-backdrop" onClick={closePanel}>
          <div className="modal-panel strategy-modal-panel" onClick={(event) => event.stopPropagation()}>
            <div className="modal-title-row">
              <div>
                <span>{language === "zh" ? "策略编辑" : "Strategy editor"}</span>
                <h2>{language === "zh" ? "集中编辑写文与美编策略" : "Edit writing and design strategies"}</h2>
              </div>
              <button className="secondary-button" type="button" onClick={closePanel}>
                {language === "zh" ? "关闭" : "Close"}
              </button>
            </div>
            <div className="strategy-grid">
              <label>
                <span>{language === "zh" ? "写文策略" : "Writing strategy"}</span>
                <textarea
                  value={draftWritingStrategy}
                  onChange={(event) => setDraftWritingStrategy(event.target.value)}
                  placeholder={language === "zh" ? "留空则使用系统默认写文策略" : "Leave empty to use the default writing strategy"}
                />
              </label>
              <label>
                <span>{language === "zh" ? "美编策略" : "Design strategy"}</span>
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
            </div>
            {hint ? <p className="hint strategy-panel-hint">{hint}</p> : null}
            <div className="strategy-modal-actions">
              <button className="secondary-button" type="button" onClick={closePanel}>
                {language === "zh" ? "取消" : "Cancel"}
              </button>
              <button className="primary-cta" type="button" disabled={saveDisabled || !dirty} onClick={applyStrategies}>
                <Save size={16} />
                {onSave ? (language === "zh" ? "保存并应用到项目" : "Save to project") : (language === "zh" ? "应用到当前创建" : "Apply to setup")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );

  return (
    <section className="project-section strategy-grid">
      <label>
        <span>{language === "zh" ? "写文策略" : "Writing strategy"}</span>
        <textarea
          value={writingStrategy}
          onChange={(event) => onWritingStrategyChange(event.target.value)}
          placeholder={language === "zh" ? "留空则使用系统默认写文策略" : "Leave empty to use the default writing strategy"}
        />
      </label>
      <label>
        <span>{language === "zh" ? "美编策略" : "Design strategy"}</span>
        <div className="strategy-preset-row">
          {designStrategyPresets.map((preset) => (
            <button
              key={preset.id}
              className="secondary-button"
              type="button"
              onClick={() => onDesignStrategyChange(preset.value)}
            >
              {language === "zh" ? preset.zh : preset.en}
            </button>
          ))}
        </div>
        <textarea
          value={designStrategy}
          onChange={(event) => onDesignStrategyChange(event.target.value)}
          placeholder={language === "zh" ? "留空则使用系统默认美编策略" : "Leave empty to use the default design strategy"}
        />
      </label>
      {hint ? <p className="hint strategy-panel-hint">{hint}</p> : null}
      {onSave ? (
        <div className="library-editor-actions">
          <button className="secondary-button" type="button" disabled={saveDisabled} onClick={onSave}>
            <Save size={16} />
            {saveLabel ?? (language === "zh" ? "保存策略" : "Save strategies")}
          </button>
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
      {topics.length ? (
        <div className="topic-confirm-bar">
          <div>
            <strong>{pendingTitle || (language === "zh" ? "尚未选择候选题" : "No candidate selected")}</strong>
            <span>{language === "zh" ? "点击候选题只是预选，确认后才会进入初稿阶段。" : "Clicking a card only previews it. Confirm to continue."}</span>
          </div>
          <button className="primary-cta" type="button" disabled={disabled || !pendingTopic} onClick={() => pendingTopic && onSelectTopic(pendingTopic)}>
            {language === "zh" ? "确认选题" : "Confirm topic"}
          </button>
        </div>
      ) : null}
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
  onChange,
  onImageStylePresetChange,
}: {
  language: "zh" | "en";
  value: number;
  imageStylePreset: string;
  onChange: (value: number) => void;
  onImageStylePresetChange: (value: string) => void;
}) {
  return (
    <section className="project-section image-options-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图建议设置" : "Image suggestion settings"}</h2>
        <span>{language === "zh" ? "生成前确认" : "Before suggestions"}</span>
      </div>
      <div className="image-options-layout">
        <article className="image-options-copy">
          <strong>{language === "zh" ? "先确认这轮想生成几张正文图" : "Choose how many content images you want first"}</strong>
          <p>
            {language === "zh"
              ? "这会直接影响后续生成的配图建议数量。先把数量定下来，后面的提示词和生成节奏会更稳定。"
              : "This directly controls how many content image prompts will be suggested next."}
          </p>
        </article>
        <ImageCountSelect language={language} value={value} onChange={onChange} />
      </div>
      <label className="image-style-select">
        <div className="image-count-copy">
          <span>{language === "zh" ? "配图风格预设" : "Image style preset"}</span>
          <small>
            {language === "zh"
              ? "这里的风格会直接进入配图建议提示词，不是只改界面样子。"
              : "This style is injected into the real image suggestion prompts."}
          </small>
        </div>
        <div className="image-count-control">
          <select value={imageStylePreset} onChange={(event) => onImageStylePresetChange(event.target.value)}>
            {imageStylePresets.map((preset) => (
              <option key={preset.id} value={preset.prompt}>
                {language === "zh" ? preset.zh : preset.en}
              </option>
            ))}
          </select>
        </div>
      </label>
    </section>
  );
}

function ImageCountSelect({
  language,
  value,
  onChange,
}: {
  language: "zh" | "en";
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="image-count-select">
      <div className="image-count-copy">
        <span>{language === "zh" ? "正文图片数量" : "Content image count"}</span>
        <small>
          {language === "zh"
            ? "默认先少量生成，便于快速确认版式和节奏。"
            : "Start small so layout and pacing are easier to confirm."}
        </small>
      </div>
      <div className="image-count-control">
        <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
          {[1, 2, 3].map((count) => (
            <option key={count} value={count}>
              {language === "zh" ? `${count} 张` : `${count} image${count > 1 ? "s" : ""}`}
            </option>
          ))}
        </select>
      </div>
    </label>
  );

  return (
    <label className="image-count-select">
      <span>{language === "zh" ? "正文图片数量" : "Content image count"}</span>
      <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
        {[1, 2, 3].map((count) => (
          <option key={count} value={count}>
            {language === "zh" ? `${count} 张` : `${count} image${count > 1 ? "s" : ""}`}
          </option>
        ))}
      </select>
    </label>
  );
}

function LegacyImageSection({
  language,
  coverPrompt,
  contentPromptsText,
  contentImageCount,
  progress,
  images,
  errors,
  onCoverPromptChange,
  onContentPromptsTextChange,
  onContentImageCountChange,
}: {
  language: "zh" | "en";
  coverPrompt: string;
  contentPromptsText: string;
  contentImageCount: number;
  progress: ImageProgress;
  images: Array<{ path?: string; prompt?: string }>;
  errors?: Array<{ kind?: string; index?: number; message?: string }>;
  onCoverPromptChange: (value: string) => void;
  onContentPromptsTextChange: (value: string) => void;
  onContentImageCountChange: (value: number) => void;
}) {
  return (
    <section className="project-section image-stage-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图" : "Images"}</h2>
        <span>{images.length}</span>
      </div>
      <div className="image-stage-toolbar">
        <ImageCountSelect language={language} value={contentImageCount} onChange={onContentImageCountChange} />
        <p className="hint">
          {language === "zh"
            ? "先看建议数量，再分别整理封面图和正文图提示词。"
            : "Confirm the count first, then refine cover and content prompts."}
        </p>
      </div>
      <div className="prompt-grid">
        <label>
          <span>{language === "zh" ? "封面图提示词" : "Cover prompt"}</span>
          <textarea value={coverPrompt} onChange={(event) => onCoverPromptChange(event.target.value)} placeholder={language === "zh" ? "先生成配图建议，也可以手动编辑" : "Generate suggestions first, or edit manually"} />
        </label>
        <label>
          <span>{language === "zh" ? "正文配图提示词" : "Content prompts"}</span>
          <textarea value={contentPromptsText} onChange={(event) => onContentPromptsTextChange(event.target.value)} placeholder={language === "zh" ? "每行一条提示词" : "One prompt per line"} />
        </label>
      </div>
      {progress ? (
        <div className="image-progress">
          <span>{language === "zh" ? "生成进度" : "Generation progress"}</span>
          <strong>{progress.done} / {progress.total}</strong>
        </div>
      ) : null}
      {images.length ? (
        <div className="generated-image-grid">
          {images.map((item, index) => (
            <article key={`${item.path}-${index}`} className="generated-image-card">
            {item.path ? <img src={writerApi.writerFileUrl(item.path)} alt={item.prompt || `image-${index + 1}`} /> : <ImageIcon />}
              <span>{item.prompt}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title={language === "zh" ? "还没有图片" : "No images yet"} />
      )}
      {errors?.length ? (
        <div className="image-error-list">
          {errors.map((item, index) => (
            <article key={`${item.kind || "image"}-${item.index || index}`} className="preflight-row failed">
              <strong>{item.kind === "cover" ? (language === "zh" ? "封面图失败" : "Cover failed") : language === "zh" ? `正文配图 ${item.index || index + 1} 失败` : `Content image ${item.index || index + 1} failed`}</strong>
              <span>{item.message || (language === "zh" ? "图片 API 未返回可用图片" : "Image API returned no usable image.")}</span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ImageSection({
  language,
  coverPrompt,
  contentPromptsText,
  contentImageCount,
  progress,
  imageState,
  images,
  errors,
  isRunning,
  onCoverPromptChange,
  onContentPromptsTextChange,
  onRetryTasks,
}: {
  language: "zh" | "en";
  coverPrompt: string;
  contentPromptsText: string;
  contentImageCount: number;
  progress: ImageProgress;
  imageState?: WriterProject["images"];
  images: Array<{ path?: string; prompt?: string; index?: number }>;
  errors?: Array<{ kind?: string; index?: number; message?: string }>;
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
                <button className="secondary-button" type="button" disabled={isRunning || !task.prompt.trim()} onClick={() => onRetryTasks([taskToRetryInput(task)])}>
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

function PublishSection({ language, project }: { language: "zh" | "en"; project: WriterProject }) {
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

function stageLabel(step: WriterStep, language: "zh" | "en") {
  const labels: Record<WriterStep, { zh: string; en: string }> = {
    created: { zh: "知识导入", en: "Knowledge import" },
    knowledge_confirmed: { zh: "选题生成", en: "Topic generation" },
    topics: { zh: "选题确认", en: "Topic selection" },
    topic: { zh: "初稿生成", en: "Draft generation" },
    draft: { zh: "文章编辑", en: "Draft editing" },
    images: { zh: "配图建议与生成", en: "Image suggestions" },
    designed: { zh: "美编生成", en: "Design output" },
    publish_check: { zh: "发布确认", en: "Publish confirmation" },
    published: { zh: "发布结果", en: "Publish result" },
  };
  return language === "zh" ? labels[step].zh : labels[step].en;
}

function visibleWriterStep(step: WriterStep, nextAction: string): WriterStep {
  if (step === "published") return "published";
  if (step === "draft" && nextAction === "generate_images") return "images";
  return step;
}

function nextActionForVisibleStep(
  visibleStep: WriterStep,
  actualVisibleStep: WriterStep,
  backendNextAction: string,
  project: WriterProject | undefined,
  imagePromptDirty: boolean,
) {
  if (visibleStep === actualVisibleStep) return backendNextAction;
  if (visibleStep === "created") return "confirm_knowledge";
  if (visibleStep === "knowledge_confirmed") return "generate_topics";
  if (visibleStep === "topics") return "select_topic";
  if (visibleStep === "topic") return "generate_draft";
  if (visibleStep === "draft") return "suggest_images";
  if (visibleStep === "images") {
    if (imagePromptDirty || !project?.images?.items?.length) return "generate_images";
    return "format_article";
  }
  if (visibleStep === "designed") return project?.design_confirmed ? "run_preflight" : "confirm_design";
  if (visibleStep === "publish_check") return "run_preflight";
  if (visibleStep === "published") return "publish";
  return backendNextAction;
}

function primaryAction(language: "zh" | "en", project: WriterProject | undefined, step: WriterStep, nextAction: string, isRunning: boolean) {
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
      label: language === "zh" ? "先导入知识" : "Import knowledge first",
      disabled: true,
      reason: language === "zh" ? "请在下方导入右侧三库勾选文件。" : "Import checked library files below first.",
    };
  }
  if (step === "images" && nextAction === "retry_failed_images") {
    return {
      label: language === "zh" ? "重试失败图片" : "Retry failed images",
      disabled: false,
      reason: "",
    };
  }
  const labelMap: Partial<Record<WriterStep, string>> = {
    knowledge_confirmed: language === "zh" ? "生成选题" : "Generate topics",
    topics: language === "zh" ? "请选择一个选题" : "Pick a topic",
    topic: language === "zh" ? "生成初稿" : "Generate draft",
    draft: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "生成配图建议" : "Suggest images"),
    images: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "美编生成 HTML" : "Generate HTML"),
    designed: nextAction === "confirm_design" ? (language === "zh" ? "确认并进入预检" : "Confirm and continue") : (language === "zh" ? "执行预检" : "Run preflight"),
    publish_check: nextAction === "publish" ? (language === "zh" ? "发布" : "Publish") : (language === "zh" ? "重新预检" : "Run preflight again"),
    published: language === "zh" ? "已发布" : "Published",
  };
  return {
    label: labelMap[step] ?? (language === "zh" ? "继续" : "Continue"),
    disabled: step === "topics" || step === "published",
    reason: step === "topics" ? (language === "zh" ? "请先点击下方一个选题卡片确认。" : "Click one topic card below first.") : "",
  };
}

function runPrimary(
  step: WriterStep,
  nextAction: string,
  actions: {
    onGenerateTopics: () => void;
    onGenerateDraft: () => void;
    onSuggestImages: () => void;
    onGenerateImages: () => void;
    onRetryFailedImages: () => void;
    onFormat: () => void;
    onConfirmDesign: () => void;
    onPreflight: () => void;
    onPublish: () => void;
  },
) {
  if (step === "knowledge_confirmed") actions.onGenerateTopics();
  else if (step === "topic") actions.onGenerateDraft();
  else if (step === "draft" && nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "draft") actions.onSuggestImages();
  else if (step === "images" && nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "images" && nextAction === "retry_failed_images") actions.onRetryFailedImages();
  else if (step === "images") actions.onFormat();
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

function imageRetryTasks(project: WriterProject | undefined, coverPrompt: string, contentPromptsText: string, contentImageCount: number): WriterImageRetryTask[] {
  if (!project) return [];
  return imageTaskList("zh", coverPrompt, contentPromptsText, contentImageCount, project.images, project.images?.errors ?? [])
    .filter((task) => task.status === "failed" || task.status === "pending")
    .map(taskToRetryInput)
    .filter((task) => task.prompt.trim());
}

function taskToRetryInput(task: ImageTask): WriterImageRetryTask {
  return {
    kind: task.kind,
    index: task.index,
    prompt: task.prompt,
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

function text(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function projectTypeLabel(value: unknown, language: "zh" | "en") {
  const match = projectTypes.find((item) => item.id === value);
  return match ? (language === "zh" ? match.zh : match.en) : String(value || (language === "zh" ? "公众号文章" : "WeChat article"));
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
