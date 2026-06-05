import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Archive,
  BookOpen,
  ClipboardPaste,
  FileAudio,
  FileText,
  Image,
  Link,
  LoaderCircle,
  MessageSquareText,
  Network,
  PenTool,
  Search,
  Settings,
  Upload,
  Users
} from "lucide-react";
import "./styles.css";

const modules = [
  { id: "collect", label: "收集", route: "/collect", icon: Upload, desc: "读取信息并保存原料" },
  { id: "learn", label: "学习", route: "/learn", icon: BookOpen, desc: "提炼重点并构建关系网" },
  { id: "mine", label: "挖掘", route: "/mine", icon: Users, desc: "多视角解读重点知识" },
  { id: "create", label: "创作", route: "/create", icon: PenTool, desc: "引用三库生成成品" },
  { id: "settings", label: "设置中心", route: "/settings", icon: Settings, desc: "模型、ASR、图片与视角模板" }
];

const libraries = [
  { id: "raw", label: "原料库", desc: "收集模块输出的原文级 Markdown", defaultModule: "collect" },
  { id: "focus", label: "重点库", desc: "学习模块输出的知识簇文件", defaultModule: "learn" },
  { id: "perspective", label: "视角库", desc: "挖掘模块输出的视角解读文件", defaultModule: "mine" }
];

const libraryDefaults = {
  collect: "raw",
  learn: "focus",
  mine: "perspective",
  create: "focus",
  settings: "raw"
};

const sampleFiles = {
  raw: [
    { title: "英伟达 RTX Spark 与 AIPC 市场", status: "未处理", source: "截图", tags: ["AIPC", "芯片", "生态"] },
    { title: "游戏产业资本逻辑与中美日格局", status: "未处理", source: "视频", tags: ["游戏资本", "产业整合"] },
    { title: "内存市场与韩国半导体产业发展", status: "未处理", source: "文档", tags: ["内存市场", "HBM技术"] }
  ],
  focus: [
    { title: "AI PC 产业链核心知识簇", status: "已提炼", source: "学习", tags: ["结构", "引用", "产业链"] },
    { title: "游戏资本格局重点库文件", status: "已入网", source: "学习", tags: ["资本", "中美日"] }
  ],
  perspective: [
    { title: "投资者视角：AIPC 需求信号", status: "已解读", source: "挖掘", tags: ["投资者", "需求信号"] },
    { title: "创业者视角：游戏产业机会", status: "已解读", source: "挖掘", tags: ["创业者", "行业需求"] }
  ]
};

const collectTypes = [
  { id: "text", label: "文本", hint: "键入、粘贴或临时记录", icon: FileText },
  { id: "screenshot", label: "截图", hint: "粘贴、上传或拖入图片", icon: Image },
  { id: "document", label: "文档", hint: "PDF、Word、Markdown、TXT", icon: FileText },
  { id: "media", label: "音视频", hint: "上传文件或输入音视频链接", icon: FileAudio },
  { id: "webLink", label: "网页链接", hint: "读取网页正文为 Markdown", icon: Link }
];

function isMediaPlatformLink(item) {
  const linkType = String(item.link_type || "");
  const url = String(item.url || item.final_url || "");
  return (
    linkType === "platform_douyin" ||
    linkType === "platform_bilibili" ||
    linkType === "platform_wechat_channels" ||
    /(^|\/\/|\.)(douyin|iesdouyin|bilibili|b23)\.com/i.test(url) ||
    /channels\.weixin\.qq\.com/i.test(url)
  );
}

function activeModuleFromPath() {
  const path = window.location.pathname.replace(/^\/+/, "") || "collect";
  return modules.some((item) => item.id === path) ? path : "collect";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const detail = payload?.error?.message || payload?.detail || response.statusText;
    throw new Error(detail || "请求失败");
  }
  return payload;
}

async function uploadFiles(url, files) {
  const selected = [...(files || [])];
  if (!selected.length) throw new Error("请先选择文件");
  const form = new FormData();
  selected.forEach((file) => form.append("files", file, file.name));
  return requestJson(url, { method: "POST", body: form });
}

function pastedImageFiles(event) {
  const files = [...(event.clipboardData?.files || [])].filter((file) => file.type.startsWith("image/"));
  if (files.length) return files;
  return [...(event.clipboardData?.items || [])]
    .filter((item) => item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

function App() {
  const [activeModule, setActiveModule] = useState(activeModuleFromPath());
  const [activeLibrary, setActiveLibrary] = useState(libraryDefaults[activeModule]);

  function navigate(moduleId) {
    const next = modules.find((item) => item.id === moduleId);
    if (!next) return;
    window.history.pushState({}, "", next.route);
    setActiveModule(moduleId);
    setActiveLibrary(libraryDefaults[moduleId]);
  }

  return (
    <AppShell
      activeModule={activeModule}
      activeLibrary={activeLibrary}
      onNavigate={navigate}
      onLibraryChange={setActiveLibrary}
    />
  );
}

function AppShell({ activeModule, activeLibrary, onNavigate, onLibraryChange }) {
  return (
    <div className="research-shell">
      <LeftNav activeModule={activeModule} onNavigate={onNavigate} />
      <main className="main-workspace">
        <WorkspaceHeader activeModule={activeModule} />
        <MainWorkspace activeModule={activeModule} />
      </main>
      <GlobalLibraryPanel
        activeModule={activeModule}
        activeLibrary={activeLibrary}
        onLibraryChange={onLibraryChange}
      />
    </div>
  );
}

function LeftNav({ activeModule, onNavigate }) {
  const workspaceModules = modules.filter((item) => item.id !== "settings");
  const settingsModule = modules.find((item) => item.id === "settings");
  const SettingsIcon = settingsModule?.icon;
  const [projects, setProjects] = useState([]);

  async function refreshProjects() {
    try {
      const payload = await requestJson("/api/v2/create/projects");
      setProjects(payload.data.items || []);
    } catch {
      setProjects([]);
    }
  }

  useEffect(() => {
    refreshProjects();
    window.addEventListener("research-os:create-projects-updated", refreshProjects);
    return () => window.removeEventListener("research-os:create-projects-updated", refreshProjects);
  }, []);

  function openProject(projectId) {
    onNavigate("create");
    window.dispatchEvent(new CustomEvent("research-os:open-create-project", { detail: { projectId } }));
  }
  return (
    <aside className="left-nav" aria-label="知识酷主导航">
      <div className="brand">
        <strong>知识酷</strong>
        <span>Research OS</span>
      </div>
      <nav>
        {workspaceModules.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={item.id === activeModule ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{item.label}</span>
              <small>{item.desc}</small>
            </button>
          );
        })}
      </nav>
      <div className="project-nav-block">
        <span>项目</span>
        <button type="button" className={activeModule === "create" ? "project-nav-item active" : "project-nav-item"} onClick={() => onNavigate("create")}>
          新建创作项目
        </button>
        {projects.slice(0, 6).map((project) => (
          <button key={project.id} type="button" className="project-nav-item compact" onClick={() => openProject(project.id)}>
            {project.name}
          </button>
        ))}
      </div>
      {settingsModule && (
        <button
          className={settingsModule.id === activeModule ? "nav-item active settings-nav" : "nav-item settings-nav"}
          type="button"
          onClick={() => onNavigate(settingsModule.id)}
        >
          <SettingsIcon size={18} aria-hidden="true" />
          <span>{settingsModule.label}</span>
          <small>{settingsModule.desc}</small>
        </button>
      )}
    </aside>
  );
}

function WorkspaceHeader({ activeModule }) {
  const module = modules.find((item) => item.id === activeModule);
  return (
    <header className="workspace-header">
      <div>
        <h1>{module.label}</h1>
        <p>{module.desc}</p>
      </div>
      <label className="workspace-search">
        <Search size={16} aria-hidden="true" />
        <input type="search" placeholder="搜索材料 / 知识 / 视角 / 项目" />
      </label>
    </header>
  );
}

function MainWorkspace({ activeModule }) {
  const workspaces = {
    collect: <CollectWorkspace />,
    learn: <LearnWorkspace />,
    mine: <MineWorkspace />,
    create: <CreateWorkspace />,
    settings: <SettingsWorkspace />
  };
  return <section className="workspace-window">{workspaces[activeModule]}</section>;
}

