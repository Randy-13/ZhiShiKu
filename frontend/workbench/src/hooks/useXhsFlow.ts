import { useCallback, useEffect, useRef, useState } from "react";
import { xhsApi } from "../apiXhs";
import type { WriterLibraryFileInput } from "../api";
import type { ActivityEvent, Language, WorkspaceId, XhsAccountProfile, XhsCarouselStrategy, XhsLoginStatus, XhsProject, XhsProjectState, XhsRunningTask } from "../domain";

type AddActivity = (event: Omit<ActivityEvent, "id" | "time">) => void;

type Options = {
  language: Language;
  addActivity: AddActivity;
  selectWorkspace: (id: WorkspaceId) => void;
};

type XhsTaskMeta = {
  id: string;
  title: string;
  runningLabel: string;
};

type XhsRunningLabelKey =
  | "creating"
  | "opening"
  | "importing"
  | "generating"
  | "confirming"
  | "revising"
  | "checking"
  | "filling"
  | "publishing"
  | "saving"
  | "deleting"
  | "exporting"
  | "working";

export type XhsImageRetryTask = {
  kind: "cover" | "content";
  prompt: string;
  index?: number;
  aspectRatio?: string;
};

function xhsRunningLabel(language: Language, key: XhsRunningLabelKey) {
  const labels: Record<XhsRunningLabelKey, { zh: string; en: string }> = {
    creating: { zh: "\u521b\u5efa\u4e2d", en: "Creating" },
    opening: { zh: "\u6253\u5f00\u4e2d", en: "Opening" },
    importing: { zh: "\u5bfc\u5165\u4e2d", en: "Importing" },
    generating: { zh: "\u751f\u6210\u4e2d", en: "Generating" },
    confirming: { zh: "\u786e\u8ba4\u4e2d", en: "Confirming" },
    revising: { zh: "\u4fee\u8ba2\u4e2d", en: "Revising" },
    checking: { zh: "\u68c0\u67e5\u4e2d", en: "Checking" },
    filling: { zh: "\u586b\u5165\u4e2d", en: "Filling" },
    publishing: { zh: "\u53d1\u5e03\u4e2d", en: "Publishing" },
    saving: { zh: "\u4fdd\u5b58\u4e2d", en: "Saving" },
    deleting: { zh: "\u5220\u9664\u4e2d", en: "Deleting" },
    exporting: { zh: "\u5bfc\u51fa\u4e2d", en: "Exporting" },
    working: { zh: "\u5904\u7406\u4e2d", en: "Working" },
  };
  return language === "zh" ? labels[key].zh : labels[key].en;
}

function downloadXhsPackage(state: XhsProjectState) {
  const packagePath = state.project.export_package?.package_path;
  if (!packagePath) return false;
  const link = document.createElement("a");
  link.href = xhsApi.fileUrl(packagePath);
  link.download = state.project.export_package?.filename || "xhs_publish_package.zip";
  document.body.appendChild(link);
  link.click();
  link.remove();
  return true;
}

