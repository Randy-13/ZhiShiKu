import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ExpansionExternalSource, PerspectiveExpansionPreview } from "../apiMine";
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

const interpretationSections = [
  "mine.interpret.section.stance",
  "mine.interpret.section.extract",
  "mine.interpret.section.analysis",
  "mine.interpret.section.risks",
  "mine.interpret.section.conclusion",
] as const;

export function MineWorkspace({
  t,
  language,
  perspectives,
  selectedPerspective,
  selectedSources,
  draft,
  isRunning,
  isExpanding,
  isSaving,
  disabledReason,
  rightRail,
  onSelectPerspective,
  onSavePerspective,
  onDeletePerspective,
  onRunInterpretation,
  onPreviewExpansion,
  onMergeExpansion,
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
  isExpanding: boolean;
  isSaving: boolean;
  disabledReason: string;
  rightRail: ReactNode;
  onSelectPerspective: (id: string) => void;
  onSavePerspective: (profile: PerspectiveProfile) => Promise<void>;
  onDeletePerspective: (id: string) => Promise<void>;
  onRunInterpretation: () => void;
  onPreviewExpansion: (instruction?: string) => Promise<PerspectiveExpansionPreview | undefined>;
  onMergeExpansion: (instruction: string | undefined, externalSources: ExpansionExternalSource[]) => Promise<void>;
  onUpdateDraft: (draft: PerspectiveDraft | undefined) => void;
  onSaveDraft: () => void;
}) {
  const [editing, setEditing] = useState<PerspectiveProfile>(selectedPerspective ?? emptyProfile);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isProfileSaving, setIsProfileSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [draftTextarea, setDraftTextarea] = useState<HTMLTextAreaElement | null>(null);
  const [isExpansionDialogOpen, setIsExpansionDialogOpen] = useState(false);
  const [expansionCommand, setExpansionCommand] = useState("");
  const [expansionPreview, setExpansionPreview] = useState<PerspectiveExpansionPreview>();
  const [selectedExpansionUrls, setSelectedExpansionUrls] = useState<Set<string>>(() => new Set());
  const [expansionError, setExpansionError] = useState("");

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
  const canExpandDraft = Boolean(draft?.markdown.trim()) && !isRunning && !isExpanding && !isSaving && !disabledReason && Boolean(selectedPerspective);
  const selectedExpansionSources = useMemo(
    () => expansionPreview?.externalSources.filter((source) => selectedExpansionUrls.has(source.url || source.relative_path)) ?? [],
    [expansionPreview, selectedExpansionUrls],
  );

  const jumpToInterpretationSection = (label: string) => {
    if (!draftTextarea || !draft?.markdown) return;
    const index = draft.markdown.indexOf(label);
    draftTextarea.focus();
    if (index >= 0) {
      draftTextarea.setSelectionRange(index, index);
      draftTextarea.scrollTop = (index / Math.max(draft.markdown.length, 1)) * draftTextarea.scrollHeight;
    }
  };

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

  const openExpansionDialog = () => {
    setExpansionPreview(undefined);
    setSelectedExpansionUrls(new Set());
    setExpansionError("");
    setIsExpansionDialogOpen(true);
  };

  const previewExpansionSources = async () => {
    if (!canExpandDraft) return;
    setExpansionError("");
    try {
      const preview = await onPreviewExpansion(expansionCommand.trim());
      setExpansionPreview(preview);
      setSelectedExpansionUrls(new Set((preview?.externalSources ?? []).map((source) => source.url || source.relative_path).filter(Boolean)));
    } catch (error) {
      setExpansionError(error instanceof Error ? error.message : t("mine.expand.dialog.searchFailed"));
    }
  };

  const toggleExpansionSource = (source: ExpansionExternalSource) => {
    const key = source.url || source.relative_path;
    setSelectedExpansionUrls((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const mergeExpansionSources = async () => {
    if (!canExpandDraft || !selectedExpansionSources.length) return;
    setExpansionError("");
    try {
      await onMergeExpansion(expansionCommand.trim(), selectedExpansionSources);
      setIsExpansionDialogOpen(false);
    } catch (error) {
      setExpansionError(error instanceof Error ? error.message : t("mine.expand.dialog.mergeFailed"));
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
              <EmptyState title={t("mine.sources.empty")} />
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
                <div className="interpret-section-nav" aria-label={t("mine.interpret.sections")}>
                  {interpretationSections.map((key) => {
                    const label = t(key);
                    const isPresent = draft.markdown.includes(label);
                    return (
                      <button
                        className={isPresent ? "section-anchor present" : "section-anchor"}
                        type="button"
                        key={key}
                        onClick={() => jumpToInterpretationSection(label)}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
                <textarea
                  ref={setDraftTextarea}
                  className="article-editor-large"
                  value={draft.markdown}
                  onChange={(event) => onUpdateDraft({ ...draft, markdown: event.target.value })}
                />
              </label>
              <div className="mine-draft-actions">
                <button className="secondary-button" type="button" disabled={!canExpandDraft} onClick={openExpansionDialog}>
                  {isExpanding ? t("mine.interpret.expanding") : t("mine.interpret.expand")}
                </button>
                <button className="primary-cta" type="button" disabled={!canSaveDraft} onClick={onSaveDraft}>
                  {isSaving ? t("common.loading") : t("mine.interpret.save")}
                </button>
              </div>
            </section>
          ) : (
            <EmptyState title={t("mine.draft.empty")} />
          )}
          {isExpansionDialogOpen ? (
            <div className="modal-backdrop" role="presentation" onMouseDown={() => setIsExpansionDialogOpen(false)}>
              <section
                className="modal-panel expansion-command-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="expansion-command-title"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <div className="panel-heading-row">
                  <div>
                    <span>{t("mine.interpret.expand")}</span>
                    <h2 id="expansion-command-title">{t("mine.expand.dialog.title")}</h2>
                  </div>
                  <button className="secondary-button" type="button" onClick={() => setIsExpansionDialogOpen(false)}>
                    {t("common.close")}
                  </button>
                </div>
                <label className="expansion-command-field">
                  <span>{t("mine.expand.dialog.command")}</span>
                  <textarea
                    value={expansionCommand}
                    placeholder={t("mine.expand.dialog.placeholder")}
                    onChange={(event) => setExpansionCommand(event.target.value)}
                  />
                </label>
                {expansionError ? <p className="disabled-reason">{expansionError}</p> : null}
                {expansionPreview ? (
                  <section className="expansion-preview-panel" aria-label={t("mine.expand.dialog.preview")}>
                    <div className="expansion-preview-heading">
                      <strong>{t("mine.expand.dialog.preview")}</strong>
                      <span>
                        {expansionPreview.externalSources.length
                          ? t("mine.expand.dialog.readableCount").replace("{count}", String(expansionPreview.externalSources.length))
                          : t("mine.expand.dialog.noSources")}
                      </span>
                    </div>
                    {expansionPreview.externalSources.length ? (
                      <div className="expansion-source-list">
                        {expansionPreview.externalSources.map((source, index) => {
                          const key = source.url || source.relative_path || `${source.title}-${index}`;
                          const selected = selectedExpansionUrls.has(source.url || source.relative_path);
                          return (
                            <label className="expansion-source-row" key={key}>
                              <input type="checkbox" checked={selected} onChange={() => toggleExpansionSource(source)} />
                              <span className="expansion-source-body">
                                <span className="expansion-source-title">
                                  <strong>{source.title || source.url}</strong>
                                  <em>{source.authority}</em>
                                </span>
                                <span className="expansion-source-url">{source.url || source.relative_path}</span>
                                <span className="expansion-source-snippet">{source.snippet || source.text.slice(0, 420)}</span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="disabled-reason">{expansionPreview.warning || t("mine.expand.dialog.noSourcesDetail")}</p>
                    )}
                    {expansionPreview.searchReport?.errors?.length ? (
                      <details className="expansion-diagnostics">
                        <summary>{t("mine.expand.dialog.diagnostics")}</summary>
                        <ul>
                          {expansionPreview.searchReport.errors.map((error) => (
                            <li key={error}>{error}</li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </section>
                ) : null}
                <div className="mine-draft-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      setExpansionCommand("");
                      setExpansionPreview(undefined);
                      setSelectedExpansionUrls(new Set());
                      setExpansionError("");
                    }}
                    disabled={isExpanding}
                  >
                    {t("mine.expand.dialog.clear")}
                  </button>
                  <button className="secondary-button" type="button" disabled={!canExpandDraft} onClick={previewExpansionSources}>
                    {isExpanding ? t("mine.expand.dialog.searching") : t("mine.expand.dialog.search")}
                  </button>
                  <button className="primary-cta" type="button" disabled={!canExpandDraft || !selectedExpansionSources.length} onClick={mergeExpansionSources}>
                    {isExpanding ? t("mine.interpret.expanding") : t("mine.expand.dialog.merge")}
                  </button>
                </div>
              </section>
            </div>
          ) : null}
        </main>
      </div>

      {rightRail}
    </section>
  );
}
