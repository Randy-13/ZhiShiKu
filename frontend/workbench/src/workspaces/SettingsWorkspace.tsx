import {
  CheckCircle2,
  Cookie,
  ExternalLink,
  FolderOpen,
  Plug,
  RefreshCw,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { authApi, quotaApi, settingsApi } from "../api";
import type {
  ApiSettingInput,
  ApiSettingItem,
  ApiSettingsPayload,
  ApiSettingTemplate,
  ApiTestResult,
  AsrSettingInput,
  AsrSettingItem,
  AsrSettingsPayload,
  AsrSettingTemplate,
  AuthContext,
  BilibiliCookieStatus,
  ImageApiSettingInput,
  ImageApiSettingItem,
  ImageApiSettingsPayload,
  MediaDependencyItem,
  MediaDependencyStatus,
  QuotaCounter,
  QuotaStatus,
  StorageLocations,
  TrashFileItem,
  TrashStatus,
} from "../api";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";
import { StatusBadge } from "../components/StatusBadge";
import type { ActivityEvent, Language, TextExtractionMode } from "../domain";
import type { Translator } from "../i18n";

type StorageKey = keyof StorageLocations;
type ApiMode = "chat" | "image" | "audio";

type ApiFormState = {
  id?: string;
  name: string;
  provider: string;
  protocol: string;
  base_url: string;
  model: string;
  api_key: string;
  timeout: string;
  max_retries: string;
  size: string;
  quality: string;
  aspect_ratio: string;
  response_format: string;
  real_image_test: boolean;
  make_active: boolean;
};

type AsrFormState = {
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  timeout: string;
};

const emptyForm: ApiFormState = {
  name: "",
  provider: "compatible",
  protocol: "openai_compatible",
  base_url: "",
  model: "",
  api_key: "",
  timeout: "60",
  max_retries: "2",
  size: "1024x1024",
  quality: "auto",
  aspect_ratio: "1:1",
  response_format: "",
  real_image_test: false,
  make_active: true,
};

const emptyAsrForm: AsrFormState = {
  provider: "compatible",
  base_url: "",
  model: "",
  api_key: "",
  timeout: "60",
};

const storageFields: Array<{
  key: StorageKey;
  editable: boolean;
  zh: string;
  en: string;
  noteZh: string;
  noteEn: string;
}> = [
  {
    key: "storage_root",
    editable: true,
    zh: "运行存储根目录",
    en: "Runtime storage root",
    noteZh: "上传缓存和派生目录的默认根目录。",
    noteEn: "Default root for upload caches and derived folders.",
  },
  {
    key: "image_cache",
    editable: true,
    zh: "收集截图缓存",
    en: "Screenshot cache",
    noteZh: "收集区截图和粘贴图片保存位置。",
    noteEn: "Saved screenshots and pasted images from Collect.",
  },
  {
    key: "document_cache",
    editable: true,
    zh: "收集文件缓存",
    en: "Document cache",
    noteZh: "上传 PDF、文档和文本文件保存位置。",
    noteEn: "Uploaded PDFs, documents, and text files.",
  },
  {
    key: "media_cache",
    editable: true,
    zh: "音视频缓存",
    en: "Media cache",
    noteZh: "本地音视频、转写和平台解析结果保存位置。",
    noteEn: "Local media, transcripts, and platform parsing results.",
  },
  {
    key: "raw_library",
    editable: true,
    zh: "原文库文件",
    en: "Originals library",
    noteZh: "收集区生成的可编辑原文 Markdown。",
    noteEn: "Editable original Markdown generated from Collect.",
  },
  {
    key: "focus_library",
    editable: true,
    zh: "重点库文件",
    en: "Focus library",
    noteZh: "学习区提炼后的重点 Markdown。",
    noteEn: "Refined focus Markdown from Learn.",
  },
  {
    key: "perspective_library",
    editable: true,
    zh: "视角库文件",
    en: "Perspective library",
    noteZh: "挖掘区视角解读和分析文件。",
    noteEn: "Perspective interpretation and analysis files.",
  },
  {
    key: "writer_projects",
    editable: true,
    zh: "创作项目地址",
    en: "Writer projects",
    noteZh: "创作项目、文章、配图和美编产物。",
    noteEn: "Writing projects, articles, images, and formatted output.",
  },
  {
    key: "database",
    editable: false,
    zh: "SQLite 数据库",
    en: "SQLite database",
    noteZh: "数据库文件只展示位置，不在这里迁移。",
    noteEn: "Shown for reference; database migration is not handled here.",
  },
];

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
  const [apiModalOpen, setApiModalOpen] = useState(false);
  const [dependencyModalOpen, setDependencyModalOpen] = useState(false);
  const [cookieStatus, setCookieStatus] = useState<BilibiliCookieStatus>();
  const [cookieLoading, setCookieLoading] = useState(false);
  const [cookieActionMessage, setCookieActionMessage] = useState("");
  const [dependencyStatus, setDependencyStatus] = useState<MediaDependencyStatus>();
  const [dependencyLoading, setDependencyLoading] = useState(false);
  const [dependencyMessage, setDependencyMessage] = useState("");
  const [storageLocations, setStorageLocations] = useState<StorageLocations>({});
  const [storageDraft, setStorageDraft] = useState<StorageLocations>({});
  const [storageLoading, setStorageLoading] = useState(false);
  const [storageMessage, setStorageMessage] = useState("");
  const [trashStatus, setTrashStatus] = useState<TrashStatus>();
  const [trashLoading, setTrashLoading] = useState(false);
  const [trashMessage, setTrashMessage] = useState("");
  const [trashModalOpen, setTrashModalOpen] = useState(false);
  const [authContext, setAuthContext] = useState<AuthContext>();
  const [quotaStatus, setQuotaStatus] = useState<QuotaStatus>();
  const [quotaMessage, setQuotaMessage] = useState("");

  const localDiagnosticsVisible = authContext
    ? authContext.deploymentMode !== "cloud" || authContext.user?.role === "admin"
    : false;

  async function refreshCookieStatus() {
    setCookieLoading(true);
    setCookieActionMessage("");
    try {
      setCookieStatus(await settingsApi.bilibiliCookieStatus());
    } catch (error) {
      setCookieStatus({ ok: false, message: error instanceof Error ? error.message : String(error) });
    } finally {
      setCookieLoading(false);
    }
  }

  async function refreshDependencyStatus() {
    setDependencyLoading(true);
    setDependencyMessage("");
    try {
      setDependencyStatus(await settingsApi.mediaDependencies());
    } catch (error) {
      setDependencyMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setDependencyLoading(false);
    }
  }

  async function refreshQuotaStatus() {
    setQuotaMessage("");
    try {
      setQuotaStatus(await quotaApi.me());
    } catch (error) {
      setQuotaMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function openCookieLogin() {
    setCookieLoading(true);
    setCookieActionMessage("");
    try {
      const result = await settingsApi.openBilibiliCookieLogin();
      setCookieActionMessage(
        result.message || (language === "zh" ? "已打开 B 站登录窗口。" : "Opened Bilibili login window."),
      );
    } catch (error) {
      setCookieActionMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setCookieLoading(false);
    }
  }

  async function refreshStorageLocations() {
    setStorageLoading(true);
    setStorageMessage("");
    try {
      const settings = await settingsApi.workbenchSettings();
      const locations = settings.storage_locations ?? {};
      setStorageLocations(locations);
      setStorageDraft(locations);
    } catch (error) {
      setStorageMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setStorageLoading(false);
    }
  }

  async function saveStorageLocations() {
    setStorageLoading(true);
    setStorageMessage("");
    try {
      const payload = await settingsApi.saveWorkbenchSettings({
        text_extraction_mode: textExtractionMode,
        storage_locations: Object.fromEntries(
          storageFields
            .filter((field) => field.editable)
            .map((field) => [field.key, String(storageDraft[field.key] ?? "").trim()]),
        ),
      });
      const locations = payload.storage_locations ?? {};
      setStorageLocations(locations);
      setStorageDraft(locations);
      setStorageMessage(language === "zh" ? "本地存储位置已保存并生效。" : "Local storage locations saved and applied.");
      setTrashStatus((current) => (current ? { ...current, path: locations.trash ?? current.path } : current));
    } catch (error) {
      setStorageMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setStorageLoading(false);
    }
  }

  async function refreshTrashStatus() {
    setTrashLoading(true);
    setTrashMessage("");
    try {
      setTrashStatus(await settingsApi.trashStatus());
    } catch (error) {
      setTrashMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setTrashLoading(false);
    }
  }

  async function clearTrash() {
    setTrashLoading(true);
    setTrashMessage("");
    try {
      const result = await settingsApi.clearTrash();
      setTrashStatus(result);
      setTrashMessage(
        language === "zh"
          ? `已彻底删除 ${result.deleted_files ?? 0} 个垃圾箱文件。`
          : `Permanently deleted ${result.deleted_files ?? 0} trash file(s).`,
      );
    } catch (error) {
      setTrashMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setTrashLoading(false);
    }
  }

  useEffect(() => {
    authApi
      .me()
      .then((context) => {
        setAuthContext(context);
        const canSeeLocalDiagnostics = context.deploymentMode !== "cloud" || context.user?.role === "admin";
        refreshCookieStatus();
        refreshQuotaStatus();
        refreshDependencyStatus();
        if (canSeeLocalDiagnostics) {
          refreshStorageLocations();
          refreshTrashStatus();
        }
      })
      .catch(() => {
        refreshCookieStatus();
        refreshQuotaStatus();
        refreshDependencyStatus();
      });
  }, []);

  const dependencyItems = useMemo(() => Object.entries(dependencyStatus ?? {}), [dependencyStatus]);
  const readyCount = dependencyItems.filter(([, item]) => item.available || item.configured || item.verified).length;
  const dependencySummary =
    dependencyItems.length > 0
      ? language === "zh"
        ? `${readyCount}/${dependencyItems.length} 项可用`
        : `${readyCount}/${dependencyItems.length} ready`
      : language === "zh"
        ? "查看依赖状态"
        : "Review dependency status";

  return (
    <section className="workspace-layout">
      <div className="workspace-main">
        <PrimaryTaskPanel
          eyebrow={t("common.primary")}
          title={t("settings.language")}
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
          <div className="settings-action-card">
            <div>
              <h2>{t("settings.api")}</h2>
            </div>
            <button className="secondary-button" type="button" onClick={() => setApiModalOpen(true)}>
              <Plug size={16} />
              {language === "zh" ? "配置 API" : "Configure API"}
            </button>
          </div>

          <div className="settings-action-card">
            <div>
              <h2>{t("settings.dependencies")}</h2>
              <p className="hint">{dependencyMessage || dependencySummary}</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => setDependencyModalOpen(true)}>
              <CheckCircle2 size={16} />
              {language === "zh" ? "查看详情" : "View details"}
            </button>
          </div>

          <div className="quota-settings-card">
            <div className="dependency-check-title">
              <CheckCircle2 size={17} />
              <h2>{language === "zh" ? "额度与用量" : "Quota and usage"}</h2>
            </div>
            {quotaMessage ? <p className="inline-error">{quotaMessage}</p> : null}
            {quotaStatus ? (
              <div className="quota-metric-list">
                <QuotaMetric
                  label={language === "zh" ? "链接解析" : "Link parsing"}
                  counter={quotaStatus.daily.link_parse_daily}
                />
                <QuotaMetric
                  label={language === "zh" ? "AI 生成" : "AI generation"}
                  counter={quotaStatus.daily.llm_generate_daily}
                />
                <QuotaMetric
                  label={language === "zh" ? "并发任务" : "Concurrent jobs"}
                  counter={quotaStatus.jobs.concurrent_jobs}
                />
                <QuotaMetric
                  label={language === "zh" ? "存储空间" : "Storage"}
                  counter={quotaStatus.uploads.storage_bytes}
                  formatter={formatBytes}
                />
                <div className="quota-limit-row">
                  <span>{language === "zh" ? "单文件上传" : "Single upload"}</span>
                  <strong>{formatBytes(quotaStatus.uploads.single_upload_bytes.limit)}</strong>
                </div>
              </div>
            ) : null}
          </div>

          {localDiagnosticsVisible ? (
            <>
              <div className="settings-action-card">
                <div>
                  <h2>{language === "zh" ? "垃圾箱" : "Trash"}</h2>
                  <p className="hint">
                    {language === "zh"
                      ? `${trashStatus?.file_count ?? 0} 个文件，${formatBytes(trashStatus?.size_bytes ?? 0)}`
                      : `${trashStatus?.file_count ?? 0} file(s), ${formatBytes(trashStatus?.size_bytes ?? 0)}`}
                  </p>
                </div>
                <button className="secondary-button" type="button" onClick={() => setTrashModalOpen(true)}>
                  <Trash2 size={16} />
                  {language === "zh" ? "管理垃圾箱" : "Manage trash"}
                </button>
              </div>

              <div className="storage-settings-card">
                <div className="dependency-check-title">
                  <FolderOpen size={17} />
                  <h2>{t("settings.storage")}</h2>
                </div>
                <div className="storage-location-list">
                  {storageFields.map((field) => (
                    <label key={field.key} className={field.editable ? "storage-location-row" : "storage-location-row readonly"}>
                      <span>
                        <strong>{language === "zh" ? field.zh : field.en}</strong>
                        <small>{language === "zh" ? field.noteZh : field.noteEn}</small>
                      </span>
                      <input
                        value={storageDraft[field.key] ?? storageLocations[field.key] ?? ""}
                        readOnly={!field.editable}
                        onChange={(event) =>
                          setStorageDraft((current) => ({
                            ...current,
                            [field.key]: event.target.value,
                          }))
                        }
                      />
                    </label>
                  ))}
                </div>
                {storageMessage ? (
                  <p className={isErrorMessage(storageMessage) ? "inline-error" : "hint"}>{storageMessage}</p>
                ) : null}
                <div className="dependency-actions">
                  <button className="secondary-button" type="button" onClick={refreshStorageLocations} disabled={storageLoading}>
                    <RefreshCw size={16} />
                    {language === "zh" ? "刷新位置" : "Refresh"}
                  </button>
                  <button className="secondary-button" type="button" onClick={saveStorageLocations} disabled={storageLoading}>
                    <Save size={16} />
                    {storageLoading ? (language === "zh" ? "处理中" : "Saving") : language === "zh" ? "保存位置" : "Save paths"}
                  </button>
                </div>
              </div>
            </>
          ) : null}

          <div>
            <h2>{t("settings.extraction")}</h2>
            <div className="input-row" role="group" aria-label={t("settings.extraction")}>
              <button
                className={textExtractionMode === "local_ocr" ? "choice active" : "choice"}
                type="button"
                onClick={() => onTextExtractionModeChange("local_ocr")}
              >
                {t("settings.extraction.local")}
              </button>
              <button
                className={textExtractionMode === "ai_vision" ? "choice active" : "choice"}
                type="button"
                onClick={() => onTextExtractionModeChange("ai_vision")}
              >
                {t("settings.extraction.api")}
              </button>
            </div>
          </div>

          <div>
            <h2>{language === "zh" ? "B 站 Cookie" : "Bilibili cookies"}</h2>
            <div className="dependency-check-row compact">
              <div className="dependency-check-title">
                <Cookie size={17} />
                <strong>{language === "zh" ? "字幕提取登录状态" : "Subtitle login status"}</strong>
                <StatusBadge tone={cookieStatus?.ok ? "done" : "error"}>
                  {cookieStatus?.ok ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "需处理" : "Action needed"}
                </StatusBadge>
              </div>
              <p className="hint">{cookieStatus?.message}</p>
              {cookieActionMessage ? <p className="hint">{cookieActionMessage}</p> : null}
              <div className="dependency-actions">
                <button className="secondary-button" type="button" onClick={refreshCookieStatus} disabled={cookieLoading}>
                  <RefreshCw size={16} />
                  {language === "zh" ? "重新检查" : "Recheck"}
                </button>
                {localDiagnosticsVisible ? (
                  <button className="secondary-button" type="button" onClick={openCookieLogin} disabled={cookieLoading}>
                    <ExternalLink size={16} />
                    {language === "zh" ? "登录获取 Cookie" : "Log in"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        {localDiagnosticsVisible ? (
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
            ) : null}
          </section>
        ) : null}
      </div>

      {rightRail}

      {apiModalOpen ? <ApiSettingsModal language={language} onClose={() => setApiModalOpen(false)} /> : null}

      {dependencyModalOpen ? (
        <DependencyStatusModal
          language={language}
          cookieStatus={cookieStatus}
          cookieLoading={cookieLoading}
          cookieActionMessage={cookieActionMessage}
          dependencyStatus={dependencyStatus}
          dependencyLoading={dependencyLoading}
          dependencyMessage={dependencyMessage}
          localDiagnosticsVisible={localDiagnosticsVisible}
          onClose={() => setDependencyModalOpen(false)}
          onRefreshDependencies={refreshDependencyStatus}
          onRefreshCookies={refreshCookieStatus}
          onOpenCookieLogin={localDiagnosticsVisible ? openCookieLogin : undefined}
        />
      ) : null}

      {trashModalOpen && localDiagnosticsVisible ? (
        <TrashModal
          language={language}
          status={trashStatus}
          isLoading={trashLoading}
          message={trashMessage}
          onClose={() => setTrashModalOpen(false)}
          onRefresh={refreshTrashStatus}
          onClear={clearTrash}
          onDeleteSelected={async (paths) => {
            setTrashLoading(true);
            setTrashMessage("");
            try {
              const result = await settingsApi.deleteTrashFiles(paths);
              setTrashStatus(result);
              setTrashMessage(
                language === "zh"
                  ? `已彻底删除 ${result.deleted_files ?? paths.length} 个选中文件。`
                  : `Deleted ${result.deleted_files ?? paths.length} selected file(s).`,
              );
            } catch (error) {
              setTrashMessage(error instanceof Error ? error.message : String(error));
            } finally {
              setTrashLoading(false);
            }
          }}
          onRestoreSelected={async (paths) => {
            setTrashLoading(true);
            setTrashMessage("");
            try {
              const result = await settingsApi.restoreTrashFiles(paths);
              setTrashStatus(result);
              setTrashMessage(
                language === "zh"
                  ? `已恢复 ${result.restored?.length ?? paths.length} 个选中文件。`
                  : `Restored ${result.restored?.length ?? paths.length} selected file(s).`,
              );
            } catch (error) {
              setTrashMessage(error instanceof Error ? error.message : String(error));
            } finally {
              setTrashLoading(false);
            }
          }}
        />
      ) : null}
    </section>
  );
}

function DependencyStatusModal({
  language,
  cookieStatus,
  cookieLoading,
  cookieActionMessage,
  dependencyStatus,
  dependencyLoading,
  dependencyMessage,
  localDiagnosticsVisible,
  onClose,
  onRefreshDependencies,
  onRefreshCookies,
  onOpenCookieLogin,
}: {
  language: Language;
  cookieStatus?: BilibiliCookieStatus;
  cookieLoading: boolean;
  cookieActionMessage: string;
  dependencyStatus?: MediaDependencyStatus;
  dependencyLoading: boolean;
  dependencyMessage: string;
  localDiagnosticsVisible: boolean;
  onClose: () => void;
  onRefreshDependencies: () => Promise<void>;
  onRefreshCookies: () => Promise<void>;
  onOpenCookieLogin?: () => Promise<void>;
}) {
  const items = Object.entries(dependencyStatus ?? {});

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel dependency-modal-panel" role="dialog" aria-modal="true" aria-label={language === "zh" ? "依赖检查" : "Dependency checks"}>
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "设置" : "Settings"}</span>
            <h2>{language === "zh" ? "依赖检查" : "Dependency checks"}</h2>
          </div>
          <button className="icon-button" type="button" aria-label={language === "zh" ? "关闭" : "Close"} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="dependency-actions">
          <button className="secondary-button" type="button" onClick={onRefreshDependencies} disabled={dependencyLoading}>
            <RefreshCw size={16} />
            {language === "zh" ? "刷新依赖" : "Refresh dependencies"}
          </button>
          <button className="secondary-button" type="button" onClick={onRefreshCookies} disabled={cookieLoading}>
            <RefreshCw size={16} />
            {language === "zh" ? "刷新 Cookie" : "Refresh cookies"}
          </button>
          {onOpenCookieLogin ? (
            <button className="secondary-button" type="button" onClick={onOpenCookieLogin} disabled={cookieLoading}>
              <ExternalLink size={16} />
              {language === "zh" ? "登录获取 Cookie" : "Log in"}
            </button>
          ) : null}
        </div>

        <div className="dependency-summary-list">
          <div className="dependency-check-row compact">
            <div className="dependency-check-title">
              <Cookie size={17} />
              <strong>{language === "zh" ? "B 站 Cookie" : "Bilibili cookies"}</strong>
              <StatusBadge tone={cookieStatus?.ok ? "done" : "error"}>
                {cookieStatus?.ok ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "需处理" : "Action needed"}
              </StatusBadge>
            </div>
            <p className="hint">{cookieStatus?.message}</p>
            {localDiagnosticsVisible && cookieStatus?.path ? <small className="dependency-path">{cookieStatus.path}</small> : null}
            <div className="dependency-meta">
              {typeof cookieStatus?.cookie_count === "number" ? (
                <span>{language === "zh" ? `Cookie 数：${cookieStatus.cookie_count}` : `Cookies: ${cookieStatus.cookie_count}`}</span>
              ) : null}
              {cookieStatus?.last_modified ? (
                <span>{language === "zh" ? `更新：${cookieStatus.last_modified}` : `Updated: ${cookieStatus.last_modified}`}</span>
              ) : null}
            </div>
            {cookieStatus?.missing?.length ? (
              <p className="inline-error">
                {language === "zh" ? `缺少：${cookieStatus.missing.join(", ")}` : `Missing: ${cookieStatus.missing.join(", ")}`}
              </p>
            ) : null}
            {cookieActionMessage ? <p className="hint">{cookieActionMessage}</p> : null}
          </div>

          {dependencyMessage ? <p className="inline-error">{dependencyMessage}</p> : null}
          {!dependencyMessage && !items.length && dependencyLoading ? (
            <p className="hint">{language === "zh" ? "正在读取依赖状态..." : "Loading dependency status..."}</p>
          ) : null}
          {items.map(([key, item]) => (
            <DependencyItemCard key={key} language={language} name={key} item={item} />
          ))}
        </div>
      </section>
    </div>
  );
}

