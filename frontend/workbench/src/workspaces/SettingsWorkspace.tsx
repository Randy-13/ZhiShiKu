import {
  CheckCircle2,
  Cookie,
  Database,
  ExternalLink,
  FolderOpen,
  KeyRound,
  Palette,
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
  DatabaseStatus,
  HtmlGrabCheckStatus,
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
  WechatPublisherBindingStatus,
} from "../api";
import { PrimaryTaskPanel } from "../components/PrimaryTaskPanel";
import { StatusBadge } from "../components/StatusBadge";
import type { ActivityEvent, Language, TextExtractionMode, XhsLoginStatus } from "../domain";
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

type WechatPublisherFormState = {
  appid: string;
  appsecret: string;
  accountName: string;
  author: string;
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

const emptyWechatPublisherForm: WechatPublisherFormState = {
  appid: "",
  appsecret: "",
  accountName: "",
  author: "Bobo",
};

const SETTINGS_STATUS_CACHE_KEY = "figurelearning.settings.statusSnapshot.v1";

type SettingsStatusCache = {
  version: 1;
  lastRefreshedAt?: string;
  cookieStatus?: BilibiliCookieStatus;
  dependencyStatus?: MediaDependencyStatus;
  dependencyMessage?: string;
  htmlGrabStatus?: HtmlGrabCheckStatus;
  htmlGrabMessage?: string;
  storageLocations?: StorageLocations;
  trashStatus?: TrashStatus;
  quotaStatus?: QuotaStatus;
  quotaMessage?: string;
  databaseStatus?: DatabaseStatus;
  databaseMessage?: string;
  wechatPublisherStatus?: WechatPublisherBindingStatus;
  wechatPublisherMessage?: string;
  xhsAuthStatus?: XhsLoginStatus;
  xhsAuthMessage?: string;
};

function readSettingsStatusCache(): SettingsStatusCache | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(SETTINGS_STATUS_CACHE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as Partial<SettingsStatusCache>;
    if (parsed.version !== 1) return undefined;
    return parsed as SettingsStatusCache;
  } catch {
    return undefined;
  }
}

