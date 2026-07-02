import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, authApi, libraryApi } from "./api";
import type { AuthContext, LibraryKind } from "./api";
import type {
  KnowledgeItem,
  Language,
  TextExtractionMode,
} from "./domain";
import { createTranslator, workspaceLabel } from "./i18n";
import { AppShell } from "./shell/AppShell";
import { CollectWorkspace } from "./workspaces/CollectWorkspace";
import { LearnWorkspace } from "./workspaces/LearnWorkspace";
import { MineWorkspace } from "./workspaces/MineWorkspace";
import { CreateWorkspace } from "./workspaces/CreateWorkspace";
import { LibraryWorkspace } from "./workspaces/LibraryWorkspace";
import { SettingsWorkspace } from "./workspaces/SettingsWorkspace";
import { KnowledgeLibraryRail } from "./components/KnowledgeLibraryRail";
import { AuthGate } from "./components/AuthGate";
import { JobCenter } from "./components/JobCenter";
import { UserAdminPanel } from "./components/UserAdminPanel";
import { useActivityLog } from "./hooks/useActivityLog";
import { useAppShell } from "./hooks/useAppShell";
import { useCollectFlow } from "./hooks/useCollectFlow";
import { useJobsFlow } from "./hooks/useJobsFlow";
import { useLearningFlow } from "./hooks/useLearningFlow";
import { useLibraryRail } from "./hooks/useLibraryRail";
import { useMineFlow } from "./hooks/useMineFlow";
import { useWriterFlow } from "./hooks/useWriterFlow";
import { useWorkspaceRoute } from "./hooks/useWorkspaceRoute";

const libraryKinds: LibraryKind[] = ["original", "focus", "perspective"];

