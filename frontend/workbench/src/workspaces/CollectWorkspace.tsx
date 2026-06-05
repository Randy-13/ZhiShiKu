import { useEffect, useRef, useState } from "react";
import type { ClipboardEvent, DragEvent, ReactNode } from "react";
import type { MaterialType, SourceMaterial } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { ObjectList } from "../components/ObjectList";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";

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
  rightRail,
  onSelectMaterial,
  onCreateMaterial,
  onUploadFiles,
  onPasteImages,
  onResolveLinks,
  onSaveToOriginalLibrary,
  onDeleteMaterials,
}: {
  t: Translator;
  materials: SourceMaterial[];
  selectedMaterial?: SourceMaterial;
  rightRail: ReactNode;
  onSelectMaterial: (id: string) => void;
  onCreateMaterial: (item: Pick<SourceMaterial, "type" | "title" | "source">) => void;
  onUploadFiles: (type: MaterialType, files: File[]) => void;
  onPasteImages: (files: File[]) => void;
  onResolveLinks: (urls: string[]) => void;
  onSaveToOriginalLibrary: (ids?: string[]) => void;
  onDeleteMaterials: (ids: string[]) => void;
}) {
  const imageInputRef = useRef<HTMLInputElement>(null);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);
  const [activePane, setActivePane] = useState<MaterialType>("text");
  const [textValue, setTextValue] = useState("");
  const [linkValue, setLinkValue] = useState("");
  const [checkedMaterialIds, setCheckedMaterialIds] = useState<string[]>([]);

  useEffect(() => {
    const visibleIds = new Set(materials.map((item) => item.id));
    setCheckedMaterialIds((current) => current.filter((id) => visibleIds.has(id)));
  }, [materials]);

  const handleDrop = (event: DragEvent<HTMLElement>, type: MaterialType) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files ?? []);
    if (!files.length) return;
    onUploadFiles(type, files);
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files ?? []).filter((file) => file.type.startsWith("image/"));
    if (!files.length) return;
    event.preventDefault();
    onPasteImages(files);
  };

  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("collect.input")}
          body={t("collect.body")}
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
                onClick={() => imageInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "image")}
              />
              <textarea
                className="paste-target"
                rows={3}
                placeholder="点击这里后直接 Ctrl+V 粘贴截图。"
                onPaste={handlePaste}
                readOnly
              />
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                multiple
                hidden
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
                onClick={() => documentInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "file")}
              />
              <input
                ref={documentInputRef}
                type="file"
                accept=".md,.markdown,.txt,.docx,.pdf"
                multiple
                hidden
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
                onClick={() => mediaInputRef.current?.click()}
                onDrop={(event) => handleDrop(event, "media")}
              />
              <input
                ref={mediaInputRef}
                type="file"
                accept=".mp3,.m4a,.wav,.aac,.flac,.mp4,.mov,.mkv,.webm,.srt,.vtt,.ass"
                multiple
                hidden
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
                <button className="secondary-button" type="button" onClick={() => setLinkValue("")}>
                  清空链接
                </button>
              </div>
            </section>
          ) : null}
        </PrimaryTaskPanel>

        <section className="content-panel">
          <h2>{t("collect.queue")}</h2>
          {materials.length === 0 ? (
            <EmptyState title={t("collect.empty")} body={t("collect.empty.body")} />
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
                    disabled={!materials.some((item) => item.status !== "error")}
                    onClick={() => {
                      onSaveToOriginalLibrary(materials.filter((item) => item.status !== "error").map((item) => item.id));
                      setCheckedMaterialIds([]);
                    }}
                  >
                    {t("collect.saveAllOriginals")}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!checkedMaterialIds.length}
                    onClick={() => {
                      onSaveToOriginalLibrary(checkedMaterialIds);
                      setCheckedMaterialIds([]);
                    }}
                  >
                    {t("collect.saveSelectedOriginals")}
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
      </div>

      {rightRail}
    </section>
  );
}

function Dropzone({
  title,
  body,
  onClick,
  onDrop,
}: {
  title: string;
  body: string;
  onClick: () => void;
  onDrop: (event: DragEvent<HTMLElement>) => void;
}) {
  return (
    <button
      className="collector-dropzone"
      type="button"
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
