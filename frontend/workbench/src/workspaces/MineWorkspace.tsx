import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { KnowledgeItem, PerspectiveDraft, PerspectiveProfile } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "../components/EmptyState";

const emptyProfile: PerspectiveProfile = {
  id: "",
  name: "",
  positioning: "",
  coreGoal: "",
  stance: "",
};

export function MineWorkspace({
  t,
  language,
  perspectives,
  selectedPerspective,
  selectedSources,
  draft,
  isRunning,
  isSaving,
  disabledReason,
  rightRail,
  onSelectPerspective,
  onSavePerspective,
  onDeletePerspective,
  onRunInterpretation,
  onUpdateDraft,
  onSaveDraft,
}: {
  t: Translator;
  language: "zh" | "en";
  perspectives: PerspectiveProfile[];
  selectedPerspective?: PerspectiveProfile;
  selectedSources: KnowledgeItem[];
  draft?: PerspectiveDraft;
  isRunning: boolean;
  isSaving: boolean;
  disabledReason: string;
  rightRail: ReactNode;
  onSelectPerspective: (id: string) => void;
  onSavePerspective: (profile: PerspectiveProfile) => Promise<void>;
  onDeletePerspective: (id: string) => Promise<void>;
  onRunInterpretation: () => void;
  onUpdateDraft: (draft: PerspectiveDraft | undefined) => void;
  onSaveDraft: () => void;
}) {
  const [editing, setEditing] = useState<PerspectiveProfile>(selectedPerspective ?? emptyProfile);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isProfileSaving, setIsProfileSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (isEditorOpen) return;
    setEditing(selectedPerspective ?? emptyProfile);
  }, [isEditorOpen, selectedPerspective]);

  const canSaveProfile = useMemo(
    () => Boolean(editing.name.trim() && editing.positioning.trim() && editing.coreGoal.trim() && editing.stance.trim()),
    [editing],
  );

  const draftTitle = draft?.title.trim() || (language === "zh" ? "未命名视角解读" : "Untitled perspective interpretation");
  const canSaveDraft = Boolean(draft?.markdown.trim()) && !isSaving;

  const updateEditing = (updates: Partial<PerspectiveProfile>) => {
    setEditing((current) => ({ ...current, ...updates }));
  };

  const createNewProfile = () => {
    setEditing({
      ...emptyProfile,
      id: "",
      name: language === "zh" ? "自定义视角" : "Custom lens",
    });
    setIsEditorOpen(true);
  };

  const editProfile = (profile: PerspectiveProfile) => {
    setEditing(profile);
    setIsEditorOpen(true);
  };

  const saveProfile = async () => {
    if (!canSaveProfile) return;
    setIsProfileSaving(true);
    try {
      await onSavePerspective({
        ...editing,
        name: editing.name.trim(),
        positioning: editing.positioning.trim(),
        coreGoal: editing.coreGoal.trim(),
        stance: editing.stance.trim(),
      });
      setIsEditorOpen(false);
    } finally {
      setIsProfileSaving(false);
    }
  };

  const deleteProfile = async () => {
    if (!editing.id || editing.readonly) return;
    setIsDeleting(true);
    try {
      await onDeletePerspective(editing.id);
      setIsEditorOpen(false);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section className="workspace-layout mine-layout">
      <div className="workspace-main mine-workspace-main">
        <aside className="content-panel mine-profile-panel">
          <div className="panel-heading-row">
            <div>
              <span>{t("mine.profile.manage")}</span>
              <h2>{t("mine.profile.title")}</h2>
            </div>
            <button className="secondary-button" type="button" onClick={createNewProfile}>
              {t("mine.profile.new")}
            </button>
          </div>

          <div className="perspective-list" aria-label={t("mine.profile.list")}>
            {perspectives.map((item) => (
              <div className={item.id === selectedPerspective?.id ? "perspective-row selected" : "perspective-row"} key={item.id}>
                <button className="perspective-select" type="button" onClick={() => onSelectPerspective(item.id)}>
                  <strong>{item.name}</strong>
                </button>
                <button className="secondary-button perspective-edit-button" type="button" onClick={() => editProfile(item)}>
                  {t("mine.profile.edit")}
                </button>
              </div>
            ))}
          </div>

          {isEditorOpen ? (
            <div className="modal-backdrop" role="presentation" onMouseDown={() => setIsEditorOpen(false)}>
              <section
                className="modal-panel perspective-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="perspective-editor-title"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <div className="panel-heading-row">
                  <div>
                    <span>{t("mine.profile.manage")}</span>
                    <h2 id="perspective-editor-title">{editing.id ? t("mine.profile.editTitle") : t("mine.profile.newTitle")}</h2>
                  </div>
                  <button className="secondary-button" type="button" onClick={() => setIsEditorOpen(false)}>
                    {t("common.close")}
                  </button>
                </div>
                <div className="perspective-editor">
                  <label>
                    <span>{t("mine.profile.name")}</span>
                    <input value={editing.name} onChange={(event) => updateEditing({ name: event.target.value })} />
                  </label>
                  <label>
                    <span>{t("mine.profile.positioning")}</span>
                    <textarea value={editing.positioning} onChange={(event) => updateEditing({ positioning: event.target.value })} />
                  </label>
                  <label>
                    <span>{t("mine.profile.goal")}</span>
                    <textarea value={editing.coreGoal} onChange={(event) => updateEditing({ coreGoal: event.target.value })} />
                  </label>
                  <label>
                    <span>{t("mine.profile.stance")}</span>
                    <textarea value={editing.stance} onChange={(event) => updateEditing({ stance: event.target.value })} />
                  </label>
                  <div className="library-editor-actions">
                    <button className="primary-cta" type="button" disabled={!canSaveProfile || isProfileSaving} onClick={saveProfile}>
                      {isProfileSaving ? t("common.loading") : t("mine.profile.save")}
                    </button>
                    <button
                      className="secondary-button danger-button"
                      type="button"
                      disabled={!editing.id || editing.readonly || isDeleting}
                      onClick={deleteProfile}
                      title={editing.readonly ? t("mine.profile.deleteReadonly") : undefined}
                    >
                      {isDeleting ? t("common.loading") : t("mine.profile.delete")}
                    </button>
                  </div>
                  {!canSaveProfile ? <p className="disabled-reason">{t("mine.profile.required")}</p> : null}
                </div>
              </section>
            </div>
          ) : null}
        </aside>

        <main className="content-panel mine-interpret-panel">
          <div className="panel-heading-row">
            <div>
              <span>{t("common.primary")}</span>
              <h2>{t("mine.interpret.title")}</h2>
              <p>{t("mine.interpret.body")}</p>
            </div>
            <button
              className="primary-cta"
              type="button"
              disabled={Boolean(disabledReason) || !selectedPerspective || isRunning}
              onClick={onRunInterpretation}
            >
              {isRunning ? t("common.loading") : t("mine.interpret.run")}
            </button>
          </div>
          {disabledReason ? <p className="disabled-reason">{disabledReason}</p> : null}

          <section className="mine-source-strip" aria-label={t("mine.sources")}>
            {selectedSources.length ? (
              selectedSources.map((item) => (
                <article key={item.id}>
                  <strong>{item.title}</strong>
                  <span>{item.markdownPath}</span>
                </article>
              ))
            ) : (
              <EmptyState title={t("mine.sources.empty")} body={t("mine.sources.empty.body")} />
            )}
          </section>

          {draft ? (
            <section className="knowledge-draft-editor">
              <label>
                <span>{t("library.title")}</span>
                <input value={draftTitle} onChange={(event) => onUpdateDraft({ ...draft, title: event.target.value })} />
              </label>
              <label>
                <span>{t("library.content")}</span>
                <textarea
                  className="article-editor-large"
                  value={draft.markdown}
                  onChange={(event) => onUpdateDraft({ ...draft, markdown: event.target.value })}
                />
              </label>
              <div className="library-editor-actions">
                <button className="primary-cta" type="button" disabled={!canSaveDraft} onClick={onSaveDraft}>
                  {isSaving ? t("common.loading") : t("mine.interpret.save")}
                </button>
              </div>
            </section>
          ) : (
            <EmptyState title={t("mine.draft.empty")} body={t("mine.draft.empty.body")} />
          )}
        </main>
      </div>

      {rightRail}
    </section>
  );
}
