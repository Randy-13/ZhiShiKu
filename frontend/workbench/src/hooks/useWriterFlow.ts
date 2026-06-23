import { useCallback, useEffect, useState } from "react";
import { writerApi } from "../apiWriter";
import type { WriterLibraryFileInput } from "../api";
import type { ActivityEvent, Language, WorkspaceId, WriterProject, WriterProjectState } from "../domain";

type AddActivity = (event: Omit<ActivityEvent, "id" | "time">) => void;

type Options = {
  language: Language;
  addActivity: AddActivity;
  selectWorkspace: (id: WorkspaceId) => void;
};

export type WriterImageRetryTask = {
  kind: "cover" | "content";
  prompt: string;
  index?: number;
};

export function useWriterFlow({ language, addActivity, selectWorkspace }: Options) {
  const [writerProjects, setWriterProjects] = useState<WriterProject[]>([]);
  const [writerState, setWriterState] = useState<WriterProjectState>();
  const [selectedWriterProjectId, setSelectedWriterProjectId] = useState<string>();
  const [isWriting, setIsWriting] = useState(false);

  const refreshWriterProjects = useCallback(
    async (selectedId?: string) => {
      const payload = await writerApi.writerProjects();
      const items = payload.items ?? [];
      setWriterProjects(items);
      const nextId = selectedId ?? selectedWriterProjectId;
      if (nextId && items.some((item) => item.id === nextId)) {
        const state = await writerApi.writerProject(nextId);
        setWriterState(state);
        setSelectedWriterProjectId(state.project.id);
      } else {
        setWriterState(undefined);
        setSelectedWriterProjectId(undefined);
      }
    },
    [selectedWriterProjectId],
  );

  useEffect(() => {
    refreshWriterProjects().catch((error) => {
      addActivity({
        title: language === "zh" ? "写文项目同步失败" : "Writer project sync failed",
        detail: error instanceof Error ? error.message : "Writer project API failed",
        workspace: "create",
        status: "error",
      });
    });
  }, [addActivity, language, refreshWriterProjects]);

  const runWriterAction = useCallback(
    async (title: string, action: () => Promise<WriterProjectState>) => {
      setIsWriting(true);
      try {
        const state = await action();
        setWriterState(state);
        setSelectedWriterProjectId(state.project.id);
        await refreshWriterProjects(state.project.id);
        addActivity({ title, detail: state.project.workspace, workspace: "create", status: "done" });
      } catch (error) {
        addActivity({
          title,
          detail: error instanceof Error ? error.message : "Writer project action failed",
          workspace: "create",
          status: "error",
        });
      } finally {
        setIsWriting(false);
      }
    },
    [addActivity, refreshWriterProjects],
  );

  const createWriterProject = useCallback(
    (name: string, projectType: string, libraryFiles: WriterLibraryFileInput[] = [], writingStrategy = "", designStrategy = "") => {
      selectWorkspace("create");
      runWriterAction(language === "zh" ? "创建创作项目" : "Create writing project", () =>
        writerApi.createWriterProject(
          name || (language === "zh" ? "未命名创作项目" : "Untitled writing project"),
          [],
          projectType,
          libraryFiles,
          writingStrategy,
          designStrategy,
        ),
      );
    },
    [language, runWriterAction, selectWorkspace],
  );

  const selectWriterProject = useCallback(
    (projectId: string) => {
      selectWorkspace("create");
      runWriterAction(language === "zh" ? "打开写文项目" : "Open writing project", () => writerApi.writerProject(projectId));
    },
    [language, runWriterAction, selectWorkspace],
  );

  const requireProjectId = useCallback(() => {
    const projectId = selectedWriterProjectId ?? writerState?.project.id;
    if (!projectId) throw new Error(language === "zh" ? "请先创建或选择写文项目" : "Create or select a writing project first");
    return projectId;
  }, [language, selectedWriterProjectId, writerState]);

  const importWriterKnowledge = useCallback(
    (libraryFiles: WriterLibraryFileInput[]) => {
      runWriterAction(language === "zh" ? "导入项目知识" : "Import project knowledge", () => writerApi.confirmWriterKnowledge(requireProjectId(), [], libraryFiles));
    },
    [language, requireProjectId, runWriterAction],
  );

  const generateWriterTopics = useCallback(() => {
    runWriterAction(language === "zh" ? "生成选题建议" : "Generate topic suggestions", () => writerApi.generateWriterProjectTopics(requireProjectId()));
  }, [language, requireProjectId, runWriterAction]);

  const selectWriterTopic = useCallback(
    (topic: Record<string, unknown>) => {
      runWriterAction(language === "zh" ? "选择选题" : "Select topic", () => writerApi.selectWriterProjectTopic(requireProjectId(), topic));
    },
    [language, requireProjectId, runWriterAction],
  );

  const saveWriterStrategies = useCallback(
    (writingStrategy?: string, designStrategy?: string) => {
      runWriterAction(language === "zh" ? "保存项目策略" : "Save project strategies", () =>
        writerApi.updateWriterProjectStrategies(requireProjectId(), writingStrategy, designStrategy),
      );
    },
    [language, requireProjectId, runWriterAction],
  );

  const generateWriterDraft = useCallback(
    (writingStrategy?: string, designStrategy?: string) => {
      runWriterAction(language === "zh" ? "生成初稿" : "Generate draft", async () => {
        const projectId = requireProjectId();
        if (writingStrategy !== undefined || designStrategy !== undefined) {
          await writerApi.updateWriterProjectStrategies(projectId, writingStrategy, designStrategy);
        }
        return writerApi.generateWriterProjectDraft(projectId);
      });
    },
    [language, requireProjectId, runWriterAction],
  );

  const reviseWriterProject = useCallback(
    (instruction: string, markdown?: string) => {
      runWriterAction(language === "zh" ? "修订文章" : "Revise article", () => writerApi.reviseWriterProject(requireProjectId(), instruction, markdown));
    },
    [language, requireProjectId, runWriterAction],
  );

  const suggestWriterImages = useCallback(
    (markdown?: string, contentImageCount = 1, imageStylePreset?: string) => {
      const project = writerState?.project;
      runWriterAction(language === "zh" ? "生成配图建议" : "Suggest images", () =>
        writerApi.suggestWriterProjectImages(
          requireProjectId(),
          markdown ?? project?.article_markdown,
          project?.topic ?? undefined,
          contentImageCount,
          imageStylePreset ?? project?.image_style_preset,
        ),
      );
    },
    [language, requireProjectId, runWriterAction, writerState],
  );

  const generateWriterImages = useCallback(
    (coverPrompt?: string, contentImagePrompts?: string[], onProgress?: (done: number, total: number) => void) => {
      const project = writerState?.project;
      runWriterAction(language === "zh" ? "生成图片" : "Generate images", async () => {
        const projectId = requireProjectId();
        const cover = (coverPrompt ?? project?.cover_prompt ?? "").trim();
        const prompts = contentImagePrompts ?? project?.content_image_prompts ?? [];
        const tasks: Array<{ kind: "cover" | "content"; prompt: string; index?: number }> = [];
        if (cover) tasks.push({ kind: "cover", prompt: cover });
        prompts.forEach((prompt, index) => {
          const trimmed = prompt.trim();
          if (trimmed) tasks.push({ kind: "content", prompt: trimmed, index: index + 1 });
        });
        if (!tasks.length) return writerApi.generateWriterProjectImages(projectId, cover, prompts);
        let latest: WriterProjectState | undefined;
        onProgress?.(0, tasks.length);
        for (const [index, task] of tasks.entries()) {
          latest = await writerApi.generateWriterProjectImageItem(projectId, task.kind, task.prompt, task.index);
          setWriterState(latest);
          onProgress?.(index + 1, tasks.length);
        }
        return latest ?? writerApi.writerProject(projectId);
      });
    },
    [language, requireProjectId, runWriterAction, writerState],
  );

  const retryWriterImageItems = useCallback(
    (tasks: WriterImageRetryTask[], onProgress?: (done: number, total: number) => void) => {
      runWriterAction(language === "zh" ? "重试失败图片" : "Retry failed images", async () => {
        const projectId = requireProjectId();
        const runnable = tasks
          .map((task) => ({ ...task, prompt: task.prompt.trim() }))
          .filter((task) => task.prompt && (task.kind === "cover" || (task.index ?? 0) > 0));
        if (!runnable.length) return writerApi.writerProject(projectId);
        let latest: WriterProjectState | undefined;
        onProgress?.(0, runnable.length);
        for (const [index, task] of runnable.entries()) {
          latest = await writerApi.generateWriterProjectImageItem(projectId, task.kind, task.prompt, task.index);
          setWriterState(latest);
          onProgress?.(index + 1, runnable.length);
        }
        return latest ?? writerApi.writerProject(projectId);
      });
    },
    [language, requireProjectId, runWriterAction],
  );

  const formatWriterProject = useCallback(
    (markdown?: string, designStrategy?: string, writingStrategy?: string) => {
      runWriterAction(language === "zh" ? "美编排版" : "Design article", async () => {
        const projectId = requireProjectId();
        if (writingStrategy !== undefined || designStrategy !== undefined) {
          await writerApi.updateWriterProjectStrategies(projectId, writingStrategy, designStrategy);
        }
        return writerApi.formatWriterProject(projectId, markdown, designStrategy);
      });
    },
    [language, requireProjectId, runWriterAction],
  );

  const confirmWriterDesign = useCallback(() => {
    runWriterAction(language === "zh" ? "确认美编预览" : "Confirm design preview", () => writerApi.confirmWriterProjectDesign(requireProjectId()));
  }, [language, requireProjectId, runWriterAction]);

  const preflightWriterProject = useCallback(() => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "发布检查" : "Run preflight", () =>
      writerApi.preflightWriterProject(requireProjectId(), project?.title || project?.name || "", project?.digest),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  const publishWriterProject = useCallback(() => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "发布到草稿箱" : "Publish to draft box", () =>
      writerApi.publishWriterProject(requireProjectId(), project?.title || project?.name || "", project?.digest),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  return {
    writerProjects,
    writerState,
    selectedWriterProjectId,
    isWriting,
    createWriterProject,
    selectWriterProject,
    importWriterKnowledge,
    generateWriterTopics,
    selectWriterTopic,
    saveWriterStrategies,
    generateWriterDraft,
    reviseWriterProject,
    suggestWriterImages,
    generateWriterImages,
    retryWriterImageItems,
    formatWriterProject,
    confirmWriterDesign,
    preflightWriterProject,
    publishWriterProject,
  };
}