export function useXhsFlow({ language, addActivity, selectWorkspace }: Options) {
  const [xhsProjects, setXhsProjects] = useState<XhsProject[]>([]);
  const [xhsState, setXhsState] = useState<XhsProjectState>();
  const [selectedXhsProjectId, setSelectedXhsProjectId] = useState<string>();
  const [xhsAccountProfiles, setXhsAccountProfiles] = useState<XhsAccountProfile[]>([]);
  const [xhsCarouselStrategies, setXhsCarouselStrategies] = useState<XhsCarouselStrategy[]>([]);
  const [selectedXhsAccountProfileId, setSelectedXhsAccountProfileId] = useState("");
  const [xhsRunningTask, setXhsRunningTask] = useState<XhsRunningTask>();
  const [xhsLoginStatus, setXhsLoginStatus] = useState<XhsLoginStatus>();
  const selectedXhsProjectIdRef = useRef<string>();
  const isXhsRunning = Boolean(xhsRunningTask);

  const rememberSelectedXhsProjectId = useCallback((projectId: string | undefined) => {
    selectedXhsProjectIdRef.current = projectId;
    setSelectedXhsProjectId(projectId);
  }, []);

  const refreshXhsProjects = useCallback(
    async (selectedId?: string) => {
      const payload = await xhsApi.projects();
      const items = payload.items ?? [];
      setXhsProjects(items);
      const nextId = selectedId ?? selectedXhsProjectIdRef.current;
      if (nextId) {
        const state = await xhsApi.project(nextId);
        setXhsState(state);
        rememberSelectedXhsProjectId(state.project.id);
      }
    },
    [rememberSelectedXhsProjectId],
  );

  useEffect(() => {
    refreshXhsProjects().catch((error) => {
      addActivity({
        title: language === "zh" ? "小红书项目同步失败" : "XHS project sync failed",
        detail: error instanceof Error ? error.message : "XHS API failed",
        workspace: "xhs",
        status: "error",
      });
    });
  }, [addActivity, language, refreshXhsProjects]);

  const refreshXhsAccountProfiles = useCallback(
    async (selectedId?: string) => {
      const payload = await xhsApi.accountProfiles();
      const items = payload.items ?? [];
      setXhsAccountProfiles(items);
      const nextId = selectedId ?? selectedXhsAccountProfileId;
      if (nextId && items.some((item) => item.id === nextId)) {
        setSelectedXhsAccountProfileId(nextId);
      } else {
        setSelectedXhsAccountProfileId(items[0]?.id ?? "");
      }
      return items;
    },
    [selectedXhsAccountProfileId],
  );

  useEffect(() => {
    refreshXhsAccountProfiles().catch((error) => {
      addActivity({
        title: language === "zh" ? "小红书账号定位同步失败" : "XHS account profile sync failed",
        detail: error instanceof Error ? error.message : "XHS profile API failed",
        workspace: "xhs",
        status: "error",
      });
    });
  }, [addActivity, language, refreshXhsAccountProfiles]);

  const refreshXhsCarouselStrategies = useCallback(async () => {
    const payload = await xhsApi.carouselStrategies();
    setXhsCarouselStrategies(payload.items ?? []);
    return payload.items ?? [];
  }, []);

  useEffect(() => {
    refreshXhsCarouselStrategies().catch((error) => {
      addActivity({
        title: language === "zh" ? "小红书轮播策略同步失败" : "XHS carousel strategy sync failed",
        detail: error instanceof Error ? error.message : "XHS strategy API failed",
        workspace: "xhs",
        status: "error",
      });
    });
  }, [addActivity, language, refreshXhsCarouselStrategies]);

  const runXhsTask = useCallback(async <T,>(task: XhsTaskMeta, action: () => Promise<T>) => {
    setXhsRunningTask({ id: task.id, label: task.title, runningLabel: task.runningLabel, startedAt: Date.now() });
    try {
      return await action();
    } finally {
      setXhsRunningTask(undefined);
    }
  }, []);

  const runXhsAction = useCallback(
    async (task: XhsTaskMeta, action: () => Promise<XhsProjectState>) => {
      try {
        const state = await runXhsTask(task, action);
        setXhsState(state);
        rememberSelectedXhsProjectId(state.project.id);
        await refreshXhsProjects(state.project.id);
        addActivity({ title: task.title, detail: state.project.workspace, workspace: "xhs", status: "done" });
      } catch (error) {
        addActivity({
          title: task.title,
          detail: error instanceof Error ? error.message : "XHS action failed",
          workspace: "xhs",
          status: "error",
        });
      }
    },
    [addActivity, refreshXhsProjects, rememberSelectedXhsProjectId, runXhsTask],
  );

  const requireProjectId = useCallback(() => {
    const projectId = selectedXhsProjectId ?? xhsState?.project.id;
    if (!projectId) throw new Error(language === "zh" ? "请先创建或选择小红书项目" : "Create or select an XHS project first");
    return projectId;
  }, [language, selectedXhsProjectId, xhsState]);

  const createXhsProject = useCallback(
    (name: string, accountProfileId: string, libraryFiles: WriterLibraryFileInput[]) => {
      selectWorkspace("xhs");
      runXhsAction({ id: "create_project", title: language === "zh" ? "创建小红书项目" : "Create XHS project", runningLabel: xhsRunningLabel(language, "creating") }, () =>
        xhsApi.createProject(name || (language === "zh" ? "未命名小红书图文" : "Untitled XHS post"), accountProfileId, libraryFiles),
      );
    },
    [language, runXhsAction, selectWorkspace],
  );

  const saveXhsAccountProfile = useCallback(
    async (profile: Omit<XhsAccountProfile, "id" | "created_at" | "updated_at">, profileId?: string) => {
      setXhsRunningTask({ id: "xhs_settings", label: language === "zh" ? "XHS settings task" : "XHS settings task", runningLabel: xhsRunningLabel(language, "working"), startedAt: Date.now() });
      try {
        const payload = profileId ? await xhsApi.updateAccountProfile(profileId, profile) : await xhsApi.createAccountProfile(profile);
        const items = payload.items ?? [];
        setXhsAccountProfiles(items);
        const nextId = payload.profile?.id ?? profileId ?? items[0]?.id ?? "";
        setSelectedXhsAccountProfileId(nextId);
        addActivity({
          title: profileId ? (language === "zh" ? "更新小红书账号定位" : "Update XHS account profile") : language === "zh" ? "新建小红书账号定位" : "Create XHS account profile",
          detail: payload.profile?.name ?? profile.name,
          workspace: "xhs",
          status: "done",
        });
        return payload.profile;
      } catch (error) {
        addActivity({
          title: language === "zh" ? "保存小红书账号定位失败" : "Save XHS account profile failed",
          detail: error instanceof Error ? error.message : "XHS profile API failed",
          workspace: "xhs",
          status: "error",
        });
        throw error;
      } finally {
        setXhsRunningTask(undefined);
      }
    },
    [addActivity, language],
  );

  const deleteXhsAccountProfile = useCallback(
    async (profileId: string) => {
      setXhsRunningTask({ id: "xhs_settings", label: language === "zh" ? "XHS settings task" : "XHS settings task", runningLabel: xhsRunningLabel(language, "working"), startedAt: Date.now() });
      try {
        const payload = await xhsApi.deleteAccountProfile(profileId);
        const items = payload.items ?? [];
        setXhsAccountProfiles(items);
        setSelectedXhsAccountProfileId((current) => (current === profileId ? items[0]?.id ?? "" : current));
        addActivity({
          title: language === "zh" ? "删除小红书账号定位" : "Delete XHS account profile",
          detail: profileId,
          workspace: "xhs",
          status: "done",
        });
      } catch (error) {
        addActivity({
          title: language === "zh" ? "删除小红书账号定位失败" : "Delete XHS account profile failed",
          detail: error instanceof Error ? error.message : "XHS profile API failed",
          workspace: "xhs",
          status: "error",
        });
      } finally {
        setXhsRunningTask(undefined);
      }
    },
    [addActivity, language],
  );

  const saveXhsCarouselStrategy = useCallback(
    async (strategy: { id?: string; name: string; description?: string; config: Record<string, unknown> }) => {
      setXhsRunningTask({ id: "xhs_settings", label: language === "zh" ? "XHS settings task" : "XHS settings task", runningLabel: xhsRunningLabel(language, "working"), startedAt: Date.now() });
      try {
        const payload = await xhsApi.saveCarouselStrategy(strategy);
        setXhsCarouselStrategies(payload.items ?? []);
        addActivity({
          title: strategy.id ? (language === "zh" ? "更新小红书轮播策略" : "Update XHS carousel strategy") : language === "zh" ? "新建小红书轮播策略" : "Create XHS carousel strategy",
          detail: payload.item?.name ?? strategy.name,
          workspace: "xhs",
          status: "done",
        });
        return payload.item;
      } catch (error) {
        addActivity({
          title: language === "zh" ? "保存小红书轮播策略失败" : "Save XHS carousel strategy failed",
          detail: error instanceof Error ? error.message : "XHS strategy API failed",
          workspace: "xhs",
          status: "error",
        });
        throw error;
      } finally {
        setXhsRunningTask(undefined);
      }
    },
    [addActivity, language],
  );

  const deleteXhsCarouselStrategy = useCallback(
    async (strategyId: string) => {
      setXhsRunningTask({ id: "xhs_settings", label: language === "zh" ? "XHS settings task" : "XHS settings task", runningLabel: xhsRunningLabel(language, "working"), startedAt: Date.now() });
      try {
        const payload = await xhsApi.deleteCarouselStrategy(strategyId);
        setXhsCarouselStrategies(payload.items ?? []);
        addActivity({ title: language === "zh" ? "删除小红书轮播策略" : "Delete XHS carousel strategy", detail: strategyId, workspace: "xhs", status: "done" });
      } catch (error) {
        addActivity({
          title: language === "zh" ? "删除小红书轮播策略失败" : "Delete XHS carousel strategy failed",
          detail: error instanceof Error ? error.message : "XHS strategy API failed",
          workspace: "xhs",
          status: "error",
        });
      } finally {
        setXhsRunningTask(undefined);
      }
    },
    [addActivity, language],
  );

  const selectXhsProject = useCallback(
    (projectId: string) => {
      selectWorkspace("xhs");
      runXhsAction({ id: "open_project", title: language === "zh" ? "打开小红书项目" : "Open XHS project", runningLabel: xhsRunningLabel(language, "opening") }, () => xhsApi.project(projectId));
    },
    [language, runXhsAction, selectWorkspace],
  );

  const importXhsKnowledge = useCallback(
    (libraryFiles: WriterLibraryFileInput[]) => {
      runXhsAction({ id: "import_knowledge", title: language === "zh" ? "导入小红书素材" : "Import XHS sources", runningLabel: xhsRunningLabel(language, "importing") }, () => xhsApi.confirmKnowledge(requireProjectId(), libraryFiles));
    },
    [language, requireProjectId, runXhsAction],
  );

  const generateXhsTopics = useCallback(() => {
    runXhsAction({ id: "generate_topics", title: language === "zh" ? "生成小红书选题" : "Generate XHS topics", runningLabel: xhsRunningLabel(language, "generating") }, () => xhsApi.generateTopics(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const selectXhsTopic = useCallback(
    (topic: Record<string, unknown>) => {
      runXhsAction({ id: "select_topic", title: language === "zh" ? "选择小红书选题" : "Select XHS topic", runningLabel: xhsRunningLabel(language, "confirming") }, () => xhsApi.selectTopic(requireProjectId(), topic));
    },
    [language, requireProjectId, runXhsAction],
  );

  const configureXhsImageText = useCallback(
    (config: Record<string, unknown>) => {
      runXhsAction({ id: "configure_image_text", title: language === "zh" ? "确认小红书图文配置" : "Confirm XHS image-text config", runningLabel: xhsRunningLabel(language, "confirming") }, () => xhsApi.configureImageText(requireProjectId(), config));
    },
    [language, requireProjectId, runXhsAction],
  );

  const generateXhsDraft = useCallback(() => {
    runXhsAction({ id: "generate_draft", title: language === "zh" ? "生成小红书图文草稿" : "Generate XHS draft", runningLabel: xhsRunningLabel(language, "generating") }, () => xhsApi.generateDraft(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const confirmXhsDraft = useCallback(() => {
    runXhsAction({ id: "confirm_draft", title: language === "zh" ? "确认小红书图文草稿" : "Confirm XHS draft", runningLabel: xhsRunningLabel(language, "confirming") }, () => xhsApi.confirmDraft(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const reviseXhsDraft = useCallback(
    (instruction: string, content?: string) => {
      runXhsAction({ id: "revise_draft", title: language === "zh" ? "修订小红书草稿" : "Revise XHS draft", runningLabel: xhsRunningLabel(language, "revising") }, () => xhsApi.revise(requireProjectId(), instruction, content));
    },
    [language, requireProjectId, runXhsAction],
  );

  const suggestXhsImages = useCallback(
    (content?: string) => {
      runXhsAction({ id: "suggest_images", title: language === "zh" ? "生成小红书配图建议" : "Suggest XHS images", runningLabel: xhsRunningLabel(language, "generating") }, () => xhsApi.suggestImages(requireProjectId(), content));
    },
    [language, requireProjectId, runXhsAction],
  );

  const confirmXhsImageSuggestions = useCallback(() => {
    runXhsAction({ id: "confirm_image_suggestions", title: language === "zh" ? "确认小红书配图建议" : "Confirm XHS image suggestions", runningLabel: xhsRunningLabel(language, "confirming") }, () => xhsApi.confirmImageSuggestions(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const generateXhsImages = useCallback(
    (coverPrompt?: string, contentImagePrompts: string[] = [], onProgress?: (done: number, total: number) => void) => {
      runXhsAction({ id: "generate_images", title: language === "zh" ? "生成小红书轮播图" : "Generate XHS images", runningLabel: xhsRunningLabel(language, "generating") }, async () => {
        const projectId = requireProjectId();
        const cover = (coverPrompt ?? "").trim();
        const prompts = contentImagePrompts.map((prompt) => prompt.trim()).filter(Boolean);
        const tasks: XhsImageRetryTask[] = [];
        if (cover) tasks.push({ kind: "cover", prompt: cover, aspectRatio: "3:4" });
        prompts.forEach((prompt, index) => tasks.push({ kind: "content", prompt, index: index + 1, aspectRatio: "3:4" }));
        if (!tasks.length) return xhsApi.generateImages(projectId, cover, prompts);
        let latest: XhsProjectState | undefined;
        onProgress?.(0, tasks.length);
        for (const [index, task] of tasks.entries()) {
          latest = await xhsApi.generateImageItem(projectId, task.kind, task.prompt, task.index, task.aspectRatio || "3:4");
          setXhsState(latest);
          onProgress?.(index + 1, tasks.length);
        }
        return latest ?? xhsApi.project(projectId);
      });
    },
    [language, requireProjectId, runXhsAction],
  );

  const retryXhsImageItems = useCallback(
    (tasks: XhsImageRetryTask[], onProgress?: (done: number, total: number) => void) => {
      runXhsAction({ id: "retry_failed_images", title: language === "zh" ? "重试小红书失败图片" : "Retry failed XHS images", runningLabel: xhsRunningLabel(language, "generating") }, async () => {
        const projectId = requireProjectId();
        const runnable = tasks
          .map((task) => ({ ...task, prompt: task.prompt.trim() }))
          .filter((task) => task.prompt && (task.kind === "cover" || (task.index ?? 0) > 0));
        if (!runnable.length) return xhsApi.project(projectId);
        let latest: XhsProjectState | undefined;
        onProgress?.(0, runnable.length);
        for (const [index, task] of runnable.entries()) {
          latest = await xhsApi.generateImageItem(projectId, task.kind, task.prompt, task.index, task.aspectRatio || "3:4");
          setXhsState(latest);
          onProgress?.(index + 1, runnable.length);
        }
        return latest ?? xhsApi.project(projectId);
      });
    },
    [language, requireProjectId, runXhsAction],
  );

  const refreshXhsLoginStatus = useCallback(async () => {
    const status = await runXhsTask(
      {
        id: "refresh_login",
        title: language === "zh" ? "\u5c0f\u7ea2\u4e66\u767b\u5f55\u68c0\u67e5" : "Check XHS login",
        runningLabel: xhsRunningLabel(language, "checking"),
      },
      () => xhsApi.loginStatus(),
    );
    setXhsLoginStatus(status);
    return status;
  }, [language, runXhsTask]);

  const preflightXhsPublish = useCallback(() => {
    runXhsAction({ id: "run_preflight", title: language === "zh" ? "小红书发布预检" : "Run XHS preflight", runningLabel: xhsRunningLabel(language, "checking") }, () => xhsApi.preflight(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const fillXhsPublish = useCallback(() => {
    runXhsAction({ id: "fill_publish", title: language === "zh" ? "填入小红书发布页" : "Fill XHS publish form", runningLabel: xhsRunningLabel(language, "filling") }, () => xhsApi.fillPublish(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const confirmXhsPublish = useCallback(() => {
    runXhsAction({ id: "confirm_publish", title: language === "zh" ? "确认发布小红书" : "Confirm XHS publish", runningLabel: xhsRunningLabel(language, "publishing") }, () => xhsApi.confirmPublish(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const saveXhsPublishDraft = useCallback(() => {
    runXhsAction({ id: "save_publish_draft", title: language === "zh" ? "保存小红书草稿" : "Save XHS draft", runningLabel: xhsRunningLabel(language, "saving") }, () => xhsApi.saveDraft(requireProjectId()));
  }, [language, requireProjectId, runXhsAction]);

  const exportXhsPackage = useCallback(() => {
    const title = language === "zh" ? "瀵煎嚭灏忕孩涔﹀浘鏂囧帇缂╁寘" : "Export XHS package";
    runXhsAction({ id: "export_package", title, runningLabel: xhsRunningLabel(language, "exporting") }, async () => {
      const state = await xhsApi.exportPackage(requireProjectId());
      downloadXhsPackage(state);
      return state;
    });
  }, [language, requireProjectId, runXhsAction]);

  return {
    xhsProjects,
    xhsState,
    selectedXhsProjectId,
    xhsAccountProfiles,
    xhsCarouselStrategies,
    selectedXhsAccountProfileId,
    setSelectedXhsAccountProfileId,
    isXhsRunning,
    xhsRunningTask,
    xhsLoginStatus,
    saveXhsAccountProfile,
    deleteXhsAccountProfile,
    saveXhsCarouselStrategy,
    deleteXhsCarouselStrategy,
    createXhsProject,
    selectXhsProject,
    importXhsKnowledge,
    generateXhsTopics,
    selectXhsTopic,
    configureXhsImageText,
    generateXhsDraft,
    confirmXhsDraft,
    reviseXhsDraft,
    suggestXhsImages,
    confirmXhsImageSuggestions,
    generateXhsImages,
    retryXhsImageItems,
    refreshXhsLoginStatus,
    preflightXhsPublish,
    exportXhsPackage,
    fillXhsPublish,
    confirmXhsPublish,
    saveXhsPublishDraft,
  };
}
