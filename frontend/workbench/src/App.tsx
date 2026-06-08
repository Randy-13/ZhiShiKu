import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Boxes, Cog, Feather, Inbox, Pickaxe } from "lucide-react";
import { api, materialFromUpload, rawMaterialGroupKey } from "./api";
import type { LibraryKind, ReadableDraftInput, WriterLibraryFileInput } from "./api";
import type {
  ActivityEvent,
  CreationDraft,
  KnowledgeDraft,
  KnowledgeItem,
  Language,
  LegacyStageId,
  MaterialType,
  PerspectiveDraft,
  PerspectiveProfile,
  SourceMaterial,
  TextExtractionMode,
  WriterProject,
  WriterProjectState,
  WorkspaceId,
  WorkspaceNavItem,
} from "./domain";
import { createTranslator, workspaceLabel } from "./i18n";
import { AppShell } from "./shell/AppShell";
import { CollectWorkspace } from "./workspaces/CollectWorkspace";
import type { CollectInputBusy } from "./workspaces/CollectWorkspace";
import { LearnWorkspace } from "./workspaces/LearnWorkspace";
import { MineWorkspace } from "./workspaces/MineWorkspace";
import { CreateWorkspace } from "./workspaces/CreateWorkspace";
import { LibraryWorkspace } from "./workspaces/LibraryWorkspace";
import { SettingsWorkspace } from "./workspaces/SettingsWorkspace";
import { KnowledgeLibraryRail } from "./components/KnowledgeLibraryRail";
import type { LibraryBucket } from "./components/KnowledgeLibraryRail";

const legacyMap: Record<LegacyStageId, WorkspaceId> = {
  overview: "collect",
  inbox: "collect",
  packs: "library",
  processing: "learn",
  perspectives: "mine",
  review: "create",
};

const workspaceOrder: WorkspaceId[] = ["collect", "learn", "mine", "create", "library", "settings"];
const libraryKinds: LibraryKind[] = ["original", "focus", "perspective"];

