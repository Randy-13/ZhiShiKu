import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { KnowledgeItem } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";

type KnowledgeEditDraft = {
  title: string;
  note: string;
  body: string;
};

type LibraryBucket = "original" | "focus" | "perspective";

export function LibraryWorkspace({
  t,
  activeBucket,
  rightRail,
  selectedKnowledge,
  onSaveKnowledge,
}: {
  t: Translator;
  activeBucket: LibraryBucket;
  rightRail: ReactNode;
  selectedKnowledge?: KnowledgeItem;
  onSaveKnowledge: (draft: KnowledgeEditDraft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<KnowledgeEditDraft>(() => fromKnowledge(selectedKnowledge));
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    setDraft(fromKnowledge(selectedKnowledge));
    setSaveError("");
  }, [selectedKnowledge]);

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

  return (
    <section className="workspace-layout library-editor-layout">
      <div className="workspace-main">
        <section className="content-panel library-editor-panel">
          <div className="panel-heading-row">
            <div>
              <span>{t("common.primary")}</span>
              <h2>{t("library.editor")}</h2>
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
            <EmptyState title={t("library.editor.empty")} />
          )}
        </section>
      </div>

      {rightRail}
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
