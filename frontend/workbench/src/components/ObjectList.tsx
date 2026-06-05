import { materialStatusLabel, materialTypeLabel } from "../i18n";
import type { SourceMaterial } from "../domain";
import { StatusBadge } from "./StatusBadge";

type Translator = ReturnType<typeof import("../i18n").createTranslator>;

export function ObjectList({
  items,
  selectedId,
  checkedIds,
  t,
  onSelect,
  onToggleCheck,
}: {
  items: SourceMaterial[];
  selectedId?: string;
  checkedIds?: string[];
  t: Translator;
  onSelect: (id: string) => void;
  onToggleCheck?: (id: string) => void;
}) {
  return (
    <div className="object-list">
      {items.map((item) => {
        const checked = checkedIds?.includes(item.id) ?? false;
        return (
          <div className={item.id === selectedId ? "object-row selected" : "object-row"} key={item.id}>
            {onToggleCheck ? (
              <input
                aria-label={`${t("common.selected")} ${item.title}`}
                checked={checked}
                type="checkbox"
                onChange={() => onToggleCheck(item.id)}
              />
            ) : (
              <span>{materialTypeLabel(t, item.type)}</span>
            )}
            <button type="button" className="object-row-main" onClick={() => onSelect(item.id)}>
              <span>{materialTypeLabel(t, item.type)}</span>
              <strong>{item.title}</strong>
              {item.error ? <small className="object-row-error">{item.error}</small> : null}
              {item.note ? <small className="object-row-note">{item.note}</small> : null}
            </button>
            <StatusBadge tone={item.status === "error" ? "error" : item.status === "ready" ? "done" : "idle"}>
              {materialStatusLabel(t, item.status)}
            </StatusBadge>
          </div>
        );
      })}
    </div>
  );
}