function DependencyItemCard({ language, name, item }: { language: Language; name: string; item: MediaDependencyItem }) {
  const isReady = item.available || item.configured || item.verified;
  return (
    <div className="dependency-check-row compact">
      <div className="dependency-check-title">
        <CheckCircle2 size={17} />
        <strong>{item.label || name}</strong>
        <StatusBadge tone={isReady ? "done" : "error"}>
          {isReady ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "待处理" : "Needs setup"}
        </StatusBadge>
      </div>
      {item.purpose ? <p className="hint">{item.purpose}</p> : null}
      {item.message || item.detail ? <p className="hint">{item.message || item.detail}</p> : null}
      <div className="dependency-meta">
        {item.provider ? <span>{language === "zh" ? `提供方：${item.provider}` : `Provider: ${item.provider}`}</span> : null}
        {item.model ? <span>{language === "zh" ? `模型：${item.model}` : `Model: ${item.model}`}</span> : null}
        {item.auth ? <span>{language === "zh" ? `鉴权：${item.auth}` : `Auth: ${item.auth}`}</span> : null}
        {typeof item.verified === "boolean" ? (
          <span>{language === "zh" ? `已验证：${item.verified ? "是" : "否"}` : `Verified: ${item.verified ? "yes" : "no"}`}</span>
        ) : null}
      </div>
      {item.base_url ? <small className="dependency-path">{item.base_url}</small> : null}
    </div>
  );
}

