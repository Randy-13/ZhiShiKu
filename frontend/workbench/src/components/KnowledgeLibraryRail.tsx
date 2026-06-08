import { useMemo } from "react";
import type { KnowledgeItem } from "../domain";
import type { Translator } from "../i18n";
import { EmptyState } from "./EmptyState";
import { RightContext } from "../shell/RightContext";

export type LibraryBucket = "original" | "focus" | "perspective";

const libraryBuckets: LibraryBucket[] = ["original", "focus", "perspective"];

export function KnowledgeLibraryRail({
  t,
  knowledge,
  selectedKnowledge,
  mode = "manage",
  activeBucket,
  query,
  checkedIds,
  isDeleting,
  onBucketChange,
  onQueryChange,
  onCheckedIdsChange,
  onSelectKnowledge,
  onDeleteKnowledge,
}: {
  t: Translator;
  knowledge: KnowledgeItem[];
  selectedKnowledge?: KnowledgeItem;
  mode?: "manage";
  activeBucket: LibraryBucket;
  query: string;
  checkedIds: string[];
  isDeleting: boolean;
  onBucketChange: (bucket: LibraryBucket) => void;
  onQueryChange: (query: string) => void;
  onCheckedIdsChange: (ids: string[]) => void;
  onSelectKnowledge: (id: string) => void;
  onDeleteKnowledge: (ids: string[]) => Promise<void>;
}) {
  const activeLibraryLabel = t(`library.bucket.${activeBucket}`);
  const visibleKnowledge = useMemo(() => {
    const clean = query.trim().toLowerCase();
    if (!clean) return knowledge;
    return knowledge.filter((item) => `${item.title} ${item.note ?? ""} ${item.body}`.toLowerCase().includes(clean));
  }, [knowledge, query]);
  const currentLibraryIds = useMemo(() => new Set(knowledge.map((item) => item.id)), [knowledge]);
  const deletionTargets = mode === "manage" ? checkedIds.filter((id) => currentLibraryIds.has(id)) : [];

  function toggleChecked(id: string) {
    onCheckedIdsChange(checkedIds.includes(id) ? checkedIds.filter((item) => item !== id) : [...checkedIds, id]);
  }

  async function handleDeleteSelected() {
    if (!deletionTargets.length || isDeleting) return;
    await onDeleteKnowledge(deletionTargets);
    onCheckedIdsChange([]);
  }

  return (
    <RightContext title={t("library.list")}>
      <div className="library-bucket-tabs" role="tablist" aria-label={t("library.bucket.switcher")}>
        {libraryBuckets.map((bucket) => (
          <button
            key={bucket}
            type="button"
            role="tab"
            aria-selected={activeBucket === bucket}
            className={activeBucket === bucket ? "bucket-tab selected" : "bucket-tab"}
            onClick={() => onBucketChange(bucket)}
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
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
        {mode === "manage" ? (
          <button
            className="secondary-button danger-button"
            type="button"
            disabled={!deletionTargets.length || isDeleting}
            onClick={handleDeleteSelected}
          >
            {isDeleting ? t("library.deleting") : t("library.deleteSelected")}
          </button>
        ) : null}
      </div>

      {(
        knowledge.length === 0 ? (
          <EmptyState title={t("library.empty")} body={t("library.empty.body")} />
        ) : visibleKnowledge.length === 0 ? (
          <EmptyState title={t("library.noMatches")} body={t("library.search.empty")} />
        ) : (
          <div className="knowledge-mini-list">
            {visibleKnowledge.map((item) => (
              <div className={selectedKnowledge?.id === item.id ? "mini-knowledge-row selected" : "mini-knowledge-row"} key={item.id}>
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
  );
}

function formatKnowledgeDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}
