import { useEffect, useMemo, useState } from "react";
import type { KnowledgeItem } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { RightContext } from "../shell/RightContext";

type KnowledgeEditDraft = {
  title: string;
  note: string;
  body: string;
};

type LibraryBucket = "original" | "focus" | "perspective";

const libraryBuckets: LibraryBucket[] = ["original", "focus", "perspective"];

export function LibraryWorkspace({
  t,
  knowledge,
  selectedKnowledge,
  onSelectKnowledge,
  onSaveKnowledge,
  onDeleteKnowledge,
}: {
  t: Translator;
  knowledge: KnowledgeItem[];
  selectedKnowledge?: KnowledgeItem;
  onSelectKnowledge: (id: string) => void;
  onSaveKnowledge: (draft: KnowledgeEditDraft) => Promise<void>;
  onDeleteKnowledge: (ids: string[]) => Promise<void>;
}) {
  const [activeBucket, setActiveBucket] = useState<LibraryBucket>("original");
  const [draft, setDraft] = useState<KnowledgeEditDraft>(() => fromKnowledge(selectedKnowledge));
  const [isSaving, setIsSaving] = useState(false);
  const [query, setQuery] = useState("");
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    setDraft(fromKnowledge(selectedKnowledge));
    setSaveError("");
  }, [selectedKnowledge]);

  useEffect(() => {
    setCheckedIds((current) => current.filter((id) => knowledge.some((item) => item.id === id)));
  }, [knowledge]);

  const activeLibraryLabel = t(`library.bucket.${activeBucket}`);
  const visibleKnowledge = useMemo(() => {
    const clean = query.trim().toLowerCase();
    const bucketItems = knowledge.filter((item) => (item.library ?? "focus") === activeBucket);
    if (!clean) return bucketItems;
    return bucketItems.filter((item) => `${item.title} ${item.note ?? ""} ${item.body}`.toLowerCase().includes(clean));
  }, [activeBucket, knowledge, query]);
  const deletionTargets = checkedIds.length ? checkedIds : selectedKnowledge ? [selectedKnowledge.id] : [];

  const isDirty = useMemo(() => {
    if (!selectedKnowledge) return false;
    return (
      draft.title !== selectedKnowledge.title ||
      draft.note !== (selectedKnowledge.note ?? "") ||
      draft.body !== selectedKnowledge.body
    );
  }, [draft, selectedKnowledge]);

  const canSave = Boolean(selectedKnowledge && draft.body.trim() && !isSaving && isDirty);

  async function handleSave() {
    if (!canSave) return;
    setIsSaving(true);
    setSaveError("");
    try {
      await onSaveKnowledge({ ...draft, body: stripRepeatedNoteQuotes(draft.body, draft.note) });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : t("library.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteSelected() {
    if (!deletionTargets.length || isDeleting) return;
    setIsDeleting(true);
    try {
      await onDeleteKnowledge(deletionTargets);
      setCheckedIds([]);
    } finally {
      setIsDeleting(false);
    }
  }

  function toggleChecked(id: string) {
    setCheckedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <section className="workspace-layout library-editor-layout">
      <div className="workspace-main">
        <section className="content-panel library-editor-panel">
          <div className="panel-heading-row">
            <div>
              <span>{t("common.primary")}</span>
              <h2>{t("library.editor")}</h2>
              <p>{t("library.body")}</p>
            </div>
          </div>

          {selectedKnowledge && (selectedKnowledge.library ?? "focus") === activeBucket ? (
            <div className="knowledge-draft-editor library-file-editor">
              <label>
                <span>{t("library.title")}</span>
                <input
                  value={draft.title}
                  onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                />
              </label>
              <label>
                <span>{t("library.note")}</span>
                <input
                  value={draft.note}
                  onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))}
                />
              </label>
              <label>
                <span>{t("library.content")}</span>
                <textarea
                  className="article-editor-large"
                  value={draft.body}
                  onChange={(event) => setDraft((current) => ({ ...current, body: event.target.value }))}
                />
              </label>

              <div className="library-editor-actions">
                <button className="primary-cta" type="button" disabled={!canSave} onClick={handleSave}>
                  <strong>{isSaving ? t("library.saving") : t("library.save")}</strong>
                </button>
              </div>

              {!selectedKnowledge.backendId ? <p className="disabled-reason">{t("library.localOnly")}</p> : null}
              {saveError ? <p className="disabled-reason">{saveError}</p> : null}
              {!isDirty ? <p className="hint">{t("library.noChanges")}</p> : null}
            </div>
          ) : (
            <EmptyState title={t("library.editor.empty")} body={t("library.needSelect")} />
          )}
        </section>
      </div>

      <RightContext title={t("library.list")}>
        <div className="library-bucket-tabs" role="tablist" aria-label={t("library.bucket.switcher")}>
          {libraryBuckets.map((bucket) => (
            <button
              key={bucket}
              type="button"
              role="tab"
              aria-selected={activeBucket === bucket}
              className={activeBucket === bucket ? "bucket-tab selected" : "bucket-tab"}
              onClick={() => setActiveBucket(bucket)}
            >
              {t(`library.bucket.${bucket}`)}
            </button>
          ))}
        </div>

        <div className="library-list-tools">
          <label>
            <span>{t("library.search.current")}</span>
            <input
              value={query}
              placeholder={t("library.search.placeholder")}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button
            className="secondary-button danger-button"
            type="button"
            disabled={!deletionTargets.length || isDeleting}
            onClick={handleDeleteSelected}
          >
            {isDeleting ? t("library.deleting") : t("library.deleteSelected")}
          </button>
        </div>

        {(
          visibleKnowledge.length === 0 && !query.trim() ? (
            <EmptyState title={t("library.empty")} body={t("library.empty.body")} />
          ) : visibleKnowledge.length === 0 ? (
            <EmptyState title={t("library.noMatches")} body={t("library.search.empty")} />
          ) : (
            <div className="knowledge-mini-list">
              {visibleKnowledge.map((item) => (
                <div
                  className={selectedKnowledge?.id === item.id ? "mini-knowledge-row selected" : "mini-knowledge-row"}
                  key={item.id}
                >
                  <input
                    type="checkbox"
                    checked={checkedIds.includes(item.id)}
                    aria-label={t("library.selectFile")}
                    onChange={() => toggleChecked(item.id)}
                  />
                  <button className="mini-knowledge-title-button" type="button" onClick={() => onSelectKnowledge(item.id)}>
                    <strong>{item.title}</strong>
                    <span className="mini-knowledge-meta">
                      {item.note ? <span className="mini-knowledge-note">{item.note}</span> : <span />}
                      {formatKnowledgeDate(item.createdAt || item.updatedAt) ? (
                        <small className="mini-knowledge-date">{formatKnowledgeDate(item.createdAt || item.updatedAt)}</small>
                      ) : null}
                    </span>
                  </button>
                </div>
              ))}
            </div>
          )
        )}
      </RightContext>
    </section>
  );
}

function fromKnowledge(item?: KnowledgeItem): KnowledgeEditDraft {
  return {
    title: item?.title ?? "",
    note: item?.note ?? "",
    body: stripRepeatedNoteQuotes(item?.body ?? "", item?.note ?? ""),
  };
}

function formatKnowledgeDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}

function stripRepeatedNoteQuotes(body: string, note: string) {
  const cleanNote = normalizeNote(note);
  if (!cleanNote) return body;
  const lines = body.split(/\r?\n/);
  let index = 0;
  let removed = false;
  while (index < lines.length) {
    while (index < lines.length && !lines[index].trim()) index += 1;
    if (index >= lines.length) break;
    const line = lines[index].trim();
    if (!line.startsWith(">")) break;
    const quote = normalizeNote(line.replace(/^>\s?/, ""));
    if (quote !== cleanNote) break;
    removed = true;
    index += 1;
  }
  return removed ? lines.slice(index).join("\n").replace(/^\n+/, "") : body;
}

function normalizeNote(value: string) {
  return value.replace(/\s+/g, "").trim();
}