function WorkbenchApp({
  authContext,
  onAuthContextChange,
}: {
  authContext: AuthContext;
  onAuthContextChange: (nextContext: AuthContext) => void;
}) {
  const [language, setLanguage] = useState<Language>("zh");
  const [textExtractionMode, setTextExtractionMode] = useState<TextExtractionMode>("ai_vision");
  const t = useMemo(() => createTranslator(language), [language]);
  const { navItems } = useAppShell(t);
  const { activeWorkspace, selectWorkspace } = useWorkspaceRoute("collect");
  const [knowledge, setKnowledge] = useState<KnowledgeItem[]>([]);
  const [selectedKnowledgeId, setSelectedKnowledgeId] = useState<string>();
  const { activities, addActivity } = useActivityLog();
  const {
    libraryRailBucket,
    setLibraryRailBucket,
    libraryRailQuery,
    setLibraryRailQuery,
    libraryRailCheckedIds,
    setLibraryRailCheckedIds,
    libraryRailKnowledge,
    selectedRailOriginals,
    selectedRailKnowledge,
    mineSourceDisabledReason,
    addToLearningQueueDisabledReason,
  } = useLibraryRail(knowledge, language, t);
  const [isDeletingKnowledge, setIsDeletingKnowledge] = useState(false);
  const [isUserAdminOpen, setIsUserAdminOpen] = useState(false);
  const {
    jobs,
    activeJobCount,
    isJobCenterOpen,
    isJobsLoading,
    jobsError,
    refreshJobs,
    cancelJob,
    openJobCenter,
    closeJobCenter,
  } = useJobsFlow();
  const {
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
    sanitizeWriterPublishHtml,
    confirmWriterDesign,
    preflightWriterProject,
    publishWriterProject,
  } = useWriterFlow({ language, addActivity, selectWorkspace });

  const refreshLibraries = useCallback(async (options?: { selectFirst?: boolean; clearChecked?: boolean }) => {
    if (options?.clearChecked !== false) setLibraryRailCheckedIds([]);
    try {
      const groups = await Promise.all(libraryKinds.map((kind) => libraryApi.listLibraryFiles(kind)));
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
      const items = await libraryApi.listKnowledge();
      setKnowledge(items);
      if (options?.selectFirst && items[0]) setSelectedKnowledgeId(items[0].id);
      return items;
    }
  }, [addActivity]);

  const {
    materials,
    selectedMaterial,
    collectDraft,
    setCollectDraft,
    collectInputBusy,
    isCollectingReadable,
    isSavingRawDraft,
    setSelectedMaterialId,
    createMaterial,
    uploadFiles,
    pasteImages,
    resolveLinks: resolveLinksV2,
    generateCollectReadableDraft,
    saveCollectDraftToOriginalLibrary,
    deleteMaterials,
  } = useCollectFlow({
    language,
    textExtractionMode,
    addActivity,
    refreshLibraries,
    setSelectedKnowledgeId,
  });

  const {
    learningQueue,
    selectedLearningMaterial,
    knowledgeDraft,
    setKnowledgeDraft,
    isLearning,
    setSelectedLearningMaterialId,
    addSelectedOriginalsToLearningQueue,
    generateKnowledge,
    commitKnowledgeDraft,
  } = useLearningFlow({
    language,
    selectedRailOriginals,
    addToLearningQueueDisabledReason,
    addActivity,
    setKnowledge,
    setSelectedKnowledgeId,
    setLibraryRailBucket,
    refreshLibraries,
  });

  const {
    perspectives,
    selectedPerspective,
    perspectiveDraft,
    setPerspectiveDraft,
    isMining,
    isSavingPerspective,
    setSelectedPerspectiveId,
    savePerspectiveProfile,
    deletePerspectiveProfile,
    runPerspectiveInterpretation,
    savePerspectiveDraft,
  } = useMineFlow({
    language,
    selectedRailOriginals,
    mineSourceDisabledReason,
    addActivity,
    setKnowledge,
    setSelectedKnowledgeId,
    setLibraryRailBucket,
    refreshLibraries,
  });

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

  const selectedKnowledge = useMemo(
    () => knowledge.find((item) => item.id === selectedKnowledgeId),
    [knowledge, selectedKnowledgeId],
  );

  useEffect(() => {
    if (!selectedKnowledge || selectedKnowledge.body) return;
    const loadKnowledge = selectedKnowledge.backendId
      ? libraryApi.readKnowledge(selectedKnowledge.backendId)
      : selectedKnowledge.markdownPath && selectedKnowledge.library
        ? libraryApi.readLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath)
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

  const filteredMaterials = useMemo(() => materials, [materials]);
  const filteredLearningQueue = useMemo(() => learningQueue, [learningQueue]);
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
          saved = await libraryApi.updateKnowledge(selectedKnowledge.backendId, trimmed);
        } else if (selectedKnowledge.markdownPath && selectedKnowledge.library) {
          saved = await libraryApi.updateLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath, trimmed);
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
        await libraryApi.deleteLibraryFile(item.library, item.markdownPath);
        movedCount += 1;
      }

      if (backendIds.length) {
        const result = await libraryApi.deleteKnowledge(backendIds);
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
    <ResponsiveKnowledgeRail
      summary={`${t("library.list")} · ${t(`library.bucket.${libraryRailBucket}`)}`}
      count={libraryRailKnowledge.length}
    >
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
    </ResponsiveKnowledgeRail>
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
            onSaveStrategies={saveWriterStrategies}
            onGenerateDraft={generateWriterDraft}
            onRevise={reviseWriterProject}
            onSuggestImages={suggestWriterImages}
            onGenerateImages={generateWriterImages}
            onRetryImageItems={retryWriterImageItems}
            onFormat={formatWriterProject}
            onSanitizePublishHtml={sanitizeWriterPublishHtml}
            onConfirmDesign={confirmWriterDesign}
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
  const localRunningCount =
    Number(Boolean(collectInputBusy)) +
    Number(isCollectingReadable) +
    Number(isSavingRawDraft) +
    Number(isLearning) +
    Number(isMining) +
    Number(isSavingPerspective) +
    Number(isWriting) +
    activities.filter((event) => event.status === "running").length;
  const runningCount = activeJobCount + localRunningCount;
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      onAuthContextChange({
        deploymentMode: authContext.deploymentMode,
        authenticated: false,
        user: null,
        workspace: null,
      });
    }
  }, [authContext.deploymentMode, onAuthContextChange]);

  return (
    <>
      <AppShell
        appName={t("app.name")}
        appSubtitle={t("app.subtitle")}
        navItems={navItems}
        activeId={activeWorkspace}
        activeTitle={workspaceLabel(t, activeWorkspace)}
        activeDescription={activeItem.description}
        queueLabel={t("topbar.queue")}
        queueStatus={runningCount > 0 ? `${runningCount}` : t("topbar.ready")}
        onOpenQueue={openJobCenter}
        authContext={authContext}
        onLogout={logout}
        onOpenUserAdmin={() => setIsUserAdminOpen(true)}
        onSelect={selectWorkspace}
      >
        {content}
      </AppShell>
      <UserAdminPanel
        authContext={authContext}
        isOpen={isUserAdminOpen}
        onClose={() => setIsUserAdminOpen(false)}
      />
      <JobCenter
        jobs={jobs}
        isOpen={isJobCenterOpen}
        isLoading={isJobsLoading}
        error={jobsError}
        onClose={closeJobCenter}
        onRefresh={refreshJobs}
        onCancel={cancelJob}
      />
    </>
  );
}

export default function App() {
  return (
    <AuthGate>
      {({ context, onContextChange }) => (
        <WorkbenchApp authContext={context} onAuthContextChange={onContextChange} />
      )}
    </AuthGate>
  );
}

function ResponsiveKnowledgeRail({ summary, count, children }: { summary: string; count: number; children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <aside className={isOpen ? "responsive-knowledge-rail mobile-open" : "responsive-knowledge-rail"}>
      <button
        className="mobile-knowledge-rail-toggle"
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span>{summary}</span>
        <strong>{count}</strong>
      </button>
      <div className="knowledge-rail-content">{children}</div>
    </aside>
  );
}


