import type { ReactNode } from "react";
import type { ActivityEvent, Language, TextExtractionMode } from "../domain";
import type { Translator } from "../i18n";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";
import { StatusBadge } from "../components/StatusBadge";

export function SettingsWorkspace({
  t,
  language,
  textExtractionMode,
  activities,
  rightRail,
  onLanguageChange,
  onTextExtractionModeChange,
  onSave,
}: {
  t: Translator;
  language: Language;
  textExtractionMode: TextExtractionMode;
  activities: ActivityEvent[];
  rightRail: ReactNode;
  onLanguageChange: (language: Language) => void;
  onTextExtractionModeChange: (mode: TextExtractionMode) => void;
  onSave: () => void;
}) {
  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("settings.language")}
          body={t("settings.body")}
          action={t("settings.primary")}
          onAction={onSave}
        >
          <div className="input-row" role="group" aria-label={t("settings.language")}>
            <button className={language === "zh" ? "choice active" : "choice"} type="button" onClick={() => onLanguageChange("zh")}>
              {t("common.zh")}
            </button>
            <button className={language === "en" ? "choice active" : "choice"} type="button" onClick={() => onLanguageChange("en")}>
              {t("common.en")}
            </button>
          </div>
        </PrimaryTaskPanel>

        <section className="content-panel settings-grid">
          <div>
            <h2>{t("settings.api")}</h2>
            <p className="hint">{t("settings.api.body")}</p>
          </div>
          <div>
            <h2>{t("settings.storage")}</h2>
            <p className="hint">{t("settings.storage.body")}</p>
          </div>
          <div>
            <h2>{t("settings.extraction")}</h2>
            <p className="hint">{t("settings.extraction.body")}</p>
            <div className="input-row" role="group" aria-label={t("settings.extraction")}>
              <button className={textExtractionMode === "local_ocr" ? "choice active" : "choice"} type="button" onClick={() => onTextExtractionModeChange("local_ocr")}>
                {t("settings.extraction.local")}
              </button>
              <button className={textExtractionMode === "ai_vision" ? "choice active" : "choice"} type="button" onClick={() => onTextExtractionModeChange("ai_vision")}>
                {t("settings.extraction.api")}
              </button>
            </div>
          </div>
          <div>
            <h2>{t("settings.dependencies")}</h2>
            <StatusBadge tone="muted">{t("common.pending")}</StatusBadge>
          </div>
        </section>

        <section className="content-panel runtime-log-panel">
          <div className="section-heading">
            <h2>{t("settings.runtimeLog")}</h2>
            <span>{activities.length}</span>
          </div>
          {activities.length ? (
            <div className="runtime-log-list">
              {activities.map((event) => (
                <article key={event.id} className={`runtime-log-row ${event.status}`}>
                  <div>
                    <strong>{event.title}</strong>
                    <p>{event.detail}</p>
                  </div>
                  <span>{event.time}</span>
                </article>
              ))}
            </div>
          ) : (
            <p className="hint">{t("settings.runtimeLog.empty")}</p>
          )}
        </section>
      </div>

      {rightRail}
    </section>
  );
}
