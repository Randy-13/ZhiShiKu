import { ExternalLink, Eye, FolderPlus, ImageIcon, Save, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LibraryKind, WriterLibraryFileInput } from "../api";
import type { KnowledgeItem, WriterProject, WriterProjectState, WriterStep } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";
import { StatusBadge } from "../components/StatusBadge";
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
  onGenerateDraft: () => void;
  onRevise: (instruction: string, markdown?: string) => void;
  onSuggestImages: (markdown?: string) => void;
  onGenerateImages: (coverPrompt?: string, contentPrompts?: string[]) => void;
  onFormat: (markdown?: string, designStrategy?: string) => void;
  onPreflight: () => void;
  onPublish: () => void;
};

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
  onGenerateDraft,
  onRevise,
  onSuggestImages,
  onGenerateImages,
  onFormat,
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
  const [pendingTopic, setPendingTopic] = useState<Record<string, unknown> | null>(null);

  const project = writerState?.project;
  const step = writerState?.step ?? "created";
  const nextAction = writerState?.next_action ?? "";
  const visibleStep = visibleWriterStep(step, nextAction, isRunning);
  const articleMarkdown = markdownDraft || project?.article_markdown || "";
  const labels = steps.map((item) => (language === "zh" ? item.zh : item.en));
  const selectedLibraryFiles = useMemo(() => toWriterLibraryFiles(selectedKnowledgeFiles), [selectedKnowledgeFiles]);
  const images = imageItems(project);
  const guide = guideForState(language, project, step, nextAction);
  const primary = primaryAction(language, project, step, nextAction, isRunning);

  useEffect(() => {
    setMarkdownDraft("");
    setRevision("");
    setPendingTopic(null);
  }, [project?.id, project?.article_markdown]);

  useEffect(() => {
    if (project?.id) setCreateMode(false);
    setWritingStrategy(project?.writing_strategy ?? "");
    setDesignStrategy(project?.design_strategy ?? "");
    setCoverPrompt(project?.cover_prompt ?? "");
    setContentPromptsText((project?.content_image_prompts ?? []).join("\n"));
  }, [project?.id, project?.writing_strategy, project?.design_strategy, project?.cover_prompt, project?.content_image_prompts]);

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
          <PrimaryTaskPanel
            eyebrow={language === "zh" ? "当前项目下一步" : "Next in project"}
            title={guide.title}
            body={guide.body}
            action={primary.label}
            disabled={primary.disabled}
            disabledReason={primary.reason}
            onAction={() =>
              runPrimary(step, nextAction, {
                onGenerateTopics,
                onGenerateDraft,
                onSuggestImages: () => onSuggestImages(articleMarkdown),
                onGenerateImages: () => onGenerateImages(coverPrompt || project.cover_prompt, promptLines(contentPromptsText)),
                onFormat: () => onFormat(articleMarkdown, designStrategy),
                onPreflight,
                onPublish,
              })
            }
          >
            <div className="project-meta-row">
              <StatusBadge tone="done">{projectTypeLabel(project.type, language)}</StatusBadge>
              <span>{project.workspace}</span>
            </div>
            <Stepper steps={labels} activeIndex={stepIndex[visibleStep] ?? 0} onSelect={() => undefined} />
          </PrimaryTaskPanel>
        )}

        <section className="content-panel project-work-panel">
          {!project ? (
            <EmptyState
              title={language === "zh" ? "先创建项目" : "Create a project first"}
              body={language === "zh" ? "右侧三库勾选的文件可以在创建时直接导入，也可以创建后再导入。" : "Files checked in the right rail can be imported now or after project creation."}
            />
          ) : (
            <ProjectStageWorkspace
              language={language}
              project={project}
              step={step}
              visibleStep={visibleStep}
              nextAction={nextAction}
              selectedLibraryFiles={selectedLibraryFiles}
              isRunning={isRunning}
              articleMarkdown={articleMarkdown}
              revision={revision}
              coverPrompt={coverPrompt}
              contentPromptsText={contentPromptsText}
              designStrategy={designStrategy}
              images={images}
              imageErrors={project.images?.errors ?? []}
              pendingTopic={pendingTopic}
              onPendingTopicChange={setPendingTopic}
              onImportKnowledge={() => onImportKnowledge(selectedLibraryFiles)}
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
  nextAction,
  selectedLibraryFiles,
  isRunning,
  articleMarkdown,
  revision,
  coverPrompt,
  contentPromptsText,
  designStrategy,
  images,
  imageErrors,
  pendingTopic,
  onPendingTopicChange,
  onImportKnowledge,
  onSelectTopic,
  onMarkdownChange,
  onRevisionChange,
  onRevise,
  onCoverPromptChange,
  onContentPromptsTextChange,
  onDesignStrategyChange,
}: {
  language: "zh" | "en";
  project: WriterProject;
  step: WriterStep;
  visibleStep: WriterStep;
  nextAction: string;
  selectedLibraryFiles: WriterLibraryFileInput[];
  isRunning: boolean;
  articleMarkdown: string;
  revision: string;
  coverPrompt: string;
  contentPromptsText: string;
  designStrategy: string;
  images: Array<{ path?: string; prompt?: string }>;
  imageErrors: Array<{ kind?: string; index?: number; message?: string }>;
  pendingTopic: Record<string, unknown> | null;
  onPendingTopicChange: (topic: Record<string, unknown> | null) => void;
  onImportKnowledge: () => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onMarkdownChange: (value: string) => void;
  onRevisionChange: (value: string) => void;
  onRevise: () => void;
  onCoverPromptChange: (value: string) => void;
  onContentPromptsTextChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
}) {
  const stageTitle = stageLabel(visibleStep, language);
  return (
    <div className="stage-workspace">
      <div className="stage-panel-heading">
        <div>
          <span>{language === "zh" ? "当前工作区" : "Current workspace"}</span>
          <h2>{stageTitle}</h2>
        </div>
        <div className="stage-heading-tools">
          {visibleStep === "designed" ? (
            <DesignStrategySelect language={language} value={designStrategy} onChange={onDesignStrategyChange} />
          ) : null}
          <StatusBadge tone="muted">{nextAction || visibleStep}</StatusBadge>
        </div>
      </div>

      {step === "created" ? (
        <ProjectKnowledge
          language={language}
          files={project.library_files ?? []}
          selectedFiles={selectedLibraryFiles}
          isRunning={isRunning}
          onImport={onImportKnowledge}
        />
      ) : null}

      {step === "knowledge_confirmed" ? (
        <ReferenceReadyPanel language={language} project={project} />
      ) : null}

      {step === "topics" ? (
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

      {step === "topic" ? <TopicSummaryPanel language={language} topic={project.topic} /> : null}

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

      {visibleStep === "images" ? (
        <ImageSection
          language={language}
          coverPrompt={coverPrompt}
          contentPromptsText={contentPromptsText}
          images={images}
          errors={imageErrors}
          onCoverPromptChange={onCoverPromptChange}
          onContentPromptsTextChange={onContentPromptsTextChange}
        />
      ) : null}

      {visibleStep === "designed" ? (
        <div className="stage-stack">
          <DesignStagePanel
            language={language}
            project={project}
          />
        </div>
      ) : null}

      {step === "designed" || step === "publish_check" || step === "published" ? (
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
      <p className="hint">
        {language === "zh" ? "知识来源已就绪，下一步生成多个选题方向。" : "References are ready. Generate topic options next."}
      </p>
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
        <p className="hint">{language === "zh" ? "还没有确认选题，请回到选题阶段选择一个方向。" : "No topic is confirmed yet."}</p>
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

function DesignStagePanel({ language, project }: { language: "zh" | "en"; project: WriterProject }) {
  return (
    <section className="project-section design-stage-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "美编输出" : "Design output"}</h2>
        <span>{project.html_path ? (language === "zh" ? "已生成" : "Generated") : language === "zh" ? "待生成" : "Pending"}</span>
      </div>
      {project.html_path ? (
        <HtmlPreviewControls language={language} htmlPath={project.html_path} />
      ) : (
        <p className="hint">
          {language === "zh" ? "点击主按钮后会按右上角策略生成 HTML，完成后可在这里预览。" : "Use the main action to generate HTML with the selected strategy. Preview appears here after it is ready."}
        </p>
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
        <p>
          {language === "zh"
            ? "项目会保存写文策略、美编策略、导入知识、选题、初稿、配图、美编 HTML、预检和发布结果。"
            : "The project stores strategy, references, topics, draft, images, HTML, preflight, and publish output."}
        </p>
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
      <p className="hint">
        {language === "zh"
          ? `右侧三库已勾选 ${selectedFiles.length} 个文件，创建后会直接导入项目。`
          : `${selectedFiles.length} checked file(s) from the right rail will be imported after creation.`}
      </p>
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
}: {
  language: "zh" | "en";
  writingStrategy: string;
  designStrategy: string;
  onWritingStrategyChange: (value: string) => void;
  onDesignStrategyChange: (value: string) => void;
}) {
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
        <p className="hint">
          {language === "zh"
            ? `右侧三库已勾选 ${selectedFiles.length} 个文件。导入后会作为本项目生成选题和初稿的依据。`
            : `${selectedFiles.length} checked file(s) in the right rail will become project references.`}
        </p>
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
          body={language === "zh" ? "先在右侧原文库、重点库或视角库勾选文件，再导入项目。" : "Check files in Originals, Focus, or Perspectives, then import them."}
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
        <p className="hint">{language === "zh" ? "导入知识后，点击主按钮生成多个选题。" : "Import knowledge, then use the main action to generate topics."}</p>
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

function ImageSection({
  language,
  coverPrompt,
  contentPromptsText,
  images,
  errors,
  onCoverPromptChange,
  onContentPromptsTextChange,
}: {
  language: "zh" | "en";
  coverPrompt: string;
  contentPromptsText: string;
  images: Array<{ path?: string; prompt?: string }>;
  errors?: Array<{ kind?: string; index?: number; message?: string }>;
  onCoverPromptChange: (value: string) => void;
  onContentPromptsTextChange: (value: string) => void;
}) {
  return (
    <section className="project-section image-stage-panel">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图" : "Images"}</h2>
        <span>{images.length}</span>
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
      {images.length ? (
        <div className="generated-image-grid">
          {images.map((item, index) => (
            <article key={`${item.path}-${index}`} className="generated-image-card">
              {item.path ? <img src={`/api/writer/file?path=${encodeURIComponent(item.path)}`} alt={item.prompt || `image-${index + 1}`} /> : <ImageIcon />}
              <span>{item.prompt}</span>
            </article>
          ))}
        </div>
      ) : (
        <p className="hint">{language === "zh" ? "先生成配图建议，再根据提示词调用配图 API 生成图片。" : "Generate image suggestions first, then call the image API."}</p>
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
        <p className="hint">{language === "zh" ? "美编生成 HTML 后，执行预检；预检通过后发布到公众号草稿箱。" : "Generate HTML, run preflight, then publish to the draft box."}</p>
      )}
    </section>
  );
}

function HtmlPreviewControls({ language, htmlPath }: { language: "zh" | "en"; htmlPath: string }) {
  const [showPreview, setShowPreview] = useState(false);
  const url = `/api/writer/file?path=${encodeURIComponent(htmlPath)}`;
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

function visibleWriterStep(step: WriterStep, nextAction: string, isRunning: boolean): WriterStep {
  if (step === "published") return "published";
  if (nextAction === "generate_topics") return "topics";
  if (nextAction === "select_topic") return "topic";
  if (nextAction === "generate_draft") return "draft";
  if (nextAction === "suggest_images" || nextAction === "generate_images") return "images";
  if (nextAction === "format_article") return "designed";
  if (nextAction === "run_preflight") return "publish_check";
  if (nextAction === "publish") return isRunning ? "published" : "publish_check";
  return step;
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
  const labelMap: Partial<Record<WriterStep, string>> = {
    knowledge_confirmed: language === "zh" ? "生成选题" : "Generate topics",
    topics: language === "zh" ? "请选择一个选题" : "Pick a topic",
    topic: language === "zh" ? "生成初稿" : "Generate draft",
    draft: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "生成配图建议" : "Suggest images"),
    images: language === "zh" ? "美编生成 HTML" : "Generate HTML",
    designed: language === "zh" ? "执行预检" : "Run preflight",
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
    onFormat: () => void;
    onPreflight: () => void;
    onPublish: () => void;
  },
) {
  if (step === "knowledge_confirmed") actions.onGenerateTopics();
  else if (step === "topic") actions.onGenerateDraft();
  else if (step === "draft" && nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "draft") actions.onSuggestImages();
  else if (step === "images") actions.onFormat();
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

function imageItems(project?: WriterProject) {
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