function CollectWorkspace() {
  const [activeType, setActiveType] = useState("text");
  const [textValue, setTextValue] = useState("");
  const [webLinkValue, setWebLinkValue] = useState("");
  const [mediaLinkValue, setMediaLinkValue] = useState("");
  const [queues, setQueues] = useState({ text: [], screenshot: [], document: [], media: [], webLink: [] });
  const [savedItems, setSavedItems] = useState([]);
  const [status, setStatus] = useState("信息读取先入待分析队列，再统一读取为原料 Markdown。");
  const [busy, setBusy] = useState(false);

  function runTask(task, doneMessage) {
    setBusy(true);
    setStatus("正在处理材料...");
    task()
      .then(doneMessage)
      .catch((error) => setStatus(error.message || "处理失败"))
      .finally(() => setBusy(false));
  }

  function enqueueItems(type, nextItems, message) {
    const rows = nextItems.map((item) => ({
      localId: `${Date.now()}-${Math.random()}`,
      id: item.id || null,
      content: item.content || "",
      url: item.url || item.canonical_url || item.source_url || "",
      title: item.title || item.original_name || item.filename || item.url || item.image_path || item.file_path || "待分析材料",
      source: item.image_path || item.file_path || item.canonical_url || item.source_url || item.source || "",
      status: item.status || "已入队",
      link_type: item.link_type || "",
      extraction_strategy: item.extraction_strategy || "",
      access_status: item.access_status || ""
    }));
    setQueues((current) => ({ ...current, [type]: [...current[type], ...rows] }));
    setStatus(message);
  }

  function appendSaved(item) {
    window.dispatchEvent(new CustomEvent("research-os:library-updated", { detail: { library: "raw" } }));
    setSavedItems((current) => [
      {
        id: `${Date.now()}-${Math.random()}`,
        title: item.title,
        status: "已保存",
        source: item.markdown_path
      },
      ...current
    ]);
  }

  function addTextToQueue() {
    const content = textValue.trim();
    if (!content) {
      setStatus("请先输入文本。");
      return;
    }
    enqueueItems("text", [{ content, title: content.split(/\n/)[0].slice(0, 60), status: "待读取" }], "文本已加入待分析队列。");
    setTextValue("");
  }

  function addWebLinksToQueue() {
    const urls = webLinkValue.split(/\s+/).map((item) => item.trim()).filter(Boolean);
    if (!urls.length) {
      setStatus("请先输入网页链接。");
      return;
    }
    runTask(
      async () => {
        const inspected = [];
        for (const url of urls) {
          const payload = await requestJson("/api/v2/collect/inspect-link", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
          });
          inspected.push(payload.data.item);
        }
        return inspected;
        },
        (items) => {
          const mediaItems = items.filter((item) => isMediaPlatformLink(item));
          const webItems = items.filter((item) => !isMediaPlatformLink(item));
          if (mediaItems.length) {
            setStatus("检测到音视频平台链接，请切换到「音视频」入口读取；网页链接入口只处理普通网页、文章、PDF 和报告。");
          }
          if (!webItems.length) {
            return;
          }
          enqueueItems(
            "webLink",
            webItems.map((item) => ({
              ...item,
              title: item.title || item.url,
              status: `${item.link_type} / ${item.access_status}`
            })),
          "网页链接已识别类型并加入待分析队列。"
        );
        setWebLinkValue("");
      }
    );
  }

  function resolveMediaLink() {
    const urls = mediaLinkValue.split(/\s+/).map((item) => item.trim()).filter(Boolean);
    if (!urls.length) {
      setStatus("请先输入音视频链接。");
      return;
    }
    runTask(
      async () => {
        const results = [];
        for (const url of urls) {
          const payload = await requestJson("/api/media/resolve-url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
          });
          results.push(payload.item);
        }
        return results;
      },
      (mediaItems) => {
        enqueueItems("media", mediaItems, "音视频链接已加入待分析队列。");
        setMediaLinkValue("");
      }
    );
  }

  function uploadScreenshotFiles(files) {
    runTask(
      () => uploadFiles("/api/images", files),
      (payload) => enqueueItems("screenshot", payload.items || [], "截图已加入待分析队列。")
    );
  }

  function pasteScreenshots(event) {
    const files = pastedImageFiles(event);
    if (!files.length) return;
    event.preventDefault();
    runTask(
      async () => {
        const images = await Promise.all(files.map(async (file, index) => ({
          filename: file.name || `clipboard-${Date.now()}-${index}.png`,
          content_type: file.type || "image/png",
          data_url: await fileToDataUrl(file)
        })));
        return requestJson("/api/images/paste", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ images })
        });
      },
      (payload) => enqueueItems("screenshot", payload.items || [], "粘贴截图已加入待分析队列。")
    );
  }

  function uploadDocuments(files) {
    runTask(
      () => uploadFiles("/api/files", files),
      (payload) => enqueueItems("document", payload.items || [], "文档已加入待分析队列。")
    );
  }

  function uploadMedia(files) {
    runTask(
      () => uploadFiles("/api/media/upload", files),
      (payload) => enqueueItems("media", payload.items || [], "音视频文件已加入待分析队列。")
    );
  }

  function readActiveQueueAsMarkdown() {
    const queue = queues[activeType] || [];
    if (!queue.length) {
      setStatus("当前类型的待分析队列为空。");
      return;
    }
    const materialType = activeType === "webLink" ? "web_link" : activeType;
    runTask(
      () => requestJson("/api/v2/collect/raw-markdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          material_type: materialType,
          items: queue.map((item) => ({
            id: item.id,
            content: item.content,
            url: item.url,
            title: item.title,
            link_type: item.link_type,
            extraction_strategy: item.extraction_strategy,
            access_status: item.access_status
          }))
        })
      }),
      (payload) => {
        if (!payload.data.ok) {
          setStatus(payload.data.error || "读取失败");
          return;
        }
        appendSaved(payload.data.item);
        setQueues((current) => ({ ...current, [activeType]: [] }));
        setStatus("队列已读取为一个原料 Markdown 文件。");
      }
    );
  }

  function clearActiveQueue() {
    setQueues((current) => ({ ...current, [activeType]: [] }));
    setStatus("已清空当前类型的待分析队列。");
  }

  return (
    <div className="collect-grid">
      <section className="module-card span-2">
        <SectionTitle kicker="信息读取" title="先入队，再统一提取为原料 Markdown" />
        <div className="input-type-grid">
          {collectTypes.map((type) => {
            const Icon = type.icon;
            return (
              <button
                key={type.id}
                className={type.id === activeType ? "input-type active" : "input-type"}
                type="button"
                onClick={() => setActiveType(type.id)}
              >
                <Icon size={18} aria-hidden="true" />
                <strong>{type.label}</strong>
                <span>{type.hint}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="module-card span-2 collect-workbench">
        {activeType === "text" && (
          <TextCollectPanel value={textValue} onChange={setTextValue} onSave={addTextToQueue} busy={busy} />
        )}
        {activeType === "screenshot" && (
          <ScreenshotCollectPanel onFiles={uploadScreenshotFiles} onPaste={pasteScreenshots} busy={busy} />
        )}
        {activeType === "document" && (
          <FileCollectPanel
            kicker="文档读取"
            title="上传或拖入文档"
            accept=".pdf,.docx,.md,.markdown,.txt"
            icon={FileText}
            primaryText="选择文档"
            hint="支持 PDF、Word、Markdown、TXT。这里只做格式解析和文本提取。"
            onFiles={uploadDocuments}
            busy={busy}
          />
        )}
        {activeType === "media" && (
          <MediaCollectPanel
            value={mediaLinkValue}
            onChange={setMediaLinkValue}
            onResolve={resolveMediaLink}
            onFiles={uploadMedia}
            busy={busy}
          />
        )}
        {activeType === "webLink" && (
          <LinkCollectPanel value={webLinkValue} onChange={setWebLinkValue} onSave={addWebLinksToQueue} busy={busy} />
        )}
      </section>

      <section className="module-card span-2">
        <CollectQueuePanel
          activeType={activeType}
          items={queues[activeType] || []}
          busy={busy}
          onRead={readActiveQueueAsMarkdown}
          onClear={clearActiveQueue}
        />
      </section>

      <section className="module-card span-2">
        <SectionTitle kicker="读取结果" title="已保存的原料 Markdown 文件" />
        <CollectResultList items={savedItems} status={status} busy={busy} />
      </section>
    </div>
  );
}

function TextCollectPanel({ value, onChange, onSave, busy }) {
  return (
    <>
      <SectionTitle kicker="文本读取" title="输入或粘贴原文" />
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="在这里粘贴多段记录。每次点击加入队列后，可以继续输入下一段，最后统一读取成一个原料 Markdown。"
      />
      <div className="action-row">
        <button type="button" onClick={onSave} disabled={busy}>加入待分析队列</button>
        <button type="button" className="secondary" onClick={() => onChange("")}>清空文本</button>
      </div>
    </>
  );
}

function ScreenshotCollectPanel({ onFiles, onPaste, busy }) {
  return (
    <>
      <SectionTitle kicker="截图读取" title="粘贴框与上传区分开处理" />
      <div className="screenshot-workbench">
        <div className="paste-box" onPaste={onPaste} tabIndex={0}>
          <ClipboardPaste size={30} aria-hidden="true" />
          <strong>粘贴截图</strong>
          <span>点击这里后按 Ctrl+V。每张截图会先进入待分析队列。</span>
        </div>
        <FileCollectPanel
          kicker="截图上传"
          title=""
          accept="image/*"
          icon={Upload}
          primaryText="上传或拖入截图"
          hint="支持 PNG、JPG、WEBP 等图片。"
          onFiles={onFiles}
          busy={busy}
          compact
        />
      </div>
    </>
  );
}

function FileCollectPanel({ kicker, title, accept, icon: Icon, primaryText, hint, onFiles, busy, compact = false }) {
  const inputId = `collect-file-${kicker}`;

  function handleDrop(event) {
    event.preventDefault();
    onFiles(event.dataTransfer.files);
  }

  return (
    <>
      {!compact && <SectionTitle kicker={kicker} title={title} />}
      <label
        className="collect-dropzone"
        htmlFor={inputId}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        tabIndex={0}
      >
        <Icon size={30} aria-hidden="true" />
        <strong>{primaryText}</strong>
        <span>{hint}</span>
        <input
          id={inputId}
          type="file"
          accept={accept}
          multiple
          onChange={(event) => onFiles(event.target.files)}
          disabled={busy}
        />
      </label>
    </>
  );
}

function MediaCollectPanel({ value, onChange, onResolve, onFiles, busy }) {
  return (
    <>
      <SectionTitle kicker="音视频读取" title="输入音视频链接或上传文件" />
      <label className="field-stack">
        <span>音视频链接</span>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="每行一个音视频链接。解析后进入待分析队列，统一转写为原料 Markdown。"
        />
      </label>
      <div className="action-row">
        <button type="button" onClick={onResolve} disabled={busy}>加入链接队列</button>
        <label className="upload-button">
          上传音视频文件
          <input
            type="file"
            accept="audio/*,video/*,.srt,.vtt,.ass"
            multiple
            onChange={(event) => onFiles(event.target.files)}
            disabled={busy}
          />
        </label>
      </div>
    </>
  );
}

function LinkCollectPanel({ value, onChange, onSave, busy }) {
  return (
    <>
      <SectionTitle kicker="网页链接读取" title="先收集链接，再统一抓取网页正文" />
      <label className="field-stack">
        <span>网页链接</span>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="每行一个网页链接。加入队列后，会统一读取为一个原料 Markdown。"
        />
      </label>
      <div className="action-row">
        <button type="button" onClick={onSave} disabled={busy}>加入待分析队列</button>
      </div>
    </>
  );
}

function CollectQueuePanel({ activeType, items, busy, onRead, onClear }) {
  const label = collectTypes.find((item) => item.id === activeType)?.label || "材料";
  return (
    <div className="collect-results">
      <SectionTitle kicker="待分析队列" title={`${label}材料将合并读取为一个原料 Markdown`} />
      {!items.length ? (
        <div className="empty-state compact">当前类型暂无待分析材料。</div>
      ) : (
        <div className="stub-list">
          {items.map((item, index) => (
            <article key={item.localId}>
              <strong>{index + 1}. {item.title}</strong>
              <span>{item.status}</span>
              {item.extraction_strategy && <span>{item.extraction_strategy}</span>}
              {item.source && <small>{item.source}</small>}
            </article>
          ))}
        </div>
      )}
      <div className="action-row">
        <button type="button" onClick={onRead} disabled={busy || !items.length}>读取为原料 Markdown</button>
        <button type="button" className="secondary" onClick={onClear} disabled={busy || !items.length}>清空队列</button>
      </div>
    </div>
  );
}

function CollectResultList({ items, status, busy }) {
  return (
    <div className="collect-results">
      <div className="collect-status">
        {busy && <LoaderCircle size={16} aria-hidden="true" className="spin" />}
        <span>{status}</span>
      </div>
      {!items.length ? (
        <div className="empty-state compact">暂无已保存原料。队列读取完成后会显示 Markdown 路径。</div>
      ) : (
        <div className="stub-list">
          {items.map((item) => (
            <article key={item.id}>
              <strong>{item.title}</strong>
              <span>{item.status}</span>
              {item.source && <small>{item.source}</small>}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function LearnWorkspace() {
  const [rawFiles, setRawFiles] = useState([]);
  const [selectedPaths, setSelectedPaths] = useState([]);
  const [draftPaths, setDraftPaths] = useState([]);
  const [markdown, setMarkdown] = useState("");
  const [status, setStatus] = useState("请选择原料库文件，生成只包含知识结构和原文引用入口的重点库 Markdown。");
  const [busy, setBusy] = useState(false);

  async function refreshRawFiles() {
    setBusy(true);
    setStatus("正在读取原料库...");
    try {
      const payload = await requestJson("/api/v2/libraries/raw/files?pending_focus=true");
      setRawFiles(payload.data.items || []);
      setStatus("原料库已更新，请选择待学习文件。");
    } catch (err) {
      setStatus(err.message || "原料库读取失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refreshRawFiles();
  }, []);

  function toggleRawFile(path) {
    setSelectedPaths((current) => (
      current.includes(path) ? current.filter((item) => item !== path) : [...current, path]
    ));
  }

  async function refineFocusMarkdown() {
    if (!selectedPaths.length) {
      setStatus("请先选择至少一个原料文件。");
      return;
    }
    setBusy(true);
    setStatus("正在提炼知识簇草稿...");
    try {
      const payload = await requestJson("/api/v2/learn/refine-knowledge-cluster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_paths: selectedPaths })
      });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "知识簇生成失败");
        return;
      }
      setMarkdown(payload.data.markdown || "");
      setDraftPaths(selectedPaths);
      setStatus("提炼完成，请检查并修改草稿，然后保存到重点库。");
    } catch (err) {
      setStatus(err.message || "知识簇生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveFocusMarkdown() {
    const paths = draftPaths.length ? draftPaths : selectedPaths;
    if (!paths.length) {
      setStatus("请先选择原料并完成提炼。");
      return;
    }
    if (!markdown.trim()) {
      setStatus("请先提炼或填写重点库 Markdown。");
      return;
    }
    setBusy(true);
    setStatus("正在保存到重点库...");
    try {
      const payload = await requestJson("/api/v2/learn/focus-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_paths: paths, markdown })
      });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "保存失败");
        return;
      }
      const savedPath = payload.data.item.markdown_path;
      setSelectedPaths((current) => current.filter((path) => !paths.includes(path)));
      setDraftPaths([]);
      await refreshRawFiles();
      setStatus(`已保存到重点库：${savedPath}`);
      window.dispatchEvent(new CustomEvent("research-os:library-updated", { detail: { library: "focus" } }));
      window.dispatchEvent(new CustomEvent("research-os:library-updated", { detail: { library: "raw" } }));
    } catch (err) {
      setStatus(err.message || "保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="learn-grid">
      <section className="module-card learn-panel">
        <div className="section-title-row">
          <SectionTitle kicker="原料库输入" title="待处理原料文件" />
          <button type="button" className="secondary" onClick={refreshRawFiles} disabled={busy}>刷新</button>
        </div>
        <p className="panel-note">{selectedPaths.length} 个已选择。这里只显示尚未保存到重点库的原料文件。</p>
        <LibrarySelectionList
          files={rawFiles}
          selectedPaths={selectedPaths}
          onToggle={toggleRawFile}
          emptyText="原料库暂无文件。请先在收集模块生成原料 Markdown。"
        />
      </section>
      <section className="module-card learn-panel">
        <SectionTitle kicker="核心知识簇" title="知识结构 + 原文引用入口" />
        <textarea
          value={markdown}
          onChange={(event) => setMarkdown(event.target.value)}
          placeholder="生成后的重点库 Markdown 会显示在这里。"
        />
        <div className="action-row">
          <button type="button" onClick={refineFocusMarkdown} disabled={busy || !selectedPaths.length}>提炼</button>
          <button type="button" className="secondary" onClick={saveFocusMarkdown} disabled={busy || !markdown.trim()}>
            保存
          </button>
        </div>
        <div className="collect-status">
          {busy && <LoaderCircle size={16} aria-hidden="true" className="spin" />}
          <span>{status}</span>
        </div>
      </section>
      <section className="module-card span-2">
        <SectionTitle kicker="知识关系网" title="节点提取、入网与知识拉取" />
        <div className="graph-and-chat">
          <div className="graph-placeholder">
            <Network size={28} aria-hidden="true" />
            <span>下一步接入重点库文件的节点提取与关系网构建。</span>
          </div>
          <div className="chat-placeholder">
            <MessageSquareText size={24} aria-hidden="true" />
            <strong>知识拉取</strong>
            <textarea placeholder="关系网入网后，在这里基于知识节点提问。" />
          </div>
        </div>
      </section>
    </div>
  );
}

function MineWorkspace() {
  const [perspectives, setPerspectives] = useState([]);
  const [activePerspectiveId, setActivePerspectiveId] = useState("");
  const [draftPerspective, setDraftPerspective] = useState(null);
  const [queue, setQueue] = useState([]);
  const [markdown, setMarkdown] = useState("");
  const [draftSources, setDraftSources] = useState([]);
  const [status, setStatus] = useState("从右侧全局库勾选原料库或重点库文件，加入待解读队列后再按视角解读。");
  const [busy, setBusy] = useState(false);

  async function loadPerspectives(preferredId = "") {
    const payload = await requestJson("/api/v2/mine/perspectives");
    const items = payload.data.items || [];
    setPerspectives(items);
    const selected = items.find((item) => item.id === preferredId) || items.find((item) => item.id === activePerspectiveId) || items[0];
    if (selected) {
      setActivePerspectiveId(selected.id);
      setDraftPerspective(selected);
    }
    return items;
  }

  useEffect(() => {
    loadPerspectives().catch((error) => setStatus(error.message || "视角模板读取失败"));
  }, []);

  useEffect(() => {
    function handleMineSources(event) {
      const files = event.detail?.files || [];
      if (!files.length) return;
      setQueue((current) => {
        const existing = new Set(current.map((item) => item.markdown_path));
        const next = files
          .filter((file) => ["raw", "focus"].includes(file.library) && file.markdown_path && !existing.has(file.markdown_path))
          .map((file) => ({
            library: file.library,
            markdown_path: file.markdown_path,
            title: file.title,
            status: file.status,
            source: file.source
          }));
        return [...current, ...next];
      });
      setStatus("已加入待解读队列。");
    }
    window.addEventListener("research-os:mine-add-sources", handleMineSources);
    return () => window.removeEventListener("research-os:mine-add-sources", handleMineSources);
  }, []);

  function selectPerspective(id) {
    const item = perspectives.find((perspective) => perspective.id === id);
    if (!item) return;
    setActivePerspectiveId(id);
    setDraftPerspective(item);
  }

  function updatePerspective(field, value) {
    setDraftPerspective((current) => ({ ...(current || {}), [field]: value }));
  }

  function updatePerspectiveList(field, value) {
    updatePerspective(field, value.split("\n").map((item) => item.trim()).filter(Boolean));
  }

  function removeQueueItem(path) {
    setQueue((current) => current.filter((item) => item.markdown_path !== path));
  }

  function createPerspective() {
    const id = `custom_${Date.now()}`;
    const item = {
      id,
      name: "自定义视角",
      role: "",
      target_subject: "",
      purpose: "",
      focus_dimensions: ["信息关注点"],
      analysis_questions: ["这个视角要判断什么？"],
      output_style: "结构化解读，保留原文引用",
      evidence_rule: "每条判断必须引用 S1/S2 等来源编号",
      origin: "custom"
    };
    setPerspectives((current) => [item, ...current]);
    setActivePerspectiveId(id);
    setDraftPerspective(item);
    setStatus("已新建自定义视角，请完善结构后保存。");
  }

  function duplicatePerspective() {
    if (!draftPerspective) return;
    const item = {
      ...draftPerspective,
      id: `custom_${Date.now()}`,
      name: `${draftPerspective.name || "视角"} 副本`,
      origin: "custom",
      readonly: false
    };
    setPerspectives((current) => [item, ...current]);
    setActivePerspectiveId(item.id);
    setDraftPerspective(item);
    setStatus("已复制为自定义视角，请修改后保存。");
  }

  async function savePerspectiveProfile() {
    if (!draftPerspective?.name?.trim()) {
      setStatus("视角名称不能为空。");
      return;
    }
    setBusy(true);
    setStatus("正在保存视角结构...");
    try {
      const payload = await requestJson("/api/v2/mine/perspectives", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draftPerspective)
      });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "视角保存失败");
        return;
      }
      await loadPerspectives(payload.data.item.id);
      setStatus("视角结构已保存。");
    } catch (error) {
      setStatus(error.message || "视角保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function deletePerspectiveProfile() {
    if (!draftPerspective?.id?.startsWith("custom_")) {
      setStatus("预设视角不能删除，请先复制为自定义视角。");
      return;
    }
    setBusy(true);
    setStatus("正在删除自定义视角...");
    try {
      const payload = await requestJson(`/api/v2/mine/perspectives/${draftPerspective.id}`, { method: "DELETE" });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "删除失败");
        return;
      }
      const items = await loadPerspectives();
      if (!items.length) {
        setDraftPerspective(null);
        setActivePerspectiveId("");
      }
      setStatus("自定义视角已删除。");
    } catch (error) {
      setStatus(error.message || "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function interpretQueue() {
    if (!queue.length) {
      setStatus("请先从右侧全局库加入原料库或重点库文件。");
      return;
    }
    if (!draftPerspective?.name) {
      setStatus("请先选择或编辑一个视角。");
      return;
    }
    setBusy(true);
    setStatus("正在按视角解读材料...");
    try {
      const payload = await requestJson("/api/v2/mine/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: queue, perspective: draftPerspective })
      });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "解读失败");
        return;
      }
      setMarkdown(payload.data.markdown || "");
      setDraftSources(queue);
      setStatus("解读完成。你可以先修改 Markdown，再保存到视角库。");
    } catch (error) {
      setStatus(error.message || "解读失败");
    } finally {
      setBusy(false);
    }
  }

  async function savePerspectiveMarkdown() {
    const sources = draftSources.length ? draftSources : queue;
    if (!sources.length) {
      setStatus("保存视角文件需要保留来源队列。");
      return;
    }
    if (!markdown.trim()) {
      setStatus("请先生成或填写视角解读 Markdown。");
      return;
    }
    setBusy(true);
    setStatus("正在保存到视角库...");
    try {
      const payload = await requestJson("/api/v2/mine/perspective-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources, perspective: draftPerspective, markdown })
      });
      if (!payload.data.ok) {
        setStatus(payload.data.error || "保存失败");
        return;
      }
      setQueue((current) => current.filter((item) => !sources.some((source) => source.markdown_path === item.markdown_path)));
      setDraftSources([]);
      setStatus(`已保存到视角库：${payload.data.item.markdown_path}`);
      window.dispatchEvent(new CustomEvent("research-os:library-updated", { detail: { library: "perspective" } }));
    } catch (error) {
      setStatus(error.message || "保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mine-grid">
      <section className="module-card mine-panel">
        <SectionTitle kicker="视角管理" title="结构化视角，而不是并列功能" />
        <div className="perspective-list">
          {perspectives.map((item) => (
            <button
              key={item.id}
              className={item.id === activePerspectiveId ? "perspective-pill active" : "perspective-pill"}
              type="button"
              onClick={() => selectPerspective(item.id)}
            >
              {item.name}
            </button>
          ))}
        </div>
        <div className="action-row compact-actions">
          <button type="button" onClick={createPerspective} disabled={busy}>新建视角</button>
          <button type="button" className="secondary" onClick={duplicatePerspective} disabled={busy || !draftPerspective}>复制为自定义</button>
          <button type="button" className="secondary" onClick={savePerspectiveProfile} disabled={busy || !draftPerspective}>保存视角</button>
          <button type="button" className="secondary" onClick={deletePerspectiveProfile} disabled={busy || !draftPerspective}>删除自定义</button>
        </div>
        {draftPerspective && (
          <div className="perspective-editor">
            <label className="field-stack">
              <span>视角名称</span>
              <input value={draftPerspective.name || ""} onChange={(event) => updatePerspective("name", event.target.value)} />
            </label>
            <label className="field-stack">
              <span>角色定位</span>
              <textarea value={draftPerspective.role || ""} onChange={(event) => updatePerspective("role", event.target.value)} />
            </label>
            <label className="field-stack">
              <span>关注对象</span>
              <textarea value={draftPerspective.target_subject || ""} onChange={(event) => updatePerspective("target_subject", event.target.value)} />
            </label>
            <label className="field-stack">
              <span>核心目的</span>
              <textarea value={draftPerspective.purpose || ""} onChange={(event) => updatePerspective("purpose", event.target.value)} />
            </label>
            <label className="field-stack">
              <span>关注维度</span>
              <textarea
                value={(draftPerspective.focus_dimensions || []).join("\n")}
                onChange={(event) => updatePerspectiveList("focus_dimensions", event.target.value)}
              />
            </label>
            <label className="field-stack">
              <span>判断问题</span>
              <textarea
                value={(draftPerspective.analysis_questions || []).join("\n")}
                onChange={(event) => updatePerspectiveList("analysis_questions", event.target.value)}
              />
            </label>
            <label className="field-stack">
              <span>输出风格</span>
              <textarea value={draftPerspective.output_style || ""} onChange={(event) => updatePerspective("output_style", event.target.value)} />
            </label>
            <label className="field-stack">
              <span>证据规则</span>
              <textarea value={draftPerspective.evidence_rule || ""} onChange={(event) => updatePerspective("evidence_rule", event.target.value)} />
            </label>
          </div>
        )}
      </section>
      <section className="module-card mine-panel">
        <SectionTitle kicker="待解读队列" title="从全局库勾选原料库或重点库文件入队" />
        <p className="panel-note">原料库适合观察原文表达和创作逻辑；重点库适合基于知识结构做视角判断。</p>
        <div className="file-list mine-queue">
          {!queue.length && <div className="empty-state compact">右侧全局库切到原料库或重点库，勾选文件后点击“加入待解读队列”。</div>}
          {queue.map((item) => (
            <article className="file-card" key={item.markdown_path}>
              <strong>{item.title}</strong>
              <span>{item.library === "raw" ? "原料库" : "重点库"} / {item.status}</span>
              <small className="file-path">{item.markdown_path}</small>
              <button type="button" className="secondary" onClick={() => removeQueueItem(item.markdown_path)}>移出</button>
            </article>
          ))}
        </div>
        <div className="action-row">
          <button type="button" onClick={interpretQueue} disabled={busy || !queue.length}>解读</button>
          <button type="button" className="secondary" onClick={() => setQueue([])} disabled={busy || !queue.length}>清空队列</button>
        </div>
        <div className="collect-status">
          {busy && <LoaderCircle size={16} aria-hidden="true" className="spin" />}
          <span>{status}</span>
        </div>
      </section>
      <section className="module-card mine-panel">
        <SectionTitle kicker="解读结果" title="带视角标签与原文引用的 Markdown" />
        <textarea
          value={markdown}
          onChange={(event) => setMarkdown(event.target.value)}
          placeholder="解读后会生成可编辑的视角 Markdown。保存后进入右侧视角库。"
        />
        <div className="action-row">
          <button type="button" onClick={savePerspectiveMarkdown} disabled={busy || !markdown.trim()}>保存到视角库</button>
          <button type="button" className="secondary" onClick={() => setMarkdown("")} disabled={busy}>清空草稿</button>
        </div>
      </section>
    </div>
  );
}

function CreateWorkspace() {
  const projectTypes = [
    { id: "article", label: "文章项目", enabled: true },
    { id: "image_text", label: "图文项目", enabled: false },
    { id: "short_video", label: "短视频脚本", enabled: false },
    { id: "long_video", label: "长视频脚本", enabled: false }
  ];
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProject, setActiveProject] = useState(null);
  const [draftProject, setDraftProject] = useState({ name: "", project_type: "article", description: "" });
  const [topics, setTopics] = useState([]);
  const [selectedTopicIndex, setSelectedTopicIndex] = useState(-1);
  const [articleMarkdown, setArticleMarkdown] = useState("");
  const [formattedHtml, setFormattedHtml] = useState("");
  const [publishPreflight, setPublishPreflight] = useState(null);
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [status, setStatus] = useState("先创建文章项目，再从全局库加入库文件。图文和视频创作暂未开放。");
  const [busy, setBusy] = useState(false);
  const queue = activeProject?.library_files || [];
  const selectedTopic = topics[selectedTopicIndex] || null;

  async function loadProjects(preferredId = "") {
    const payload = await requestJson("/api/v2/create/projects");
    const items = payload.data.items || [];
    setProjects(items);
    const selected = items.find((item) => item.id === preferredId) || items.find((item) => item.id === activeProjectId) || items[0];
    if (selected) await loadProject(selected.id);
    return items;
  }

  async function loadProject(projectId) {
    const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(projectId)}`);
    const item = payload.data.item;
    setActiveProjectId(item.id);
    setActiveProject(item);
    setArticleMarkdown(item.article_markdown || "");
    setFormattedHtml(item.html || "");
    setPublishPreflight(null);
    setDraftProject({ name: item.name || "", project_type: item.type || "article", description: item.description || "" });
    setTopics([]);
    setSelectedTopicIndex(-1);
    setStatus(`已打开项目：${item.name}`);
  }

  async function createProject() {
    setBusy(true);
    try {
      const payload = await requestJson("/api/v2/create/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: draftProject.name || "未命名创作项目", project_type: "article", description: "" })
      });
      const item = payload.data.item;
      await loadProjects(item.id);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(`项目环境已创建：${item.name}`);
    } catch (error) {
      setStatus(error.message || "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveProjectSettings() {
    if (!activeProject) {
      setStatus("请先创建或打开一个项目环境。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draftProject)
      });
      setActiveProject(payload.data.item);
      await loadProjects(payload.data.item.id);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(`项目设置已保存：${payload.data.item.name}`);
    } catch (error) {
      setStatus(error.message || "项目设置保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveProjectFiles(nextFiles) {
    if (!activeProject) {
      setStatus("请先创建或打开一个项目。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/library-files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: nextFiles })
      });
      setActiveProject(payload.data.item);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(`库文件已更新：${(payload.data.item.library_files || []).length} 个`);
    } catch (error) {
      setStatus(error.message || "库文件更新失败");
    } finally {
      setBusy(false);
    }
  }

  function removeQueueItem(markdownPath) {
    saveProjectFiles(queue.filter((item) => item.markdown_path !== markdownPath));
  }

  async function generateTopics() {
    if (!activeProject || !queue.length) {
      setStatus("请先打开项目并加入库文件。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/topics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (payload.data.ok === false) throw new Error(payload.data.error || "生成选题失败");
      const nextTopics = payload.data.suggestions || [];
      setTopics(nextTopics);
      setSelectedTopicIndex(nextTopics.length ? 0 : -1);
      setStatus(`已生成 ${nextTopics.length} 个文章选题。`);
    } catch (error) {
      setStatus(error.message || "生成选题失败");
    } finally {
      setBusy(false);
    }
  }

  async function generateArticle() {
    if (!selectedTopic) {
      setStatus("请先选择一个选题。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/article`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: selectedTopic })
      });
      if (payload.data.ok === false) throw new Error(payload.data.error || "生成文章失败");
      setArticleMarkdown(payload.data.markdown || "");
      setFormattedHtml("");
      setPublishPreflight(null);
      setActiveProject(payload.data.project);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(`文章已保存到项目：${payload.data.article_path}`);
    } catch (error) {
      setStatus(error.message || "生成文章失败");
    } finally {
      setBusy(false);
    }
  }

  async function reviseArticle() {
    if (!articleMarkdown.trim() || !revisionInstruction.trim()) {
      setStatus("请先保留正文并填写修改要求。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: articleMarkdown, instruction: revisionInstruction })
      });
      if (payload.data.ok === false) throw new Error(payload.data.error || "修改文章失败");
      setArticleMarkdown(payload.data.markdown || "");
      setFormattedHtml("");
      setPublishPreflight(null);
      setRevisionInstruction("");
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(payload.data.change_summary || `修订稿已保存：${payload.data.version_path}`);
    } catch (error) {
      setStatus(error.message || "修改文章失败");
    } finally {
      setBusy(false);
    }
  }

  async function formatArticle() {
    if (!activeProject || !articleMarkdown.trim()) {
      setStatus("请先生成或填写文章正文。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/format`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: articleMarkdown, theme: "tech" })
      });
      if (payload.data.ok === false) throw new Error(payload.data.error || "美编排版失败");
      setFormattedHtml(payload.data.html || "");
      setActiveProject(payload.data.project);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
      setStatus(`美编 HTML 已保存：${payload.data.path}`);
    } catch (error) {
      setStatus(error.message || "美编排版失败");
    } finally {
      setBusy(false);
    }
  }

  async function runPublishPreflight() {
    if (!activeProject) {
      setStatus("请先打开项目。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/publish/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: activeProject.name, author: "Bobo" })
      });
      setPublishPreflight(payload.data);
      setStatus(payload.data.ok ? "发布预检通过。" : "发布预检未通过，请查看检查项。");
    } catch (error) {
      setStatus(error.message || "发布预检失败");
    } finally {
      setBusy(false);
    }
  }

  async function publishDraft() {
    if (!publishPreflight?.ok) {
      setStatus("请先通过发布预检。");
      return;
    }
    setBusy(true);
    try {
      const payload = await requestJson(`/api/v2/create/projects/${encodeURIComponent(activeProject.id)}/writer/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: activeProject.name, author: "Bobo" })
      });
      if (payload.data.ok === false) throw new Error(payload.data.error || "发布失败");
      setStatus(`草稿箱发布完成：${payload.data.media_id || payload.data.path || "已返回结果"}`);
      window.dispatchEvent(new CustomEvent("research-os:create-projects-updated"));
    } catch (error) {
      setStatus(error.message || "发布失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadProjects().catch((error) => setStatus(error.message || "创作项目读取失败"));
  }, []);

  useEffect(() => {
    function handleOpenProject(event) {
      const projectId = event.detail?.projectId;
      if (projectId) loadProject(projectId).catch((error) => setStatus(error.message || "项目打开失败"));
    }
    window.addEventListener("research-os:open-create-project", handleOpenProject);
    return () => window.removeEventListener("research-os:open-create-project", handleOpenProject);
  }, []);

  useEffect(() => {
    function handleCreateFiles(event) {
      const files = event.detail?.files || [];
      if (!files.length) return;
      const existing = new Set(queue.map((item) => item.markdown_path));
      const nextFiles = [
        ...queue,
        ...files
          .filter((file) => ["raw", "focus", "perspective"].includes(file.library) && file.markdown_path && !existing.has(file.markdown_path))
          .map((file) => ({ library: file.library, markdown_path: file.markdown_path, title: file.title }))
      ];
      saveProjectFiles(nextFiles);
    }
    window.addEventListener("research-os:create-add-files", handleCreateFiles);
    return () => window.removeEventListener("research-os:create-add-files", handleCreateFiles);
  }, [activeProject, queue]);

  return (
    <div className="create-grid">
      <section className="module-card project-manager">
        <SectionTitle kicker="项目管理" title="创建或打开创作项目" />
        <div className="form-grid single-column">
          <TextField label="项目名称" value={draftProject.name} onChange={(value) => setDraftProject({ ...draftProject, name: value })} />
          <SelectField
            label="项目类型"
            value={draftProject.project_type}
            options={projectTypes.map((item) => [item.id, item.enabled ? item.label : `${item.label}（暂未开放）`])}
            onChange={(value) => setDraftProject({ ...draftProject, project_type: value })}
          />
          <TextField label="项目说明" value={draftProject.description} onChange={(value) => setDraftProject({ ...draftProject, description: value })} />
        </div>
        <div className="action-row">
          <button type="button" onClick={createProject} disabled={busy}>新建项目环境</button>
          <button type="button" className="secondary" onClick={saveProjectSettings} disabled={busy || !activeProject || draftProject.project_type !== "article"}>保存基本设置</button>
        </div>
        <div className="project-list">
          {!projects.length && <div className="empty-state compact">暂无创作项目。</div>}
          {projects.map((project) => (
            <button key={project.id} type="button" className={project.id === activeProjectId ? "project-list-item active" : "project-list-item"} onClick={() => loadProject(project.id)}>
              <strong>{project.name}</strong>
              <span>{project.type === "article" ? "文章项目" : "暂未开放"} / {(project.library_files || []).length} 个库文件</span>
            </button>
          ))}
        </div>
      </section>
      <section className="module-card create-workbench">
        <SectionTitle kicker="文章工作区" title={activeProject ? activeProject.name : "先创建或打开一个项目"} />
        <div className="creation-flow">
          <button type="button" className="creation-step active" disabled><strong>1. 库文件</strong><span>从右侧全局库加入</span></button>
          <button type="button" className={topics.length ? "creation-step active" : "creation-step"} disabled><strong>2. 选题</strong><span>生成并选择方向</span></button>
          <button type="button" className={articleMarkdown ? "creation-step active" : "creation-step"} disabled><strong>3. 正文</strong><span>生成和修订文章</span></button>
        </div>
        <div className="create-panel-grid">
          <section>
            <div className="section-title-row">
              <SectionTitle kicker="库文件" title="项目工作区队列" />
              <button type="button" className="secondary" onClick={() => saveProjectFiles([])} disabled={busy || !queue.length}>清空</button>
            </div>
            <LibrarySelectionList files={queue} selectedPaths={queue.map((item) => item.markdown_path)} onToggle={removeQueueItem} emptyText="从右侧全局库勾选文件后，点击加入项目工作区。" />
            <div className="action-row">
              <button type="button" onClick={generateTopics} disabled={busy || !activeProject || !queue.length}>生成选题</button>
            </div>
          </section>
          <section>
            <SectionTitle kicker="选题" title="文章方向" />
            <div className="topic-list">
              {!topics.length && <div className="empty-state compact">暂无选题。</div>}
              {topics.map((topic, index) => (
                <button key={`${topic.title || "topic"}-${index}`} type="button" className={index === selectedTopicIndex ? "topic-item active" : "topic-item"} onClick={() => setSelectedTopicIndex(index)}>
                  <strong>{topic.title || "未命名选题"}</strong>
                  <span>{topic.angle || topic.reason || ""}</span>
                </button>
              ))}
            </div>
            <div className="action-row">
              <button type="button" onClick={generateArticle} disabled={busy || !selectedTopic}>生成文章</button>
            </div>
          </section>
        </div>
        <section className="article-editor">
          <SectionTitle kicker="正文" title="Markdown 草稿" />
          <textarea value={articleMarkdown} onChange={(event) => setArticleMarkdown(event.target.value)} placeholder="文章草稿会保存在当前项目环境中。" />
          <div className="revision-row">
            <input type="text" value={revisionInstruction} onChange={(event) => setRevisionInstruction(event.target.value)} placeholder="输入修改要求，例如：增强开头钩子，压缩第二部分" />
            <button type="button" onClick={reviseArticle} disabled={busy || !articleMarkdown.trim()}>修改文章</button>
          </div>
        </section>
        <section className="publish-tools">
          <div className="section-title-row">
            <SectionTitle kicker="美编与发布" title="沿用旧写文工具的后半段流程" />
            <div className="action-row inline-actions">
              <button type="button" onClick={formatArticle} disabled={busy || !articleMarkdown.trim()}>美编排版</button>
              <button type="button" className="secondary" onClick={runPublishPreflight} disabled={busy || !activeProject}>发布预检</button>
              <button type="button" className="secondary" onClick={publishDraft} disabled={busy || !publishPreflight?.ok}>发布到草稿箱</button>
            </div>
          </div>
          <div className="publish-grid">
            <div className="html-preview-box">
              {formattedHtml ? <iframe title="文章 HTML 预览" srcDoc={formattedHtml} /> : <div className="empty-state compact">暂无 HTML 预览。</div>}
            </div>
            <div className="preflight-list">
              {!publishPreflight && <div className="empty-state compact">暂无发布预检结果。</div>}
              {(publishPreflight?.checks || []).map((check) => (
                <article key={check.key} className={check.ok ? "preflight-item ok" : "preflight-item warn"}>
                  <strong>{check.label}</strong>
                  <span>{check.ok ? "已通过" : "需处理"}</span>
                  <small>{check.detail}</small>
                </article>
              ))}
            </div>
          </div>
        </section>
        <div className="collect-status">
          {busy && <LoaderCircle size={16} aria-hidden="true" className="spin" />}
          <span>{status}</span>
        </div>
      </section>
      <section className="module-card create-side-panel">
        <SectionTitle kicker="暂不实现" title="图文和视频创作" />
        <div className="creation-type-list">
          {projectTypes.filter((item) => !item.enabled).map((item) => (
            <button key={item.id} className="creation-type" type="button" disabled>{item.label}</button>
          ))}
        </div>
        <p className="panel-note">当前先完善文章工作区，后续再接入图文和视频脚本项目。</p>
      </section>
    </div>
  );

  return (
    <div className="create-grid">
      <section className="module-card">
        <SectionTitle kicker="项目管理" title="创建或打开创作项目" />
        {["文章项目", "小红书图文", "短视频脚本", "长视频脚本"].map((item) => (
          <button key={item} className="creation-type" type="button">{item}</button>
        ))}
      </section>
      <section className="module-card">
        <SectionTitle kicker="创作引导" title="按类型推进成品生成" />
        <ol className="step-list">
          <li>选择引用文件</li>
          <li>生成选题 / 大纲 / 脚本结构</li>
          <li>生成正文并修改</li>
          <li>配图、美编与发布检查</li>
        </ol>
        <button type="button" onClick={() => { window.location.href = "/writer"; }}>进入文章工作流</button>
      </section>
      <section className="module-card">
        <SectionTitle kicker="内容引用" title="从全局库插入素材" />
        <FileStub library="focus" />
      </section>
    </div>
  );
}

function SettingsWorkspace() {
  const tabs = [
    { id: "web", label: "网页基本设置" },
    { id: "model", label: "模型配置" },
    { id: "asr", label: "ASR 配置" },
    { id: "api", label: "API 配置" }
  ];
  const [activeTab, setActiveTab] = useState("web");
  const [webDraft, setWebDraft] = useState(null);
  const [apiPayload, setApiPayload] = useState({ active_id: "", items: [], templates: [] });
  const [apiDraft, setApiDraft] = useState(null);
  const [asrPayload, setAsrPayload] = useState({ item: {}, templates: [] });
  const [asrDraft, setAsrDraft] = useState(null);
  const [status, setStatus] = useState("设置中心用于管理网页基本设置、模型、ASR 和 API。");
  const [busy, setBusy] = useState(false);

  async function loadSettings() {
    setBusy(true);
    try {
      const [web, api, asr] = await Promise.all([
        requestJson("/api/v2/settings/web"),
        requestJson("/api/v2/settings/api"),
        requestJson("/api/v2/settings/asr")
      ]);
      setWebDraft(web.data.item);
      setApiPayload(api.data);
      setApiDraft((api.data.items || []).find((item) => item.id === api.data.active_id) || (api.data.items || [])[0] || emptyApiDraft());
      setAsrPayload(asr.data);
      setAsrDraft(asr.data.item || emptyAsrDraft());
      setStatus("设置已加载。");
    } catch (error) {
      setStatus(error.message || "设置读取失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  function emptyApiDraft() {
    return { name: "", provider: "compatible", base_url: "", model: "", api_key: "", timeout: 60, max_retries: 1, make_active: true };
  }

  function emptyAsrDraft() {
    return { provider: "compatible", base_url: "", model: "", api_key: "", timeout: 300 };
  }

  function applyApiTemplate(template) {
    setApiDraft({
      ...emptyApiDraft(),
      name: template.name,
      provider: template.provider,
      base_url: template.base_url,
      model: template.model,
      api_key: "",
      make_active: true
    });
  }

  function applyAsrTemplate(template) {
    setAsrDraft({
      ...emptyAsrDraft(),
      provider: template.provider,
      base_url: template.base_url,
      model: template.model,
      api_key: ""
    });
  }

  async function saveWebSettings() {
    await saveSettings("/api/v2/settings/web", webDraft, (payload) => setWebDraft(payload.data.item), "网页基本设置已保存。");
  }

  async function saveApiSettings() {
    await saveSettings("/api/v2/settings/api", apiDraft, (payload) => {
      setApiPayload(payload.data);
      setApiDraft(payload.data.item);
    }, "API 配置已保存。");
  }

  async function activateApiSetting(id) {
    await saveSettings("/api/v2/settings/api/active", { id }, (payload) => {
      setApiPayload(payload.data);
      setApiDraft(payload.data.item);
    }, "活动模型配置已切换。");
  }

  async function deleteApiSetting(id) {
    await requestAction(`/api/v2/settings/api/${id}`, { method: "DELETE" }, (payload) => {
      setApiPayload(payload.data);
      setApiDraft((payload.data.items || []).find((item) => item.id === payload.data.active_id) || emptyApiDraft());
    }, "API 配置已删除。");
  }

  async function testApiSettings() {
    await requestAction("/api/v2/settings/api/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ setting: apiDraft })
    }, (payload) => setStatus(payload.data.ok ? `API 测试通过：${payload.data.diagnostic?.model || ""}` : payload.data.error), "API 测试完成。");
  }

  async function saveAsrSettings() {
    await saveSettings("/api/v2/settings/asr", asrDraft, (payload) => {
      setAsrPayload(payload.data);
      setAsrDraft(payload.data.item);
    }, "ASR 配置已保存。");
  }

  async function testAsrSettings() {
    await requestAction("/api/v2/settings/asr/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(asrDraft)
    }, (payload) => {
      if (payload.data.item) setAsrDraft(payload.data.item);
      setStatus(payload.data.ok ? payload.data.message : payload.data.error);
    }, "ASR 配置检查完成。");
  }

  async function saveSettings(url, body, onSuccess, message) {
    await requestAction(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }, onSuccess, message);
  }

  async function requestAction(url, options, onSuccess, message) {
    setBusy(true);
    setStatus("正在保存设置...");
    try {
      const payload = await requestJson(url, options);
      if (payload.data?.ok === false) {
        setStatus(payload.data.error || "设置操作失败");
        return;
      }
      onSuccess?.(payload);
      setStatus(message);
    } catch (error) {
      setStatus(error.message || "设置操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-grid">
      <section className="module-card settings-sidebar">
        <SectionTitle kicker="设置中心" title="系统配置" />
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={activeTab === tab.id ? "settings-tab active" : "settings-tab"}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
        <div className="collect-status">
          {busy && <LoaderCircle size={16} aria-hidden="true" className="spin" />}
          <span>{status}</span>
        </div>
      </section>
      <section className="module-card settings-panel">
        {activeTab === "web" && webDraft && (
          <WebSettingsForm draft={webDraft} onChange={setWebDraft} onSave={saveWebSettings} busy={busy} />
        )}
        {activeTab === "model" && (
          <ModelSettingsPanel apiPayload={apiPayload} onActivate={activateApiSetting} onEdit={(item) => { setApiDraft(item); setActiveTab("api"); }} busy={busy} />
        )}
        {activeTab === "asr" && asrDraft && (
          <AsrSettingsForm draft={asrDraft} templates={asrPayload.templates || []} onChange={setAsrDraft} onTemplate={applyAsrTemplate} onSave={saveAsrSettings} onTest={testAsrSettings} busy={busy} />
        )}
        {activeTab === "api" && apiDraft && (
          <ApiSettingsForm
            draft={apiDraft}
            templates={apiPayload.templates || []}
            items={apiPayload.items || []}
            activeId={apiPayload.active_id}
            onChange={setApiDraft}
            onTemplate={applyApiTemplate}
            onNew={() => setApiDraft(emptyApiDraft())}
            onEdit={setApiDraft}
            onSave={saveApiSettings}
            onTest={testApiSettings}
            onActivate={activateApiSetting}
            onDelete={deleteApiSetting}
            busy={busy}
          />
        )}
      </section>
    </div>
  );
}

function WebSettingsForm({ draft, onChange, onSave, busy }) {
  return (
    <div className="settings-form">
      <SectionTitle kicker="网页基本设置" title="界面与工作区默认行为" />
      <div className="form-grid">
        <TextField label="网页名称" value={draft.app_name} onChange={(value) => onChange({ ...draft, app_name: value })} />
        <TextField label="工作区名称" value={draft.workspace_name} onChange={(value) => onChange({ ...draft, workspace_name: value })} />
        <SelectField
          label="默认入口"
          value={draft.default_route}
          options={[
            ["/collect", "收集"],
            ["/learn", "学习"],
            ["/mine", "挖掘"],
            ["/create", "创作"],
            ["/settings", "设置中心"]
          ]}
          onChange={(value) => onChange({ ...draft, default_route: value })}
        />
        <TextField
          label="全局库刷新秒数"
          type="number"
          value={draft.global_library_refresh_seconds}
          onChange={(value) => onChange({ ...draft, global_library_refresh_seconds: Number(value) })}
        />
        <SelectField
          label="语言"
          value={draft.language}
          options={[["zh-CN", "中文"], ["en-US", "English"]]}
          onChange={(value) => onChange({ ...draft, language: value })}
        />
        <label className="toggle-field">
          <input
            type="checkbox"
            checked={Boolean(draft.right_library_visible)}
            onChange={(event) => onChange({ ...draft, right_library_visible: event.target.checked })}
          />
          <span>默认显示右侧全局库</span>
        </label>
      </div>
      <div className="action-row">
        <button type="button" onClick={onSave} disabled={busy}>保存网页设置</button>
      </div>
    </div>
  );
}

function ModelSettingsPanel({ apiPayload, onActivate, onEdit, busy }) {
  const items = apiPayload.items || [];
  return (
    <div className="settings-form">
      <SectionTitle kicker="模型配置" title="选择当前用于学习、挖掘和创作的模型" />
      <div className="settings-list">
        {!items.length && <div className="empty-state compact">还没有 API 配置。请到 API 配置中新建一个模型连接。</div>}
        {items.map((item) => (
          <article className={item.id === apiPayload.active_id ? "settings-item active" : "settings-item"} key={item.id}>
            <div>
              <strong>{item.name}</strong>
              <span>{item.provider} / {item.model}</span>
              <small>{item.base_url}</small>
            </div>
            <div className="item-actions">
              <button type="button" onClick={() => onActivate(item.id)} disabled={busy || item.id === apiPayload.active_id}>
                {item.id === apiPayload.active_id ? "当前模型" : "设为当前"}
              </button>
              <button type="button" className="secondary" onClick={() => onEdit(item)} disabled={busy}>编辑</button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function ApiSettingsForm({ draft, templates, items, activeId, onChange, onTemplate, onNew, onEdit, onSave, onTest, onActivate, onDelete, busy }) {
  return (
    <div className="settings-form">
      <SectionTitle kicker="API 配置" title="LLM API 连接与 Key 管理" />
      <div className="template-row">
        {templates.map((template) => (
          <button type="button" className="secondary" key={template.id} onClick={() => onTemplate(template)} disabled={busy}>
            {template.name}
          </button>
        ))}
      </div>
      <div className="form-grid">
        <TextField label="配置名称" value={draft.name || ""} onChange={(value) => onChange({ ...draft, name: value })} />
        <TextField label="Provider" value={draft.provider || ""} onChange={(value) => onChange({ ...draft, provider: value })} />
        <TextField label="Base URL" value={draft.base_url || ""} onChange={(value) => onChange({ ...draft, base_url: value })} />
        <TextField label="模型名称" value={draft.model || ""} onChange={(value) => onChange({ ...draft, model: value })} />
        <TextField label={`API Key${draft.api_key_masked ? `（当前 ${draft.api_key_masked}）` : ""}`} value={draft.api_key || ""} onChange={(value) => onChange({ ...draft, api_key: value })} />
        <TextField label="Timeout" type="number" value={draft.timeout || 60} onChange={(value) => onChange({ ...draft, timeout: Number(value) })} />
        <TextField label="最大重试次数" type="number" value={draft.max_retries ?? 1} onChange={(value) => onChange({ ...draft, max_retries: Number(value) })} />
        <label className="toggle-field">
          <input type="checkbox" checked={draft.make_active !== false} onChange={(event) => onChange({ ...draft, make_active: event.target.checked })} />
          <span>保存后设为当前模型</span>
        </label>
      </div>
      <div className="action-row">
        <button type="button" onClick={onSave} disabled={busy}>保存 API</button>
        <button type="button" className="secondary" onClick={onTest} disabled={busy}>测试 API</button>
        <button type="button" className="secondary" onClick={onNew} disabled={busy}>新建配置</button>
      </div>
      <div className="settings-list compact-list">
        {items.map((item) => (
          <article className={item.id === activeId ? "settings-item active" : "settings-item"} key={item.id}>
            <div>
              <strong>{item.name}</strong>
              <span>{item.provider} / {item.model}</span>
              <small>{item.api_key_masked || "未显示 Key"}</small>
            </div>
            <div className="item-actions">
              <button type="button" className="secondary" onClick={() => onEdit(item)} disabled={busy}>编辑</button>
              <button type="button" onClick={() => onActivate(item.id)} disabled={busy || item.id === activeId}>启用</button>
              <button type="button" className="secondary" onClick={() => onDelete(item.id)} disabled={busy}>删除</button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function AsrSettingsForm({ draft, templates, onChange, onTemplate, onSave, onTest, busy }) {
  return (
    <div className="settings-form">
      <SectionTitle kicker="ASR 配置" title="音视频转写模型与 API" />
      <div className="template-row">
        {templates.map((template) => (
          <button type="button" className="secondary" key={template.id} onClick={() => onTemplate(template)} disabled={busy}>
            {template.name}
          </button>
        ))}
      </div>
      <div className="form-grid">
        <TextField label="Provider" value={draft.provider || ""} onChange={(value) => onChange({ ...draft, provider: value })} />
        <TextField label="Base URL" value={draft.base_url || ""} onChange={(value) => onChange({ ...draft, base_url: value })} />
        <TextField label="模型名称" value={draft.model || ""} onChange={(value) => onChange({ ...draft, model: value })} />
        <TextField label={`API Key${draft.api_key_masked ? `（当前 ${draft.api_key_masked}）` : ""}`} value={draft.api_key || ""} onChange={(value) => onChange({ ...draft, api_key: value })} />
        <TextField label="Timeout" type="number" value={draft.timeout || 300} onChange={(value) => onChange({ ...draft, timeout: Number(value) })} />
      </div>
      <div className="action-row">
        <button type="button" onClick={onSave} disabled={busy}>保存 ASR</button>
        <button type="button" className="secondary" onClick={onTest} disabled={busy}>检查配置</button>
      </div>
      {draft.last_test_message && <p className="panel-note">{draft.last_test_message}</p>}
    </div>
  );
}

function TextField({ label, value, onChange, type = "text" }) {
  return (
    <label className="field-stack">
      <span>{label}</span>
      <input type={type} value={value ?? ""} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({ label, value, options, onChange }) {
  return (
    <label className="field-stack">
      <span>{label}</span>
      <select value={value ?? ""} onChange={(event) => onChange(event.target.value)}>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </label>
  );
}

function GlobalLibraryPanel({ activeModule, activeLibrary, onLibraryChange }) {
  const [filesByLibrary, setFilesByLibrary] = useState({});
  const [selectedPaths, setSelectedPaths] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const files = useMemo(() => filesByLibrary[activeLibrary] || [], [filesByLibrary, activeLibrary]);
  const filteredFiles = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) => {
      const haystack = [file.title, file.source, file.status, ...(file.tags || [])].join(" ").toLowerCase();
      return haystack.includes(needle);
    });
  }, [files, query]);
  const mineSelectable = activeModule === "mine" && ["raw", "focus"].includes(activeLibrary);
  const createSelectable = activeModule === "create";
  const selectedFiles = useMemo(
    () => filteredFiles.filter((file) => selectedPaths.includes(file.markdown_path)),
    [filteredFiles, selectedPaths]
  );

  async function refreshLibrary(libraryId = activeLibrary) {
    setLoading(true);
    setError("");
    try {
      const payload = await requestJson(`/api/v2/libraries/${libraryId}/files`);
      setFilesByLibrary((current) => ({ ...current, [libraryId]: payload.data.items || [] }));
    } catch (err) {
      setError(err.message || "全局库读取失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshLibrary(activeLibrary);
    setSelectedPaths([]);
  }, [activeLibrary]);

  useEffect(() => {
    function handleLibraryUpdated(event) {
      const library = event.detail?.library || "raw";
      refreshLibrary(library);
    }
    window.addEventListener("research-os:library-updated", handleLibraryUpdated);
    const timer = window.setInterval(() => refreshLibrary(activeLibrary), 8000);
    return () => {
      window.removeEventListener("research-os:library-updated", handleLibraryUpdated);
      window.clearInterval(timer);
    };
  }, [activeLibrary]);

  return (
    <aside className="global-library" aria-label="全局库">
      <div className="library-header">
        <div>
          <h2>全局库</h2>
          <p>原料库、重点库与视角库</p>
        </div>
        <Archive size={22} aria-hidden="true" />
      </div>
      <div className="library-tabs">
        {libraries.map((library) => (
          <button
            key={library.id}
            className={library.id === activeLibrary ? "active" : ""}
            type="button"
            onClick={() => onLibraryChange(library.id)}
          >
            {library.label}
          </button>
        ))}
      </div>
      <p className="library-context">
        当前模块：{modules.find((item) => item.id === activeModule)?.label}，默认库：{libraries.find((item) => item.id === activeLibrary)?.label}
      </p>
      <div className="library-tools">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="查询标题 / 标签 / 来源"
        />
        <button type="button" onClick={() => refreshLibrary(activeLibrary)} disabled={loading}>
          {loading ? "刷新中" : "刷新"}
        </button>
      </div>
      {mineSelectable && (
        <button
          type="button"
          className="wide-button"
          onClick={() => {
            window.dispatchEvent(
              new CustomEvent("research-os:mine-add-sources", {
                detail: { files: selectedFiles }
              })
            );
            setSelectedPaths([]);
          }}
          disabled={!selectedFiles.length}
        >
          加入待解读队列
        </button>
      )}
      {createSelectable && (
        <button
          type="button"
          className="wide-button"
          onClick={() => {
            window.dispatchEvent(new CustomEvent("research-os:create-add-files", { detail: { files: selectedFiles } }));
            setSelectedPaths([]);
          }}
          disabled={!selectedFiles.length}
        >
          加入项目工作区
        </button>
      )}
      {error && <div className="library-message error">{error}</div>}
      <div className="file-list">
        {!loading && !filteredFiles.length && (
          <div className="empty-state compact">当前库暂无文件。新生成的原料会自动出现在这里。</div>
        )}
        {filteredFiles.map((file) => (
          <article className="file-card" key={file.id || file.markdown_path || file.title}>
            <label>
              <input
                type="checkbox"
                disabled={!mineSelectable && !createSelectable}
                checked={selectedPaths.includes(file.markdown_path)}
                onChange={() => {
                  setSelectedPaths((current) => (
                    current.includes(file.markdown_path)
                      ? current.filter((path) => path !== file.markdown_path)
                      : [...current, file.markdown_path]
                  ));
                }}
              />
              <strong>{file.title}</strong>
            </label>
            <span>{file.source} / {file.status}</span>
            {file.markdown_path && <small className="file-path">{file.markdown_path}</small>}
            <div>{(file.tags || []).map((tag) => <small key={tag}>{tag}</small>)}</div>
          </article>
        ))}
      </div>
    </aside>
  );
}

function FileStub({ library }) {
  return (
    <div className="stub-list">
      {(sampleFiles[library] || []).slice(0, 2).map((file) => (
        <article key={file.title}>
          <strong>{file.title}</strong>
          <span>{file.status}</span>
        </article>
      ))}
    </div>
  );
}

function LibrarySelectionList({ files, selectedPaths, onToggle, emptyText }) {
  if (!files.length) {
    return <div className="empty-state compact">{emptyText}</div>;
  }
  return (
    <div className="file-list">
      {files.map((file) => {
        const path = file.markdown_path || file.id;
        return (
          <article className="file-card" key={path}>
            <label>
              <input
                type="checkbox"
                checked={selectedPaths.includes(path)}
                onChange={() => onToggle(path)}
              />
              <strong>{file.title}</strong>
            </label>
            <span>{file.source} / {file.status}</span>
            {path && <small className="file-path">{path}</small>}
            <div>{(file.tags || []).map((tag) => <small key={tag}>{tag}</small>)}</div>
          </article>
        );
      })}
    </div>
  );
}

function SectionTitle({ kicker, title }) {
  return (
    <div className="section-title">
      <span>{kicker}</span>
      <h2>{title}</h2>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
