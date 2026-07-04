import { useCallback, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { collectApi, materialFromUpload } from "../api";
import type { ReadableDraftInput } from "../api";
import type { ActivityEvent, KnowledgeItem, Language, MaterialType, SourceMaterial, TextExtractionMode } from "../domain";
import type { CollectInputBusy } from "../workspaces/CollectWorkspace";
import { uid } from "../utils/uid";

type AddActivity = (event: Omit<ActivityEvent, "id" | "time">) => void;

type Options = {
  language: Language;
  textExtractionMode: TextExtractionMode;
  addActivity: AddActivity;
  refreshLibraries: () => Promise<KnowledgeItem[]>;
  setSelectedKnowledgeId: (id: string) => void;
};

type CreateMaterialInput = Pick<SourceMaterial, "type" | "title" | "source"> & {
  backendId?: number;
  error?: string;
  note?: string;
  linkType?: string;
  extractionStrategy?: string;
  accessStatus?: string;
};

export function useCollectFlow({ language, textExtractionMode, addActivity, refreshLibraries, setSelectedKnowledgeId }: Options) {
  const [materials, setMaterials] = useState<SourceMaterial[]>([]);
  const [selectedMaterialId, setSelectedMaterialId] = useState<string>();
  const [collectDraft, setCollectDraft] = useState<ReadableDraftInput>();
  const [collectInputBusy, setCollectInputBusy] = useState<CollectInputBusy>(null);
  const [isCollectingReadable, setIsCollectingReadable] = useState(false);
  const [isSavingRawDraft, setIsSavingRawDraft] = useState(false);

  const selectedMaterial = useMemo(
    () => materials.find((item) => item.id === selectedMaterialId),
    [materials, selectedMaterialId],
  );

  const insertMaterial = useCallback(
    (material: SourceMaterial) => {
      setMaterials((current) => [material, ...current.filter((item) => item.id !== material.id)]);
      setSelectedMaterialId(material.id);
      addActivity({ title: material.title, detail: "素材已进入收集队列", workspace: "collect", status: material.status === "error" ? "error" : "done" });
    },
    [addActivity],
  );

  const insertMaterials = useCallback(
    (nextMaterials: SourceMaterial[]) => {
      if (!nextMaterials.length) return;
      const nextIds = new Set(nextMaterials.map((item) => item.id));
      setMaterials((current) => [...nextMaterials, ...current.filter((item) => !nextIds.has(item.id))]);
      setSelectedMaterialId(nextMaterials[0].id);
      nextMaterials.forEach((material) => {
        addActivity({ title: material.title, detail: "素材已进入收集队列", workspace: "collect", status: material.status === "error" ? "error" : "done" });
      });
    },
    [addActivity],
  );

  const createMaterial = useCallback(
    (item: CreateMaterialInput) => {
      insertMaterial({
        id: uid("material"),
        type: item.type,
        title: item.title,
        source: item.source,
        status: item.error ? "error" : "captured",
        backendId: item.backendId,
        error: item.error,
        note: item.note,
        linkType: item.linkType,
        extractionStrategy: item.extractionStrategy,
        accessStatus: item.accessStatus,
      });
    },
    [insertMaterial],
  );

  const uploadFiles = useCallback(
    async (type: MaterialType, files: File[]) => {
      if (!files.length) return;
      setCollectInputBusy(type);
      try {
        const uploaded = await collectApi.uploadMaterial(type, files);
        if (!uploaded.length) throw new Error("旧后端没有返回上传结果");
        let enriched = uploaded;
        if (type === "file") {
          const ids = uploaded.map((item) => item.id).filter((id): id is number => typeof id === "number");
          const pageInfo = await collectApi.loadFilePageInfo(ids).catch(() => []);
          enriched = uploaded.map((item) => ({ ...item, ...(pageInfo.find((info) => info.id === item.id) ?? {}) }));
        }
        insertMaterials(enriched.map((item, index) => materialFromUpload(type, item, files[index]?.name ?? "上传素材")));
      } catch (error) {
        insertMaterials(
          files.map((file) => ({
            id: uid("material"),
            type,
            title: file.name,
            source: file.name,
            status: "error" as const,
            error: error instanceof Error ? error.message : "上传旧后端失败",
          })),
        );
      } finally {
        setCollectInputBusy(null);
      }
    },
    [insertMaterials],
  );

  const pasteImages = useCallback(
    async (files: File[]) => {
      if (!files.length) return;
      setCollectInputBusy("paste-image");
      try {
        const uploaded = await collectApi.uploadPastedImages(files);
        if (!uploaded.length) throw new Error("旧后端没有返回粘贴截图结果");
        insertMaterials(uploaded.map((item, index) => materialFromUpload("image", item, files[index]?.name ?? "粘贴截图")));
      } catch (error) {
        const detail = error instanceof Error ? error.message : "粘贴截图上传失败";
        insertMaterials(
          files.map((file) => ({
            id: uid("material"),
            type: "image",
            title: file.name || "本地暂存截图",
            source: "clipboard",
            status: "captured" as const,
            note: `后端上传失败，已作为本地暂存素材继续：${detail}`,
          })),
        );
        addActivity({ title: "粘贴截图后端上传失败", detail, workspace: "collect", status: "error" });
      } finally {
        setCollectInputBusy(null);
      }
    },
    [addActivity, insertMaterials],
  );

  const resolveLinks = useCallback(
    async (urls: string[]) => {
      if (!urls.length) return;
      setCollectInputBusy("link");
      const existing = new Set(materials.map((item) => item.source));
      try {
        for (const url of urls) {
          if (existing.has(url)) continue;
          if (looksLikeMediaUrl(url)) {
            try {
              const resolved = await collectApi.resolveMediaUrl(url);
              if (!resolved) throw new Error("Legacy backend did not return media metadata.");
              const material = materialFromUpload("media", resolved, url);
              insertMaterial(material);
              if (material.backendId) {
                collectApi.transcribeMedia([material.backendId]).catch(() => undefined);
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
            const inspected = await collectApi.inspectLink(url);
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
              linkType: inspected?.link_type,
              extractionStrategy: inspected?.extraction_strategy,
              accessStatus: inspected?.access_status,
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
      const selectedItems = materials.filter((item) => idSet.has(item.id) && canRetryReadableExtraction(item));
      if (!selectedItems.length) return;

      setIsCollectingReadable(true);
      setMaterials((current) =>
        current.map((item) =>
          idSet.has(item.id)
            ? { ...item, status: "learning", error: undefined, progressMessage: readableProgressMessage(language, 0, selectedItems.length) }
            : item,
        ),
      );

      try {
        const batchResult =
          selectedItems.length > 1 && selectedItems.some((item) => item.type === "image")
            ? await createReadableDraftWithItemProgress({
                items: selectedItems,
                parserMode: textExtractionMode,
                language,
                setMaterials,
              })
            : { draft: await collectApi.createReadableDraft(selectedItems, textExtractionMode), successfulIds: selectedItems.map((item) => item.id) };
        const draft = batchResult.draft;
        setCollectDraft(draft);
        const successfulIds = new Set(batchResult.successfulIds);
        setMaterials((current) =>
          current.map((item) =>
            idSet.has(item.id) && successfulIds.has(item.id)
              ? { ...item, status: "ready", error: undefined, progressMessage: undefined }
              : item,
          ),
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
          current.map((item) => (idSet.has(item.id) ? { ...item, status: "error", error: detail, progressMessage: undefined } : item)),
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
      const item = await collectApi.saveRawDraft(collectDraft);
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
  }, [addActivity, collectDraft, language, refreshLibraries, setSelectedKnowledgeId]);

  const deleteMaterials = useCallback(
    (ids: string[]) => {
      if (!ids.length) return;
      const idSet = new Set(ids);
      setMaterials((current) => current.filter((item) => !idSet.has(item.id)));
      setSelectedMaterialId((current) => (current && idSet.has(current) ? undefined : current));
      addActivity({ title: "删除素材", detail: `已从素材队列删除 ${ids.length} 个素材`, workspace: "collect", status: "done" });
    },
    [addActivity],
  );

  return {
    materials,
    selectedMaterialId,
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
    resolveLinks,
    generateCollectReadableDraft,
    saveCollectDraftToOriginalLibrary,
    deleteMaterials,
  };
}


type ReadableProgressOptions = {
  items: SourceMaterial[];
  parserMode: TextExtractionMode;
  language: Language;
  setMaterials: Dispatch<SetStateAction<SourceMaterial[]>>;
};

async function createReadableDraftWithItemProgress({ items, parserMode, language, setMaterials }: ReadableProgressOptions) {
  const drafts: ReadableDraftInput[] = [];
  const successfulIds: string[] = [];
  const errors: string[] = [];

  for (const [index, item] of items.entries()) {
    setMaterials((current) =>
      current.map((currentItem) =>
        currentItem.id === item.id
          ? { ...currentItem, status: "learning", error: undefined, progressMessage: readableProgressMessage(language, index + 1, items.length) }
          : currentItem,
      ),
    );

    try {
      const draft = await collectApi.createReadableDraft([item], parserMode);
      drafts.push(draft);
      successfulIds.push(item.id);
      setMaterials((current) =>
        current.map((currentItem) =>
          currentItem.id === item.id
            ? { ...currentItem, status: "ready", error: undefined, progressMessage: undefined }
            : currentItem,
        ),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Readable original generation failed";
      errors.push(`${item.title}: ${message}`);
      setMaterials((current) =>
        current.map((currentItem) =>
          currentItem.id === item.id
            ? { ...currentItem, status: "error", error: message, progressMessage: undefined }
            : currentItem,
        ),
      );
    }
  }

  if (!drafts.length) {
    throw new Error(errors[0] || "Readable original generation failed");
  }

  return { draft: mergeReadableDrafts(drafts, items, errors, language), successfulIds };
}

function mergeReadableDrafts(drafts: ReadableDraftInput[], items: SourceMaterial[], errors: string[], language: Language): ReadableDraftInput {
  if (drafts.length === 1) return drafts[0];
  const title = mergedReadableDraftTitle(drafts, items, language);
  const failedNote = errors.length ? (language === "zh" ? `\u90e8\u5206\u5931\u8d25\uff1a${errors.join("\uff1b")}` : `Partial failures: ${errors.join("; ")}`) : "";
  return {
    title,
    note: [language === "zh" ? `\u5df2\u5408\u5e76 ${drafts.length} \u6761\u7d20\u6750\u3002` : `Merged ${drafts.length} materials.`, failedNote].filter(Boolean).join(" "),
    body: drafts.map((draft, index) => `## ${index + 1}. ${draft.title}\n\n${draft.body}`).join("\n\n---\n\n"),
    sourceIds: drafts.flatMap((draft) => draft.sourceIds),
    materialType: drafts[0]?.materialType ?? "screenshot",
    source: items.map((item) => item.source || item.title).filter(Boolean).join("; "),
  };
}

function mergedReadableDraftTitle(drafts: ReadableDraftInput[], items: SourceMaterial[], language: Language) {
  const fallbackTitle = language === "zh" ? `\u5408\u5e76\u539f\u6587\uff08${drafts.length}\u6761\uff09` : `Merged original ${drafts.length} items`;
  const title = firstDistinctSpecificTitle([
    ...drafts.map((draft) => draft.title),
    ...items.map((item) => item.title),
  ]);
  if (!title) return fallbackTitle;
  if (drafts.length <= 1) return title;
  return language === "zh" ? `${title}\u7b49${drafts.length}\u6761\u539f\u6587` : `${title} and ${drafts.length - 1} more original${drafts.length > 2 ? "s" : ""}`;
}

function firstDistinctSpecificTitle(titles: string[]) {
  const seen = new Set<string>();
  for (const rawTitle of titles) {
    const title = rawTitle.trim();
    if (!title || seen.has(title) || isGenericReadableTitle(title)) continue;
    seen.add(title);
    return title.length > 48 ? `${title.slice(0, 48)}...` : title;
  }
  return "";
}

function isGenericReadableTitle(title: string) {
  const normalized = title.trim().toLowerCase();
  return (
    !normalized ||
    normalized.startsWith("merged original") ||
    normalized.includes("\u5408\u5e76\u539f\u6587") ||
    normalized.includes("\u622a\u56fe\u539f\u6599") ||
    normalized.includes("\u672a\u547d\u540d\u539f\u6587") ||
    normalized === "readable document"
  );
}

function readableProgressMessage(language: Language, current: number, total: number) {
  if (total <= 1) return language === "zh" ? "\u6b63\u5728\u63d0\u53d6\u539f\u6587..." : "Extracting readable original...";
  if (current <= 0) return language === "zh" ? `\u7b49\u5f85\u63d0\u53d6\uff0c\u5171 ${total} \u9879` : `Waiting to extract ${total} items`;
  return language === "zh" ? `\u6b63\u5728\u63d0\u53d6\u7b2c ${current}/${total} \u9879` : `Extracting ${current}/${total}`;
}
function canRetryReadableExtraction(item: SourceMaterial) {
  if (item.type === "text") return true;
  if (item.type === "link") return true;
  if (item.type === "media" && item.source) return true;
  return typeof item.backendId === "number";
}
function looksLikeMediaUrl(url: string) {
  return /bilibili|douyin|youtube|youtu\.be|vimeo|xiaohongshu|xhslink|video|mp4|m3u8|audio/i.test(url);
}