function uid(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.round(Math.random() * 10000)}`;
}

function initialDraft(): CreationDraft {
  return {
    id: "draft-local",
    title: "未命名作品",
    channel: "article",
    step: 0,
    body: "从知识库选择一条知识后，创作步骤会在这里逐步生成。",
    status: "draft",
  };
}

export default function App() {
  const [language, setLanguage] = useState<Language>("zh");
  const [textExtractionMode, setTextExtractionMode] = useState<TextExtractionMode>("local_ocr");
  const t = useMemo(() => createTranslator(language), [language]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("collect");
  const [materials, setMaterials] = useState<SourceMaterial[]>([]);
  const [selectedMaterialId, setSelectedMaterialId] = useState<string>();
  const [learningQueue, setLearningQueue] = useState<SourceMaterial[]>([]);
  const [selectedLearningMaterialId, setSelectedLearningMaterialId] = useState<string>();
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [selectedKnowledgeId, setSelectedKnowledgeId] = useState<string>();
  const [collectDraft, setCollectDraft] = useState<ReadableDraftInput>();
  const [knowledgeDraft, setKnowledgeDraft] = useState<KnowledgeDraft>();
  const [perspectives, setPerspectives] = useState<PerspectiveProfile[]>([]);
  const [selectedPerspectiveId, setSelectedPerspectiveId] = useState<string>();
  const [perspectiveDraft, setPerspectiveDraft] = useState<PerspectiveDraft>();
  const [draft, setDraft] = useState<CreationDraft>(() => initialDraft());
  const [writerProjects, setWriterProjects] = useState<WriterProject[]>([]);
  const [writerState, setWriterState] = useState<WriterProjectState>();
  const [selectedWriterProjectId, setSelectedWriterProjectId] = useState<string>();
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [search, setSearch] = useState("");
  const [libraryRailBucket, setLibraryRailBucket] = useState<LibraryBucket>("original");
  const [libraryRailQuery, setLibraryRailQuery] = useState("");
  const [libraryRailCheckedIds, setLibraryRailCheckedIds] = useState<string[]>([]);
  const [isDeletingKnowledge, setIsDeletingKnowledge] = useState(false);
  const [collectInputBusy, setCollectInputBusy] = useState<CollectInputBusy>(null);
  const [isCollectingReadable, setIsCollectingReadable] = useState(false);
  const [isSavingRawDraft, setIsSavingRawDraft] = useState(false);
  const [isLearning, setIsLearning] = useState(false);
  const [isMining, setIsMining] = useState(false);
  const [isSavingPerspective, setIsSavingPerspective] = useState(false);
  const [isWriting, setIsWriting] = useState(false);

  const addActivity = useCallback((event: Omit<ActivityEvent, "id" | "time">) => {
    setActivities((current) => [
      {
        ...event,
        id: uid("activity"),
        time: new Date().toLocaleTimeString(),
      },
      ...current.slice(0, 49),
    ]);
  }, []);

  const refreshLibraries = useCallback(async (options?: { selectFirst?: boolean; clearChecked?: boolean }) => {
    if (options?.clearChecked !== false) setLibraryRailCheckedIds([]);
    try {
      const groups = await Promise.all(libraryKinds.map((kind) => api.listLibraryFiles(kind)));
      const items = groups.flat();
      setKnowledge(items);
      if (options?.selectFirst && items[0]) setSelectedKnowledgeId(items[0].id);
      return items;
    } catch (error) {
      addActivity({
        title: "知识库同步失败",
        detail: error instanceof Error ? error.message : "无法连接 v2 三库，尝试旧知识库接口。",
        workspace: "library",
        status: "error",
      });
      const items = await api.listKnowledge();
      setKnowledge(items);
      if (options?.selectFirst && items[0]) setSelectedKnowledgeId(items[0].id);
      return items;
    }
  }, [addActivity]);

  useEffect(() => {
    const applyRoute = () => {
      const raw = window.location.hash.replace("#/", "").replace("#", "") as WorkspaceId | LegacyStageId;
      const path = window.location.pathname.replace(/^\/+/, "").split("/")[0] as WorkspaceId | LegacyStageId;
      const route = raw || path;
      if (!route) return;
      const next = workspaceOrder.includes(route as WorkspaceId) ? (route as WorkspaceId) : legacyMap[route as LegacyStageId];
      if (next) setActiveWorkspace(next);
    };
    applyRoute();
    window.addEventListener("hashchange", applyRoute);
    window.addEventListener("popstate", applyRoute);
    return () => {
      window.removeEventListener("hashchange", applyRoute);
      window.removeEventListener("popstate", applyRoute);
    };
  }, []);

  useEffect(() => {
    refreshLibraries({ selectFirst: true }).catch((error) => {
      addActivity({
        title: "知识库同步失败",
        detail: error instanceof Error ? error.message : "无法连接旧后端",
        workspace: "library",
        status: "error",
      });
    });
  }, [addActivity, refreshLibraries]);

  useEffect(() => {
    api
      .workbenchSettings()
      .then((settings) => {
        if (settings.text_extraction_mode === "local_ocr" || settings.text_extraction_mode === "ai_vision") {
          setTextExtractionMode(settings.text_extraction_mode);
        }
      })
      .catch((error) => {
        addActivity({
          title: language === "zh" ? "工作台设置加载失败" : "Workbench settings load failed",
          detail: error instanceof Error ? error.message : "Unable to load workbench settings",
          workspace: "settings",
          status: "error",
        });
      });
  }, [addActivity, language]);

  const refreshWriterProjects = useCallback(async (selectedId?: string) => {
    const payload = await api.writerProjects();
    const items = payload.items ?? [];
    setWriterProjects(items);
    const nextId = selectedId ?? selectedWriterProjectId;
    if (nextId && items.some((item) => item.id === nextId)) {
      const state = await api.writerProject(nextId);
      setWriterState(state);
      setSelectedWriterProjectId(state.project.id);
    } else {
      setWriterState(undefined);
      setSelectedWriterProjectId(undefined);
    }
  }, [selectedWriterProjectId]);

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

  const refreshPerspectiveProfiles = useCallback(async (nextSelectedId?: string) => {
    const items = await api.listPerspectiveProfiles();
    setPerspectives(items);
    setSelectedPerspectiveId((current) => {
      if (nextSelectedId && items.some((item) => item.id === nextSelectedId)) return nextSelectedId;
      if (current && items.some((item) => item.id === current)) return current;
      return items[0]?.id;
    });
    return items;
  }, []);

  useEffect(() => {
    refreshPerspectiveProfiles().catch((error) => {
      addActivity({
        title: language === "zh" ? "视角列表加载失败" : "Perspective list load failed",
        detail: error instanceof Error ? error.message : "Perspective API failed",
        workspace: "mine",
        status: "error",
      });
    });
  }, [addActivity, language, refreshPerspectiveProfiles]);

  const navItems = useMemo<WorkspaceNavItem[]>(
    () => [
      { id: "collect", label: t("workspace.collect"), description: t("workspace.collect.desc"), icon: Inbox },
      { id: "learn", label: t("workspace.learn"), description: t("workspace.learn.desc"), icon: BookOpen },
      { id: "mine", label: t("workspace.mine"), description: t("workspace.mine.desc"), icon: Pickaxe },
      { id: "create", label: t("workspace.create"), description: t("workspace.create.desc"), icon: Feather },
      { id: "library", label: t("workspace.library"), description: t("workspace.library.desc"), icon: Boxes },
      { id: "settings", label: t("workspace.settings"), description: t("workspace.settings.desc"), icon: Cog },
    ],
    [t],
  );

  const selectedMaterial = useMemo(
    () => materials.find((item) => item.id === selectedMaterialId),
    [materials, selectedMaterialId],
  );
  const selectedLearningMaterial = useMemo(
    () => learningQueue.find((item) => item.id === selectedLearningMaterialId) ?? learningQueue[0],
    [learningQueue, selectedLearningMaterialId],
  );
  const selectedKnowledge = useMemo(
    () => knowledge.find((item) => item.id === selectedKnowledgeId),
    [knowledge, selectedKnowledgeId],
  );

  useEffect(() => {
    if (!selectedKnowledge || selectedKnowledge.body) return;
    const loadKnowledge = selectedKnowledge.backendId
      ? api.readKnowledge(selectedKnowledge.backendId)
      : selectedKnowledge.markdownPath && selectedKnowledge.library
        ? api.readLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath)
        : undefined;
    if (!loadKnowledge) return;
    loadKnowledge
      .then((item) => {
        setKnowledge((current) =>
          current.map((candidate) =>
            candidate.id === selectedKnowledge.id
              ? {
                  ...candidate,
                  ...item,
                  id: candidate.id,
                  sourceIds: candidate.sourceIds,
                  markdownPath: item.markdownPath ?? candidate.markdownPath,
                  note: item.note ?? candidate.note,
                }
              : candidate,
          ),
        );
      })
      .catch((error) => {
        addActivity({
          title: language === "zh" ? "知识文件读取失败" : "Knowledge file load failed",
          detail: error instanceof Error ? error.message : "Unable to read knowledge Markdown",
          workspace: "library",
          status: "error",
        });
      });
  }, [addActivity, language, selectedKnowledge]);

  const filteredMaterials = useMemo(() => filterBySearch(materials, search), [materials, search]);
  const filteredLearningQueue = useMemo(() => filterBySearch(learningQueue, search), [learningQueue, search]);
  const libraryRailKnowledge = useMemo(
    () => knowledge.filter((item) => (item.library ?? "focus") === libraryRailBucket),
    [knowledge, libraryRailBucket],
  );
  const selectedRailOriginals = useMemo(
    () =>
      libraryRailBucket === "original"
        ? knowledge.filter((item) => libraryRailCheckedIds.includes(item.id) && (item.library ?? "focus") === "original")
        : [],
    [knowledge, libraryRailBucket, libraryRailCheckedIds],
  );
  const selectedRailKnowledge = useMemo(() => {
    const idSet = new Set(libraryRailCheckedIds);
    return knowledge.filter((item) => idSet.has(item.id));
  }, [knowledge, libraryRailCheckedIds]);
  const selectedPerspective = useMemo(
    () => perspectives.find((item) => item.id === selectedPerspectiveId) ?? perspectives[0],
    [perspectives, selectedPerspectiveId],
  );
  const mineSourceDisabledReason = useMemo(() => {
    if (libraryRailBucket !== "original") return language === "zh" ? "请先把右侧知识列表切换到原文库。" : "Switch the right library rail to Originals first.";
    if (!selectedRailOriginals.length) return language === "zh" ? "请先在右侧原文库勾选解读来源。" : "Select source files in the right Originals rail first.";
    if (selectedRailOriginals.some((item) => !item.markdownPath)) {
      return language === "zh" ? "所选原文缺少可解读的 Markdown 路径。" : "The selected original is missing an interpretable Markdown path.";
    }
    return "";
  }, [language, libraryRailBucket, selectedRailOriginals]);
  const addToLearningQueueDisabledReason = useMemo(() => {
    if (libraryRailBucket !== "original") return t("learn.addToQueue.disabled.notOriginalBucket");
    if (!selectedRailOriginals.length) return t("learn.addToQueue.disabled.noOriginalSelection");
    if (selectedRailOriginals.some((item) => !item.markdownPath)) {
      return t("learn.addToQueue.disabled.missingPath");
    }
    return "";
  }, [libraryRailBucket, selectedRailOriginals, t]);

  const selectWorkspace = useCallback((id: WorkspaceId) => {
    setActiveWorkspace(id);
    window.history.replaceState(null, "", `#/${id}`);
  }, []);

  const insertMaterial = useCallback(
    (material: SourceMaterial) => {
      setMaterials((current) => [material, ...current.filter((item) => item.id !== material.id)]);
      setSelectedMaterialId(material.id);
      addActivity({ title: material.title, detail: "素材已进入收集队列", workspace: "collect", status: material.status === "error" ? "error" : "done" });
    },
    [addActivity],
  );

  const createMaterial = useCallback(
    (item: Pick<SourceMaterial, "type" | "title" | "source"> & { backendId?: number; error?: string; note?: string }) => {
      insertMaterial({
        id: uid("material"),
        type: item.type,
        title: item.title,
        source: item.source,
        status: item.error ? "error" : "captured",
        backendId: item.backendId,
        error: item.error,
        note: item.note,
      });
    },
    [insertMaterial],
  );

  const uploadFiles = useCallback(
    async (type: MaterialType, files: File[]) => {
      if (!files.length) return;
      setCollectInputBusy(type);
      try {
        const uploaded = await api.uploadMaterial(type, files);
        if (!uploaded.length) throw new Error("旧后端没有返回上传结果");
        let enriched = uploaded;
        if (type === "file") {
          const ids = uploaded.map((item) => item.id).filter((id): id is number => typeof id === "number");
          const pageInfo = await api.loadFilePageInfo(ids).catch(() => []);
          enriched = uploaded.map((item) => ({ ...item, ...(pageInfo.find((info) => info.id === item.id) ?? {}) }));
        }
        enriched.forEach((item, index) => insertMaterial(materialFromUpload(type, item, files[index]?.name ?? "上传素材")));
      } catch (error) {
        files.forEach((file) =>
          createMaterial({
            type,
            title: file.name,
            source: file.name,
            error: error instanceof Error ? error.message : "上传旧后端失败",
          }),
        );
      } finally {
        setCollectInputBusy(null);
      }
    },
    [createMaterial, insertMaterial],
  );

  const pasteImages = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      setCollectInputBusy("paste-image");
      try {
        const uploaded = await api.uploadPastedImages(files);
        if (!uploaded.length) throw new Error("旧后端没有返回粘贴截图结果");
        uploaded.forEach((item, index) => insertMaterial(materialFromUpload("image", item, files[index]?.name ?? "粘贴截图")));
      } catch (error) {
        const detail = error instanceof Error ? error.message : "粘贴截图上传失败";
        files.forEach((file) =>
          createMaterial({
            type: "image",
            title: file.name || "本地暂存截图",
            source: "clipboard",
            note: `后端上传失败，已作为本地暂存素材继续：${detail}`,
          }),
        );
        addActivity({ title: "粘贴截图后端上传失败", detail, workspace: "collect", status: "error" });
      } finally {
        setCollectInputBusy(null);
      }
    },
    [addActivity, createMaterial, insertMaterial],
  );

  const resolveLinks = useCallback(
    async (urls: string[]) => {
      const existing = new Set(materials.map((item) => item.source));
      for (const url of urls) {
        if (existing.has(url)) continue;
        if (looksLikeMediaUrl(url)) {
          try {
            const resolved = await api.resolveMediaUrl(url);
            if (!resolved) throw new Error("旧后端没有返回媒体记录");
            const material = materialFromUpload("media", resolved, url);
            insertMaterial(material);
            if (material.backendId) {
              api.transcribeMedia([material.backendId]).catch(() => undefined);
            }
          } catch (error) {
            createMaterial({
              type: "link",
              title: url,
              source: url,
              error: error instanceof Error ? error.message : "媒体链接解析失败",
            });
          }
        } else {
          createMaterial({
            type: "link",
            title: url,
            source: url,
            note: language === "zh" ? "网页链接将在保存到原文库时抓取正文。" : "The page text will be fetched when saving to Originals.",
          });
        }
      }
    },
    [createMaterial, insertMaterial, language, materials],
  );

  const saveMaterialsToOriginalLibrary = useCallback(async (ids?: string[]) => {
    const requestedIds = ids?.length ? ids : selectedMaterial ? [selectedMaterial.id] : [];
    if (!requestedIds.length) return;
    const idSet = new Set(requestedIds);
    const selectedItems = materials.filter((item) => idSet.has(item.id) && item.status !== "error");
    if (!selectedItems.length) return;
    try {
      const groups = groupMaterialsByRawType(selectedItems);
      const results = [];
      for (const group of groups) {
        results.push(await api.createRawLibraryFile(group));
      }
      setMaterials((current) => current.filter((item) => !idSet.has(item.id)));
      setSelectedMaterialId((current) => (current && idSet.has(current) ? undefined : current));
      setSelectedKnowledgeId(results[0]?.item.id);
      await refreshLibraries();
      const errorCount = results.reduce((total, result) => total + (result.errors?.length ?? 0), 0);
      addActivity({
        title: results[0]?.item.title ?? (language === "zh" ? "原文库文件" : "Original file"),
        detail:
          language === "zh"
            ? `已生成 ${results.length} 个原文库文件${errorCount ? `，${errorCount} 条来源提取失败` : ""}。`
            : `Created ${results.length} Originals file(s)${errorCount ? ` with ${errorCount} extraction error(s)` : ""}.`,
        workspace: "collect",
        status: errorCount ? "error" : "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "原文库文件生成失败" : "Original file creation failed",
        detail: error instanceof Error ? error.message : "Raw library API failed",
        workspace: "collect",
        status: "error",
      });
    }
  }, [addActivity, language, materials, refreshLibraries, selectedMaterial]);

  const resolveLinksV2 = useCallback(
    async (urls: string[]) => {
      if (!urls.length) return;
      setCollectInputBusy("link");
      const existing = new Set(materials.map((item) => item.source));
      try {
        for (const url of urls) {
        if (existing.has(url)) continue;
        if (looksLikeMediaUrl(url)) {
          try {
            const resolved = await api.resolveMediaUrl(url);
            if (!resolved) throw new Error("Legacy backend did not return media metadata.");
            const material = materialFromUpload("media", resolved, url);
            insertMaterial(material);
            if (material.backendId) {
              api.transcribeMedia([material.backendId]).catch(() => undefined);
            }
          } catch (error) {
            createMaterial({
              type: "link",
              title: url,
              source: url,
              error: error instanceof Error ? error.message : "Media link resolution failed",
            });
          }
          continue;
        }

        try {
          const inspected = await api.inspectLink(url);
          const noteParts = [
            inspected?.notes ?? "",
            inspected?.link_type ? `${language === "zh" ? "类型" : "Type"}: ${inspected.link_type}` : "",
            inspected?.extraction_strategy
              ? `${language === "zh" ? "提取方式" : "Strategy"}: ${inspected.extraction_strategy}`
              : "",
          ].filter(Boolean);
          createMaterial({
            type: "link",
            title: inspected?.title?.trim() || url,
            source: inspected?.final_url?.trim() || url,
            note: noteParts.join(" | "),
          });
        } catch (error) {
          createMaterial({
            type: "link",
            title: url,
            source: url,
            note:
              error instanceof Error
                ? error.message
                : language === "zh"
                  ? "网页链接检查失败，后续仍可尝试生成原文。"
                  : "Link inspection failed, but you can still try generating the readable original.",
          });
        }
        }
      } finally {
        setCollectInputBusy(null);
      }
    },
    [createMaterial, insertMaterial, language, materials],
  );

  const generateCollectReadableDraft = useCallback(
    async (ids?: string[]) => {
      const requestedIds = ids?.length ? ids : selectedMaterial ? [selectedMaterial.id] : [];
      if (!requestedIds.length) return;
      const idSet = new Set(requestedIds);
      const selectedItems = materials.filter((item) => idSet.has(item.id) && item.status !== "error");
      if (!selectedItems.length) return;

      setIsCollectingReadable(true);
      setMaterials((current) =>
        current.map((item) => (idSet.has(item.id) ? { ...item, status: "learning", error: undefined } : item)),
      );

      try {
        const draft = await api.createReadableDraft(selectedItems, textExtractionMode);
        setCollectDraft(draft);
        setMaterials((current) =>
          current.map((item) => (idSet.has(item.id) ? { ...item, status: "ready", error: undefined } : item)),
        );
        addActivity({
          title: draft.title,
          detail: language === "zh" ? "已生成可编辑原文草稿，请确认后加入原文库。" : "Readable original draft generated.",
          workspace: "collect",
          status: "done",
        });
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Readable original generation failed";
        setMaterials((current) =>
          current.map((item) => (idSet.has(item.id) ? { ...item, status: "error", error: detail } : item)),
        );
        addActivity({
          title: language === "zh" ? "生成原文失败" : "Generate original failed",
          detail,
          workspace: "collect",
          status: "error",
        });
      } finally {
        setIsCollectingReadable(false);
      }
    },
    [addActivity, language, materials, selectedMaterial, textExtractionMode],
  );

  const saveCollectDraftToOriginalLibrary = useCallback(async () => {
    if (!collectDraft) return;
    setIsSavingRawDraft(true);
    try {
      const item = await api.saveRawDraft(collectDraft);
      const sourceIdSet = new Set(collectDraft.sourceIds);
      setCollectDraft(undefined);
      setSelectedKnowledgeId(item.id);
      setMaterials((current) => current.filter((material) => !sourceIdSet.has(material.id)));
      setSelectedMaterialId((current) => (current && sourceIdSet.has(current) ? undefined : current));
      await refreshLibraries();
      addActivity({
        title: item.title,
        detail: language === "zh" ? "原文文件已加入原文库。" : "Original file saved to Originals.",
        workspace: "collect",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "加入原文库失败" : "Add to Originals failed",
        detail: error instanceof Error ? error.message : "Save raw draft failed",
        workspace: "collect",
        status: "error",
      });
    } finally {
      setIsSavingRawDraft(false);
    }
  }, [addActivity, collectDraft, language, refreshLibraries]);

  const deleteMaterials = useCallback((ids: string[]) => {
    if (!ids.length) return;
    const idSet = new Set(ids);
    setMaterials((current) => current.filter((item) => !idSet.has(item.id)));
    setSelectedMaterialId((current) => (current && idSet.has(current) ? undefined : current));
    addActivity({ title: "删除素材", detail: `已从素材队列删除 ${ids.length} 个素材`, workspace: "collect", status: "done" });
  }, [addActivity]);

  const addSelectedOriginalsToLearningQueue = useCallback(() => {
    if (addToLearningQueueDisabledReason) return;
    const items = selectedRailOriginals
      .filter((item) => item.markdownPath)
      .map((item) => ({
        id: item.id,
        type: "text" as const,
        title: item.title,
        source: item.markdownPath ?? "",
        status: "queued" as const,
        note: item.note,
      }));
    if (!items.length) return;
    setLearningQueue((current) => {
      const existingIds = new Set(current.map((item) => item.id));
      return [...current, ...items.filter((item) => !existingIds.has(item.id))];
    });
    setSelectedLearningMaterialId((current) => current ?? items[0]?.id);
    addActivity({
      title: language === "zh" ? "加入学习队列" : "Added to learning queue",
      detail:
        language === "zh"
          ? `已加入 ${items.length} 个原文库文件，重复文件会自动跳过。`
          : `Added ${items.length} original file(s); duplicates are skipped automatically.`,
      workspace: "learn",
      status: "done",
    });
  }, [addActivity, addToLearningQueueDisabledReason, language, selectedRailOriginals]);

  const generateKnowledge = useCallback(async (ids: string[]) => {
    const idSet = new Set(ids);
    const selectedMaterials = learningQueue.filter((item) => idSet.has(item.id));
    if (!selectedMaterials.length) return;
    const rawPaths = selectedMaterials.map((item) => item.source).filter(Boolean);
    const allRawLibraryFiles = rawPaths.length === selectedMaterials.length && selectedMaterials.every((item) => item.source);
    setIsLearning(true);
    setLearningQueue((current) => current.map((item) => (idSet.has(item.id) ? { ...item, status: "learning", error: undefined } : item)));
    try {
      if (!allRawLibraryFiles) {
        const detail =
          language === "zh"
            ? "学习区只处理从右侧原文库加入的文件。请先在收集区保存原文库文件，再从右栏原文库加入学习队列。"
            : "Learn only processes files added from the right Originals rail. Save material to Originals in Collect first, then add it from the rail.";
        setLearningQueue((current) =>
          current.map((item) =>
            idSet.has(item.id)
              ? {
                  ...item,
                  status: "error",
                  error: detail,
                  note: detail,
                }
              : item,
          ),
        );
        addActivity({
          title: language === "zh" ? "学习队列来源不正确" : "Invalid learning queue source",
          detail,
          workspace: "learn",
          status: "error",
        });
        return;
      }
      const refined = await api.refineKnowledgeCluster(rawPaths);
      const title = markdownTitle(refined.markdown) || selectedMaterials[0]?.title || (language === "zh" ? "未命名重点文件" : "Untitled focus file");
      const draft: KnowledgeDraft = {
        id: uid("focus-draft"),
        title,
        note:
          language === "zh"
            ? `核心知识簇：${refined.cluster_count ?? 0} 个；来源：${selectedMaterials.map((item) => item.title).join("、")}`
            : `Core clusters: ${refined.cluster_count ?? 0}; sources: ${selectedMaterials.map((item) => item.title).join(", ")}`,
        body: refined.markdown ?? "",
        sourceIds: rawPaths,
        status: "draft",
      };
      setKnowledgeDraft(draft);
      setLearningQueue((current) => current.map((item) => (idSet.has(item.id) ? { ...item, status: "queued", error: undefined } : item)));
      addActivity({
        title: draft.title,
        detail: language === "zh" ? "已提炼为重点文件草稿，请编辑确认后加入重点库。" : "Focus draft generated. Review and add it to Focus.",
        workspace: "learn",
        status: "done",
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "生成重点知识失败";
      setLearningQueue((current) =>
        current.map((item) => (idSet.has(item.id) ? { ...item, status: "error", error: detail, note: detail } : item)),
      );
      addActivity({
        title: language === "zh" ? "生成重点知识失败" : "Generate focus knowledge failed",
        detail,
        workspace: "learn",
        status: "error",
      });
    } finally {
      setIsLearning(false);
    }
  }, [addActivity, language, learningQueue]);

  const commitKnowledgeDraft = useCallback(async () => {
    if (!knowledgeDraft) return;
    const isFocusDraft = knowledgeDraft.sourceIds.length > 0;
    let item: KnowledgeItem;
    try {
      item = isFocusDraft
        ? await api.saveFocusFile(knowledgeDraft.sourceIds, knowledgeDraft.body, knowledgeDraft.title)
        : await api.commitKnowledgeDraft(knowledgeDraft);
      item = {
        ...item,
        id: item.id || knowledgeDraft.id,
        title: item.title || knowledgeDraft.title.trim() || (language === "zh" ? "未命名知识" : "Untitled knowledge"),
        note: knowledgeDraft.note.trim(),
        body: knowledgeDraft.body,
        sourceIds: knowledgeDraft.sourceIds,
        library: isFocusDraft ? "focus" : item.library,
        status: "saved",
        confidence: "medium",
      };
    } catch (error) {
      addActivity({
        title: language === "zh" ? "加入重点库失败" : "Add to Focus failed",
        detail: error instanceof Error ? error.message : "Focus draft save failed",
        workspace: "learn",
        status: "error",
      });
      return;
    }
    setKnowledge((current) => [item, ...current.filter((candidate) => candidate.id !== item.id)]);
    setSelectedKnowledgeId(item.id);
    setKnowledgeDraft(undefined);
    if (isFocusDraft) {
      const sourceIdSet = new Set(knowledgeDraft.sourceIds);
      setSelectedLearningMaterialId((current) => {
        if (!current) return current;
        const remaining = learningQueue.filter((queueItem) => !sourceIdSet.has(queueItem.source));
        return remaining.some((queueItem) => queueItem.id === current) ? current : remaining[0]?.id;
      });
      setLearningQueue((current) => current.filter((queueItem) => !sourceIdSet.has(queueItem.source)));
      setLibraryRailBucket("focus");
    }
    await refreshLibraries();
    addActivity({ title: item.title, detail: language === "zh" ? "重点文件已加入重点库" : "Focus file added to library", workspace: "library", status: "done" });
  }, [addActivity, knowledgeDraft, language, learningQueue, refreshLibraries]);

  const savePerspectiveProfile = useCallback(
    async (profile: PerspectiveProfile) => {
      try {
        const items = await api.savePerspectiveProfile(profile);
        setPerspectives(items);
        const saved = items.find((item) => item.name === profile.name && item.coreGoal === profile.coreGoal) ?? items[0];
        setSelectedPerspectiveId(saved?.id);
        addActivity({
          title: saved?.name ?? profile.name,
          detail: language === "zh" ? "视角已保存" : "Perspective saved",
          workspace: "mine",
          status: "done",
        });
      } catch (error) {
        addActivity({
          title: language === "zh" ? "视角保存失败" : "Perspective save failed",
          detail: error instanceof Error ? error.message : "Perspective API failed",
          workspace: "mine",
          status: "error",
        });
        throw error;
      }
    },
    [addActivity, language],
  );

  const deletePerspectiveProfile = useCallback(
    async (profileId: string) => {
      try {
        const items = await api.deletePerspectiveProfile(profileId);
        setPerspectives(items);
        setSelectedPerspectiveId((current) => (current === profileId ? items[0]?.id : current));
        addActivity({
          title: language === "zh" ? "视角已删除" : "Perspective deleted",
          detail: profileId,
          workspace: "mine",
          status: "done",
        });
      } catch (error) {
        addActivity({
          title: language === "zh" ? "视角删除失败" : "Perspective delete failed",
          detail: error instanceof Error ? error.message : "Perspective API failed",
          workspace: "mine",
          status: "error",
        });
        throw error;
      }
    },
    [addActivity, language],
  );

  const runPerspectiveInterpretation = useCallback(async () => {
    if (!selectedPerspective || mineSourceDisabledReason) return;
    setIsMining(true);
    try {
      const draft = await api.interpretPerspective(selectedRailOriginals, selectedPerspective);
      setPerspectiveDraft(draft);
      addActivity({
        title: draft.title,
        detail: language === "zh" ? "视角解读草稿已生成，请确认后加入视角库。" : "Perspective draft generated. Review and save it to Perspectives.",
        workspace: "mine",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "视角解读失败" : "Perspective interpretation failed",
        detail: error instanceof Error ? error.message : "Mine API failed",
        workspace: "mine",
        status: "error",
      });
    } finally {
      setIsMining(false);
    }
  }, [addActivity, language, mineSourceDisabledReason, selectedPerspective, selectedRailOriginals]);

  const savePerspectiveDraft = useCallback(async () => {
    if (!perspectiveDraft || !selectedPerspective) return;
    const markdown = perspectiveDraft.markdown.trim();
    if (!markdown) {
      addActivity({
        title: language === "zh" ? "加入视角库失败" : "Add to Perspectives failed",
        detail: language === "zh" ? "视角解读正文不能为空" : "Perspective body cannot be empty",
        workspace: "mine",
        status: "error",
      });
      return;
    }
    setIsSavingPerspective(true);
    try {
      const item = await api.savePerspectiveFile(selectedRailOriginals, selectedPerspective, markdown, perspectiveDraft.title);
      setKnowledge((current) => [item, ...current.filter((candidate) => candidate.id !== item.id)]);
      setSelectedKnowledgeId(item.id);
      setPerspectiveDraft(undefined);
      setLibraryRailBucket("perspective");
      await refreshLibraries();
      addActivity({
        title: item.title,
        detail: language === "zh" ? "视角文件已加入视角库" : "Perspective file added to library",
        workspace: "mine",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "加入视角库失败" : "Add to Perspectives failed",
        detail: error instanceof Error ? error.message : "Perspective save API failed",
        workspace: "mine",
        status: "error",
      });
    } finally {
      setIsSavingPerspective(false);
    }
  }, [addActivity, language, perspectiveDraft, refreshLibraries, selectedPerspective, selectedRailOriginals]);

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
        api.createWriterProject(
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
      runWriterAction(language === "zh" ? "打开写文项目" : "Open writing project", () => api.writerProject(projectId));
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
      runWriterAction(language === "zh" ? "导入项目知识" : "Import project knowledge", () => api.confirmWriterKnowledge(requireProjectId(), [], libraryFiles));
    },
    [language, requireProjectId, runWriterAction],
  );

  const generateWriterTopics = useCallback(() => {
    runWriterAction(language === "zh" ? "生成选题建议" : "Generate topic suggestions", () => api.generateWriterProjectTopics(requireProjectId()));
  }, [language, requireProjectId, runWriterAction]);

  const selectWriterTopic = useCallback(
    (topic: Record<string, unknown>) => {
      runWriterAction(language === "zh" ? "选择选题" : "Select topic", () => api.selectWriterProjectTopic(requireProjectId(), topic));
    },
    [language, requireProjectId, runWriterAction],
  );

  const generateWriterDraft = useCallback(() => {
    runWriterAction(language === "zh" ? "生成初稿" : "Generate draft", () => api.generateWriterProjectDraft(requireProjectId()));
  }, [language, requireProjectId, runWriterAction]);

  const reviseWriterProject = useCallback(
    (instruction: string, markdown?: string) => {
      runWriterAction(language === "zh" ? "修订文章" : "Revise article", () => api.reviseWriterProject(requireProjectId(), instruction, markdown));
    },
    [language, requireProjectId, runWriterAction],
  );

  const suggestWriterImages = useCallback((markdown?: string) => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "生成配图建议" : "Suggest images", () =>
      api.suggestWriterProjectImages(requireProjectId(), markdown ?? project?.article_markdown, project?.topic ?? undefined),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  const generateWriterImages = useCallback((coverPrompt?: string, contentImagePrompts?: string[]) => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "生成图片" : "Generate images", () =>
      api.generateWriterProjectImages(requireProjectId(), coverPrompt ?? project?.cover_prompt, contentImagePrompts ?? project?.content_image_prompts ?? []),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  const formatWriterProject = useCallback(
    (markdown?: string, designStrategy?: string) => {
      runWriterAction(language === "zh" ? "美编排版" : "Design article", () => api.formatWriterProject(requireProjectId(), markdown, designStrategy));
    },
    [language, requireProjectId, runWriterAction],
  );

  const preflightWriterProject = useCallback(() => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "发布检查" : "Run preflight", () =>
      api.preflightWriterProject(requireProjectId(), project?.title || project?.name || "", project?.digest),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  const publishWriterProject = useCallback(() => {
    const project = writerState?.project;
    runWriterAction(language === "zh" ? "发布到草稿箱" : "Publish to draft box", () =>
      api.publishWriterProject(requireProjectId(), project?.title || project?.name || "", project?.digest),
    );
  }, [language, requireProjectId, runWriterAction, writerState]);

  const saveWorkbenchSettings = useCallback(async () => {
    try {
      await api.saveWorkbenchSettings({ text_extraction_mode: textExtractionMode });
      const extractionLabel =
        textExtractionMode === "local_ocr" ? t("settings.extraction.local") : t("settings.extraction.api");
      addActivity({
        title: t("settings.saved"),
        detail: `${t("settings.extraction")}: ${extractionLabel}`,
        workspace: "settings",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "设置保存失败" : "Settings save failed",
        detail: error instanceof Error ? error.message : "Unable to save workbench settings",
        workspace: "settings",
        status: "error",
      });
    }
  }, [addActivity, language, t, textExtractionMode]);

  const saveKnowledgeEdit = useCallback(
    async (draft: { title: string; note: string; body: string }) => {
      if (!selectedKnowledge) return;
      const trimmed = {
        title: draft.title.trim() || (language === "zh" ? "未命名知识" : "Untitled knowledge"),
        note: draft.note.trim(),
        body: draft.body,
      };
      if (!trimmed.body.trim()) {
        throw new Error(language === "zh" ? "正文不能为空" : "Body cannot be empty");
      }

      let saved: KnowledgeItem;
      try {
        if (selectedKnowledge.backendId) {
          saved = await api.updateKnowledge(selectedKnowledge.backendId, trimmed);
        } else if (selectedKnowledge.markdownPath && selectedKnowledge.library) {
          saved = await api.updateLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath, trimmed);
        } else {
          saved = { ...selectedKnowledge, ...trimmed, status: "saved", confidence: "medium" };
          addActivity({
            title: trimmed.title,
            detail: language === "zh" ? "这条知识没有后端记录，已暂存在当前页面状态。" : "This item has no backend record; changes are kept in the current page state.",
            workspace: "library",
            status: "error",
          });
        }
      } catch (error) {
        addActivity({
          title: trimmed.title,
          detail: error instanceof Error ? error.message : language === "zh" ? "知识文件保存失败" : "Knowledge file save failed",
          workspace: "library",
          status: "error",
        });
        throw error;
      }

      const next = {
        ...selectedKnowledge,
        ...saved,
        id: selectedKnowledge.id,
        title: saved.title || trimmed.title,
        note: trimmed.note,
        body: saved.body || trimmed.body,
        sourceIds: selectedKnowledge.sourceIds,
        markdownPath: saved.markdownPath ?? selectedKnowledge.markdownPath,
        library: saved.library ?? selectedKnowledge.library,
        status: saved.status || "saved",
        confidence: saved.confidence || "medium",
      };
      setKnowledge((current) => current.map((item) => (item.id === selectedKnowledge.id ? next : item)));
      setSelectedKnowledgeId(next.id);
      addActivity({
        title: next.title,
        detail: language === "zh" ? "知识文件已保存" : "Knowledge file saved",
        workspace: "library",
        status: "done",
      });
    },
    [addActivity, language, selectedKnowledge],
  );

  const deleteKnowledgeFiles = useCallback(
    async (ids: string[]) => {
      if (!ids.length) return;
      const idSet = new Set(ids);
      const selectedItems = knowledge.filter((item) => idSet.has(item.id));
      const fileItems = selectedItems.filter((item) => item.markdownPath && item.library);
      const fileItemIds = new Set(fileItems.map((item) => item.id));
      const backendIds = selectedItems
        .filter((item) => !fileItemIds.has(item.id))
        .map((item) => item.backendId)
        .filter((id): id is number => typeof id === "number");
      const localIds = selectedItems.filter((item) => !fileItemIds.has(item.id) && !item.backendId).map((item) => item.id);

      let movedCount = 0;
      for (const item of fileItems) {
        if (!item.markdownPath || !item.library) continue;
        await api.deleteLibraryFile(item.library, item.markdownPath);
        movedCount += 1;
      }

      if (backendIds.length) {
        const result = await api.deleteKnowledge(backendIds);
        const deletedCount = movedCount + result.deleted.length + localIds.length;
        const skippedCount = result.skipped.length;
        addActivity({
          title: language === "zh" ? "删除知识文件" : "Delete knowledge files",
          detail:
            language === "zh"
              ? `已将 ${deletedCount} 个文件移入垃圾箱${skippedCount ? `，${skippedCount} 个因已入图谱或状态限制未删除` : ""}`
              : `Moved ${deletedCount} file(s) to trash${skippedCount ? `, ${skippedCount} skipped because of graph/status protection` : ""}`,
          workspace: "library",
          status: skippedCount ? "error" : "done",
        });
        const items = await refreshLibraries();
        const deletedIds = new Set(result.deleted.map((item) => String(item.id)));
        setSelectedKnowledgeId((current) => {
          if (!current) return items[0]?.id;
          const currentItem = selectedItems.find((item) => item.id === current);
          if (fileItemIds.has(current)) return items[0]?.id;
          if (currentItem?.backendId && deletedIds.has(String(currentItem.backendId))) return items[0]?.id;
          if (localIds.includes(current)) return items[0]?.id;
          return items.some((item) => item.id === current) ? current : items[0]?.id;
        });
        return;
      }

      const items = await refreshLibraries();
      setSelectedKnowledgeId((current) => {
        if (!current || idSet.has(current)) return items[0]?.id;
        return items.some((item) => item.id === current) ? current : items[0]?.id;
      });
      addActivity({
        title: language === "zh" ? "删除知识文件" : "Delete knowledge files",
        detail:
          language === "zh"
            ? `已将 ${movedCount + localIds.length} 个文件移入垃圾箱`
            : `Moved ${movedCount + localIds.length} file(s) to trash`,
        workspace: "library",
        status: "done",
      });
    },
    [addActivity, knowledge, language, refreshLibraries],
  );

  useEffect(() => {
    const visibleIds = new Set(knowledge.map((item) => item.id));
    setLibraryRailCheckedIds((current) => current.filter((id) => visibleIds.has(id)));
  }, [knowledge]);

  const deleteKnowledgeFromRail = useCallback(
    async (ids: string[]) => {
      setIsDeletingKnowledge(true);
      try {
        await deleteKnowledgeFiles(ids);
      } finally {
        setIsDeletingKnowledge(false);
      }
    },
    [deleteKnowledgeFiles],
  );

  const knowledgeRail = (
    <KnowledgeLibraryRail
      t={t}
      knowledge={libraryRailKnowledge}
      selectedKnowledge={selectedKnowledge}
      mode="manage"
      activeBucket={libraryRailBucket}
      query={libraryRailQuery}
      checkedIds={libraryRailCheckedIds}
      isDeleting={isDeletingKnowledge}
      onBucketChange={setLibraryRailBucket}
      onQueryChange={setLibraryRailQuery}
      onCheckedIdsChange={setLibraryRailCheckedIds}
      onSelectKnowledge={setSelectedKnowledgeId}
      onDeleteKnowledge={deleteKnowledgeFromRail}
    />
  );

  const content = (() => {
    switch (activeWorkspace) {
      case "collect":
        return (
          <CollectWorkspace
            t={t}
            materials={filteredMaterials}
            selectedMaterial={selectedMaterial}
            readableDraft={collectDraft}
            isGeneratingReadable={isCollectingReadable}
            isSavingReadable={isSavingRawDraft}
            inputBusy={collectInputBusy}
            rightRail={knowledgeRail}
            onSelectMaterial={setSelectedMaterialId}
            onCreateMaterial={createMaterial}
            onUploadFiles={uploadFiles}
            onPasteImages={pasteImages}
            onResolveLinks={resolveLinksV2}
            onGenerateReadableDraft={generateCollectReadableDraft}
            onUpdateReadableDraft={setCollectDraft}
            onSaveReadableDraft={saveCollectDraftToOriginalLibrary}
            onDeleteMaterials={deleteMaterials}
          />
        );
      case "learn":
        return (
          <LearnWorkspace
            t={t}
            queue={filteredLearningQueue}
            selectedMaterial={selectedLearningMaterial}
            knowledgeDraft={knowledgeDraft}
            isRunning={isLearning}
            rightRail={knowledgeRail}
            addToQueueDisabledReason={addToLearningQueueDisabledReason}
            onSelectMaterial={setSelectedLearningMaterialId}
            onAddSelectedOriginalsToQueue={addSelectedOriginalsToLearningQueue}
            onGenerateKnowledge={generateKnowledge}
            onUpdateKnowledgeDraft={setKnowledgeDraft}
            onCommitKnowledgeDraft={commitKnowledgeDraft}
          />
        );
      case "mine":
        return (
          <MineWorkspace
            t={t}
            language={language}
            perspectives={perspectives}
            selectedPerspective={selectedPerspective}
            selectedSources={selectedRailOriginals}
            draft={perspectiveDraft}
            isRunning={isMining}
            isSaving={isSavingPerspective}
            disabledReason={mineSourceDisabledReason}
            rightRail={knowledgeRail}
            onSelectPerspective={setSelectedPerspectiveId}
            onSavePerspective={savePerspectiveProfile}
            onDeletePerspective={deletePerspectiveProfile}
            onRunInterpretation={runPerspectiveInterpretation}
            onUpdateDraft={setPerspectiveDraft}
            onSaveDraft={savePerspectiveDraft}
          />
        );
      case "create":
        return (
          <CreateWorkspace
            t={t}
            language={language}
            rightRail={knowledgeRail}
            writerProjects={writerProjects}
            writerState={writerState}
            selectedProjectId={selectedWriterProjectId}
            selectedKnowledgeFiles={selectedRailKnowledge}
            isRunning={isWriting}
            onCreateProject={createWriterProject}
            onSelectProject={selectWriterProject}
            onImportKnowledge={importWriterKnowledge}
            onGenerateTopics={generateWriterTopics}
            onSelectTopic={selectWriterTopic}
            onGenerateDraft={generateWriterDraft}
            onRevise={reviseWriterProject}
            onSuggestImages={suggestWriterImages}
            onGenerateImages={generateWriterImages}
            onFormat={formatWriterProject}
            onPreflight={preflightWriterProject}
            onPublish={publishWriterProject}
          />
        );
      case "library":
        return (
          <LibraryWorkspace
            t={t}
            activeBucket={libraryRailBucket}
            rightRail={knowledgeRail}
            selectedKnowledge={selectedKnowledge}
            onSaveKnowledge={saveKnowledgeEdit}
          />
        );
      case "settings":
        return (
          <SettingsWorkspace
            t={t}
            language={language}
            textExtractionMode={textExtractionMode}
            activities={activities}
            rightRail={knowledgeRail}
            onLanguageChange={setLanguage}
            onTextExtractionModeChange={setTextExtractionMode}
            onSave={saveWorkbenchSettings}
          />
        );
    }
  })();

  const activeItem = navItems.find((item) => item.id === activeWorkspace) ?? navItems[0];
  const runningCount = Number(isLearning) + Number(isWriting) + activities.filter((event) => event.status === "running").length;

  return (
    <AppShell
      appName={t("app.name")}
      appSubtitle={t("app.subtitle")}
      navItems={navItems}
      activeId={activeWorkspace}
      activeTitle={workspaceLabel(t, activeWorkspace)}
      activeDescription={activeItem.description}
      searchPlaceholder={t("topbar.search")}
      importLabel={t("topbar.import")}
      queueLabel={t("topbar.queue")}
      queueStatus={runningCount > 0 ? `${runningCount}` : t("topbar.ready")}
      search={search}
      onSearchChange={setSearch}
      onImport={() => selectWorkspace("collect")}
      onSelect={selectWorkspace}
    >
      {content}
    </AppShell>
  );
}

function markdownTitle(markdown?: string) {
  if (!markdown) return "";
  const line = markdown.split(/\r?\n/).find((item) => item.trim().startsWith("# "));
  return line ? line.replace(/^#\s+/, "").trim() : "";
}

function filterBySearch<T extends { title: string; body?: string; source?: string }>(items: T[], search: string) {
  const clean = search.trim().toLowerCase();
  if (!clean) return items;
  return items.filter((item) => `${item.title} ${item.body ?? ""} ${item.source ?? ""}`.toLowerCase().includes(clean));
}

function groupMaterialsByRawType(materials: SourceMaterial[]) {
  const groups = new Map<string, SourceMaterial[]>();
  materials.forEach((material) => {
    const key = rawMaterialGroupKey(material);
    groups.set(key, [...(groups.get(key) ?? []), material]);
  });
  return Array.from(groups.values());
}

function localReadableDocument(material: SourceMaterial, language: Language): KnowledgeItem {
  const title = material.title.trim() || (language === "zh" ? "未命名原文" : "Untitled source");
  const source = material.source.trim();
  const body =
    material.type === "text" && source
      ? `# ${title}\n\n${source}`
      : `# ${title}\n\n${material.note || (language === "zh" ? "该素材需要后端 OCR、文件解析或转写接口提取正文。" : "This material needs backend OCR, file parsing, or transcription before readable text is available.")}`;
  return {
    id: uid("readable"),
    title,
    note: language === "zh" ? "本地原文草稿" : "Local readable draft",
    body,
    sourceIds: [material.id],
    status: "draft",
    confidence: material.type === "text" ? "medium" : "needsReview",
  };
}

function combineReadableDocuments(items: KnowledgeItem[], materials: SourceMaterial[], language: Language): KnowledgeItem {
  if (items.length === 1) return items[0];
  const title =
    language === "zh"
      ? `${materials[0]?.title || "组合材料"} 等 ${items.length} 个原文文档`
      : `${materials[0]?.title || "Combined material"} and ${items.length - 1} more readable documents`;
  return {
    id: uid("readable"),
    title,
    note: language === "zh" ? "多素材本地原文草稿" : "Local draft from multiple source materials",
    body: items.map((item, index) => `## ${index + 1}. ${item.title}\n\n${item.body.replace(/^# .+\n+/, "")}`).join("\n\n---\n\n"),
    sourceIds: materials.map((item) => item.id),
    status: "draft",
    confidence: items.every((item) => item.confidence !== "needsReview") ? "medium" : "needsReview",
  };
}

function knowledgeDraftFromGenerated(items: KnowledgeItem[], materials: SourceMaterial[], language: Language): KnowledgeDraft {
  const primary = items[0];
  const title =
    items.length === 1
      ? primary?.title || materials[0]?.title || (language === "zh" ? "未命名知识" : "Untitled knowledge")
      : language === "zh"
        ? `${materials[0]?.title || "组合素材"} 等 ${items.length} 条知识`
        : `${materials[0]?.title || "Combined material"} and ${items.length - 1} more`;
  const note =
    language === "zh"
      ? `来源素材：${materials.map((item) => item.title).join("、")}`
      : `Source materials: ${materials.map((item) => item.title).join(", ")}`;
  const body = items
    .map((item, index) => {
      const heading = items.length > 1 ? `\n\n## ${index + 1}. ${item.title}\n\n` : "";
      return `${heading}${item.body}`.trim();
    })
    .join("\n\n---\n\n");
  return {
    id: uid("knowledge-draft"),
    title,
    note,
    body,
    sourceIds: materials.map((item) => item.id),
    backendId: items.length === 1 ? primary?.backendId : undefined,
    status: "draft",
  };
}

function localAdvanceDraft(current: CreationDraft, title: string, language: Language): CreationDraft {
  const nextStep = Math.min(current.step + 1, 5);
  return {
    ...current,
    step: nextStep,
    status: nextStep >= 5 ? "ready" : nextStep >= 3 ? "review" : "draft",
    body: draftBody(nextStep, title, language),
  };
}

function draftBody(step: number, title: string, language: Language) {
  const zh = [
    `已确认知识：${title}`,
    `选题：把“${title}”转化为一个可讨论的问题。`,
    `初稿：围绕核心判断、证据和反方观点组织文章。`,
    `修订：压缩铺垫，强化结论，并补充来源核对。`,
    `配图：待接入真实配图接口，当前记录配图需求。`,
    `发布检查：标题、来源、事实核对和风险提示均已列入审核。`,
  ];
  const en = [
    `Knowledge confirmed: ${title}`,
    `Topic: turn "${title}" into a discussable question.`,
    `Draft: organize the article around claim, evidence, and counterpoint.`,
    `Revision: tighten setup, strengthen conclusion, and verify sources.`,
    `Image: real image generation is pending; image requirements are recorded.`,
    `Preflight: title, sources, fact checks, and risk notes are ready for review.`,
  ];
  return (language === "zh" ? zh : en)[step] ?? title;
}

function extractTopic(payload: Record<string, unknown>) {
  const topics = Array.isArray(payload.topics) ? payload.topics : Array.isArray(payload.items) ? payload.items : [];
  const first = topics[0];
  if (first && typeof first === "object") return first as Record<string, unknown>;
  return { title: String(payload.title ?? "未命名选题"), topic: String(payload.topic ?? payload.summary ?? "") };
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function looksLikeMediaUrl(url: string) {
  return /bilibili|douyin|youtube|youtu\.be|vimeo|xiaohongshu|xhslink|video|mp4|m3u8|audio/i.test(url);
}
