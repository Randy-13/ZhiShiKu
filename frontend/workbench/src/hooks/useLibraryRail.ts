import { useMemo, useState } from "react";
import type { KnowledgeItem, Language } from "../domain";
import type { LibraryBucket } from "../components/KnowledgeLibraryRail";

type Translator = (key: string) => string;

export function useLibraryRail(knowledge: KnowledgeItem[], language: Language, t: Translator) {
  const [libraryRailBucket, setLibraryRailBucket] = useState<LibraryBucket>("original");
  const [libraryRailQuery, setLibraryRailQuery] = useState("");
  const [libraryRailCheckedIds, setLibraryRailCheckedIds] = useState<string[]>([]);

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

  return {
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
  };
}
