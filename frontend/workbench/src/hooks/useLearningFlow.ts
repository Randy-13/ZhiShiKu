import { useCallback, useMemo, useState } from "react";
import { collectApi, libraryApi } from "../api";
import type { LibraryBucket } from "../components/KnowledgeLibraryRail";
import type { ActivityEvent, KnowledgeDraft, KnowledgeItem, Language, SourceMaterial } from "../domain";
import { uid } from "../utils/uid";

type AddActivity = (event: Omit<ActivityEvent, "id" | "time">) => void;

type Options = {
  language: Language;
  selectedRailOriginals: KnowledgeItem[];
  addToLearningQueueDisabledReason: string;
  addActivity: AddActivity;
  setKnowledge: React.Dispatch<React.SetStateAction<KnowledgeItem[]>>;
  setSelectedKnowledgeId: (id: string) => void;
  setLibraryRailBucket: (bucket: LibraryBucket) => void;
  refreshLibraries: () => Promise<KnowledgeItem[]>;
};

export function useLearningFlow({
  language,
  selectedRailOriginals,
  addToLearningQueueDisabledReason,
  addActivity,
  setKnowledge,
  setSelectedKnowledgeId,
  setLibraryRailBucket,
  refreshLibraries,
}: Options) {
  const [learningQueue, setLearningQueue] = useState<SourceMaterial[]>([]);
  const [selectedLearningMaterialId, setSelectedLearningMaterialId] = useState<string>();
  const [knowledgeDraft, setKnowledgeDraft] = useState<KnowledgeDraft>();
  const [isLearning, setIsLearning] = useState(false);

  const selectedLearningMaterial = useMemo(
    () => learningQueue.find((item) => item.id === selectedLearningMaterialId) ?? learningQueue[0],
    [learningQueue, selectedLearningMaterialId],
  );

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

  const generateKnowledge = useCallback(
    async (ids: string[]) => {
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
        const refined = await collectApi.refineKnowledgeCluster(rawPaths);
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
    },
    [addActivity, language, learningQueue],
  );

  const commitKnowledgeDraft = useCallback(async () => {
    if (!knowledgeDraft) return;
    const isFocusDraft = knowledgeDraft.sourceIds.length > 0;
    let item: KnowledgeItem;
    try {
      item = isFocusDraft
        ? await collectApi.saveFocusFile(knowledgeDraft.sourceIds, knowledgeDraft.body, knowledgeDraft.title)
        : await libraryApi.commitKnowledgeDraft(knowledgeDraft);
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
  }, [addActivity, knowledgeDraft, language, learningQueue, refreshLibraries, setKnowledge, setLibraryRailBucket, setSelectedKnowledgeId]);

  return {
    learningQueue,
    selectedLearningMaterial,
    knowledgeDraft,
    setKnowledgeDraft,
    isLearning,
    setSelectedLearningMaterialId,
    addSelectedOriginalsToLearningQueue,
    generateKnowledge,
    commitKnowledgeDraft,
  };
}

function markdownTitle(markdown?: string) {
  if (!markdown) return "";
  const line = markdown.split(/\r?\n/).find((item) => item.trim().startsWith("# "));
  return line ? line.replace(/^#\s+/, "").trim() : "";
}
