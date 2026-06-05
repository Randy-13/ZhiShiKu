import { FolderPlus, ImageIcon } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { WriterProject, WriterProjectState, WriterStep } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";
import { StatusBadge } from "../components/StatusBadge";
import { Stepper } from "../components/Stepper";

const steps: Array<{ id: WriterStep; zh: string; en: string }> = [
  { id: "created", zh: "项目", en: "Project" },
  { id: "knowledge_confirmed", zh: "知识", en: "Knowledge" },
  { id: "topics", zh: "选题", en: "Topics" },
  { id: "topic", zh: "确认", en: "Topic" },
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
  selectedKnowledgeIds: number[];
  isRunning: boolean;
  onCreateProject: (name: string, projectType: string) => void;
  onSelectProject: (projectId: string) => void;
  onImportKnowledge: () => void;
  onGenerateTopics: () => void;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onGenerateDraft: () => void;
  onRevise: (instruction: string, markdown?: string) => void;
  onSuggestImages: () => void;
  onGenerateImages: () => void;
  onFormat: (markdown?: string) => void;
  onPreflight: () => void;
  onPublish: () => void;
};

export function CreateWorkspace({
  t,
  language,
  rightRail,
  writerProjects,
  writerState,
  selectedProjectId,
  selectedKnowledgeIds,
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
  const [revision, setRevision] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const project = writerState?.project;
  const step = writerState?.step ?? "created";
  const labels = steps.map((item) => (language === "zh" ? item.zh : item.en));
  const currentIndex = stepIndex[step] ?? 0;
  const nextAction = writerState?.next_action ?? "";
  const selectedBackendKnowledge = selectedKnowledgeIds.length;
  const projectKnowledge = project?.library_files ?? [];
  const topics = project?.topics ?? [];
  const articleMarkdown = markdownDraft || project?.article_markdown || "";

  const images = imageItems(project);
  const primary = primaryAction(step, Boolean(project), selectedBackendKnowledge, isRunning, language, project, nextAction);
  const guide = guideForState(language, project, step, nextAction, selectedBackendKnowledge);

  useEffect(() => {
    setMarkdownDraft("");
    setRevision("");
  }, [project?.id, project?.article_markdown]);

  useEffect(() => {
    if (project?.id) setCreateMode(false);
  }, [project?.id]);

  return (
    <section className="create-project-layout">
      <aside className="content-panel project-list-panel">
        <div className="panel-heading">
          <h2>{language === "zh" ? "写文项目" : "Writing projects"}</h2>
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
                onClick={() => {
                  onSelectProject(item.id);
                }}
              >
                <strong>{item.name || item.id}</strong>
                <span>{item.workspace}</span>
              </button>
            ))
          ) : (
            <EmptyState
              title={language === "zh" ? "还没有写文项目" : "No writing projects"}
              body={language === "zh" ? "先创建一个项目，系统会生成独立本地文件夹。" : "Create a project first. A local project folder will be created."}
            />
          )}
        </div>
      </aside>

      <div className="workspace-main">
        {createMode || !project ? (
          <ProjectSetupGuide
            language={language}
            name={projectName}
            projectType={projectType}
            isRunning={isRunning}
            hasOpenProject={Boolean(project)}
            onNameChange={setProjectName}
            onTypeChange={setProjectType}
            onCancel={() => setCreateMode(false)}
            onCreate={() => {
              onCreateProject(projectName.trim(), projectType);
              setProjectName("");
            }}
          />
        ) : (
          <PrimaryTaskPanel
            eyebrow={language === "zh" ? "项目内下一步" : "Next in project"}
            title={guide.title}
            body={guide.body}
            action={primary.label}
            disabled={primary.disabled}
            disabledReason={primary.reason}
            onAction={() =>
              runPrimary(step, {
                nextAction,
                onImportKnowledge,
                onGenerateTopics,
                onGenerateDraft,
                onDraftImageAction: onSuggestImages,
                onGenerateImages,
                onFormat: () => onFormat(articleMarkdown),
                onPreflight,
                onPublish,
              })
            }
          >
            <div className="project-meta-row">
              <StatusBadge tone="done">{project.type === "article" ? (language === "zh" ? "写作" : "Writing") : String(project.type ?? "")}</StatusBadge>
              <span>{project.workspace}</span>
            </div>
            <Stepper steps={labels} activeIndex={currentIndex} onSelect={() => undefined} />
          </PrimaryTaskPanel>
        )}

        <section className="content-panel project-work-panel">
          {!project ? (
            <EmptyState
              title={language === "zh" ? "先创建一个写文项目" : "Create a writing project first"}
              body={language === "zh" ? "创建后会自动进入项目工作流：导入知识、生成选题、确认选题、初稿、配图、美编、预检、发布。" : "After creation, you'll flow through references, topics, draft, images, design, preflight, and publish."}
            />
          ) : (
            <>
              <WorkflowGuideCard language={language} guide={guide} />
              <StageWorkspace
                language={language}
                step={step}
                project={project}
                projectKnowledge={projectKnowledge}
                selectedKnowledgeCount={selectedBackendKnowledge}
                topics={topics}
                selectedTopic={project.topic}
                isRunning={isRunning}
                articleMarkdown={articleMarkdown}
                revision={revision}
                images={images}
                onSelectTopic={onSelectTopic}
                onMarkdownChange={setMarkdownDraft}
                onRevisionChange={setRevision}
                onRevise={() => {
                  onRevise(revision, articleMarkdown);
                  setRevision("");
                }}
              />
            </>
          )}
        </section>
      </div>

      {rightRail}
    </section>
  );
}

