import { useCallback, useEffect, useMemo, useState } from "react";
import { mineApi } from "../apiMine";
import type { ExpansionExternalSource, PerspectiveExpansionPreview } from "../apiMine";
import type { LibraryBucket } from "../components/KnowledgeLibraryRail";
import type { ActivityEvent, KnowledgeItem, Language, PerspectiveDraft, PerspectiveProfile } from "../domain";

type AddActivity = (event: Omit<ActivityEvent, "id" | "time">) => void;

type Options = {
  language: Language;
  selectedRailOriginals: KnowledgeItem[];
  mineSourceDisabledReason: string;
  addActivity: AddActivity;
  setKnowledge: React.Dispatch<React.SetStateAction<KnowledgeItem[]>>;
  setSelectedKnowledgeId: (id: string) => void;
  setLibraryRailBucket: (bucket: LibraryBucket) => void;
  refreshLibraries: () => Promise<KnowledgeItem[]>;
};

export function useMineFlow({
  language,
  selectedRailOriginals,
  mineSourceDisabledReason,
  addActivity,
  setKnowledge,
  setSelectedKnowledgeId,
  setLibraryRailBucket,
  refreshLibraries,
}: Options) {
  const [perspectives, setPerspectives] = useState<PerspectiveProfile[]>([]);
  const [selectedPerspectiveId, setSelectedPerspectiveId] = useState<string>();
  const [perspectiveDraft, setPerspectiveDraft] = useState<PerspectiveDraft>();
  const [isMining, setIsMining] = useState(false);
  const [isExpandingPerspective, setIsExpandingPerspective] = useState(false);
  const [isSavingPerspective, setIsSavingPerspective] = useState(false);

  const selectedPerspective = useMemo(
    () => perspectives.find((item) => item.id === selectedPerspectiveId) ?? perspectives[0],
    [perspectives, selectedPerspectiveId],
  );

  const refreshPerspectiveProfiles = useCallback(async (nextSelectedId?: string) => {
    const items = await mineApi.listPerspectiveProfiles();
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

  const savePerspectiveProfile = useCallback(
    async (profile: PerspectiveProfile) => {
      try {
        const items = await mineApi.savePerspectiveProfile(profile);
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
        const items = await mineApi.deletePerspectiveProfile(profileId);
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
      const draft = await mineApi.interpretPerspective(selectedRailOriginals, selectedPerspective);
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
      const item = await mineApi.savePerspectiveFile(selectedRailOriginals, selectedPerspective, markdown, perspectiveDraft.title);
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
  }, [addActivity, language, perspectiveDraft, refreshLibraries, selectedPerspective, selectedRailOriginals, setKnowledge, setLibraryRailBucket, setSelectedKnowledgeId]);

  const runPerspectiveExpansion = useCallback(async (instruction = "") => {
    if (!selectedPerspective || mineSourceDisabledReason || !perspectiveDraft?.markdown.trim()) return;
    setIsExpandingPerspective(true);
    try {
      const draft = await mineApi.expandPerspective(selectedRailOriginals, selectedPerspective, perspectiveDraft.markdown, instruction);
      setPerspectiveDraft(draft);
      addActivity({
        title: draft.title,
        detail:
          language === "zh"
            ? instruction.trim()
              ? `拓展解读已按命令生成：${instruction.trim()}`
              : "拓展解读已生成，已用官方优先的外部证据覆盖当前草稿。"
            : "Expanded interpretation generated and applied to the current draft.",
        workspace: "mine",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "拓展解读失败" : "Expansion failed",
        detail: error instanceof Error ? error.message : "Perspective expansion API failed",
        workspace: "mine",
        status: "error",
      });
    } finally {
      setIsExpandingPerspective(false);
    }
  }, [addActivity, language, mineSourceDisabledReason, perspectiveDraft, selectedPerspective, selectedRailOriginals]);

  const previewPerspectiveExpansion = useCallback(async (instruction = ""): Promise<PerspectiveExpansionPreview | undefined> => {
    if (!selectedPerspective || mineSourceDisabledReason || !perspectiveDraft?.markdown.trim()) return undefined;
    setIsExpandingPerspective(true);
    try {
      const preview = await mineApi.previewPerspectiveExpansion(
        selectedRailOriginals,
        selectedPerspective,
        perspectiveDraft.markdown,
        instruction,
      );
      addActivity({
        title: language === "zh" ? "拓展来源预览完成" : "Expansion sources previewed",
        detail:
          language === "zh"
            ? `找到 ${preview.externalSources.length} 个可读外部来源。`
            : `${preview.externalSources.length} readable external source(s) found.`,
        workspace: "mine",
        status: "done",
      });
      return preview;
    } catch (error) {
      addActivity({
        title: language === "zh" ? "拓展来源检索失败" : "Expansion source search failed",
        detail: error instanceof Error ? error.message : "Perspective expansion preview API failed",
        workspace: "mine",
        status: "error",
      });
      throw error;
    } finally {
      setIsExpandingPerspective(false);
    }
  }, [addActivity, language, mineSourceDisabledReason, perspectiveDraft, selectedPerspective, selectedRailOriginals]);

  const mergePerspectiveExpansion = useCallback(async (instruction = "", externalSources: ExpansionExternalSource[]) => {
    if (!selectedPerspective || mineSourceDisabledReason || !perspectiveDraft?.markdown.trim()) return;
    setIsExpandingPerspective(true);
    try {
      const draft = await mineApi.mergePerspectiveExpansion(
        selectedRailOriginals,
        selectedPerspective,
        perspectiveDraft.markdown,
        externalSources,
        instruction,
      );
      setPerspectiveDraft(draft);
      addActivity({
        title: draft.title,
        detail:
          language === "zh"
            ? `已将 ${externalSources.length} 个外部来源智能融入当前草稿。`
            : `${externalSources.length} external source(s) merged into the current draft.`,
        workspace: "mine",
        status: "done",
      });
    } catch (error) {
      addActivity({
        title: language === "zh" ? "拓展解读融入失败" : "Expansion merge failed",
        detail: error instanceof Error ? error.message : "Perspective expansion merge API failed",
        workspace: "mine",
        status: "error",
      });
      throw error;
    } finally {
      setIsExpandingPerspective(false);
    }
  }, [addActivity, language, mineSourceDisabledReason, perspectiveDraft, selectedPerspective, selectedRailOriginals]);

  return {
    perspectives,
    selectedPerspective,
    perspectiveDraft,
    setPerspectiveDraft,
    isMining,
    isExpandingPerspective,
    isSavingPerspective,
    setSelectedPerspectiveId,
    savePerspectiveProfile,
    deletePerspectiveProfile,
    runPerspectiveInterpretation,
    runPerspectiveExpansion,
    previewPerspectiveExpansion,
    mergePerspectiveExpansion,
    savePerspectiveDraft,
  };
}
