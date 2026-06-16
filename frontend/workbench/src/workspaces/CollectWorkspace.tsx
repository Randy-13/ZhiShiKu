import { useEffect, useRef, useState } from "react";
import type { ClipboardEvent, DragEvent, ReactNode } from "react";
import type { ReadableDraftInput } from "../api";
import type { MaterialType, SourceMaterial } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { ObjectList } from "../components/ObjectList";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";

export type CollectInputBusy = "image" | "file" | "media" | "link" | "browser-link" | "paste-image" | null;

const panes: Array<{ id: MaterialType; labelKey: string; helper: string }> = [
  { id: "text", labelKey: "collect.type.text", helper: "键入、粘贴或临时记录" },
  { id: "image", labelKey: "collect.type.image", helper: "拖入截图或 Ctrl+V 粘贴" },
  { id: "file", labelKey: "collect.type.file", helper: "PDF、Word、Markdown、TXT" },
  { id: "media", labelKey: "collect.type.media", helper: "本地音视频或字幕" },
  { id: "link", labelKey: "collect.type.link", helper: "网页、Bilibili、抖音、研报地址" },
];

export function CollectWorkspace({
  t,
  materials,
  selectedMaterial,
  readableDraft,
  isGeneratingReadable,
  isSavingReadable,
  inputBusy,
  rightRail,
  onSelectMaterial,
  onCreateMaterial,
  onUploadFiles,
  onPasteImages,
  onResolveLinks,
  onBrowserExtractLink,
  onGenerateReadableDraft,
  onUpdateReadableDraft,
  onSaveReadableDraft,
  onDeleteMaterials,
}: {
  t: Translator;
  materials: SourceMaterial[];
  selectedMaterial?: SourceMaterial;
  readableDraft?: ReadableDraftInput;
  isGeneratingReadable: boolean;
  isSavingReadable: boolean;
  inputBusy: CollectInputBusy;
  rightRail: ReactNode;
  onSelectMaterial: (id: string) => void;
  onCreateMaterial: (item: Pick<SourceMaterial, "type" | "title" | "source">) => void;
  onUploadFiles: (type: MaterialType, files: File[]) => void;
  onPasteImages: (files: File[]) => void;
  onResolveLinks: (urls: string[]) => void;
  onBrowserExtractLink: (id: string) => void;
  onGenerateReadableDraft: (ids?: string[]) => void;
  onUpdateReadableDraft: (draft: ReadableDraftInput) => void;
  onSaveReadableDraft: () => void;
  onDeleteMaterials: (ids: string[]) => void;
}) {
  const imageInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);
  const [activePane, setActivePane] = useState<MaterialType>("text");
  const [textValue, setTextValue] = useState("");
  const [linkValue, setLinkValue] = useState("");
  const [checkedMaterialIds, setCheckedMaterialIds] = useState<string[]>([]);
  const isInputBusy = inputBusy !== null;
  const busyMessage =
    inputBusy === "link"
      ? "正在加入链接材料..."
      : inputBusy === "browser-link"
        ? t("collect.browserExtractBusy")
      : inputBusy === "image"
        ? "正在上传图片..."
        : inputBusy === "paste-image"
          ? "正在加入粘贴图片..."
          : inputBusy === "file"
            ? "正在上传文件..."
            : inputBusy === "media"
              ? "正在上传音视频..."
              : "";

  useEffect(() => {
    const visibleIds = new Set(materials.map((item) => item.id));
    setCheckedMaterialIds((current) => current.filter((id) => visibleIds.has(id)));
  }, [materials]);

  const selectedIds = checkedMaterialIds.length ? checkedMaterialIds : selectedMaterial ? [selectedMaterial.id] : [];
  const browserExtractTarget =
    selectedIds.length === 1 ? materials.find((item) => item.id === selectedIds[0] && isBrowserExtractableLink(item)) : undefined;

  const handleDrop = (event: DragEvent<HTMLElement>, type: MaterialType) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files ?? []);
    if (!files.length || isInputBusy) return;
    onUploadFiles(type, files);
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files ?? []).filter((file) => file.type.startsWith("image/"));
    if (!files.length || isInputBusy) return;
    event.preventDefault();
    onPasteImages(files);
  };

  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("collect.input")}
        >
          <div className="material-type-grid" role="tablist" aria-label={t("collect.input")}>
            {panes.map((pane) => (
              <button
                className={activePane === pane.id ? "material-type-card active" : "material-type-card"}
                type="button"
                role="tab"
                aria-selected={activePane === pane.id}
                key={pane.id}
                onClick={() => setActivePane(pane.id)}
              >
                <strong>{t(pane.labelKey)}</strong>
                <span>{pane.helper}</span>
              </button>
            ))}
          </div>
          {busyMessage ? (
            <div className="collector-busy" role="status" aria-live="polite">
              <span className="collector-busy-dot" />
              <span>{busyMessage}</span>
            </div>
          ) : null}

          {activePane === "text" ? (
            <section className="collector-pane">
              <label>
                <span>文本材料</span>
                <textarea
                  value={textValue}
                  rows={6}
                  placeholder="粘贴或输入一段材料，可以是网页摘录、会议笔记、临时观点。"
                  onChange={(event) => setTextValue(event.target.value)}
                />
              </label>
              <div className="action-row">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={isInputBusy}
                  onClick={() => {
                    const value = textValue.trim();
                    if (!value) return;
                    onCreateMaterial({ type: "text", title: value.slice(0, 32), source: value });
                    setTextValue("");
                  }}
                >
                  加入文本材料
                </button>
                <button className="secondary-button" type="button" onClick={() => setTextValue("")}>
                  清空文本
                </button>
              </div>
            </section>
          ) : null}

          {activePane === "image" ? (
            <section className="collector-pane">
              <Dropzone
                title="拖入一组截图"
                body="也可以点击选择文件；粘贴框支持连续 Ctrl+V 粘贴截图。"
                disabled={isInputBusy}
                onClick={() => imageInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "image")}
              />
              <textarea
                className="paste-target"
                rows={3}
                placeholder="点击这里后直接 Ctrl+V 粘贴截图。"
                onPaste={handlePaste}
                readOnly
                disabled={isInputBusy}
              />
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                multiple
                hidden
                disabled={isInputBusy}
                onChange={(event) => {
                  const files = Array.from(event.currentTarget.files ?? []);
                  if (files.length) onUploadFiles("image", files);
                  event.currentTarget.value = "";
                }}
              />
            </section>
          ) : null}

          {activePane === "file" ? (
            <section className="collector-pane">
              <Dropzone
                title="拖入一组文件"
                body="支持 Markdown、TXT、Word .docx、PDF；上传后会读取页数和默认范围。"
                disabled={isInputBusy}
                onClick={() => documentInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "file")}
              />
              <input
                ref={documentInputRef}
                type="file"
                accept=".md,.markdown,.txt,.docx,.pdf"
                multiple
                hidden
                disabled={isInputBusy}
                onChange={(event) => {
                  const files = Array.from(event.currentTarget.files ?? []);
                  if (files.length) onUploadFiles("file", files);
                  event.currentTarget.value = "";
                }}
              />
            </section>
          ) : null}

          {activePane === "media" ? (
            <section className="collector-pane">
              <Dropzone
                title="拖入本地音视频或字幕"
                body="支持 mp3、m4a、wav、mp4、mov、mkv、webm、srt、vtt、ass。"
                disabled={isInputBusy}
                onClick={() => mediaInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "media")}
              />
              <input
                ref={mediaInputRef}
                type="file"
                accept=".mp3,.m4a,.wav,.aac,.flac,.mp4,.mov,.mkv,.webm,.srt,.vtt,.ass"
                multiple
                hidden
                disabled={isInputBusy}
                onChange={(event) => {
                  const files = Array.from(event.currentTarget.files ?? []);
                  if (files.length) onUploadFiles("media", files);
                  event.currentTarget.value = "";
                }}
              />
            </section>
          ) : null}

          {activePane === "link" ? (
            <section className="collector-pane">
              <label>
                <span>链接材料</span>
                <textarea
                  value={linkValue}
                  rows={5}
                  placeholder="每行一个链接，例如网页、Bilibili、抖音、研报地址。"
                  onChange={(event) => setLinkValue(event.target.value)}
                />
              </label>
              <div className="action-row">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={isInputBusy}
                  onClick={() => {
                    const urls = linkValue
                      .split(/\n+/)
                      .map((item) => item.trim())
                      .filter(Boolean);
                    if (!urls.length) return;
                    onResolveLinks(urls);
                    setLinkValue("");
                  }}
                >
                  加入链接材料
                </button>
                <button className="secondary-button" type="button" disabled={isInputBusy} onClick={() => setLinkValue("")}>
                  清空链接
                </button>
              </div>
            </section>
          ) : null}
        </PrimaryTaskPanel>

        <section className="content-panel">
          <h2>{t("collect.queue")}</h2>
          {materials.length === 0 ? (
            <EmptyState title={t("collect.empty")} />
          ) : (
            <>
              <div className="queue-toolbar">
                <span>
                  {t("collect.selectedCount")} {checkedMaterialIds.length} / {materials.length}
                </span>
                <div className="action-row">
                  <button className="secondary-button" type="button" onClick={() => setCheckedMaterialIds(materials.map((item) => item.id))}>
                    {t("common.selectAll")}
                  </button>
                  <button className="secondary-button" type="button" onClick={() => setCheckedMaterialIds([])}>
                    {t("common.clearSelection")}
                  </button>
                  <button className="secondary-button" type="button" disabled={!checkedMaterialIds.length} onClick={() => onDeleteMaterials(checkedMaterialIds)}>
                    {t("collect.deleteSelected")}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!browserExtractTarget || inputBusy === "browser-link"}
                    title={browserExtractTarget ? "" : t("collect.browserExtractDisabled")}
                    onClick={() => {
                      if (!browserExtractTarget) return;
                      onBrowserExtractLink(browserExtractTarget.id);
                      setCheckedMaterialIds([]);
                    }}
                  >
                    {inputBusy === "browser-link" ? t("collect.browserExtracting") : t("collect.browserExtract")}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!selectedIds.length || isGeneratingReadable}
                    onClick={() => {
                      onGenerateReadableDraft(selectedIds);
                      setCheckedMaterialIds([]);
                    }}
                  >
                    {isGeneratingReadable ? t("collect.generatingOriginal") : t("collect.generateOriginal")}
                  </button>
                </div>
              </div>
              <ObjectList
                items={materials}
                selectedId={selectedMaterial?.id}
                checkedIds={checkedMaterialIds}
                t={t}
                onSelect={onSelectMaterial}
                onToggleCheck={(id) =>
                  setCheckedMaterialIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
                }
              />
            </>
          )}
        </section>

        <section className="content-panel">
          <div className="section-heading">
            <h2>{t("collect.preview")}</h2>
            <button
              className="secondary-button"
              type="button"
              disabled={!readableDraft || isSavingReadable}
              onClick={onSaveReadableDraft}
            >
              {isSavingReadable ? t("collect.savingOriginal") : t("collect.addToOriginalLibrary")}
            </button>
          </div>
          {readableDraft ? (
            <div className="knowledge-draft-editor">
              <label>
                <span>{t("collect.draft.title")}</span>
                <input
                  value={readableDraft.title}
                  onChange={(event) => onUpdateReadableDraft({ ...readableDraft, title: event.target.value })}
                />
              </label>
              <label>
                <span>{t("collect.draft.note")}</span>
                <input
                  value={readableDraft.note}
                  onChange={(event) => onUpdateReadableDraft({ ...readableDraft, note: event.target.value })}
                />
              </label>
              <label>
                <span>{t("collect.draft.body")}</span>
                <textarea
                  className="article-editor-large"
                  value={readableDraft.body}
                  onChange={(event) => onUpdateReadableDraft({ ...readableDraft, body: event.target.value })}
                />
              </label>
            </div>
          ) : (
            <EmptyState title={t("collect.preview.empty")} />
          )}
        </section>
      </div>

      {rightRail}
    </section>
  );
}

function isBrowserExtractableLink(item: SourceMaterial) {
  if (item.type !== "link") return false;
  return item.linkType === "public_webpage" || item.linkType === "dynamic_webpage" || item.linkType === "browser_webpage";
}

function Dropzone({
  title,
  body,
  disabled = false,
  onClick,
  onDrop,
}: {
  title: string;
  body: string;
  disabled?: boolean;
  onClick: () => void;
  onDrop: (event: DragEvent<HTMLElement>) => void;
}) {
  return (
    <button
      className="collector-dropzone"
      type="button"
      disabled={disabled}
      onClick={onClick}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
    >
      <span className="drop-icon">+</span>
      <strong>{title}</strong>
      <small>{body}</small>
    </button>
  );
}