function ProjectSetupGuide({
  language,
  name,
  projectType,
  isRunning,
  hasOpenProject,
  onNameChange,
  onTypeChange,
  onCancel,
  onCreate,
}: {
  language: "zh" | "en";
  name: string;
  projectType: string;
  isRunning: boolean;
  hasOpenProject: boolean;
  onNameChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onCancel: () => void;
  onCreate: () => void;
}) {
  return (
    <section className="content-panel project-setup-guide">
      <div className="setup-copy">
        <span>{language === "zh" ? "创建项目" : "Create project"}</span>
        <h2>{language === "zh" ? "先建立一个独立写文项目" : "Start with a writing project"}</h2>
        <p>
          {language === "zh"
            ? "项目会生成本地文件夹。之后所有参考材料、选题、初稿、图片、美编和发布结果都保存在这个项目里。"
            : "A local folder is created first. References, topics, drafts, images, design output, and publish results stay inside it."}
        </p>
      </div>
      <div className="setup-form-grid">
        <label>
          <span>{language === "zh" ? "项目名称" : "Project name"}</span>
          <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder={language === "zh" ? "例如：AI 芯片文章" : "Example: AI chip article"} />
        </label>
        <label>
          <span>{language === "zh" ? "项目类型" : "Project type"}</span>
          <select value={projectType} onChange={(event) => onTypeChange(event.target.value)}>
            <option value="article">{language === "zh" ? "写作" : "Writing"}</option>
          </select>
        </label>
      </div>
      <div className="setup-actions">
        <button className="primary-cta" type="button" disabled={isRunning || !name.trim()} onClick={onCreate}>
          <strong>{language === "zh" ? "创建并进入工作流" : "Create and start workflow"}</strong>
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

function WorkflowGuideCard({ language, guide }: { language: "zh" | "en"; guide: ReturnType<typeof guideForState> }) {
  return (
    <section className="project-section workflow-guide-card">
      <div>
        <span>{language === "zh" ? "当前引导" : "Current guidance"}</span>
        <h2>{guide.title}</h2>
        <p>{guide.body}</p>
      </div>
      <ol>
        {guide.checkpoints.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>
    </section>
  );
}

function ProjectKnowledge({ language, files, selectedCount }: { language: "zh" | "en"; files: WriterProject["library_files"]; selectedCount: number }) {
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "项目参考材料" : "Project references"}</h2>
        <span>
          {files?.length || selectedCount} {language === "zh" ? "项" : "items"}
        </span>
      </div>
      {files?.length ? (
        <div className="reference-list">
          {files.map((item) => (
            <article key={`${item.knowledge_id}-${item.markdown_path}`} className="reference-row">
              <strong>{item.title || item.markdown_path}</strong>
              <span>{item.markdown_path}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title={language === "zh" ? "尚未导入知识" : "No references yet"}
          body={language === "zh" ? "在右侧检索并勾选知识库文件，然后加入当前项目。" : "Search and select knowledge files on the right, then add them to this project."}
        />
      )}
    </section>
  );
}

function TopicCards({
  language,
  topics,
  selected,
  disabled,
  onSelectTopic,
}: {
  language: "zh" | "en";
  topics: Array<Record<string, unknown>>;
  selected?: Record<string, unknown> | null;
  disabled: boolean;
  onSelectTopic: (topic: Record<string, unknown>) => void;
}) {
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "临时选题建议" : "Temporary topic suggestions"}</h2>
        <span>{topics.length}</span>
      </div>
      {topics.length ? (
        <div className="topic-card-grid">
          {topics.map((topic, index) => {
            const title = text(topic.title, topic.topic, language === "zh" ? "未命名选题" : "Untitled topic");
            const active = selected && text(selected.title, selected.topic) === title;
            return (
              <button key={`${title}-${index}`} className={active ? "topic-card selected" : "topic-card"} type="button" disabled={disabled} onClick={() => onSelectTopic(topic)}>
                <strong>{title}</strong>
                <span>{text(topic.angle, topic.reason, topic.summary)}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="hint">{language === "zh" ? "先导入知识，再点击生成选题建议。" : "Import references first, then generate topic suggestions."}</p>
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
        <h2>{language === "zh" ? "初稿与修订" : "Draft and revision"}</h2>
        <span>{markdown ? `${markdown.length} chars` : language === "zh" ? "未生成" : "Not generated"}</span>
      </div>
      {title ? <h3 className="article-title">{title}</h3> : null}
      {digest ? <p className="hint">{digest}</p> : null}
      <textarea
        className="article-editor-large"
        value={markdown}
        onChange={(event) => onMarkdownChange(event.target.value)}
        placeholder={language === "zh" ? "初稿会显示在这里，也可以在修订前先手动调整。" : "The generated draft appears here. You can edit it before revision or design."}
      />
      <div className="revision-row">
        <input value={revision} onChange={(event) => onRevisionChange(event.target.value)} placeholder={language === "zh" ? "修订指令，例如：压缩开头" : "Revision instruction"} />
        <button className="secondary-button" type="button" disabled={disabled} onClick={onRevise}>
          {language === "zh" ? "修订" : "Revise"}
        </button>
      </div>
    </section>
  );
}

function ImageSection({ language, project, images }: { language: "zh" | "en"; project: WriterProject; images: Array<{ path?: string; prompt?: string }> }) {
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "配图" : "Images"}</h2>
        <span>{images.length}</span>
      </div>
      <div className="prompt-grid">
        <article>
          <strong>{language === "zh" ? "封面提示词" : "Cover prompt"}</strong>
          <p>{project.cover_prompt || (language === "zh" ? "尚未生成配图建议" : "No image suggestion yet")}</p>
        </article>
        <article>
          <strong>{language === "zh" ? "正文配图提示词" : "Content image prompts"}</strong>
          <p>{project.content_image_prompts?.join("\n") || (language === "zh" ? "暂无" : "None")}</p>
        </article>
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
      ) : null}
    </section>
  );
}

function PublishSection({ language, project }: { language: "zh" | "en"; project: WriterProject }) {
  const checks = project.preflight?.checks ?? [];
  return (
    <section className="project-section">
      <div className="section-heading">
        <h2>{language === "zh" ? "美编与发布" : "Design and publish"}</h2>
        <span>{project.preflight?.ok ? (language === "zh" ? "预检通过" : "Passed") : language === "zh" ? "待检查" : "Pending"}</span>
      </div>
      {project.html_path ? <p className="hint">{language === "zh" ? "美编文件：" : "Designed HTML: "}{project.html_path}</p> : null}
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
        <p className="hint">{language === "zh" ? "完成美编后执行发布检查，再发布到草稿箱。" : "Run preflight after design, then publish to the draft box."}</p>
      )}
    </section>
  );
}

function StageWorkspace({
  language,
  step,
  project,
  projectKnowledge,
  selectedKnowledgeCount,
  topics,
  selectedTopic,
  isRunning,
  articleMarkdown,
  revision,
  images,
  onSelectTopic,
  onMarkdownChange,
  onRevisionChange,
  onRevise,
}: {
  language: "zh" | "en";
  step: WriterStep;
  project: WriterProject;
  projectKnowledge: WriterProject["library_files"];
  selectedKnowledgeCount: number;
  topics: Array<Record<string, unknown>>;
  selectedTopic?: Record<string, unknown> | null;
  isRunning: boolean;
  articleMarkdown: string;
  revision: string;
  images: Array<{ path?: string; prompt?: string }>;
  onSelectTopic: (topic: Record<string, unknown>) => void;
  onMarkdownChange: (value: string) => void;
  onRevisionChange: (value: string) => void;
  onRevise: () => void;
}) {
  if (step === "created") {
    return (
      <div className="stage-stack">
        <ProjectKnowledge language={language} files={projectKnowledge} selectedCount={selectedKnowledgeCount} />
        <div className="stage-hint">
          <span>{language === "zh" ? "下一步" : "Next"}</span>
          <p>{language === "zh" ? "在右侧勾选知识文件后，点击主按钮加入当前项目。" : "Select reference files on the right, then use the main action to add them."}</p>
        </div>
      </div>
    );
  }

  if (step === "knowledge_confirmed") {
    return (
      <div className="stage-stack">
        <ProjectKnowledge language={language} files={projectKnowledge} selectedCount={selectedKnowledgeCount} />
        <div className="stage-hint">
          <span>{language === "zh" ? "下一步" : "Next"}</span>
          <p>{language === "zh" ? "参考材料已经进入项目。点击主按钮生成选题建议。" : "References are now in this project. Use the main action to generate topic suggestions."}</p>
        </div>
      </div>
    );
  }

  if (step === "topics" || step === "topic") {
    return (
      <div className="stage-stack">
        <TopicCards language={language} topics={topics} selected={selectedTopic} disabled={isRunning} onSelectTopic={onSelectTopic} />
        <div className="stage-hint">
          <span>{language === "zh" ? "下一步" : "Next"}</span>
          <p>{language === "zh" ? "选中一个选题后，主按钮会推进到初稿。" : "Choose one topic, then use the main action to move to the draft."}</p>
        </div>
      </div>
    );
  }

  if (step === "draft") {
    return (
      <div className="stage-stack">
        <ArticleEditor
          language={language}
          title={project.title}
          digest={project.digest}
          markdown={articleMarkdown}
          revision={revision}
          onMarkdownChange={onMarkdownChange}
          onRevisionChange={onRevisionChange}
          onRevise={onRevise}
          disabled={!articleMarkdown.trim() || !revision.trim() || isRunning}
        />
        <div className="stage-hint">
          <span>{language === "zh" ? "下一步" : "Next"}</span>
          <p>{language === "zh" ? "先生成或调整初稿，再继续配图建议。" : "Edit the draft first, then continue to image suggestions."}</p>
        </div>
      </div>
    );
  }

  if (step === "images") {
    return (
      <div className="stage-stack">
        <ImageSection language={language} project={project} images={images} />
        <div className="stage-hint">
          <span>{language === "zh" ? "下一步" : "Next"}</span>
          <p>{language === "zh" ? "确认图片生成后，进入美编排版。" : "After image generation, continue to design."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="stage-stack">
      <PublishSection language={language} project={project} />
      <div className="stage-hint">
        <span>{language === "zh" ? "下一步" : "Next"}</span>
        <p>{language === "zh" ? "完成美编和检查后，就可以发布。" : "Finish design and checks, then publish."}</p>
      </div>
    </div>
  );
}

function guideForState(language: "zh" | "en", project: WriterProject | undefined, step: WriterStep, nextAction: string, selectedKnowledgeCount: number) {
  if (!project) {
    return {
      title: language === "zh" ? "先创建项目" : "Create a project first",
      body:
        language === "zh"
          ? "填写项目名称与项目类型，创建后会进入项目引导。"
          : "Fill in a name and type. After creation, the guided workflow begins.",
      checkpoints: [language === "zh" ? "1. 填写项目名称" : "1. Name the project", language === "zh" ? "2. 选择写作类型" : "2. Choose writing type", language === "zh" ? "3. 创建并进入工作流" : "3. Create and enter workflow"],
    };
  }
  if (step === "created") {
    return {
      title: language === "zh" ? "加入知识库文件" : "Add reference files",
      body:
        language === "zh"
          ? "在右侧检索并勾选知识库文件，然后加入当前项目。"
          : "Search the knowledge library on the right, check files, and add them to this project.",
      checkpoints: [
        language === "zh" ? `已勾选 ${selectedKnowledgeCount} 个文件` : `${selectedKnowledgeCount} selected files`,
        language === "zh" ? "加入当前项目" : "Add to current project",
        language === "zh" ? "随后生成选题建议" : "Then generate topic suggestions",
      ],
    };
  }
  if (step === "knowledge_confirmed") {
    return {
      title: language === "zh" ? "生成选题建议" : "Generate topic suggestions",
      body:
        language === "zh"
          ? "系统会根据当前项目参考材料生成几个临时选题卡片。"
          : "The system generates temporary topic cards based on project references.",
      checkpoints: [
        language === "zh" ? "点击生成选题建议" : "Generate topic suggestions",
        language === "zh" ? "从卡片中确认一个选题" : "Pick one topic card",
        language === "zh" ? "进入初稿生成" : "Continue to draft",
      ],
    };
  }
  if (step === "topics") {
    return {
      title: language === "zh" ? "确认一个选题" : "Pick a topic",
      body:
        language === "zh"
          ? "从下方临时选题卡片中选择一个，系统将据此生成初稿。"
          : "Choose one temporary topic card below. The draft is generated from that choice.",
      checkpoints: [
        language === "zh" ? "查看选题建议" : "Review topic cards",
        language === "zh" ? "点击一个卡片确认选题" : "Confirm one topic",
        language === "zh" ? "生成初稿" : "Generate draft",
      ],
    };
  }
  if (step === "topic" || step === "draft") {
    return {
      title: language === "zh" ? "生成初稿与配图" : "Draft and image flow",
      body:
        language === "zh"
          ? "初稿完成后先生成配图建议，再生成图片并展示结果。"
          : "After the draft, generate image suggestions first, then generate and display the images.",
      checkpoints: [
        language === "zh" ? `当前动作：${nextAction || "待推进"}` : `Current action: ${nextAction || "pending"}`,
        language === "zh" ? "生成配图建议" : "Generate image suggestions",
        language === "zh" ? "生成图片并展示" : "Generate and show images",
      ],
    };
  }
  if (step === "images" || step === "designed") {
    return {
      title: language === "zh" ? "美编与发布检查" : "Design and preflight",
      body:
        language === "zh"
          ? "确认图片与排版后，先做发布检查，再进入发布。"
          : "After images and layout are ready, run preflight before publishing.",
      checkpoints: [language === "zh" ? "完成美编" : "Finish design", language === "zh" ? "执行发布检查" : "Run preflight", language === "zh" ? "发布到草稿箱" : "Publish to draft box"],
    };
  }
  return {
    title: language === "zh" ? "继续当前流程" : "Continue the workflow",
    body: language === "zh" ? "按照当前项目步骤继续推进。" : "Continue with the current project step.",
    checkpoints: [language === "zh" ? "检查当前步骤" : "Check current step", language === "zh" ? "按主按钮推进" : "Use the primary action", language === "zh" ? "保持项目内完成" : "Stay inside the project"],
  };
}

function primaryAction(step: WriterStep, hasProject: boolean, selectedKnowledgeCount: number, isRunning: boolean, language: "zh" | "en", project?: WriterProject, nextAction?: string) {
  if (isRunning) return { label: language === "zh" ? "处理中..." : "Working...", disabled: true, reason: "" };
  if (!hasProject) return { label: language === "zh" ? "先创建项目" : "Create project first", disabled: true, reason: language === "zh" ? "请先在中间创建项目。" : "Create a project in the center first." };
  if (step === "created") {
    return {
      label: language === "zh" ? "加入项目" : "Add to project",
      disabled: selectedKnowledgeCount === 0,
      reason: selectedKnowledgeCount === 0 ? (language === "zh" ? "请先在右侧勾选知识库文件。" : "Select knowledge files on the right first.") : "",
    };
  }
  return {
    label: {
      knowledge_confirmed: language === "zh" ? "生成选题建议" : "Generate topics",
      topics: language === "zh" ? "确认选题" : "Pick a topic",
      topic: language === "zh" ? "生成初稿" : "Generate draft",
      draft: nextAction === "generate_images" ? (language === "zh" ? "生成图片" : "Generate images") : (language === "zh" ? "生成配图建议" : "Suggest images"),
      images: language === "zh" ? "美编排版" : "Design article",
      designed: language === "zh" ? "发布检查" : "Run preflight",
      publish_check: nextAction === "publish" ? (language === "zh" ? "发布" : "Publish") : (language === "zh" ? "重新发布检查" : "Run preflight again"),
      published: language === "zh" ? "已发布" : "Published",
      created: "",
    }[step],
    disabled: step === "topics" || step === "published",
    reason: step === "topics" ? (language === "zh" ? "请先从选题卡片中选择一个建议。" : "Select one topic card below.") : "",
  };
}

function runPrimary(
  step: WriterStep,
  actions: {
    nextAction?: string;
    onImportKnowledge: () => void;
    onGenerateTopics: () => void;
    onGenerateDraft: () => void;
    onDraftImageAction: () => void;
    onGenerateImages: () => void;
    onFormat: () => void;
    onPreflight: () => void;
    onPublish: () => void;
  },
) {
  if (step === "created") actions.onImportKnowledge();
  else if (step === "knowledge_confirmed") actions.onGenerateTopics();
  else if (step === "topic") actions.onGenerateDraft();
  else if (step === "draft" && actions.nextAction === "generate_images") actions.onGenerateImages();
  else if (step === "draft") actions.onDraftImageAction();
  else if (step === "images") actions.onFormat();
  else if (step === "designed") actions.onPreflight();
  else if (step === "publish_check" && actions.nextAction === "publish") actions.onPublish();
  else if (step === "publish_check") actions.onPreflight();
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

function text(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}