function TrashModal({
  language,
  status,
  isLoading,
  message,
  onClose,
  onRefresh,
  onClear,
  onDeleteSelected,
  onRestoreSelected,
}: {
  language: Language;
  status?: TrashStatus;
  isLoading: boolean;
  message: string;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  onClear: () => Promise<void>;
  onDeleteSelected: (paths: string[]) => Promise<void>;
  onRestoreSelected: (paths: string[]) => Promise<void>;
}) {
  const items = status?.items ?? [];
  const [checkedSet, setCheckedSet] = useState<Set<string>>(new Set());

  useEffect(() => {
    setCheckedSet(new Set());
  }, [status?.updated_at, items.length]);

  const visibleChecked = items.filter((item) => checkedSet.has(item.trash_path)).map((item) => item.trash_path);

  function toggle(path: string) {
    setCheckedSet((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  async function run(action: (paths: string[]) => Promise<void>) {
    if (!visibleChecked.length) return;
    await action(visibleChecked);
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel trash-modal-panel" role="dialog" aria-modal="true" aria-label={language === "zh" ? "管理垃圾箱" : "Manage trash"}>
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "设置" : "Settings"}</span>
            <h2>{language === "zh" ? "垃圾箱" : "Trash"}</h2>
            <p className="hint">
              {language === "zh"
                ? `当前 ${status?.file_count ?? 0} 个文件，共 ${formatBytes(status?.size_bytes ?? 0)}。`
                : `${status?.file_count ?? 0} files, ${formatBytes(status?.size_bytes ?? 0)} total.`}
            </p>
          </div>
          <button className="icon-button" type="button" aria-label={language === "zh" ? "关闭" : "Close"} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="trash-modal-toolbar">
          <div className="dependency-meta">
            {status?.path ? <span>{status.path}</span> : null}
            {status?.updated_at ? <span>{language === "zh" ? `更新时间：${status.updated_at}` : `Updated: ${status.updated_at}`}</span> : null}
          </div>
          <div className="dependency-actions">
            <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
              <RefreshCw size={16} />
              {language === "zh" ? "刷新" : "Refresh"}
            </button>
          </div>
        </div>

        {items.length ? (
          <div className="trash-file-list">
            {items.map((item) => (
              <TrashRow key={item.trash_path} item={item} checked={checkedSet.has(item.trash_path)} language={language} onToggle={toggle} />
            ))}
          </div>
        ) : null}

        {message ? <p className={isErrorMessage(message) ? "inline-error" : "hint"}>{message}</p> : null}

        <div className="api-settings-actions">
          <button className="secondary-button" type="button" disabled={!visibleChecked.length || isLoading} onClick={() => run(onRestoreSelected)}>
            {language === "zh" ? "恢复选中" : "Restore selected"}
          </button>
          <button className="secondary-button danger-button" type="button" disabled={!visibleChecked.length || isLoading} onClick={() => run(onDeleteSelected)}>
            {language === "zh" ? "彻底删除选中" : "Delete selected"}
          </button>
          <button className="secondary-button danger-button" type="button" disabled={!items.length || isLoading} onClick={onClear}>
            <Trash2 size={16} />
            {language === "zh" ? "清空垃圾箱" : "Clear trash"}
          </button>
        </div>
      </section>
    </div>
  );
}

function TrashRow({
  item,
  checked,
  language,
  onToggle,
}: {
  item: TrashFileItem;
  checked: boolean;
  language: Language;
  onToggle: (path: string) => void;
}) {
  const libraryLabel =
    item.library === "raw" || item.library === "original"
      ? language === "zh"
        ? "原文库"
        : "Originals"
      : item.library === "focus"
        ? language === "zh"
          ? "重点库"
          : "Focus"
        : item.library === "perspective"
          ? language === "zh"
            ? "视角库"
            : "Perspectives"
          : language === "zh"
            ? "未知库"
            : "Unknown";

  return (
    <label className="trash-file-row">
      <input type="checkbox" checked={checked} onChange={() => onToggle(item.trash_path)} />
      <span>
        <strong>{item.title}</strong>
        <small>{libraryLabel} · {formatBytes(item.size ?? 0)}</small>
        <em>{item.trash_path}</em>
      </span>
    </label>
  );
}

function ApiSettingsModal({ language, onClose }: { language: Language; onClose: () => void }) {
  const [mode, setMode] = useState<ApiMode>("chat");
  const [chatPayload, setChatPayload] = useState<ApiSettingsPayload>({});
  const [imagePayload, setImagePayload] = useState<ImageApiSettingsPayload>({});
  const [asrPayload, setAsrPayload] = useState<AsrSettingsPayload>({});
  const [form, setForm] = useState<ApiFormState>(emptyForm);
  const [asrForm, setAsrForm] = useState<AsrFormState>(emptyAsrForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [testResult, setTestResult] = useState<ApiTestResult>();

  const items = mode === "chat" ? chatPayload.items ?? [] : imagePayload.items ?? [];
  const templates = mode === "chat" ? chatPayload.templates ?? [] : mode === "image" ? imagePayload.templates ?? [] : [];
  const activeId = mode === "chat" ? chatPayload.active_id : imagePayload.active_id;
  const selectedItem = useMemo(() => items.find((item) => item.id === form.id), [form.id, items]);

  useEffect(() => {
    let alive = true;
    setIsLoading(true);
    Promise.all([settingsApi.apiSettings(), settingsApi.imageApiSettings(), settingsApi.asrSettings()])
      .then(([chat, image, asr]) => {
        if (!alive) return;
        setChatPayload(chat);
        setImagePayload(image);
        setAsrPayload(asr);
        setForm(formFromItem(chat.items?.find((item) => item.id === chat.active_id) ?? chat.items?.[0], "chat"));
        setAsrForm(formFromAsrItem(asr.item));
      })
      .catch((error) => {
        if (!alive) return;
        setMessage(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        if (alive) setIsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setMessage("");
    setTestResult(undefined);
    if (mode === "audio") {
      setAsrForm(formFromAsrItem(asrPayload.item));
      return;
    }
    const payload = mode === "chat" ? chatPayload : imagePayload;
    setForm(formFromItem(payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0], mode));
  }, [asrPayload.item, chatPayload, imagePayload, mode]);

  async function refresh(nextMode = mode) {
    if (nextMode === "audio") {
      const payload = await settingsApi.asrSettings();
      setAsrPayload(payload);
      setAsrForm(formFromAsrItem(payload.item));
      return;
    }
    const payload = nextMode === "chat" ? await settingsApi.apiSettings() : await settingsApi.imageApiSettings();
    if (nextMode === "chat") setChatPayload(payload);
    else setImagePayload(payload);
    setForm(formFromItem(payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0], nextMode));
  }

  async function save() {
    setIsSaving(true);
    setMessage("");
    try {
      if (mode === "audio") {
        const payload = await settingsApi.saveAsrSetting(toAsrInput(asrForm));
        setAsrPayload(payload);
        setAsrForm(formFromAsrItem(payload.item));
        setMessage(payload.message || (language === "zh" ? "音频 API 配置已保存。" : "Audio API setting saved."));
        return;
      }
      const payload =
        mode === "chat"
          ? await settingsApi.saveApiSetting(toChatInput(form))
          : await settingsApi.saveImageApiSetting(toImageInput(form));
      if (mode === "chat") setChatPayload(payload);
      else setImagePayload(payload);
      const saved = payload.item ?? payload.items?.find((item) => item.id === payload.active_id);
      setForm(formFromItem(saved, mode));
      setMessage(language === "zh" ? "API 配置已保存。" : "API setting saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function test() {
    setIsTesting(true);
    setMessage("");
    setTestResult(undefined);
    try {
      if (mode === "audio") {
        const payload = await settingsApi.testAsrSetting(toAsrInput(asrForm));
        setAsrPayload((current) => ({ ...current, ...payload }));
        const result: ApiTestResult = {
          ok: payload.ok ?? false,
          message: payload.message ?? payload.error ?? "",
          provider: payload.item?.provider ?? asrForm.provider,
          model: payload.item?.model ?? asrForm.model,
          last_test_ok: payload.item?.last_test_ok ?? payload.ok ?? false,
          last_test_at: payload.item?.last_test_at ?? "",
        };
        setTestResult(result);
        setMessage(payload.message || payload.error || (payload.ok ? (language === "zh" ? "测试通过。" : "Test passed.") : ""));
        return;
      }
      const result =
        mode === "chat"
          ? await settingsApi.testApiSetting(toChatInput(form))
          : await settingsApi.testImageApiSetting(toImageInput(form), { realTest: form.real_image_test });
      setTestResult(result);
      setMessage(isTestOk(result) ? (language === "zh" ? "测试通过。" : "Test passed.") : resultMessage(result));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsTesting(false);
    }
  }

  async function activate(id: string) {
    setMessage("");
    try {
      const payload = mode === "chat" ? await settingsApi.setActiveApiSetting(id) : await settingsApi.setActiveImageApiSetting(id);
      if (mode === "chat") setChatPayload(payload);
      else setImagePayload(payload);
      setMessage(language === "zh" ? "已启用该配置。" : "Setting activated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function remove(id: string) {
    setMessage("");
    try {
      const payload = mode === "chat" ? await settingsApi.deleteApiSetting(id) : await settingsApi.deleteImageApiSetting(id);
      if (mode === "chat") setChatPayload(payload);
      else setImagePayload(payload);
      setForm(formFromItem(payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0], mode));
      setMessage(language === "zh" ? "配置已删除。" : "Setting deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function applyTemplate(template: ApiSettingTemplate | AsrSettingTemplate) {
    if (mode === "audio") {
      setAsrForm((current) => ({
        ...current,
        provider: template.provider,
        base_url: template.base_url,
        model: template.model,
        api_key: "",
      }));
      return;
    }
    const typedTemplate = template as ApiSettingTemplate;
    setForm((current) => ({
      ...current,
      id: undefined,
      name: typedTemplate.name,
      provider: typedTemplate.provider,
      protocol: typedTemplate.protocol ?? current.protocol,
      base_url: typedTemplate.base_url,
      model: typedTemplate.model,
      size: typedTemplate.size ?? current.size,
      quality: typedTemplate.quality ?? current.quality,
      aspect_ratio: typedTemplate.aspect_ratio ?? current.aspect_ratio,
      response_format: typedTemplate.response_format ?? current.response_format,
      api_key: "",
      make_active: true,
    }));
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel api-settings-modal" role="dialog" aria-modal="true" aria-label={language === "zh" ? "API 设置" : "API settings"}>
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "设置" : "Settings"}</span>
            <h2>{language === "zh" ? "API 设置" : "API settings"}</h2>
            <p className="hint">
              {language === "zh"
                ? "统一管理文本、图片和音频处理模型配置。"
                : "Manage text, image, and audio processing models in one place."}
            </p>
          </div>
          <button className="icon-button" type="button" aria-label={language === "zh" ? "关闭" : "Close"} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="library-bucket-tabs" role="tablist" aria-label={language === "zh" ? "API 类型" : "API type"}>
          <button className={mode === "chat" ? "bucket-tab selected" : "bucket-tab"} type="button" onClick={() => setMode("chat")}>
            {language === "zh" ? "文本 API" : "Text API"}
          </button>
          <button className={mode === "image" ? "bucket-tab selected" : "bucket-tab"} type="button" onClick={() => setMode("image")}>
            {language === "zh" ? "图片 API" : "Image API"}
          </button>
          <button className={mode === "audio" ? "bucket-tab selected" : "bucket-tab"} type="button" onClick={() => setMode("audio")}>
            {language === "zh" ? "音频 ASR" : "Audio ASR"}
          </button>
        </div>

        {isLoading ? (
          <p className="hint">{language === "zh" ? "正在读取配置..." : "Loading settings..."}</p>
        ) : mode === "audio" ? (
          <div className="api-settings-grid">
            <aside className="api-settings-list">
              <div className="section-heading">
                <h3>{language === "zh" ? "当前音频配置" : "Current audio setting"}</h3>
              </div>
              <article className="api-setting-row selected">
                <button type="button">
                  <strong>{asrPayload.item?.provider || asrForm.provider || (language === "zh" ? "未配置" : "Not configured")}</strong>
                  <span>{asrPayload.item?.model || asrForm.model || (language === "zh" ? "未选择模型" : "No model selected")}</span>
                  <small>{asrPayload.item?.api_key_masked || (language === "zh" ? "未显示 Key" : "Key hidden")}</small>
                </button>
                <div className="api-row-actions">
                  <StatusBadge tone={asrPayload.item?.configured ? "done" : "error"}>
                    {asrPayload.item?.configured ? (language === "zh" ? "已配置" : "Configured") : language === "zh" ? "待配置" : "Setup needed"}
                  </StatusBadge>
                </div>
              </article>
              <div className="api-template-list">
                <h3>{language === "zh" ? "模板" : "Templates"}</h3>
                {(asrPayload.templates ?? []).map((template) => (
                  <button key={template.id} className="api-template-button" type="button" onClick={() => applyTemplate(template)}>
                    <strong>{template.name}</strong>
                    <span>{template.base_url}</span>
                  </button>
                ))}
              </div>
            </aside>

            <form className="api-settings-form" onSubmit={(event) => event.preventDefault()}>
              <div className="section-heading">
                <h3>{language === "zh" ? "编辑音频 ASR" : "Edit audio ASR"}</h3>
              </div>
              <div className="api-form-grid compact-form-grid">
                <label>
                  <span>{language === "zh" ? "服务商" : "Provider"}</span>
                  <input value={asrForm.provider} onChange={(event) => setAsrForm({ ...asrForm, provider: event.target.value })} />
                </label>
                <label>
                  <span>{language === "zh" ? "模型" : "Model"}</span>
                  <input value={asrForm.model} onChange={(event) => setAsrForm({ ...asrForm, model: event.target.value })} />
                </label>
                <label className="wide-field">
                  <span>Base URL</span>
                  <input
                    value={asrForm.base_url}
                    onChange={(event) => setAsrForm({ ...asrForm, base_url: event.target.value })}
                    placeholder="https://api.example.com/v1"
                  />
                </label>
                <label>
                  <span>API Key</span>
                  <input
                    value={asrForm.api_key}
                    onChange={(event) => setAsrForm({ ...asrForm, api_key: event.target.value })}
                    placeholder={asrPayload.item?.api_key_masked || "sk-..."}
                    type="password"
                  />
                </label>
                <label>
                  <span>{language === "zh" ? "超时秒数" : "Timeout seconds"}</span>
                  <input value={asrForm.timeout} onChange={(event) => setAsrForm({ ...asrForm, timeout: event.target.value })} inputMode="decimal" />
                </label>
              </div>

              {asrPayload.item ? (
                <div className="dependency-meta">
                  {typeof asrPayload.item.last_test_ok === "boolean" ? (
                    <span>
                      {language === "zh"
                        ? `上次测试：${asrPayload.item.last_test_ok ? "通过" : "失败"}`
                        : `Last test: ${asrPayload.item.last_test_ok ? "passed" : "failed"}`}
                    </span>
                  ) : null}
                  {asrPayload.item.last_test_at ? (
                    <span>{language === "zh" ? `测试时间：${asrPayload.item.last_test_at}` : `Tested: ${asrPayload.item.last_test_at}`}</span>
                  ) : null}
                  {asrPayload.item.source ? <span>{language === "zh" ? `来源：${asrPayload.item.source}` : `Source: ${asrPayload.item.source}`}</span> : null}
                </div>
              ) : null}

              <div className="api-settings-actions">
                <button className="secondary-button" type="button" disabled={isTesting} onClick={test}>
                  <Plug size={16} />
                  {isTesting ? (language === "zh" ? "测试中..." : "Testing...") : language === "zh" ? "测试" : "Test"}
                </button>
                <button className="primary-cta" type="button" disabled={isSaving} onClick={save}>
                  <strong>{isSaving ? (language === "zh" ? "保存中..." : "Saving...") : language === "zh" ? "保存配置" : "Save setting"}</strong>
                  <Save size={17} />
                </button>
                <button className="secondary-button" type="button" onClick={() => refresh("audio")}>
                  {language === "zh" ? "刷新" : "Refresh"}
                </button>
              </div>
              {message ? <p className={isErrorMessage(message) ? "disabled-reason" : "hint"}>{message}</p> : null}
              {testResult ? <TestResultPreview result={testResult} /> : null}
            </form>
          </div>
        ) : (
          <div className="api-settings-grid">
            <aside className="api-settings-list">
              <div className="section-heading">
                <h3>{language === "zh" ? "已有配置" : "Saved settings"}</h3>
                <button className="secondary-button" type="button" onClick={() => setForm(defaultForm(mode))}>
                  {language === "zh" ? "新建" : "New"}
                </button>
              </div>
              {items.length ? (
                <div className="api-setting-rows">
                  {items.map((item) => (
                    <article key={item.id} className={item.id === form.id ? "api-setting-row selected" : "api-setting-row"}>
                      <button type="button" onClick={() => setForm(formFromItem(item, mode))}>
                        <strong>{item.name}</strong>
                        <span>{item.model}</span>
                        <small>{item.api_key_masked || (language === "zh" ? "未显示 Key" : "Key hidden")}</small>
                      </button>
                      <div className="api-row-actions">
                        {item.id === activeId ? (
                          <StatusBadge tone="done">{language === "zh" ? "启用中" : "Active"}</StatusBadge>
                        ) : (
                          <button className="secondary-button" type="button" onClick={() => activate(item.id)}>
                            <CheckCircle2 size={15} />
                            {language === "zh" ? "启用" : "Use"}
                          </button>
                        )}
                        <button className="secondary-button danger-button" type="button" onClick={() => remove(item.id)}>
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="hint">{language === "zh" ? "还没有保存的配置。" : "No saved settings yet."}</p>
              )}

              <div className="api-template-list">
                <h3>{language === "zh" ? "模板" : "Templates"}</h3>
                {templates.map((template) => (
                  <button key={template.id} className="api-template-button" type="button" onClick={() => applyTemplate(template)}>
                    <strong>{template.name}</strong>
                    <span>{template.base_url}</span>
                  </button>
                ))}
              </div>
            </aside>

            <form className="api-settings-form" onSubmit={(event) => event.preventDefault()}>
              <div className="section-heading">
                <h3>{selectedItem ? (language === "zh" ? "编辑配置" : "Edit setting") : language === "zh" ? "新建配置" : "New setting"}</h3>
                <label className="inline-check">
                  <input type="checkbox" checked={form.make_active} onChange={(event) => setForm({ ...form, make_active: event.target.checked })} />
                  {language === "zh" ? "保存后启用" : "Activate after save"}
                </label>
              </div>
              <div className="api-form-grid">
                <label>
                  <span>{language === "zh" ? "配置名称" : "Name"}</span>
                  <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                </label>
                <label>
                  <span>{language === "zh" ? "服务商" : "Provider"}</span>
                  <input value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })} />
                </label>
                {mode === "image" ? (
                  <label>
                    <span>{language === "zh" ? "协议" : "Protocol"}</span>
                    <select value={form.protocol} onChange={(event) => setForm({ ...form, protocol: event.target.value })}>
                      <option value="openai_compatible">{language === "zh" ? "OpenAI 兼容" : "OpenAI compatible"}</option>
                      <option value="minimax">MiniMax</option>
                      <option value="custom_endpoint">{language === "zh" ? "完整 Endpoint" : "Full endpoint"}</option>
                    </select>
                  </label>
                ) : null}
                <label className="wide-field">
                  <span>Base URL</span>
                  <input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="https://api.example.com/v1" />
                  {mode === "image" ? (
                    <small className="field-hint">
                      {form.protocol === "minimax"
                        ? language === "zh"
                          ? "MiniMax 请填完整 endpoint，不会追加 /images/generations。"
                          : "Use the full MiniMax endpoint; /images/generations will not be appended."
                        : form.protocol === "custom_endpoint"
                          ? language === "zh"
                            ? "完整 Endpoint 会原样调用。"
                            : "The full endpoint will be called as-is."
                          : language === "zh"
                            ? "OpenAI 兼容协议会自动追加 /images/generations。"
                            : "OpenAI-compatible mode appends /images/generations automatically."}
                    </small>
                  ) : null}
                </label>
                <label>
                  <span>{language === "zh" ? "模型" : "Model"}</span>
                  <input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} />
                </label>
                <label>
                  <span>API Key</span>
                  <input
                    value={form.api_key}
                    onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                    placeholder={selectedItem ? selectedItem.api_key_masked || "sk-..." : "sk-..."}
                    type="password"
                  />
                </label>
                <label>
                  <span>{language === "zh" ? "超时秒数" : "Timeout seconds"}</span>
                  <input value={form.timeout} onChange={(event) => setForm({ ...form, timeout: event.target.value })} inputMode="decimal" />
                </label>
                {mode === "chat" ? (
                  <label>
                    <span>{language === "zh" ? "重试次数" : "Max retries"}</span>
                    <input value={form.max_retries} onChange={(event) => setForm({ ...form, max_retries: event.target.value })} inputMode="numeric" />
                  </label>
                ) : (
                  <>
                    {form.protocol === "minimax" ? (
                      <>
                        <label>
                          <span>{language === "zh" ? "图片比例" : "Aspect ratio"}</span>
                          <input value={form.aspect_ratio} onChange={(event) => setForm({ ...form, aspect_ratio: event.target.value })} placeholder="1:1" />
                        </label>
                        <label>
                          <span>{language === "zh" ? "返回格式" : "Response format"}</span>
                          <input
                            value={form.response_format || "base64"}
                            onChange={(event) => setForm({ ...form, response_format: event.target.value })}
                            placeholder="base64"
                          />
                        </label>
                      </>
                    ) : (
                      <>
                        <label>
                          <span>{language === "zh" ? "图片尺寸" : "Image size"}</span>
                          <input value={form.size} onChange={(event) => setForm({ ...form, size: event.target.value })} />
                        </label>
                        <label>
                          <span>{language === "zh" ? "图片质量" : "Image quality"}</span>
                          <input
                            value={form.quality}
                            onChange={(event) => setForm({ ...form, quality: event.target.value })}
                            placeholder={language === "zh" ? "留空通常最兼容" : "Blank is most compatible"}
                          />
                        </label>
                        <label className="inline-check wide-field">
                          <input
                            type="checkbox"
                            checked={form.response_format === "b64_json"}
                            onChange={(event) => setForm({ ...form, response_format: event.target.checked ? "b64_json" : "" })}
                          />
                          {language === "zh" ? "返回 Base64 图片数据" : "Return Base64 image data"}
                        </label>
                      </>
                    )}
                    <label className="inline-check wide-field">
                      <input
                        type="checkbox"
                        checked={form.real_image_test}
                        onChange={(event) => setForm({ ...form, real_image_test: event.target.checked })}
                      />
                      {language === "zh" ? "测试时真实生成一张小测试图" : "Generate a real test image when testing"}
                    </label>
                  </>
                )}
              </div>

              <div className="api-settings-actions">
                <button className="secondary-button" type="button" disabled={isTesting} onClick={test}>
                  <Plug size={16} />
                  {isTesting ? (language === "zh" ? "测试中..." : "Testing...") : language === "zh" ? "测试" : "Test"}
                </button>
                <button className="primary-cta" type="button" disabled={isSaving} onClick={save}>
                  <strong>{isSaving ? (language === "zh" ? "保存中..." : "Saving...") : language === "zh" ? "保存配置" : "Save setting"}</strong>
                  <Save size={17} />
                </button>
                <button className="secondary-button" type="button" onClick={() => refresh()}>
                  {language === "zh" ? "刷新" : "Refresh"}
                </button>
              </div>
              {message ? <p className={isErrorMessage(message) ? "disabled-reason" : "hint"}>{message}</p> : null}
              {testResult ? <TestResultPreview result={testResult} /> : null}
            </form>
          </div>
        )}
      </section>
    </div>
  );
}

function TestResultPreview({ result }: { result: ApiTestResult }) {
  return (
    <div className="api-test-result">
      {Object.entries(result).map(([key, value]) => (
        <div key={key}>
          <span>{key}</span>
          <strong>{String(value ?? "")}</strong>
        </div>
      ))}
    </div>
  );
}

function QuotaMetric({
  label,
  counter,
  formatter = formatNumber,
}: {
  label: string;
  counter: QuotaCounter;
  formatter?: (value: number) => string;
}) {
  return (
    <div className="quota-limit-row">
      <span>{label}</span>
      <strong>
        {formatter(counter.used ?? 0)}
        {counter.limit > 0 ? ` / ${formatter(counter.limit)}` : ""}
      </strong>
    </div>
  );
}

function formFromItem(item: ApiSettingItem | ImageApiSettingItem | undefined, mode: Exclude<ApiMode, "audio">): ApiFormState {
  if (!item) return defaultForm(mode);
  const image = item as ImageApiSettingItem;
  return {
    id: item.id,
    name: item.name ?? "",
    provider: item.provider ?? "compatible",
    protocol: image.protocol ?? inferImageProtocol(image),
    base_url: item.base_url ?? "",
    model: item.model ?? "",
    api_key: "",
    timeout: String(item.timeout ?? (mode === "image" ? 120 : 60)),
    max_retries: String(item.max_retries ?? 2),
    size: image.size ?? "1024x1024",
    quality: image.quality ?? "auto",
    aspect_ratio: image.aspect_ratio ?? inferAspectRatio(image.size),
    response_format: image.response_format ?? "",
    real_image_test: false,
    make_active: true,
  };
}

function formFromAsrItem(item?: AsrSettingItem): AsrFormState {
  if (!item) return { ...emptyAsrForm };
  return {
    provider: item.provider ?? "compatible",
    base_url: item.base_url ?? "",
    model: item.model ?? "",
    api_key: "",
    timeout: String(item.timeout ?? 60),
  };
}

function defaultForm(mode: Exclude<ApiMode, "audio">): ApiFormState {
  return {
    ...emptyForm,
    timeout: mode === "image" ? "120" : "60",
  };
}

function toChatInput(form: ApiFormState): ApiSettingInput {
  return {
    id: form.id,
    name: form.name.trim(),
    provider: form.provider.trim() || "compatible",
    protocol: form.protocol || "openai_compatible",
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    timeout: numberOrUndefined(form.timeout),
    max_retries: numberOrUndefined(form.max_retries),
    make_active: form.make_active,
  };
}

function toImageInput(form: ApiFormState): ImageApiSettingInput {
  return {
    id: form.id,
    name: form.name.trim(),
    provider: form.provider.trim() || "compatible",
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    timeout: numberOrUndefined(form.timeout),
    size: normalizeImageSize(form.size),
    quality: form.quality.trim() || "auto",
    aspect_ratio: form.aspect_ratio.trim() || inferAspectRatio(form.size),
    response_format: form.protocol === "minimax" ? form.response_format.trim() || "base64" : form.response_format,
    make_active: form.make_active,
  };
}

function toAsrInput(form: AsrFormState): AsrSettingInput {
  return {
    provider: form.provider.trim() || "compatible",
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    timeout: numberOrUndefined(form.timeout),
  };
}

function inferImageProtocol(item: ImageApiSettingItem) {
  const provider = (item.provider || "").toLowerCase();
  const baseUrl = (item.base_url || "").toLowerCase();
  if (provider === "minimax" || baseUrl.includes("minimaxi.com")) return "minimax";
  return "openai_compatible";
}

function inferAspectRatio(size?: string) {
  const normalized = normalizeImageSize(size || "");
  const [widthText, heightText] = normalized.split("x");
  const width = Number(widthText);
  const height = Number(heightText);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return "1:1";
  if (width === height) return "1:1";
  return width > height ? "16:9" : "9:16";
}

function normalizeImageSize(value: string) {
  const size = value.trim().replace(/[×ｘＸ* ]/g, (match) => (match === " " ? "" : "x"));
  return size || "1024x1024";
}

function numberOrUndefined(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isTestOk(result: ApiTestResult) {
  return result.ok === true || result.ok === "true";
}

function resultMessage(result: ApiTestResult) {
  const message = result.message ?? result.error ?? result.detail;
  return typeof message === "string" ? message : JSON.stringify(result);
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 || index === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[index]}`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function isErrorMessage(message: string) {
  const normalized = message.toLowerCase();
  return normalized.includes("error") || normalized.includes("failed") || message.includes("失败");
}
