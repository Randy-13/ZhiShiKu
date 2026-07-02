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
        const linkMeta = buildLinkMeta(item, t);
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
              {linkMeta.length ? (
                <div className="object-row-meta">
                  {linkMeta.map((meta) => (
                    <StatusBadge key={`${item.id}-${meta.label}`} tone={meta.tone}>
                      {meta.label}
                    </StatusBadge>
                  ))}
                </div>
              ) : null}
              {item.progressMessage ? <small className="object-row-progress">{item.progressMessage}</small> : null}
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


function buildLinkMeta(item: SourceMaterial, t: Translator) {
  if (item.type !== "link") return [] as Array<{ label: string; tone: "done" | "idle" | "error" | "muted" }>;
  const meta: Array<{ label: string; tone: "done" | "idle" | "error" | "muted" }> = [];
  if (item.linkType) {
    meta.push({
      label: `${t("collect.meta.type")}: ${linkTypeLabel(t, item.linkType)}`,
      tone: "muted",
    });
  }
  if (item.extractionStrategy) {
    meta.push({
      label: `${t("collect.meta.strategy")}: ${strategyLabel(t, item.extractionStrategy)}`,
      tone: item.extractionStrategy === "manual_review" ? "idle" : "done",
    });
  }
  if (item.accessStatus) {
    meta.push({
      label: `${t("collect.meta.access")}: ${accessStatusLabel(t, item.accessStatus)}`,
      tone: accessStatusTone(item.accessStatus),
    });
  }
  return meta;
}

function strategyLabel(t: Translator, strategy: string) {
  const labels: Record<string, string> = {
    agent_reach_jina_reader: t("collect.strategy.agentReach"),
    static_html_fetch: t("collect.strategy.staticFetch"),
    direct_html_fetch: t("collect.strategy.staticFetch"),
    reuse_logged_in_browser: t("collect.strategy.edgeSession"),
    edge_authorization: t("collect.strategy.edgeSession"),
    manual_review: t("collect.strategy.manualReview"),
    specialized_platform_parser: t("collect.strategy.platformParser"),
  };
  return labels[strategy] ?? strategy;
}

function accessStatusLabel(t: Translator, status: string) {
  const labels: Record<string, string> = {
    accessible: t("collect.access.accessible"),
    login_or_restricted: t("collect.access.loginRequired"),
    unreachable: t("collect.access.unreachable"),
  };
  return labels[status] ?? status;
}

function linkTypeLabel(t: Translator, linkType: string) {
  const labels: Record<string, string> = {
    article: t("collect.linkType.article"),
    webpage: t("collect.linkType.article"),
    platform_wechat: t("collect.linkType.wechat"),
    platform_wechat_channels: t("collect.linkType.wechatChannels"),
    platform_bilibili: t("collect.linkType.bilibili"),
    platform_xiaohongshu: t("collect.linkType.xiaohongshu"),
    platform_douyin: t("collect.linkType.douyin"),
    login_required: t("collect.linkType.loginRequired"),
    unreachable: t("collect.linkType.unreachable"),
  };
  return labels[linkType] ?? linkType;
}

function accessStatusTone(status: string): "done" | "idle" | "error" {
  if (status === "accessible") return "done";
  if (status === "login_or_restricted") return "idle";
  return "error";
}
