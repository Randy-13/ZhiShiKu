import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { KnowledgeDraft, SourceMaterial } from "../domain";
import type { Translator } from "../i18n";
import { materialStatusLabel } from "../i18n";
import { EmptyState } from "../components/EmptyState";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";

export function LearnWorkspace({
  t,
  queue,
  selectedMaterial,
  knowledgeDraft,
  isRunning,
  rightRail,
  addToQueueDisabledReason,
  onSelectMaterial,
  onAddSelectedOriginalsToQueue,
  onGenerateKnowledge,
  onUpdateKnowledgeDraft,
  onCommitKnowledgeDraft,
}: {
  t: Translator;
  queue: SourceMaterial[];
  selectedMaterial?: SourceMaterial;
  knowledgeDraft?: KnowledgeDraft;
  isRunning: boolean;
  rightRail: ReactNode;
  addToQueueDisabledReason: string;
  onSelectMaterial: (id: string) => void;
  onAddSelectedOriginalsToQueue: () => void;
  onGenerateKnowledge: (ids: string[]) => void;
  onUpdateKnowledgeDraft: (draft: KnowledgeDraft) => void;
  onCommitKnowledgeDraft: () => void;
}) {
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const selectedIds = checkedIds.length ? checkedIds : selectedMaterial ? [selectedMaterial.id] : [];
  const primaryAction = knowledgeDraft ? t("learn.commitFocus") : t("learn.primaryFocus");
  const primaryDisabledReason = knowledgeDraft ? undefined : t("learn.needSelect");

  useEffect(() => {
    const visibleIds = new Set(queue.map((item) => item.id));
    setCheckedIds((current) => current.filter((id) => visibleIds.has(id)));
  }, [queue]);

  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("learn.queue")}
          action={isRunning ? t("learn.running") : primaryAction}
          disabled={(knowledgeDraft ? false : !selectedIds.length) || isRunning}
          disabledReason={primaryDisabledReason}
          onAction={() => {
            if (knowledgeDraft) {
              onCommitKnowledgeDraft();
              return;
            }
            onGenerateKnowledge(selectedIds);
          }}
        >
          <div className="panel-heading-row">
            <div>
              <span>{t("learn.selectedCount")} {selectedIds.length} / {queue.length}</span>
            </div>
            <button
              className="secondary-button"
              type="button"
              disabled={Boolean(addToQueueDisabledReason) || isRunning}
              onClick={onAddSelectedOriginalsToQueue}
            >
              {t("learn.addToQueue")}
            </button>
          </div>
          {addToQueueDisabledReason ? <p className="disabled-reason">{addToQueueDisabledReason}</p> : null}
          <div className="queue-toolbar">
            <span>{t("learn.next")}</span>
            <div className="action-row">
              <button className="secondary-button" type="button" disabled={!queue.length} onClick={() => setCheckedIds(queue.map((item) => item.id))}>
                {t("common.selectAll")}
              </button>
              <button className="secondary-button" type="button" disabled={!checkedIds.length} onClick={() => setCheckedIds([])}>
                {t("common.clearSelection")}
              </button>
            </div>
          </div>
          <div className="queue-list">
            {queue.length === 0 ? (
              <EmptyState title={t("learn.empty")} />
            ) : (
              queue.map((item) => (
                <div className={selectedMaterial?.id === item.id ? "queue-row selected" : "queue-row"} key={item.id}>
                  <input
                    className="queue-check"
                    aria-label={item.title}
                    checked={checkedIds.includes(item.id)}
                    type="checkbox"
                    onChange={() => setCheckedIds((current) => (current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id]))}
                  />
                  <button type="button" className="queue-row-main" onClick={() => onSelectMaterial(item.id)}>
                    <strong>{item.title}</strong>
                  </button>
                  <span>{materialStatusLabel(t, item.status)}</span>
                </div>
              ))
            )}
          </div>
        </PrimaryTaskPanel>

        <section className="content-panel">
          <div className="section-heading">
            <h2>{t("learn.previewFocus")}</h2>
          </div>
          {knowledgeDraft ? (
            <div className="learn-preview-panel">
              {isRunning ? <p className="disabled-reason">{t("learn.commitFocusDisabled.running")}</p> : null}
              <KnowledgeDraftEditor t={t} draft={knowledgeDraft} onChange={onUpdateKnowledgeDraft} />
            </div>
          ) : (
            <div className="learn-preview-panel">
              <EmptyState title={t("learn.preview.empty")} />
            </div>
          )}
        </section>
      </div>

      {rightRail}
    </section>
  );
}

function KnowledgeDraftEditor({ t, draft, onChange }: { t: Translator; draft: KnowledgeDraft; onChange: (draft: KnowledgeDraft) => void }) {
  return (
    <div className="knowledge-draft-editor">
      <label>
        <span>{t("learn.draft.title")}</span>
        <input value={draft.title} onChange={(event) => onChange({ ...draft, title: event.target.value })} />
      </label>
      <label>
        <span>{t("learn.draft.note")}</span>
        <input value={draft.note} onChange={(event) => onChange({ ...draft, note: event.target.value })} />
      </label>
      <label>
        <span>{t("learn.draft.body")}</span>
        <textarea className="article-editor-large" value={draft.body} onChange={(event) => onChange({ ...draft, body: event.target.value })} />
      </label>
    </div>
  );
}