function writeSettingsStatusCache(snapshot: SettingsStatusCache) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SETTINGS_STATUS_CACHE_KEY, JSON.stringify(snapshot));
  } catch {
    // Local storage can be unavailable in privacy modes; the UI should still work.
  }
}

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
  visualTheme,
  textExtractionMode,
  activities,
  rightRail,
  onLanguageChange,
  onVisualThemeChange,
  onTextExtractionModeChange,
  onSave,
}: {
  t: Translator;
  language: Language;
  visualTheme: "dark" | "light";
  textExtractionMode: TextExtractionMode;
  activities: ActivityEvent[];
  rightRail: ReactNode;
  onLanguageChange: (language: Language) => void;
  onVisualThemeChange: (theme: "dark" | "light") => void;
  onTextExtractionModeChange: (mode: TextExtractionMode) => void;
  onSave: () => void;
}) {
  const [apiModalOpen, setApiModalOpen] = useState(false);
  const [dependencyModalOpen, setDependencyModalOpen] = useState(false);
  const [creatorAccountsModalOpen, setCreatorAccountsModalOpen] = useState(false);
  const [localDataModalOpen, setLocalDataModalOpen] = useState(false);
  const [cookieStatus, setCookieStatus] = useState<BilibiliCookieStatus>();
  const [cookieLoading, setCookieLoading] = useState(false);
  const [cookieActionMessage, setCookieActionMessage] = useState("");
  const [dependencyStatus, setDependencyStatus] = useState<MediaDependencyStatus>();
  const [dependencyLoading, setDependencyLoading] = useState(false);
  const [dependencyMessage, setDependencyMessage] = useState("");
  const [htmlGrabStatus, setHtmlGrabStatus] = useState<HtmlGrabCheckStatus>();
  const [htmlGrabLoading, setHtmlGrabLoading] = useState(false);
  const [htmlGrabMessage, setHtmlGrabMessage] = useState("");
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
  const [databaseStatus, setDatabaseStatus] = useState<DatabaseStatus>();
  const [databaseLoading, setDatabaseLoading] = useState(false);
  const [databaseMessage, setDatabaseMessage] = useState("");
  const [wechatPublisherStatus, setWechatPublisherStatus] = useState<WechatPublisherBindingStatus>();
  const [wechatPublisherForm, setWechatPublisherForm] = useState<WechatPublisherFormState>(emptyWechatPublisherForm);
  const [wechatPublisherLoading, setWechatPublisherLoading] = useState(false);
  const [wechatPublisherMessage, setWechatPublisherMessage] = useState("");
  const [xhsAuthStatus, setXhsAuthStatus] = useState<XhsLoginStatus>();
  const [xhsAuthLoading, setXhsAuthLoading] = useState(false);
  const [xhsAuthMessage, setXhsAuthMessage] = useState("");
  const [settingsStatusCache, setSettingsStatusCache] = useState<SettingsStatusCache>({ version: 1 });
  const [globalRefreshLoading, setGlobalRefreshLoading] = useState(false);
  const [globalRefreshMessage, setGlobalRefreshMessage] = useState("");

  const canManageSystemSettings = authContext
    ? authContext.deploymentMode !== "cloud" || authContext.user?.role === "admin"
    : false;
  const canViewRuntimeLog = Boolean(authContext?.authenticated);
  const localDiagnosticsVisible = canManageSystemSettings;

  function updateSettingsStatusCache(patch: Partial<SettingsStatusCache>, options: { markRefreshed?: boolean } = {}) {
    setSettingsStatusCache((current) => {
      const next: SettingsStatusCache = {
        ...current,
        ...patch,
        version: 1,
        lastRefreshedAt: options.markRefreshed ? new Date().toISOString() : (patch.lastRefreshedAt ?? current.lastRefreshedAt),
      };
      writeSettingsStatusCache(next);
      return next;
    });
  }

  function applySettingsStatusCache(snapshot: SettingsStatusCache) {
    setSettingsStatusCache(snapshot);
    if (snapshot.cookieStatus) setCookieStatus(snapshot.cookieStatus);
    if (snapshot.dependencyStatus) setDependencyStatus(snapshot.dependencyStatus);
    if (typeof snapshot.dependencyMessage === "string") setDependencyMessage(snapshot.dependencyMessage);
    if (snapshot.htmlGrabStatus) setHtmlGrabStatus(snapshot.htmlGrabStatus);
    if (typeof snapshot.htmlGrabMessage === "string") setHtmlGrabMessage(snapshot.htmlGrabMessage);
    if (snapshot.storageLocations) {
      setStorageLocations(snapshot.storageLocations);
      setStorageDraft(snapshot.storageLocations);
    }
    if (snapshot.trashStatus) setTrashStatus(snapshot.trashStatus);
    if (snapshot.quotaStatus) setQuotaStatus(snapshot.quotaStatus);
    if (typeof snapshot.quotaMessage === "string") setQuotaMessage(snapshot.quotaMessage);
    if (snapshot.databaseStatus) setDatabaseStatus(snapshot.databaseStatus);
    if (typeof snapshot.databaseMessage === "string") setDatabaseMessage(snapshot.databaseMessage);
    if (snapshot.wechatPublisherStatus) applyWechatPublisherStatus(snapshot.wechatPublisherStatus);
    if (typeof snapshot.wechatPublisherMessage === "string") setWechatPublisherMessage(snapshot.wechatPublisherMessage);
    if (snapshot.xhsAuthStatus) setXhsAuthStatus(snapshot.xhsAuthStatus);
    if (typeof snapshot.xhsAuthMessage === "string") setXhsAuthMessage(snapshot.xhsAuthMessage);
  }

  async function refreshCookieStatus() {
    setCookieLoading(true);
    setCookieActionMessage("");
    try {
      const status = await settingsApi.bilibiliCookieStatus();
      setCookieStatus(status);
      updateSettingsStatusCache({ cookieStatus: status });
      return status;
    } catch (error) {
      const status = { ok: false, message: error instanceof Error ? error.message : String(error) };
      setCookieStatus(status);
      updateSettingsStatusCache({ cookieStatus: status });
      return status;
    } finally {
      setCookieLoading(false);
    }
  }

  async function refreshDependencyStatus() {
    setDependencyLoading(true);
    setDependencyMessage("");
    try {
      const status = await settingsApi.mediaDependencies();
      setDependencyStatus(status);
      updateSettingsStatusCache({ dependencyStatus: status, dependencyMessage: "" });
      return status;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDependencyMessage(message);
      updateSettingsStatusCache({ dependencyMessage: message });
      return undefined;
    } finally {
      setDependencyLoading(false);
    }
  }

  async function refreshAllDependencyStatus() {
    await Promise.all([refreshDependencyStatus(), refreshCookieStatus(), refreshHtmlGrabStatus()]);
  }

  async function refreshQuotaStatus() {
    setQuotaMessage("");
    try {
      const status = await quotaApi.me();
      setQuotaStatus(status);
      updateSettingsStatusCache({ quotaStatus: status, quotaMessage: "" });
      return status;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setQuotaMessage(message);
      updateSettingsStatusCache({ quotaMessage: message });
      return undefined;
    }
  }

  async function refreshDatabaseStatus() {
    setDatabaseLoading(true);
    setDatabaseMessage("");
    try {
      const status = await settingsApi.databaseStatus();
      setDatabaseStatus(status);
      updateSettingsStatusCache({ databaseStatus: status, databaseMessage: "" });
      return status;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDatabaseMessage(message);
      updateSettingsStatusCache({ databaseMessage: message });
      return undefined;
    } finally {
      setDatabaseLoading(false);
    }
  }

  function applyWechatPublisherStatus(status: WechatPublisherBindingStatus) {
    setWechatPublisherStatus(status);
    setWechatPublisherForm({
      appid: status.appid || "",
      appsecret: "",
      accountName: status.account_name || "",
      author: status.author || "Bobo",
    });
  }

  async function refreshWechatPublisherBinding() {
    setWechatPublisherLoading(true);
    setWechatPublisherMessage("");
    try {
      const status = await settingsApi.wechatPublisherBinding();
      applyWechatPublisherStatus(status);
      updateSettingsStatusCache({ wechatPublisherStatus: status, wechatPublisherMessage: "" });
      return status;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWechatPublisherMessage(message);
      updateSettingsStatusCache({ wechatPublisherMessage: message });
      return undefined;
    } finally {
      setWechatPublisherLoading(false);
    }
  }

  async function saveWechatPublisherBinding() {
    setWechatPublisherLoading(true);
    setWechatPublisherMessage("");
    try {
      const result = await settingsApi.saveWechatPublisherBinding({
        appid: wechatPublisherForm.appid.trim(),
        appsecret: wechatPublisherForm.appsecret.trim() || undefined,
        account_name: wechatPublisherForm.accountName.trim(),
        author: wechatPublisherForm.author.trim() || "Bobo",
      });
      applyWechatPublisherStatus(result);
      updateSettingsStatusCache({ wechatPublisherStatus: result });
      setWechatPublisherMessage(language === "zh" ? "公众号绑定已保存。" : "WeChat account binding saved.");
    } catch (error) {
      setWechatPublisherMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setWechatPublisherLoading(false);
    }
  }

  async function refreshWechatPublisherToken() {
    setWechatPublisherLoading(true);
    setWechatPublisherMessage("");
    try {
      const result = await settingsApi.refreshWechatPublisherToken();
      setWechatPublisherMessage(String(result.message || (result.ok ? "Token OK" : "Token check failed")));
      await refreshWechatPublisherBinding();
    } catch (error) {
      setWechatPublisherMessage(error instanceof Error ? error.message : String(error));
      setWechatPublisherLoading(false);
    }
  }

  function applyXhsAuthStatus(status: XhsLoginStatus) {
    setXhsAuthStatus(status);
    setXhsAuthMessage(String(status.message || status.hint || status.error || status.stderr || ""));
  }

  async function refreshXhsAuthStatus() {
    setXhsAuthLoading(true);
    setXhsAuthMessage("");
    try {
      const status = await settingsApi.xhsAuthStatus();
      applyXhsAuthStatus(status);
      updateSettingsStatusCache({ xhsAuthStatus: status, xhsAuthMessage: String(status.message || status.hint || status.error || status.stderr || "") });
      return status;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = { ok: false, logged_in: false, error: message };
      setXhsAuthStatus(status);
      setXhsAuthMessage(message);
      updateSettingsStatusCache({ xhsAuthStatus: status, xhsAuthMessage: message });
      return status;
    } finally {
      setXhsAuthLoading(false);
    }
  }

  async function requestXhsQrcode() {
    setXhsAuthLoading(true);
    setXhsAuthMessage("");
    try {
      const status = await settingsApi.xhsAuthQrcode();
      applyXhsAuthStatus(status);
      updateSettingsStatusCache({ xhsAuthStatus: status, xhsAuthMessage: String(status.message || status.hint || status.error || status.stderr || "") });
    } catch (error) {
      setXhsAuthStatus((current) => ({ ...current, ok: false, error: error instanceof Error ? error.message : String(error) }));
      setXhsAuthMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setXhsAuthLoading(false);
    }
  }

  async function waitXhsLogin() {
    setXhsAuthLoading(true);
    setXhsAuthMessage("");
    try {
      const status = await settingsApi.xhsAuthWaitLogin();
      applyXhsAuthStatus(status);
      updateSettingsStatusCache({ xhsAuthStatus: status, xhsAuthMessage: String(status.message || status.hint || status.error || status.stderr || "") });
    } catch (error) {
      setXhsAuthStatus((current) => ({ ...current, ok: false, error: error instanceof Error ? error.message : String(error) }));
      setXhsAuthMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setXhsAuthLoading(false);
    }
  }

  async function logoutXhsAuth() {
    setXhsAuthLoading(true);
    setXhsAuthMessage("");
    try {
      const status = await settingsApi.xhsAuthLogout();
      applyXhsAuthStatus(status);
      updateSettingsStatusCache({ xhsAuthStatus: status, xhsAuthMessage: String(status.message || status.hint || status.error || status.stderr || "") });
      await refreshXhsAuthStatus();
    } catch (error) {
      setXhsAuthStatus((current) => ({ ...current, ok: false, error: error instanceof Error ? error.message : String(error) }));
      setXhsAuthMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setXhsAuthLoading(false);
    }
  }

  async function refreshHtmlGrabStatus() {
    setHtmlGrabLoading(true);
    setHtmlGrabMessage("");
    try {
      const status = await settingsApi.htmlGrabCheck();
      setHtmlGrabStatus(status);
      updateSettingsStatusCache({ htmlGrabStatus: status, htmlGrabMessage: "" });
      return status;
    } catch (error) {
      const status = { ok: false, message: error instanceof Error ? error.message : String(error) };
      setHtmlGrabStatus(status);
      updateSettingsStatusCache({ htmlGrabStatus: status, htmlGrabMessage: status.message });
      return status;
    } finally {
      setHtmlGrabLoading(false);
    }
  }

  async function openHtmlGrabAuthorize() {
    setHtmlGrabLoading(true);
    setHtmlGrabMessage("");
    try {
      const result = await settingsApi.htmlGrabAuthorize();
      setHtmlGrabMessage(result.message || (language === "zh" ? "已打开 Edge 授权页。" : "Opened Edge dev session window."));
    } catch (error) {
      setHtmlGrabMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setHtmlGrabLoading(false);
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
      updateSettingsStatusCache({ storageLocations: locations });
      return locations;
    } catch (error) {
      setStorageMessage(error instanceof Error ? error.message : String(error));
      return undefined;
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
      updateSettingsStatusCache({ storageLocations: locations });
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
      const status = await settingsApi.trashStatus();
      setTrashStatus(status);
      updateSettingsStatusCache({ trashStatus: status });
      return status;
    } catch (error) {
      setTrashMessage(error instanceof Error ? error.message : String(error));
      return undefined;
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
      updateSettingsStatusCache({ trashStatus: result });
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

  async function refreshAllSettingsStatus() {
    if (globalRefreshLoading) return;
    setGlobalRefreshLoading(true);
    setGlobalRefreshMessage("");
    const tasks: Array<Promise<unknown>> = [
      refreshQuotaStatus(),
      refreshDependencyStatus(),
      refreshCookieStatus(),
      refreshHtmlGrabStatus(),
      refreshWechatPublisherBinding(),
    ];
    if (canManageSystemSettings) {
      tasks.push(refreshXhsAuthStatus(), refreshStorageLocations(), refreshTrashStatus(), refreshDatabaseStatus());
    }
    await Promise.allSettled(tasks);
    updateSettingsStatusCache({}, { markRefreshed: true });
    setGlobalRefreshMessage(language === "zh" ? "状态已刷新并保存。" : "Status refreshed and saved.");
    setGlobalRefreshLoading(false);
  }

  useEffect(() => {
    const cached = readSettingsStatusCache();
    if (cached) applySettingsStatusCache(cached);
    authApi
      .me()
      .then((context) => {
        setAuthContext(context);
      })
      .catch(() => undefined);
  }, []);

  const dependencyItems = useMemo(() => Object.entries(dependencyStatus ?? {}), [dependencyStatus]);
  const databaseTableItems = useMemo(
    () =>
      Object.entries(databaseStatus?.tables ?? {})
        .filter(([, count]) => count >= 0)
        .sort(([a], [b]) => a.localeCompare(b)),
    [databaseStatus],
  );
  const duplicateHashCount = useMemo(
    () => Object.values(databaseStatus?.duplicate_hashes ?? {}).reduce((total, rows) => total + rows.length, 0),
    [databaseStatus],
  );
  const readyCount = dependencyItems.filter(([, item]) => item.available || item.configured || item.verified).length;
  const dependencyReadyCount = readyCount + (cookieStatus?.ok ? 1 : 0) + (htmlGrabStatus?.ok ? 1 : 0);
  const dependencyTotalCount = dependencyItems.length + 2;
  const dependencySummary =
    dependencyTotalCount > 2 || cookieStatus || htmlGrabStatus
      ? language === "zh"
        ? `${dependencyReadyCount}/${dependencyTotalCount} 项可用`
        : `${dependencyReadyCount}/${dependencyTotalCount} ready`
      : language === "zh"
        ? "查看依赖状态"
        : "Review dependency status";
  const dependencyHealthItems = [
    {
      key: "core",
      label: language === "zh" ? "核心工具" : "Core tools",
      ready: dependencyItems.length > 0 && readyCount === dependencyItems.length,
      detail:
        dependencyItems.length > 0
          ? language === "zh"
            ? `${readyCount}/${dependencyItems.length}`
            : `${readyCount}/${dependencyItems.length}`
          : language === "zh"
            ? "未检查"
            : "Not checked",
    },
    {
      key: "cookie",
      label: language === "zh" ? "B 站字幕" : "Bilibili subtitles",
      ready: Boolean(cookieStatus?.ok),
      detail: cookieStatus ? (cookieStatus.ok ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "需处理" : "Action needed") : language === "zh" ? "未检查" : "Not checked",
    },
    {
      key: "html",
      label: language === "zh" ? "网页提取" : "Web extraction",
      ready: Boolean(htmlGrabStatus?.ok),
      detail: htmlGrabStatus ? (htmlGrabStatus.ok ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "需处理" : "Action needed") : language === "zh" ? "未检查" : "Not checked",
    },
  ];
  const lastRefreshedLabel = settingsStatusCache.lastRefreshedAt
    ? new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(settingsStatusCache.lastRefreshedAt))
    : "";
  const globalRefreshHint = globalRefreshMessage || (settingsStatusCache.lastRefreshedAt
    ? language === "zh"
      ? `从缓存读取，上次刷新：${lastRefreshedLabel}`
      : `Loaded from cache. Last refresh: ${lastRefreshedLabel}`
    : language === "zh"
      ? "尚未刷新。点击刷新获取当前状态。"
      : "Not refreshed yet. Click refresh to get the current status.");

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

        <section className="content-panel settings-refresh-panel">
          <div className="settings-refresh-copy">
            <span>{language === "zh" ? "设置中心状态" : "Settings status"}</span>
            <strong>
              {settingsStatusCache.lastRefreshedAt
                ? language === "zh"
                  ? "已保存最近一次检查结果"
                  : "Latest check is cached"
                : language === "zh"
                  ? "等待手动刷新"
                  : "Waiting for manual refresh"}
            </strong>
            <p>{globalRefreshHint}</p>
          </div>
          <button className="primary-cta" type="button" onClick={refreshAllSettingsStatus} disabled={globalRefreshLoading}>
            <strong>{globalRefreshLoading ? (language === "zh" ? "刷新中..." : "Refreshing...") : language === "zh" ? "刷新全部状态" : "Refresh all status"}</strong>
            <RefreshCw size={17} className={globalRefreshLoading ? "spin-icon" : undefined} />
          </button>
        </section>

        <section className="content-panel settings-grid">
          <div className="style-settings-card">
            <div className="dependency-check-title">
              <Palette size={17} />
              <h2>{language === "zh" ? "风格设置" : "Style settings"}</h2>
            </div>
            <p className="hint">
              {language === "zh"
                ? "选择工作台整体配色。深色使用 Civitas 深青底，浅色恢复之前的浅绿色纸面。"
                : "Choose the workbench palette. Dark uses the Civitas deep teal base; light restores the earlier pale green paper style."}
            </p>
            <div className="theme-option-grid" role="radiogroup" aria-label={language === "zh" ? "工作台风格" : "Workbench style"}>
              <button
                className={visualTheme === "dark" ? "theme-option selected" : "theme-option"}
                type="button"
                role="radio"
                aria-checked={visualTheme === "dark"}
                onClick={() => onVisualThemeChange("dark")}
              >
                <span className="theme-swatch theme-swatch-dark" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <strong>{language === "zh" ? "深色 Civitas" : "Dark Civitas"}</strong>
                <small>{language === "zh" ? "深青背景，浅色控件与金色提示" : "Deep teal base with light controls and gold cues"}</small>
              </button>
              <button
                className={visualTheme === "light" ? "theme-option selected" : "theme-option"}
                type="button"
                role="radio"
                aria-checked={visualTheme === "light"}
                onClick={() => onVisualThemeChange("light")}
              >
                <span className="theme-swatch theme-swatch-light" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <strong>{language === "zh" ? "浅色纸面" : "Light paper"}</strong>
                <small>{language === "zh" ? "浅绿色纸面，低边框与墨色文字" : "Pale green paper surfaces with quiet borders"}</small>
              </button>
            </div>
          </div>

          {canManageSystemSettings ? (
            <div className="settings-action-card">
              <div>
                <h2>{t("settings.api")}</h2>
              </div>
              <button className="secondary-button" type="button" onClick={() => setApiModalOpen(true)}>
                <Plug size={16} />
                {language === "zh" ? "配置 API" : "Configure API"}
              </button>
            </div>
          ) : null}

          <div className="settings-action-card creator-account-entry">
            <div>
              <h2>{language === "zh" ? "创作者账号" : "Creator accounts"}</h2>
              <p className="hint">
                {language === "zh"
                  ? `公众号：${wechatPublisherStatus?.configured ? "已绑定" : "未绑定"}；小红书：${xhsAuthStatus?.logged_in ? "已登录" : "未登录"}`
                  : `WeChat: ${wechatPublisherStatus?.configured ? "bound" : "not bound"}; XHS: ${xhsAuthStatus?.logged_in ? "logged in" : "not logged in"}`}
              </p>
            </div>
            <button className="secondary-button" type="button" onClick={() => setCreatorAccountsModalOpen(true)}>
              <KeyRound size={16} />
              {language === "zh" ? "管理账号" : "Manage accounts"}
            </button>
          </div>

          <div className="settings-action-card">
            <div>
              <h2>{t("settings.dependencies")}</h2>
              <p className="hint">{dependencyMessage || dependencySummary}</p>
              <div className="dependency-health-list">
                {dependencyHealthItems.map((item) => (
                  <span key={item.key} className={item.ready ? "dependency-health-pill ready" : "dependency-health-pill"}>
                    <CheckCircle2 size={14} />
                    <strong>{item.label}</strong>
                    <em>{item.detail}</em>
                  </span>
                ))}
              </div>
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

          {canManageSystemSettings ? (
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

              <div className="settings-action-card local-data-entry">
                <div>
                  <h2>{language === "zh" ? "本地数据" : "Local data"}</h2>
                  <p className="hint">
                    {language === "zh"
                      ? `数据库：${databaseStatus?.backend ?? "未检查"}；存储：${storageLocations.root ?? "未检查"}`
                      : `Database: ${databaseStatus?.backend ?? "not checked"}; storage: ${storageLocations.root ?? "not checked"}`}
                  </p>
                </div>
                <button className="secondary-button" type="button" onClick={() => setLocalDataModalOpen(true)}>
                  <Database size={16} />
                  {language === "zh" ? "管理数据" : "Manage data"}
                </button>
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

        </section>

        {canViewRuntimeLog ? (
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
        ) : null}
      </div>

      {rightRail}

      {apiModalOpen && canManageSystemSettings ? <ApiSettingsModal language={language} onClose={() => setApiModalOpen(false)} /> : null}

      {dependencyModalOpen ? (
        <DependencyStatusModal
          language={language}
          cookieStatus={cookieStatus}
          cookieLoading={cookieLoading}
          cookieActionMessage={cookieActionMessage}
          htmlGrabStatus={htmlGrabStatus}
          htmlGrabLoading={htmlGrabLoading}
          htmlGrabMessage={htmlGrabMessage}
          dependencyStatus={dependencyStatus}
          dependencyLoading={dependencyLoading}
          dependencyMessage={dependencyMessage}
          localDiagnosticsVisible={localDiagnosticsVisible}
          onClose={() => setDependencyModalOpen(false)}
          onRefreshAllDependencies={refreshAllDependencyStatus}
          onRefreshCookies={refreshCookieStatus}
          onRefreshHtmlGrab={refreshHtmlGrabStatus}
          onOpenCookieLogin={localDiagnosticsVisible ? openCookieLogin : undefined}
          onOpenHtmlGrabAuthorize={localDiagnosticsVisible ? openHtmlGrabAuthorize : undefined}
        />
      ) : null}

      {creatorAccountsModalOpen ? (
        <CreatorAccountsModal
          language={language}
          authContext={authContext}
          wechatStatus={wechatPublisherStatus}
          wechatForm={wechatPublisherForm}
          wechatLoading={wechatPublisherLoading}
          wechatMessage={wechatPublisherMessage}
          xhsStatus={xhsAuthStatus}
          xhsLoading={xhsAuthLoading}
          xhsMessage={xhsAuthMessage}
          localDiagnosticsVisible={localDiagnosticsVisible}
          onClose={() => setCreatorAccountsModalOpen(false)}
          onWechatFormChange={setWechatPublisherForm}
          onRefreshWechat={refreshWechatPublisherBinding}
          onSaveWechat={saveWechatPublisherBinding}
          onRefreshWechatToken={refreshWechatPublisherToken}
          onRefreshXhs={refreshXhsAuthStatus}
          onRequestXhsQrcode={requestXhsQrcode}
          onWaitXhsLogin={waitXhsLogin}
          onLogoutXhs={logoutXhsAuth}
        />
      ) : null}

      {localDataModalOpen && canManageSystemSettings ? (
        <LocalDataModal
          language={language}
          storageLocations={storageLocations}
          storageDraft={storageDraft}
          storageLoading={storageLoading}
          storageMessage={storageMessage}
          databaseStatus={databaseStatus}
          databaseLoading={databaseLoading}
          databaseMessage={databaseMessage}
          databaseTableItems={databaseTableItems}
          duplicateHashCount={duplicateHashCount}
          onClose={() => setLocalDataModalOpen(false)}
          onStorageDraftChange={setStorageDraft}
          onRefreshStorage={refreshStorageLocations}
          onSaveStorage={saveStorageLocations}
          onRefreshDatabase={refreshDatabaseStatus}
        />
      ) : null}

      {trashModalOpen && canManageSystemSettings ? (
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
              updateSettingsStatusCache({ trashStatus: result });
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
              updateSettingsStatusCache({ trashStatus: result });
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

function CreatorAccountsModal({
  language,
  authContext,
  wechatStatus,
  wechatForm,
  wechatLoading,
  wechatMessage,
  xhsStatus,
  xhsLoading,
  xhsMessage,
  localDiagnosticsVisible,
  onClose,
  onWechatFormChange,
  onRefreshWechat,
  onSaveWechat,
  onRefreshWechatToken,
  onRefreshXhs,
  onRequestXhsQrcode,
  onWaitXhsLogin,
  onLogoutXhs,
}: {
  language: Language;
  authContext?: AuthContext;
  wechatStatus?: WechatPublisherBindingStatus;
  wechatForm: WechatPublisherFormState;
  wechatLoading: boolean;
  wechatMessage: string;
  xhsStatus?: XhsLoginStatus;
  xhsLoading: boolean;
  xhsMessage: string;
  localDiagnosticsVisible: boolean;
  onClose: () => void;
  onWechatFormChange: (form: WechatPublisherFormState | ((current: WechatPublisherFormState) => WechatPublisherFormState)) => void;
  onRefreshWechat: () => Promise<void>;
  onSaveWechat: () => Promise<void>;
  onRefreshWechatToken: () => Promise<void>;
  onRefreshXhs: () => Promise<void>;
  onRequestXhsQrcode: () => Promise<void>;
  onWaitXhsLogin: () => Promise<void>;
  onLogoutXhs: () => Promise<void>;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel creator-account-modal" role="dialog" aria-modal="true" aria-label={language === "zh" ? "创作者账号" : "Creator accounts"}>
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "设置" : "Settings"}</span>
            <h2>{language === "zh" ? "创作者账号" : "Creator accounts"}</h2>
          </div>
          <button className="icon-button" type="button" aria-label={language === "zh" ? "关闭" : "Close"} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="creator-account-modal-grid">
          <section className="wechat-publisher-card">
            <div className="dependency-check-title">
              <KeyRound size={17} />
              <h3>{language === "zh" ? "公众号发布绑定" : "WeChat publishing"}</h3>
              <StatusBadge tone={wechatStatus?.configured ? "done" : "error"}>
                {wechatStatus?.configured ? (language === "zh" ? "已绑定" : "Bound") : language === "zh" ? "未绑定" : "Not bound"}
              </StatusBadge>
            </div>
            <p className="hint">
              {language === "zh"
                ? `当前用户：${wechatStatus?.username || authContext?.user?.username || "-"}；发布会进入该用户绑定公众号的草稿箱。`
                : `Current user: ${wechatStatus?.username || authContext?.user?.username || "-"}; drafts go to this user's bound WeChat account.`}
            </p>
            <div className="wechat-publisher-form">
              <label>
                <span>{language === "zh" ? "公众号名称" : "Account name"}</span>
                <input
                  value={wechatForm.accountName}
                  onChange={(event) => onWechatFormChange((current) => ({ ...current, accountName: event.target.value }))}
                  placeholder={language === "zh" ? "例如：Bobo 的公众号" : "Example: Bobo's account"}
                  autoComplete="off"
                  name="wechat-publisher-account-name"
                />
              </label>
              <label>
                <span>AppID</span>
                <input
                  value={wechatForm.appid}
                  onChange={(event) => onWechatFormChange((current) => ({ ...current, appid: event.target.value }))}
                  placeholder="wx..."
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                  name="wechat-publisher-appid"
                />
              </label>
              <label>
                <span>AppSecret</span>
                <input
                  type="password"
                  value={wechatForm.appsecret}
                  onChange={(event) => onWechatFormChange((current) => ({ ...current, appsecret: event.target.value }))}
                  placeholder={wechatStatus?.configured ? (language === "zh" ? "留空表示不修改" : "Leave blank to keep current secret") : ""}
                  autoComplete="new-password"
                  name="wechat-publisher-appsecret-new"
                />
              </label>
              <label>
                <span>{language === "zh" ? "默认作者" : "Default author"}</span>
                <input
                  value={wechatForm.author}
                  onChange={(event) => onWechatFormChange((current) => ({ ...current, author: event.target.value }))}
                  autoComplete="off"
                  name="wechat-publisher-author"
                />
              </label>
            </div>
            <div className="wechat-publisher-meta">
              <span>Token: {wechatStatus?.token_cached ? (language === "zh" ? "已缓存" : "cached") : language === "zh" ? "未缓存" : "not cached"}</span>
              {wechatStatus?.token_updated_at ? <span>{wechatStatus.token_updated_at}</span> : null}
            </div>
            {wechatMessage ? <p className={isErrorMessage(wechatMessage) ? "inline-error" : "hint"}>{wechatMessage}</p> : null}
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshWechat} disabled={wechatLoading}>
                <RefreshCw size={16} />
                {language === "zh" ? "刷新" : "Refresh"}
              </button>
              <button className="secondary-button" type="button" onClick={onSaveWechat} disabled={wechatLoading || !wechatForm.appid.trim()}>
                <Save size={16} />
                {language === "zh" ? "保存绑定" : "Save binding"}
              </button>
              <button className="secondary-button" type="button" onClick={onRefreshWechatToken} disabled={wechatLoading || !wechatStatus?.configured}>
                <CheckCircle2 size={16} />
                {language === "zh" ? "检测 Token" : "Check token"}
              </button>
            </div>
          </section>

          <section className="xhs-auth-card">
            <div className="dependency-check-title">
              <KeyRound size={17} />
              <h3>{language === "zh" ? "小红书账号" : "Xiaohongshu account"}</h3>
              <StatusBadge tone={xhsStatus?.logged_in ? "done" : "error"}>
                {xhsStatus?.logged_in ? (language === "zh" ? "已登录" : "Logged in") : language === "zh" ? "未登录" : "Not logged in"}
              </StatusBadge>
            </div>
            <p className="hint">
              {language === "zh"
                ? "填入发布页会使用当前小红书网页登录账号。切换账号时先退出当前账号，再扫码登录新账号。"
                : "Publish-page filling uses the current XHS web session. To switch accounts, log out first, then scan in with the new account."}
            </p>
            {xhsMessage ? <p className={isErrorMessage(xhsMessage) ? "inline-error" : "hint"}>{xhsMessage}</p> : null}
            <div className="wechat-publisher-meta">
              <span>{language === "zh" ? `会话：${xhsStatus?.logged_in ? "可用" : "未就绪"}` : `Session: ${xhsStatus?.logged_in ? "ready" : "not ready"}`}</span>
              {xhsStatus?.login_method ? <span>{language === "zh" ? `登录方式：${xhsStatus.login_method}` : `Method: ${xhsStatus.login_method}`}</span> : null}
              {typeof xhsStatus?.returncode === "number" ? <span>{language === "zh" ? `返回码：${xhsStatus.returncode}` : `Exit: ${xhsStatus.returncode}`}</span> : null}
            </div>
            {xhsStatus?.qrcode_image_url ? (
              <div className="xhs-qrcode-panel xhs-qrcode-panel-modal">
                <img src={xhsStatus.qrcode_image_url} alt={language === "zh" ? "小红书登录二维码" : "XHS login QR code"} />
                <div>
                  <strong>{language === "zh" ? "请使用小红书 App 扫码" : "Scan with the XHS app"}</strong>
                  {xhsStatus.qr_login_url ? (
                    <a href={xhsStatus.qr_login_url} target="_blank" rel="noreferrer">
                      {language === "zh" ? "手机浏览器打开登录链接" : "Open login link on phone"}
                    </a>
                  ) : null}
                  {xhsStatus.qrcode_path ? <small className="dependency-path">{xhsStatus.qrcode_path}</small> : null}
                </div>
              </div>
            ) : null}
            {!localDiagnosticsVisible ? (
              <p className="disabled-reason">
                {language === "zh" ? "云端普通用户不能操作本机小红书登录，请导出 ZIP 后自行上传。" : "Cloud users cannot control local XHS login. Export the ZIP and upload manually."}
              </p>
            ) : null}
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshXhs} disabled={xhsLoading || !localDiagnosticsVisible}>
                <RefreshCw size={16} />
                {language === "zh" ? "检查登录" : "Check login"}
              </button>
              <button className="secondary-button" type="button" onClick={onRequestXhsQrcode} disabled={xhsLoading || !localDiagnosticsVisible || Boolean(xhsStatus?.logged_in)}>
                <ExternalLink size={16} />
                {language === "zh" ? "扫码登录" : "QR login"}
              </button>
              <button className="secondary-button" type="button" onClick={onWaitXhsLogin} disabled={xhsLoading || !localDiagnosticsVisible || !xhsStatus?.qrcode_image_url}>
                <CheckCircle2 size={16} />
                {language === "zh" ? "等待登录完成" : "Wait for login"}
              </button>
              <button className="secondary-button danger-button" type="button" onClick={onLogoutXhs} disabled={xhsLoading || !localDiagnosticsVisible || !xhsStatus?.logged_in}>
                <Trash2 size={16} />
                {language === "zh" ? "退出当前账号" : "Log out"}
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function LocalDataModal({
  language,
  storageLocations,
  storageDraft,
  storageLoading,
  storageMessage,
  databaseStatus,
  databaseLoading,
  databaseMessage,
  databaseTableItems,
  duplicateHashCount,
  onClose,
  onStorageDraftChange,
  onRefreshStorage,
  onSaveStorage,
  onRefreshDatabase,
}: {
  language: Language;
  storageLocations: StorageLocations;
  storageDraft: StorageLocations;
  storageLoading: boolean;
  storageMessage: string;
  databaseStatus?: DatabaseStatus;
  databaseLoading: boolean;
  databaseMessage: string;
  databaseTableItems: [string, number][];
  duplicateHashCount: number;
  onClose: () => void;
  onStorageDraftChange: (draft: StorageLocations | ((current: StorageLocations) => StorageLocations)) => void;
  onRefreshStorage: () => Promise<void>;
  onSaveStorage: () => Promise<void>;
  onRefreshDatabase: () => Promise<void>;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel local-data-modal" role="dialog" aria-modal="true" aria-label={language === "zh" ? "本地数据" : "Local data"}>
        <div className="modal-title-row">
          <div>
            <span>{language === "zh" ? "设置" : "Settings"}</span>
            <h2>{language === "zh" ? "本地数据" : "Local data"}</h2>
          </div>
          <button className="icon-button" type="button" aria-label={language === "zh" ? "关闭" : "Close"} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="local-data-modal-grid">
          <section className="database-settings-card">
            <div className="dependency-check-title">
              <Database size={17} />
              <h3>{language === "zh" ? "数据管理" : "Data management"}</h3>
              <StatusBadge tone={databaseStatus?.ok ? "done" : "error"}>
                {databaseStatus?.ok ? (language === "zh" ? "连接正常" : "Connected") : language === "zh" ? "需检查" : "Check"}
              </StatusBadge>
            </div>
            <div className="database-status-grid">
              <DatabaseMetric label={language === "zh" ? "数据库" : "Database"} value={databaseStatus?.backend ?? "unknown"} />
              <DatabaseMetric label="Schema" value={databaseStatus?.schema_version || "pending"} />
              <DatabaseMetric
                label="MySQL DSN"
                value={
                  databaseStatus?.mysql_configured
                    ? language === "zh"
                      ? "已配置"
                      : "Configured"
                    : language === "zh"
                      ? "未配置"
                      : "Not set"
                }
              />
              <DatabaseMetric label={language === "zh" ? "重复 Hash" : "Duplicate hashes"} value={String(duplicateHashCount)} />
            </div>
            {databaseStatus?.sqlite_path ? <small className="dependency-path">{databaseStatus.sqlite_path}</small> : null}
            {databaseStatus?.storage_root ? <small className="dependency-path">{databaseStatus.storage_root}</small> : null}
            {databaseMessage || databaseStatus?.error ? (
              <p className="inline-error">{databaseMessage || databaseStatus?.error}</p>
            ) : (
              <p className="hint">
                {language === "zh"
                  ? "这里只做只读检查；迁移请在命令行使用 tools/migrate_sqlite_to_mysql.py。"
                  : "Read-only status only. Run tools/migrate_sqlite_to_mysql.py from the command line for migration."}
              </p>
            )}
            {databaseTableItems.length ? (
              <div className="database-table-counts">
                {databaseTableItems.slice(0, 12).map(([table, count]) => (
                  <span key={table}>
                    <strong>{table}</strong>
                    <em>{count}</em>
                  </span>
                ))}
              </div>
            ) : null}
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshDatabase} disabled={databaseLoading}>
                <RefreshCw size={16} />
                {databaseLoading ? (language === "zh" ? "检查中" : "Checking") : language === "zh" ? "只读检查" : "Read-only check"}
              </button>
            </div>
          </section>

          <section className="storage-settings-card">
            <div className="dependency-check-title">
              <FolderOpen size={17} />
              <h3>{language === "zh" ? "本地存储" : "Local storage"}</h3>
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
                      onStorageDraftChange((current) => ({
                        ...current,
                        [field.key]: event.target.value,
                      }))
                    }
                  />
                </label>
              ))}
            </div>
            {storageMessage ? <p className={isErrorMessage(storageMessage) ? "inline-error" : "hint"}>{storageMessage}</p> : null}
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshStorage} disabled={storageLoading}>
                <RefreshCw size={16} />
                {language === "zh" ? "刷新位置" : "Refresh"}
              </button>
              <button className="secondary-button" type="button" onClick={onSaveStorage} disabled={storageLoading}>
                <Save size={16} />
                {storageLoading ? (language === "zh" ? "处理中" : "Saving") : language === "zh" ? "保存位置" : "Save paths"}
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function DependencyStatusModal({
  language,
  cookieStatus,
  cookieLoading,
  cookieActionMessage,
  htmlGrabStatus,
  htmlGrabLoading,
  htmlGrabMessage,
  dependencyStatus,
  dependencyLoading,
  dependencyMessage,
  localDiagnosticsVisible,
  onClose,
  onRefreshAllDependencies,
  onRefreshCookies,
  onRefreshHtmlGrab,
  onOpenCookieLogin,
  onOpenHtmlGrabAuthorize,
}: {
  language: Language;
  cookieStatus?: BilibiliCookieStatus;
  cookieLoading: boolean;
  cookieActionMessage: string;
  htmlGrabStatus?: HtmlGrabCheckStatus;
  htmlGrabLoading: boolean;
  htmlGrabMessage: string;
  dependencyStatus?: MediaDependencyStatus;
  dependencyLoading: boolean;
  dependencyMessage: string;
  localDiagnosticsVisible: boolean;
  onClose: () => void;
  onRefreshAllDependencies: () => Promise<void>;
  onRefreshCookies: () => Promise<void>;
  onRefreshHtmlGrab: () => Promise<void>;
  onOpenCookieLogin?: () => Promise<void>;
  onOpenHtmlGrabAuthorize?: () => Promise<void>;
}) {
  const items = Object.entries(dependencyStatus ?? {});
  const readyCount = items.filter(([, item]) => item.available || item.configured || item.verified).length;
  const totalCount = items.length + 2;
  const availableCount = readyCount + (cookieStatus?.ok ? 1 : 0) + (htmlGrabStatus?.ok ? 1 : 0);
  const issueCount = Math.max(0, totalCount - availableCount);
  const isRefreshing = dependencyLoading || cookieLoading || htmlGrabLoading;

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

        <div className="dependency-modal-summary">
          <span>
            <strong>{availableCount}</strong>
            {language === "zh" ? "可用" : "ready"}
          </span>
          <span>
            <strong>{issueCount}</strong>
            {language === "zh" ? "需处理" : "needs setup"}
          </span>
          <span>
            <strong>{totalCount}</strong>
            {language === "zh" ? "总项" : "total"}
          </span>
        </div>

        <div className="dependency-actions">
          <button className="secondary-button" type="button" onClick={onRefreshAllDependencies} disabled={isRefreshing}>
            <RefreshCw size={16} />
            {isRefreshing ? (language === "zh" ? "检查中" : "Checking") : language === "zh" ? "刷新全部" : "Refresh all"}
          </button>
        </div>

        <div className="dependency-summary-list">
          <div className="dependency-group-label">{language === "zh" ? "HTML 抓取" : "HTML grabbing"}</div>
          <div className="dependency-check-row compact">
            <div className="dependency-check-title">
              <CheckCircle2 size={17} />
              <strong>{language === "zh" ? "网页原文提取状态" : "Web article extraction status"}</strong>
              <StatusBadge tone={htmlGrabStatus?.ok ? "done" : "error"}>
                {htmlGrabStatus?.ok ? (language === "zh" ? "可用" : "Ready") : language === "zh" ? "需处理" : "Action needed"}
              </StatusBadge>
            </div>
            <p className="hint">{htmlGrabMessage || htmlGrabStatus?.message}</p>
            {htmlGrabStatus?.target_url ? <small className="dependency-path">{htmlGrabStatus.target_url}</small> : null}
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshHtmlGrab} disabled={htmlGrabLoading}>
                <RefreshCw size={16} />
                {language === "zh" ? "重新检查 HTML 抓取" : "Refresh web extraction"}
              </button>
              {onOpenHtmlGrabAuthorize ? (
                <button className="secondary-button" type="button" onClick={onOpenHtmlGrabAuthorize} disabled={htmlGrabLoading}>
                  <ExternalLink size={16} />
                  {language === "zh" ? "打开 Edge 授权页" : "Open Edge session"}
                </button>
              ) : null}
            </div>
            {(htmlGrabStatus?.checks ?? []).map((item) => (
              <DependencyItemCard key={item.key || item.label} language={language} name={item.key || "html_grab"} item={{
                label: item.label,
                available: item.ok,
                auth: item.auth,
                message: item.message,
              }} />
            ))}
          </div>

          <div className="dependency-group-label">{language === "zh" ? "B 站字幕" : "Bilibili subtitles"}</div>
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
            <div className="dependency-actions">
              <button className="secondary-button" type="button" onClick={onRefreshCookies} disabled={cookieLoading}>
                <RefreshCw size={16} />
                {language === "zh" ? "重新检查 Cookie" : "Refresh cookies"}
              </button>
              {onOpenCookieLogin ? (
                <button className="secondary-button" type="button" onClick={onOpenCookieLogin} disabled={cookieLoading}>
                  <ExternalLink size={16} />
                  {language === "zh" ? "登录获取 Cookie" : "Log in"}
                </button>
              ) : null}
            </div>
          </div>

          <div className="dependency-group-label">{language === "zh" ? "核心依赖" : "Core dependencies"}</div>
          {dependencyMessage ? <p className="inline-error">{dependencyMessage}</p> : null}
          {!dependencyMessage && !items.length && dependencyLoading ? (
            <p className="hint">{language === "zh" ? "正在读取依赖状态..." : "Loading dependency status..."}</p>
          ) : null}
          {!dependencyMessage && !items.length && !dependencyLoading ? (
            <p className="hint">{language === "zh" ? "尚未读取核心依赖状态，点击刷新全部。" : "Core dependency status has not been loaded. Refresh all to check."}</p>
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
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [testResult, setTestResult] = useState<ApiTestResult>();
  const [selectedTemplateId, setSelectedTemplateId] = useState("");

  const items = mode === "chat" ? chatPayload.items ?? [] : mode === "image" ? imagePayload.items ?? [] : asrPayload.items ?? [];
  const templates = mode === "chat" ? chatPayload.templates ?? [] : mode === "image" ? imagePayload.templates ?? [] : asrPayload.templates ?? [];
  const activeId = mode === "chat" ? chatPayload.active_id : mode === "image" ? imagePayload.active_id : asrPayload.active_id;
  const selectedItem = useMemo(() => items.find((item) => item.id === form.id), [form.id, items]);
  const isZhipuTextSetting =
    mode === "chat" &&
    (form.provider.trim().toLowerCase() === "zhipu" || form.base_url.toLowerCase().includes("bigmodel.cn"));
  const modelSuggestions =
    isZhipuTextSetting && mode === "chat" ? chatPayload.model_suggestions?.zhipu ?? [] : [];
  const isCreating = !form.id;
  const formModeTitle = isCreating
    ? language === "zh"
      ? "\u65b0\u5efa\u914d\u7f6e"
      : "New setting"
    : language === "zh"
      ? "\u7f16\u8f91\u914d\u7f6e"
      : "Edit setting";
  const formModeHint = isCreating
    ? language === "zh"
      ? "\u5f53\u524d\u662f\u4e00\u4efd\u65b0\u8349\u7a3f\uff0c\u4fdd\u5b58\u540e\u624d\u4f1a\u51fa\u73b0\u5728\u5de6\u4fa7\u5df2\u6709\u914d\u7f6e\u5217\u8868\u4e2d\u3002"
      : "This is a new draft. It appears in the saved list after you create it."
    : language === "zh"
      ? `\u6b63\u5728\u4fee\u6539\uff1a${selectedItem?.name || form.name}`
      : `Editing: ${selectedItem?.name || form.name}`;

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
    setSelectedTemplateId("");
    const payload = mode === "chat" ? chatPayload : mode === "image" ? imagePayload : asrPayload;
    setForm(formFromItem(payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0], mode));
  }, [asrPayload.item, chatPayload, imagePayload, mode]);

  async function refresh(nextMode = mode, selectedId?: string) {
    if (nextMode === "audio") {
      const payload = await settingsApi.asrSettings();
      setAsrPayload(payload);
      const selected = payload.items?.find((item) => item.id === selectedId) ?? payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0];
      setForm(formFromItem(selected, "audio"));
      return payload;
    }
    const payload = nextMode === "chat" ? await settingsApi.apiSettings() : await settingsApi.imageApiSettings();
    if (nextMode === "chat") setChatPayload(payload);
    else setImagePayload(payload);
    const selected = payload.items?.find((item) => item.id === selectedId) ?? payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0];
    setForm(formFromItem(selected, nextMode));
    return payload;
  }

  async function save() {
    setIsSaving(true);
    setMessage("");
    try {
      if (mode === "audio") {
        const payload = await settingsApi.saveAsrSetting(toAsrInput(form));
        const saved = payload.item ?? payload.items?.find((item) => item.id === payload.active_id);
        const savedId = saved?.id;
        setAsrPayload(payload);
        setForm(formFromItem(saved, "audio"));
        await refresh("audio", savedId);
        setMessage(payload.message || (language === "zh" ? "\u97f3\u9891 API \u914d\u7f6e\u5df2\u4fdd\u5b58\uff0c\u5217\u8868\u5df2\u66f4\u65b0\u3002" : "Audio API setting saved and list refreshed."));
        return;
      }
      const payload =
        mode === "chat"
          ? await settingsApi.saveApiSetting(toChatInput(form))
          : await settingsApi.saveImageApiSetting(toImageInput(form));
      const saved = payload.item ?? payload.items?.find((item) => item.id === payload.active_id);
      const savedId = saved?.id;
      if (mode === "chat") setChatPayload(payload);
      else setImagePayload(payload);
      setForm(formFromItem(saved, mode));
      await refresh(mode, savedId);
      setMessage(language === "zh" ? "API \u914d\u7f6e\u5df2\u4fdd\u5b58\uff0c\u5217\u8868\u5df2\u66f4\u65b0\u3002" : "API setting saved and list refreshed.");
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
        const payload = await settingsApi.testAsrSetting(toAsrInput(form));
        setAsrPayload((current) => ({ ...current, ...payload }));
        const result: ApiTestResult = {
          ok: payload.ok ?? false,
          message: payload.message ?? payload.error ?? "",
          provider: payload.item?.provider ?? form.provider,
          model: payload.item?.model ?? form.model,
          last_test_ok: payload.item?.last_test_ok ?? payload.ok ?? false,
          last_test_at: payload.item?.last_test_at ?? "",
        };
        setTestResult(result);
        if (payload.item?.id) await refresh("audio", payload.item.id);
        setMessage(payload.message || payload.error || (payload.ok ? (language === "zh" ? "\u6d4b\u8bd5\u901a\u8fc7\u3002" : "Test passed.") : ""));
        return;
      }
      const result =
        mode === "chat"
          ? await settingsApi.testApiSetting(toChatInput(form))
          : await settingsApi.testImageApiSetting(toImageInput(form), { realTest: form.real_image_test });
      setTestResult(result);
      if (form.id) await refresh(mode, form.id);
      setMessage(isTestOk(result) ? (language === "zh" ? "\u6d4b\u8bd5\u901a\u8fc7\uff0c\u914d\u7f6e\u5217\u8868\u5df2\u68c0\u67e5\u3002" : "Test passed and settings list checked.") : resultMessage(result));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsTesting(false);
    }
  }

  function startNewSetting() {
    setMessage("");
    setTestResult(undefined);
    setSelectedTemplateId("");
    setForm(defaultForm(mode));
  }

  function selectExistingSetting(item: ApiSettingItem | ImageApiSettingItem | AsrSettingItem) {
    setMessage("");
    setTestResult(undefined);
    setSelectedTemplateId("");
    setForm(formFromItem(item, mode));
  }

  function chooseTemplate(templateId: string) {
    setSelectedTemplateId(templateId);
    const template = templates.find((item) => item.id === templateId);
    if (!template) {
      setForm(defaultForm(mode));
      return;
    }
    applyTemplate(template);
  }

  async function activate(id: string) {
    setMessage("");
    try {
      const payload =
        mode === "chat"
          ? await settingsApi.setActiveApiSetting(id)
          : mode === "image"
            ? await settingsApi.setActiveImageApiSetting(id)
            : await settingsApi.setActiveAsrSetting(id);
      if (mode === "chat") setChatPayload(payload);
      else if (mode === "image") setImagePayload(payload);
      else setAsrPayload(payload);
      setMessage(language === "zh" ? "已启用该配置。" : "Setting activated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function remove(id: string) {
    setMessage("");
    try {
      const payload =
        mode === "chat"
          ? await settingsApi.deleteApiSetting(id)
          : mode === "image"
            ? await settingsApi.deleteImageApiSetting(id)
            : await settingsApi.deleteAsrSetting(id);
      if (mode === "chat") setChatPayload(payload);
      else if (mode === "image") setImagePayload(payload);
      else setAsrPayload(payload);
      setForm(formFromItem(payload.items?.find((item) => item.id === payload.active_id) ?? payload.items?.[0], mode));
      setMessage(language === "zh" ? "配置已删除。" : "Setting deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function applyTemplate(template: ApiSettingTemplate | AsrSettingTemplate) {
    if (mode === "audio") {
      setForm((current) => ({
        ...current,
        id: undefined,
        name: template.name,
        provider: template.provider,
        base_url: template.base_url,
        model: template.model,
        api_key: "",
        make_active: true,
      }));
      return;
    }
    const typedTemplate = template as ApiSettingTemplate;
    setSelectedTemplateId(typedTemplate.id);
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
                <h3>{language === "zh" ? "已有配置" : "Saved settings"}</h3>
                <button className="secondary-button" type="button" onClick={() => startNewSetting()}>
                  {language === "zh" ? "新建" : "New"}
                </button>
              </div>
              <article className="api-setting-row selected">
                <button type="button" onClick={() => items[0] && selectExistingSetting(items.find((item) => item.id === activeId) ?? items[0])}>
                  <strong>{items.find((item) => item.id === activeId)?.name || form.name || asrPayload.item?.name || (language === "zh" ? "未配置" : "Not configured")}</strong>
                  <span>{items.find((item) => item.id === activeId)?.model || form.model || asrPayload.item?.model || (language === "zh" ? "未选择模型" : "No model selected")}</span>
                  <small>{items.find((item) => item.id === activeId)?.api_key_masked || asrPayload.item?.api_key_masked || (language === "zh" ? "未显示 Key" : "Key hidden")}</small>
                </button>
                <div className="api-row-actions">
                  <StatusBadge tone={(items.find((item) => item.id === activeId) ?? asrPayload.item)?.configured ? "done" : "error"}>
                    {(items.find((item) => item.id === activeId) ?? asrPayload.item)?.configured ? (language === "zh" ? "启用中" : "Active") : language === "zh" ? "待配置" : "Setup needed"}
                  </StatusBadge>
                </div>
              </article>
            </aside>

            <form className="api-settings-form" onSubmit={(event) => event.preventDefault()}>
              <div className="section-heading">
                <h3>{language === "zh" ? "编辑音频 ASR" : "Edit audio ASR"}</h3>
              </div>
              <div className="api-form-grid compact-form-grid">
                {isCreating ? (
                  <label className="wide-field api-template-select">
                    <span>{language === "zh" ? "\u65b0\u5efa\u76ee\u6807" : "New setting target"}</span>
                    <select value={selectedTemplateId} onChange={(event) => chooseTemplate(event.target.value)}>
                      <option value="">{language === "zh" ? "\u81ea\u5b9a\u4e49\u914d\u7f6e" : "Custom setting"}</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} - {template.base_url}
                        </option>
                      ))}
                    </select>
                    <small className="field-hint">
                      {language === "zh"
                        ? "\u9009\u62e9\u76ee\u6807\u540e\u4f1a\u81ea\u52a8\u9884\u586b\u670d\u52a1\u5546\u3001Base URL \u548c\u6a21\u578b\uff0cAPI Key \u4ecd\u9700\u81ea\u5df1\u586b\u5199\u3002"
                        : "Choosing a target pre-fills provider, Base URL, and model. You still need to enter your API key."}
                    </small>
                  </label>
                ) : null}
                <label>
                  <span>{language === "zh" ? "配置名称" : "Name"}</span>
                  <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                </label>
                <label>
                  <span>{language === "zh" ? "服务商" : "Provider"}</span>
                  <input value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })} />
                </label>
                <label>
                  <span>{language === "zh" ? "模型" : "Model"}</span>
                  <input
                    value={form.model}
                    onChange={(event) => setForm({ ...form, model: event.target.value })}
                    list={modelSuggestions.length ? "zhipu-model-suggestions" : undefined}
                  />
                  {modelSuggestions.length ? (
                    <>
                      <datalist id="zhipu-model-suggestions">
                        {modelSuggestions.map((model) => (
                          <option key={model} value={model} />
                        ))}
                      </datalist>
                      <small className="field-hint">
                        {language === "zh"
                          ? "可选择常用智谱模型，也可以直接输入控制台支持的其他模型名。"
                          : "Choose a common Zhipu model or type any model name supported by your console."}
                      </small>
                    </>
                  ) : null}
                </label>
                <label className="wide-field">
                  <span>Base URL</span>
                  <input
                    value={form.base_url}
                    onChange={(event) => setForm({ ...form, base_url: event.target.value })}
                    placeholder="https://api.example.com/v1"
                  />
                </label>
                <label>
                  <span>API Key</span>
                  <input
                    value={form.api_key}
                    onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                    placeholder={asrPayload.item?.api_key_masked || "sk-..."}
                    type="password"
                  />
                </label>
                <label>
                  <span>{language === "zh" ? "超时秒数" : "Timeout seconds"}</span>
                  <input value={form.timeout} onChange={(event) => setForm({ ...form, timeout: event.target.value })} inputMode="decimal" />
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
                    <article key={item.id} className={!isCreating && item.id === form.id ? "api-setting-row selected" : "api-setting-row"}>
                      <button type="button" onClick={() => selectExistingSetting(item)}>
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

            </aside>

            <form className="api-settings-form" onSubmit={(event) => event.preventDefault()}>
              <div className="section-heading api-form-heading">
                <div>
                  <h3>{formModeTitle}</h3>
                  <p className="api-form-mode-hint">{formModeHint}</p>
                </div>
                <label className="inline-check">
                  <input type="checkbox" checked={form.make_active} onChange={(event) => setForm({ ...form, make_active: event.target.checked })} />
                  {language === "zh" ? "\u4fdd\u5b58\u540e\u542f\u7528" : "Activate after save"}
                </label>
              </div>
              <div className="api-form-grid">
                {isCreating ? (
                  <label className="wide-field api-template-select">
                    <span>{language === "zh" ? "\u65b0\u5efa\u76ee\u6807" : "New setting target"}</span>
                    <select value={selectedTemplateId} onChange={(event) => chooseTemplate(event.target.value)}>
                      <option value="">{language === "zh" ? "\u81ea\u5b9a\u4e49\u914d\u7f6e" : "Custom setting"}</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} - {template.base_url}
                        </option>
                      ))}
                    </select>
                    <small className="field-hint">
                      {language === "zh"
                        ? "\u9009\u62e9\u76ee\u6807\u540e\u4f1a\u81ea\u52a8\u9884\u586b\u670d\u52a1\u5546\u3001Base URL \u548c\u6a21\u578b\uff0cAPI Key \u4ecd\u9700\u81ea\u5df1\u586b\u5199\u3002"
                        : "Choosing a target pre-fills provider, Base URL, and model. You still need to enter your API key."}
                    </small>
                  </label>
                ) : null}
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
                  <strong>
                    {isSaving
                      ? language === "zh"
                        ? "\u4fdd\u5b58\u4e2d..."
                        : "Saving..."
                      : isCreating
                        ? language === "zh"
                          ? "\u521b\u5efa\u914d\u7f6e"
                          : "Create setting"
                        : language === "zh"
                          ? "\u4fdd\u5b58\u4fee\u6539"
                          : "Save changes"}
                  </strong>
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

function DatabaseMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="database-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formFromItem(item: ApiSettingItem | ImageApiSettingItem | AsrSettingItem | undefined, mode: ApiMode): ApiFormState {
  if (!item) return defaultForm(mode);
  const api = item as ApiSettingItem;
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
    max_retries: String(api.max_retries ?? 2),
    size: image.size ?? "1024x1024",
    quality: image.quality ?? "auto",
    aspect_ratio: image.aspect_ratio ?? inferAspectRatio(image.size),
    response_format: image.response_format ?? "",
    real_image_test: false,
    make_active: true,
  };
}

function defaultForm(mode: ApiMode): ApiFormState {
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
    protocol: form.protocol || "openai_compatible",
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

function toAsrInput(form: ApiFormState): AsrSettingInput {
  return {
    id: form.id,
    name: form.name.trim(),
    provider: form.provider.trim() || "compatible",
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    timeout: numberOrUndefined(form.timeout),
    make_active: form.make_active,
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
