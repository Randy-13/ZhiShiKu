const state = {
  queue: [],
  documentQueue: [],
  textMaterials: [],
  linkMaterials: [],
  documentPlan: null,
  activeInput: "screenshots",
  knowledge: [],
  selectedKnowledge: new Set(),
  filters: {
    keyword: "",
    dateFrom: "",
    dateTo: "",
  },
  activeLibraryKind: "raw",
  contracts: {
    appShell: null,
    materialTypes: [],
    settingsOverview: null,
  },
  analysis: {
    startedAt: null,
    elapsedMs: 0,
    timer: null,
    running: false,
  },
  fileAnalysis: {
    startedAt: null,
    elapsedMs: 0,
    timer: null,
    running: false,
    label: "分析时间",
    progressDone: null,
    progressTotal: null,
  },
  apiSettings: {
    items: [],
    templates: [],
    activeId: null,
    editingId: null,
    logs: [],
  },
  markdownContent: "",
  parserMode: "local_ocr",
  knowledgePanelResize: {
    dragging: false,
    startY: 0,
    startHeight: 0,
  },
  activeMode: "refine",
  mining: {
    projects: [],
    currentProject: null,
    sources: [],
    versions: [],
    artifactContent: "",
    busy: false,
  },
};

const els = {
  appRail: document.querySelector(".app-rail"),
  shellNavItems: document.querySelectorAll("[data-shell-section]"),
  materialTypeGrid: document.querySelector(".material-type-grid"),
  dropzone: document.querySelector("#dropzone"),
  refineModeTab: document.querySelector("#refineModeTab"),
  miningModeTab: document.querySelector("#miningModeTab"),
  refineWorkspace: document.querySelector("#refineWorkspace"),
  miningWorkspace: document.querySelector("#miningWorkspace"),
  screenshotInputTab: document.querySelector("#screenshotInputTab"),
  fileInputTab: document.querySelector("#fileInputTab"),
  mediaInputTab: document.querySelector("#mediaInputTab"),
  materialTypeCards: document.querySelectorAll("[data-material-type]"),
  planLearningMaterials: document.querySelector("#planLearningMaterials"),
  unifiedLearningPlan: document.querySelector("#unifiedLearningPlan"),
  unifiedLearningPlanMeta: document.querySelector("#unifiedLearningPlanMeta"),
  unifiedLearningPlanList: document.querySelector("#unifiedLearningPlanList"),
  textInputPane: document.querySelector("#textInputPane"),
  screenshotInputPane: document.querySelector("#screenshotInputPane"),
  fileInputPane: document.querySelector("#fileInputPane"),
  linkInputPane: document.querySelector("#linkInputPane"),
  textMaterialInput: document.querySelector("#textMaterialInput"),
  addTextMaterial: document.querySelector("#addTextMaterial"),
  clearTextMaterials: document.querySelector("#clearTextMaterials"),
  textMaterialQueue: document.querySelector("#textMaterialQueue"),
  textMaterialCount: document.querySelector("#textMaterialCount"),
  linkMaterialInput: document.querySelector("#linkMaterialInput"),
  addLinkMaterial: document.querySelector("#addLinkMaterial"),
  clearLinkMaterials: document.querySelector("#clearLinkMaterials"),
  linkMaterialQueue: document.querySelector("#linkMaterialQueue"),
  linkMaterialCount: document.querySelector("#linkMaterialCount"),
  documentDropzone: document.querySelector("#documentDropzone"),
  documentInput: document.querySelector("#documentInput"),
  chooseDocuments: document.querySelector("#chooseDocuments"),
  clearDocumentQueue: document.querySelector("#clearDocumentQueue"),
  planFileKnowledge: document.querySelector("#planFileKnowledge"),
  generateFileKnowledge: document.querySelector("#generateFileKnowledge"),
  documentQueue: document.querySelector("#documentQueue"),
  documentQueueCount: document.querySelector("#documentQueueCount"),
  fileAnalysisTime: document.querySelector("#fileAnalysisTime"),
  documentPlanPanel: document.querySelector("#documentPlanPanel"),
  documentPlanMeta: document.querySelector("#documentPlanMeta"),
  documentPlanSummary: document.querySelector("#documentPlanSummary"),
  documentPlanList: document.querySelector("#documentPlanList"),
  generatePlannedKnowledge: document.querySelector("#generatePlannedKnowledge"),
  pasteBox: document.querySelector("#pasteBox"),
  fileInput: document.querySelector("#fileInput"),
  chooseFiles: document.querySelector("#chooseFiles"),
  clearQueue: document.querySelector("#clearQueue"),
  generateKnowledge: document.querySelector("#generateKnowledge"),
  createMiningProject: document.querySelector("#createMiningProject"),
  newMiningProjectName: document.querySelector("#newMiningProjectName"),
  miningProjectList: document.querySelector("#miningProjectList"),
  miningProjectTitle: document.querySelector("#miningProjectTitle"),
  miningProjectStatus: document.querySelector("#miningProjectStatus"),
  miningProjectName: document.querySelector("#miningProjectName"),
  saveMiningProjectName: document.querySelector("#saveMiningProjectName"),
  miningDocumentInput: document.querySelector("#miningDocumentInput"),
  chooseMiningDocuments: document.querySelector("#chooseMiningDocuments"),
  miningImageInput: document.querySelector("#miningImageInput"),
  chooseMiningImages: document.querySelector("#chooseMiningImages"),
  miningMediaInput: document.querySelector("#miningMediaInput"),
  chooseMiningMedia: document.querySelector("#chooseMiningMedia"),
  miningMediaUrlInput: document.querySelector("#miningMediaUrlInput"),
  attachMiningMediaUrls: document.querySelector("#attachMiningMediaUrls"),
  learnCreationStrategy: document.querySelector("#learnCreationStrategy"),
  miningBusyStatus: document.querySelector("#miningBusyStatus"),
  miningSourceCount: document.querySelector("#miningSourceCount"),
  miningSourceList: document.querySelector("#miningSourceList"),
  miningVersionCount: document.querySelector("#miningVersionCount"),
  miningStrategyPreview: document.querySelector("#miningStrategyPreview"),
  createWorkspace: document.querySelector("#createWorkspace"),
  openLegacyWriterTool: document.querySelector("#openLegacyWriterTool"),
  localOcrMode: document.querySelector("#localOcrMode"),
  aiVisionMode: document.querySelector("#aiVisionMode"),
  refreshKnowledge: document.querySelector("#refreshKnowledge"),
  queue: document.querySelector("#queue"),
  queueCount: document.querySelector("#queueCount"),
  analysisTime: document.querySelector("#analysisTime"),
  knowledgeKeyword: document.querySelector("#knowledgeKeyword"),
  knowledgeDateFrom: document.querySelector("#knowledgeDateFrom"),
  knowledgeDateTo: document.querySelector("#knowledgeDateTo"),
  clearKnowledgeFilters: document.querySelector("#clearKnowledgeFilters"),
  openWriterTool: document.querySelector("#openWriterTool"),
  knowledgePanel: document.querySelector("#knowledgePanel"),
  knowledgePanelHandle: document.querySelector("#knowledgePanelHandle"),
  openGlobalSettings: document.querySelector("#openGlobalSettings"),
  settingsOverviewStatus: document.querySelector("#settingsOverviewStatus"),
  globalLibraryTabs: document.querySelectorAll("[data-library-kind]"),
  globalLibraryStatus: document.querySelector("#globalLibraryStatus"),
  clearGlobalLibrarySelection: document.querySelector("#clearGlobalLibrarySelection"),
  openApiSettings: document.querySelector("#openApiSettings"),
  closeApiSettings: document.querySelector("#closeApiSettings"),
  apiSettingsModal: document.querySelector("#apiSettingsModal"),
  apiSettingsStatus: document.querySelector("#apiSettingsStatus"),
  apiSettingSelect: document.querySelector("#apiSettingSelect"),
  apiEditMode: document.querySelector("#apiEditMode"),
  apiTemplateSelect: document.querySelector("#apiTemplateSelect"),
  newApiSetting: document.querySelector("#newApiSetting"),
  activateApiSetting: document.querySelector("#activateApiSetting"),
  deleteApiSetting: document.querySelector("#deleteApiSetting"),
  apiSettingForm: document.querySelector("#apiSettingForm"),
  apiName: document.querySelector("#apiName"),
  apiProvider: document.querySelector("#apiProvider"),
  apiBaseUrl: document.querySelector("#apiBaseUrl"),
  apiModel: document.querySelector("#apiModel"),
  apiKey: document.querySelector("#apiKey"),
  apiTimeout: document.querySelector("#apiTimeout"),
  apiMaxRetries: document.querySelector("#apiMaxRetries"),
  testApiSetting: document.querySelector("#testApiSetting"),
  saveApiSettingButton: document.querySelector("#saveApiSettingButton"),
  clearApiLogs: document.querySelector("#clearApiLogs"),
  apiLogList: document.querySelector("#apiLogList"),
  knowledgeList: document.querySelector("#knowledgeList"),
  knowledgeCount: document.querySelector("#knowledgeCount"),
  markdownPreview: document.querySelector("#markdownPreview"),
  previewTitle: document.querySelector("#previewTitle"),
  markdownModal: document.querySelector("#markdownModal"),
  closeMarkdownModal: document.querySelector("#closeMarkdownModal"),
  copyMarkdown: document.querySelector("#copyMarkdown"),
  toast: document.querySelector("#toast"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 2800);
}

function openWriterTool() {
  const ids = [...state.selectedKnowledge];
  if (!ids.length) {
    showToast("请先勾选至少一个知识文件");
    return;
  }
  window.location.href = `/create?ids=${ids.join(",")}`;
}

function parserModeLabel(mode = state.parserMode) {
  return mode === "ai_vision" ? "AI 智能解析" : "本地 PaddleOCR 解析";
}

function renderParserMode() {
  els.localOcrMode.classList.toggle("active", state.parserMode === "local_ocr");
  els.aiVisionMode.classList.toggle("active", state.parserMode === "ai_vision");
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    let detail = data.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg || JSON.stringify(item)).join("；");
    } else if (detail && typeof detail === "object") {
      detail = JSON.stringify(detail);
    }
    throw new Error(detail || `请求失败：${response.status}`);
  }
  return data;
}

async function loadV2Contracts() {
  try {
    const [appShell, materialTypes, settingsOverview] = await Promise.all([
      requestJson("/api/v2/app-shell"),
      requestJson("/api/v2/material-types"),
      requestJson("/api/v2/settings/overview"),
    ]);
    state.contracts.appShell = appShell.data || null;
    state.contracts.materialTypes = materialTypes.data || [];
    state.contracts.settingsOverview = settingsOverview.data || null;
    els.appRail?.setAttribute("data-contract-loaded", "true");
    els.materialTypeGrid?.setAttribute("data-contract-loaded", "true");
    renderSettingsOverviewStatus();
  } catch (error) {
    console.warn("v2 contracts unavailable", error);
  }
}

function renderSettingsOverviewStatus() {
  const sections = state.contracts.settingsOverview?.sections || [];
  if (!sections.length) return;
  const configured = sections.filter((section) => section.configured).length;
  const errored = sections.filter((section) => section.error).length;
  els.settingsOverviewStatus.textContent = errored
    ? `${configured}/${sections.length} 已配置，${errored} 项需检查`
    : `${configured}/${sections.length} 已配置`;
}

function workspaceEntryRoute(entryId, fallbackRoute) {
  const entries = state.contracts.appShell?.workspaceEntries || [];
  return entries.find((entry) => entry.id === entryId)?.route || fallbackRoute;
}

function navigateToWorkspaceEntry(entryId, fallbackRoute) {
  window.location.href = workspaceEntryRoute(entryId, fallbackRoute);
}

function shellSectionFromPath() {
  const path = window.location.pathname.replace(/^\/+/, "") || "collect";
  if (["collect", "learn", "mine", "create", "library", "settings", "docs"].includes(path)) return path;
  return "collect";
}

function activateShellSection(section) {
  document.body.dataset.activeShellSection = section;
  els.shellNavItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.shellSection === section);
  });
  if (section === "mine") {
    switchPrimaryMode("mining");
    setActiveGlobalLibrary("perspective");
    return;
  }
  if (section === "create") {
    switchPrimaryMode("create");
    setActiveGlobalLibrary("focus");
    return;
  }
  if (section === "learn") {
    setActiveGlobalLibrary("focus");
  } else if (section === "create") {
    setActiveGlobalLibrary("focus");
  } else {
    setActiveGlobalLibrary("raw");
  }
  switchPrimaryMode("refine");
  if (section === "learn") {
    window.setTimeout(() => document.querySelector("#knowledgePanel")?.scrollIntoView({ block: "start" }), 0);
  }
}

function setActiveGlobalLibrary(kind) {
  state.activeLibraryKind = kind;
  els.globalLibraryTabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.libraryKind === kind);
  });
  if (!els.globalLibraryStatus) return;
  const labels = {
    raw: "原料库：收集模块输出的原文级 Markdown",
    focus: "重点库：学习模块输出的知识簇文件",
    perspective: "视角库：挖掘模块输出的视角解读文件",
  };
  els.globalLibraryStatus.textContent = labels[kind] || "全局库";
}

function parseTags(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function applyKnowledgePanelHeight(height) {
  if (!els.knowledgePanel) return;
  const minHeight = 320;
  const maxHeight = Math.round(window.innerHeight * 0.9);
  const clamped = clamp(height, minHeight, maxHeight);
  els.knowledgePanel.style.height = `${clamped}px`;
  try {
    window.localStorage.setItem("figurelearning-knowledge-panel-height", String(clamped));
  } catch {}
}

function restoreKnowledgePanelHeight() {
  if (!els.knowledgePanel) return;
  try {
    const raw = window.localStorage.getItem("figurelearning-knowledge-panel-height");
    if (!raw) return;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    applyKnowledgePanelHeight(parsed);
  } catch {}
}

function stopKnowledgePanelResize() {
  if (!state.knowledgePanelResize.dragging) return;
  state.knowledgePanelResize.dragging = false;
  els.knowledgePanel.classList.remove("dragging");
  window.removeEventListener("pointermove", onKnowledgePanelResizeMove);
  window.removeEventListener("pointerup", stopKnowledgePanelResize);
}

function onKnowledgePanelResizeMove(event) {
  if (!state.knowledgePanelResize.dragging) return;
  const deltaY = event.clientY - state.knowledgePanelResize.startY;
  applyKnowledgePanelHeight(state.knowledgePanelResize.startHeight + deltaY);
}

function startKnowledgePanelResize(event) {
  if (!els.knowledgePanel) return;
  event.preventDefault();
  state.knowledgePanelResize.dragging = true;
  state.knowledgePanelResize.startY = event.clientY;
  state.knowledgePanelResize.startHeight = els.knowledgePanel.getBoundingClientRect().height;
  els.knowledgePanel.classList.add("dragging");
  window.addEventListener("pointermove", onKnowledgePanelResizeMove);
  window.addEventListener("pointerup", stopKnowledgePanelResize);
}

function nowTimeLabel() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function renderApiLogs() {
  if (!els.apiLogList) return;
  if (!state.apiSettings.logs.length) {
    els.apiLogList.textContent = "暂无日志";
    return;
  }
  els.apiLogList.innerHTML = "";
  state.apiSettings.logs.forEach((entry) => {
    const row = document.createElement("article");
    row.className = "api-log-item";
    row.innerHTML = `
      <div class="api-log-meta">
        <span>${entry.time}</span>
        <span class="api-log-level ${entry.level}">${entry.label}</span>
      </div>
      <div class="api-log-message">${entry.message}</div>
    `;
    els.apiLogList.appendChild(row);
  });
  els.apiLogList.scrollTop = els.apiLogList.scrollHeight;
}

function pushApiLog(level, message) {
  const labels = {
    info: "进行中",
    success: "成功",
    error: "失败",
  };
  state.apiSettings.logs.push({
    time: nowTimeLabel(),
    level,
    label: labels[level] || "记录",
    message,
  });
  if (state.apiSettings.logs.length > 120) {
    state.apiSettings.logs = state.apiSettings.logs.slice(-120);
  }
  renderApiLogs();
}

function activeApiSetting() {
  return state.apiSettings.items.find((item) => item.id === state.apiSettings.activeId) || null;
}

function renderApiSettingsStatus() {
  const active = activeApiSetting();
  if (!state.apiSettings.items.length) {
    els.apiSettingsStatus.textContent = "未设置 API";
    return;
  }
  if (!active) {
    els.apiSettingsStatus.textContent = "未选择当前 API";
    return;
  }
  els.apiSettingsStatus.textContent = `当前：${active.name} / ${active.model}`;
}

function renderApiSettingSelect() {
  els.apiSettingSelect.innerHTML = "";
  if (!state.apiSettings.items.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无配置";
    els.apiSettingSelect.appendChild(option);
    renderApiSettingsStatus();
    return;
  }
  state.apiSettings.items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    const activeMark = item.id === state.apiSettings.activeId ? "当前" : "可选";
    option.textContent = `${item.name} · ${item.model} · ${activeMark}`;
    els.apiSettingSelect.appendChild(option);
  });
  const selectedId = state.apiSettings.editingId || state.apiSettings.activeId || state.apiSettings.items[0]?.id;
  els.apiSettingSelect.value = selectedId || "";
  renderApiSettingsStatus();
}

function renderApiEditMode() {
  const editing = state.apiSettings.items.find((item) => item.id === state.apiSettings.editingId);
  if (editing) {
    const activeSuffix = editing.id === state.apiSettings.activeId ? "，也是当前启用配置" : "";
    els.apiEditMode.textContent = `正在修改：${editing.name}${activeSuffix}`;
    els.saveApiSettingButton.textContent = "保存修改并启用";
    return;
  }
  els.apiEditMode.textContent = "正在新增配置";
  els.saveApiSettingButton.textContent = "保存并启用";
}

function renderApiTemplateSelect() {
  els.apiTemplateSelect.innerHTML = "";
  state.apiSettings.templates.forEach((template) => {
    const option = document.createElement("option");
    option.value = template.id;
    option.textContent = template.name;
    els.apiTemplateSelect.appendChild(option);
  });
}

function fillApiFormFromTemplate(template) {
  state.apiSettings.editingId = null;
  els.apiName.value = template?.name || "";
  els.apiProvider.value = template?.provider || "compatible";
  els.apiBaseUrl.value = template?.base_url || "";
  els.apiModel.value = template?.model || "";
  els.apiKey.value = "";
  els.apiKey.placeholder = template?.api_key_placeholder || "API Key";
  els.apiTimeout.value = "120";
  els.apiMaxRetries.value = "2";
  renderApiEditMode();
}

function fillApiFormFromSetting(setting) {
  state.apiSettings.editingId = setting.id;
  els.apiSettingSelect.value = setting.id;
  els.apiName.value = setting.name || "";
  els.apiProvider.value = setting.provider || "compatible";
  els.apiBaseUrl.value = setting.base_url || "";
  els.apiModel.value = setting.model || "";
  els.apiKey.value = "";
  els.apiKey.placeholder = setting.api_key_masked ? `留空则保留 ${setting.api_key_masked}` : "API Key";
  els.apiTimeout.value = setting.timeout || 120;
  els.apiMaxRetries.value = setting.max_retries ?? 2;
  renderApiEditMode();
}

async function loadApiSettings({ silent = false } = {}) {
  pushApiLog("info", "正在加载已保存的 API 配置...");
  const data = unwrapV2(await requestJson("/api/v2/settings/api"));
  state.apiSettings.items = data.items || [];
  state.apiSettings.templates = data.templates || [];
  state.apiSettings.activeId = data.active_id || null;
  renderApiTemplateSelect();
  renderApiSettingSelect();
  const active = activeApiSetting();
  if (active) {
    fillApiFormFromSetting(active);
    pushApiLog("success", `已加载 ${state.apiSettings.items.length} 个配置，当前为「${active.name}」。`);
  } else {
    fillApiFormFromTemplate(state.apiSettings.templates[0]);
    pushApiLog("info", "没有可用的当前 API，已加载模板，等待你填写。");
    if (!silent) showToast("请先在 API 设置中添加并启用 API");
  }
}

function openApiSettings() {
  els.apiSettingsModal.classList.remove("hidden");
  pushApiLog("info", "已打开 API 设置面板。");
  loadApiSettings({ silent: true }).catch((error) => showToast(error.message));
}

function closeApiSettings() {
  els.apiSettingsModal.classList.add("hidden");
  pushApiLog("info", "已关闭 API 设置面板。");
}

function apiFormPayload() {
  return {
    id: state.apiSettings.editingId,
    name: els.apiName.value.trim(),
    provider: els.apiProvider.value,
    base_url: els.apiBaseUrl.value.trim(),
    model: els.apiModel.value.trim(),
    api_key: els.apiKey.value.trim(),
    timeout: Number(els.apiTimeout.value || 120),
    max_retries: Number(els.apiMaxRetries.value || 0),
    make_active: true,
  };
}

async function saveApiSetting(event) {
  event.preventDefault();
  const payload = apiFormPayload();
  const actionLabel = payload.id ? "更新" : "保存";
  pushApiLog("info", `正在${actionLabel}配置「${payload.name || "未命名 API"}」...`);
  const data = unwrapV2(await requestJson("/api/v2/settings/api", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
  state.apiSettings.items = data.items || [];
  state.apiSettings.activeId = data.active_id || data.item?.id || null;
  state.apiSettings.editingId = data.item?.id || null;
  renderApiSettingSelect();
  fillApiFormFromSetting(data.item);
  pushApiLog("success", `配置「${data.item.name}」已${payload.id ? "更新" : "保存"}并启用，当前模型为 ${data.item.model}。`);
  showToast(payload.id ? "API 配置已更新并启用" : "API 设置已保存并启用");
}

async function testCurrentApiSetting() {
  const payload = apiFormPayload();
  pushApiLog("info", `正在按当前表单内容测试连接：${payload.name || payload.model || "未命名配置"}...`);
  const data = unwrapV2(await requestJson("/api/v2/settings/api/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setting: payload }),
  }));
  if (data.ok === "true") {
    pushApiLog("success", `连接成功：${data.provider || payload.provider} / ${data.model || payload.model}`);
  } else {
    pushApiLog("error", data.error || "连接失败");
  }
  showToast(data.ok === "true" ? `连接成功：${data.output || "ok"}` : data.error || "连接失败");
}

async function activateSelectedApiSetting() {
  const id = els.apiSettingSelect.value;
  if (!id) {
    showToast("没有可启用的 API 配置");
    return;
  }
  const selected = state.apiSettings.items.find((item) => item.id === id);
  pushApiLog("info", `正在切换当前 API 到「${selected?.name || id}」...`);
  const data = unwrapV2(await requestJson("/api/v2/settings/api/active", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  }));
  state.apiSettings.items = data.items || [];
  state.apiSettings.activeId = data.active_id || id;
  state.apiSettings.editingId = id;
  renderApiSettingSelect();
  const setting = state.apiSettings.items.find((item) => item.id === id);
  if (setting) fillApiFormFromSetting(setting);
  pushApiLog("success", `当前 API 已切换为「${setting?.name || id}」。`);
  showToast("已切换当前 API");
}

async function deleteSelectedApiSetting() {
  const id = els.apiSettingSelect.value;
  if (!id) {
    showToast("没有可删除的 API 配置");
    return;
  }
  const selected = state.apiSettings.items.find((item) => item.id === id);
  pushApiLog("info", `正在删除配置「${selected?.name || id}」...`);
  const data = unwrapV2(await requestJson(`/api/v2/settings/api/${encodeURIComponent(id)}`, { method: "DELETE" }));
  state.apiSettings.items = data.items || [];
  state.apiSettings.activeId = data.active_id || null;
  state.apiSettings.editingId = state.apiSettings.activeId;
  renderApiSettingSelect();
  const active = activeApiSetting();
  if (active) {
    fillApiFormFromSetting(active);
  } else {
    fillApiFormFromTemplate(state.apiSettings.templates[0]);
  }
  pushApiLog("success", `配置「${selected?.name || id}」已删除。`);
  showToast("API 配置已删除");
}

function statusLabel(status, uploading) {
  if (uploading) return "上传中";
  const labels = {
    local: "待上传",
    uploaded: "已入队",
    planned: "已规划",
    processing: "分析中",
    ready: "已生成",
    error: "失败",
  };
  return labels[status] || status || "未知";
}

function formatElapsed(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function renderAnalysisTime() {
  if (!state.analysis.running && !state.analysis.elapsedMs) {
    els.analysisTime.textContent = "分析时间：--";
    els.analysisTime.classList.remove("running", "done");
    return;
  }
  const elapsedMs = state.analysis.running
    ? Date.now() - state.analysis.startedAt
    : state.analysis.elapsedMs;
  els.analysisTime.textContent = `分析时间：${formatElapsed(elapsedMs)}`;
  els.analysisTime.classList.toggle("running", state.analysis.running);
  els.analysisTime.classList.toggle("done", !state.analysis.running);
}

function startAnalysisTimer() {
  window.clearInterval(state.analysis.timer);
  state.analysis.startedAt = Date.now();
  state.analysis.elapsedMs = 0;
  state.analysis.running = true;
  renderAnalysisTime();
  state.analysis.timer = window.setInterval(renderAnalysisTime, 500);
}

function stopAnalysisTimer() {
  if (state.analysis.running && state.analysis.startedAt) {
    state.analysis.elapsedMs = Date.now() - state.analysis.startedAt;
  }
  state.analysis.running = false;
  state.analysis.startedAt = null;
  window.clearInterval(state.analysis.timer);
  state.analysis.timer = null;
  renderAnalysisTime();
}

function resetAnalysisTimer() {
  state.analysis.running = false;
  state.analysis.startedAt = null;
  state.analysis.elapsedMs = 0;
  window.clearInterval(state.analysis.timer);
  state.analysis.timer = null;
  renderAnalysisTime();
}

function renderFileAnalysisTime() {
  const label = state.fileAnalysis.label || "分析时间";
  const progress =
    state.fileAnalysis.progressTotal
      ? `  ${state.fileAnalysis.progressDone || 0}/${state.fileAnalysis.progressTotal}`
      : "";
  if (!state.fileAnalysis.running && !state.fileAnalysis.elapsedMs) {
    els.fileAnalysisTime.textContent = `${label}: --${progress}`;
    return;
  }
  const elapsed = state.fileAnalysis.running
    ? Date.now() - state.fileAnalysis.startedAt
    : state.fileAnalysis.elapsedMs;
  els.fileAnalysisTime.textContent = `${label}: ${formatElapsed(elapsed)}${progress}`;
}

function startFileAnalysisTimer(options = {}) {
  state.fileAnalysis.startedAt = Date.now();
  state.fileAnalysis.elapsedMs = 0;
  state.fileAnalysis.running = true;
  state.fileAnalysis.label = options.label || "分析时间";
  state.fileAnalysis.progressDone = options.progressDone ?? null;
  state.fileAnalysis.progressTotal = options.progressTotal ?? null;
  window.clearInterval(state.fileAnalysis.timer);
  state.fileAnalysis.timer = window.setInterval(renderFileAnalysisTime, 1000);
  renderFileAnalysisTime();
}

function updateFileAnalysisProgress(done, total) {
  state.fileAnalysis.progressDone = done;
  state.fileAnalysis.progressTotal = total;
  renderFileAnalysisTime();
}

function stopFileAnalysisTimer() {
  if (state.fileAnalysis.running && state.fileAnalysis.startedAt) {
    state.fileAnalysis.elapsedMs = Date.now() - state.fileAnalysis.startedAt;
  }
  state.fileAnalysis.running = false;
  state.fileAnalysis.startedAt = null;
  window.clearInterval(state.fileAnalysis.timer);
  state.fileAnalysis.timer = null;
  renderFileAnalysisTime();
}

function resetFileAnalysisTimer() {
  state.fileAnalysis.running = false;
  state.fileAnalysis.startedAt = null;
  state.fileAnalysis.elapsedMs = 0;
  state.fileAnalysis.label = "分析时间";
  state.fileAnalysis.progressDone = null;
  state.fileAnalysis.progressTotal = null;
  window.clearInterval(state.fileAnalysis.timer);
  state.fileAnalysis.timer = null;
  renderFileAnalysisTime();
}

function switchInputTab(tab) {
  state.activeInput = tab;
  [els.screenshotInputTab, els.fileInputTab].forEach((button) => {
    button.classList.toggle("active", button.dataset.inputTab === tab);
  });
  [els.textInputPane, els.screenshotInputPane, els.fileInputPane, els.linkInputPane].forEach((pane) => {
    pane.classList.toggle("active", pane.dataset.inputPane === tab);
  });
  const activeMaterial = {
    text: "text",
    files: "document",
    link: "link",
    screenshots: "screenshot",
  }[tab] || "screenshot";
  setActiveMaterialType(activeMaterial);
}

function setActiveMaterialType(materialType) {
  els.materialTypeCards.forEach((card) => {
    card.classList.toggle("active", card.dataset.materialType === materialType);
  });
}

function selectMaterialType(materialType) {
  if (materialType === "text") {
    switchInputTab("text");
    return;
  }
  if (materialType === "screenshot") {
    switchInputTab("screenshots");
    return;
  }
  if (materialType === "document") {
    switchInputTab("files");
    return;
  }
  if (materialType === "media") {
    setActiveMaterialType("media");
    navigateToWorkspaceEntry("collect-media", "/collect/media");
    return;
  }
  if (materialType === "link") {
    switchInputTab("link");
  }
}

function switchPrimaryMode(mode) {
  state.activeMode = mode;
  els.refineModeTab.classList.toggle("active", mode === "refine");
  els.miningModeTab.classList.toggle("active", mode === "mining");
  els.refineWorkspace.classList.toggle("active", mode === "refine");
  els.miningWorkspace.classList.toggle("active", mode === "mining");
  els.createWorkspace?.classList.toggle("active", mode === "create");
  if (mode === "mining") {
    loadMiningProjects().catch((error) => showToast(error.message));
  }
}

function applyMiningPayload(data) {
  if (data.project) state.mining.currentProject = data.project;
  state.mining.sources = data.sources || [];
  state.mining.versions = data.versions || [];
  state.mining.artifactContent = data.artifact_content || "";
  renderMiningWorkspace();
  loadMiningProjects().catch(() => {});
}

function renderMiningProjects() {
  const projects = state.mining.projects || [];
  if (!projects.length) {
    els.miningProjectList.className = "mining-project-list empty";
    els.miningProjectList.textContent = "暂无挖掘项目";
    return;
  }
  els.miningProjectList.className = "mining-project-list";
  els.miningProjectList.innerHTML = "";
  projects.forEach((project) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `mining-project-item ${state.mining.currentProject?.id === project.id ? "active" : ""}`;
    row.innerHTML = `
      <span>${escapeHtml(project.name || "未命名项目")}</span>
      <small>${escapeHtml(String(project.source_count || 0))} 个素材 · ${escapeHtml(String(project.latest_version || 0))} 版</small>
    `;
    row.addEventListener("click", () => selectMiningProject(project.id));
    els.miningProjectList.appendChild(row);
  });
}

function renderMiningWorkspace() {
  const project = state.mining.currentProject;
  renderMiningProjects();
  els.miningProjectTitle.textContent = project?.name || "未选择项目";
  els.miningProjectStatus.textContent = project
    ? `${state.mining.sources.length} 个素材 · ${state.mining.versions.length} 个策略版本`
    : "创建或选择项目后开始学习";
  els.miningProjectName.value = project?.name || "";
  els.learnCreationStrategy.textContent = state.mining.versions.length ? "完善创作策略" : "学习创作策略";
  els.miningBusyStatus.textContent = state.mining.busy ? "处理中..." : "-";
  els.miningSourceCount.textContent = `${state.mining.sources.length} 个`;
  els.miningVersionCount.textContent = `${state.mining.versions.length} 版`;
  els.miningStrategyPreview.textContent = state.mining.artifactContent || "尚未形成策略。";
  if (!state.mining.sources.length) {
    els.miningSourceList.className = "queue empty";
    els.miningSourceList.textContent = "暂无素材";
  } else {
    els.miningSourceList.className = "queue";
    els.miningSourceList.innerHTML = "";
    state.mining.sources.forEach((source) => {
      const row = document.createElement("div");
      row.className = "queue-item mining-source-item";
      row.innerHTML = `
        <div class="queue-file-icon">${escapeHtml(source.source_type || "src")}</div>
        <div>
          <div class="meta-title">${escapeHtml(source.title || "未命名素材")}</div>
          <div class="meta-sub">${escapeHtml(source.text_path || "")}</div>
        </div>
        <div class="status ${source.status || "ready"}">${escapeHtml(source.status || "ready")}</div>
      `;
      els.miningSourceList.appendChild(row);
    });
  }
}

async function loadMiningProjects() {
  const data = await requestJson("/api/mining/projects");
  state.mining.projects = data.items || [];
  renderMiningProjects();
}

async function selectMiningProject(projectId) {
  const data = await requestJson(`/api/mining/projects/${projectId}`);
  applyMiningPayload(data);
}

async function createMiningProject() {
  const name = els.newMiningProjectName.value.trim() || "创作策略学习";
  const data = await requestJson("/api/mining/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, strategy_type: "creation_strategy" }),
  });
  els.newMiningProjectName.value = "";
  applyMiningPayload(data);
  showToast("已创建挖掘项目");
}

async function renameMiningProject() {
  const project = state.mining.currentProject;
  if (!project) {
    showToast("请先选择项目");
    return;
  }
  const name = els.miningProjectName.value.trim();
  if (!name) {
    showToast("项目名称不能为空");
    return;
  }
  const data = await requestJson(`/api/mining/projects/${project.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  applyMiningPayload(data);
  showToast("已重命名项目");
}

async function attachMiningSources(sources) {
  const project = state.mining.currentProject;
  if (!project) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  if (!sources.length) return;
  state.mining.busy = true;
  renderMiningWorkspace();
  try {
    const data = await requestJson(`/api/mining/projects/${project.id}/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources }),
    });
    applyMiningPayload(data);
    const failed = (data.results || []).filter((item) => !item.ok).length;
    showToast(failed ? `已加入素材，失败 ${failed} 个` : `已加入 ${sources.length} 个学习素材`);
  } finally {
    state.mining.busy = false;
    renderMiningWorkspace();
  }
}

async function uploadMiningDocuments(files) {
  if (!state.mining.currentProject) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  const documents = [...files].filter(documentFileAllowed);
  if (!documents.length) {
    showToast("没有可加入的文章文件");
    return;
  }
  const form = new FormData();
  documents.forEach((file) => form.append("files", file, file.name));
  const data = await requestJson("/api/files", { method: "POST", body: form });
  await attachMiningSources((data.items || []).map((item) => ({
    source_type: "file",
    source_id: item.id,
    title: item.original_name || item.file_path,
  })));
}

async function uploadMiningImages(files) {
  if (!state.mining.currentProject) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  const images = [...files].filter((file) => file.type.startsWith("image/"));
  if (!images.length) {
    showToast("没有可加入的截图");
    return;
  }
  const form = new FormData();
  images.forEach((file) => form.append("files", file, file.name));
  const data = await requestJson("/api/images", { method: "POST", body: form });
  await attachMiningSources((data.items || []).map((item) => ({
    source_type: "screenshot",
    source_id: item.id,
    title: item.image_path,
    parser_mode: state.parserMode,
  })));
}

async function uploadMiningMedia(files) {
  if (!state.mining.currentProject) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  const mediaFiles = [...files];
  if (!mediaFiles.length) return;
  const form = new FormData();
  mediaFiles.forEach((file) => form.append("files", file, file.name));
  const data = await requestJson("/api/media/upload", { method: "POST", body: form });
  await attachMiningSources((data.items || []).map((item) => ({
    source_type: "media",
    source_id: item.id,
    title: item.title || item.original_name,
  })));
}

async function attachMiningMediaUrls() {
  if (!state.mining.currentProject) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  const urls = els.miningMediaUrlInput.value.split(/\n+/).map((item) => item.trim()).filter(Boolean);
  if (!urls.length) {
    showToast("请先填写音视频链接");
    return;
  }
  const refs = [];
  for (const url of urls) {
    const data = await requestJson("/api/media/resolve-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    refs.push({
      source_type: "media",
      source_id: data.item.id,
      title: data.item.title || data.item.canonical_url || url,
    });
  }
  els.miningMediaUrlInput.value = "";
  await attachMiningSources(refs);
}

async function learnCreationStrategy() {
  const project = state.mining.currentProject;
  if (!project) {
    showToast("请先创建或选择挖掘项目");
    return;
  }
  if (!state.mining.sources.length) {
    showToast("请先加入作者作品素材");
    return;
  }
  state.mining.busy = true;
  renderMiningWorkspace();
  try {
    showToast(state.mining.versions.length ? "正在完善创作策略..." : "正在学习创作策略...");
    const data = await requestJson(`/api/mining/projects/${project.id}/learn-creation-strategy`, { method: "POST" });
    applyMiningPayload(data);
    showToast("创作策略已生成");
  } finally {
    state.mining.busy = false;
    renderMiningWorkspace();
  }
}

function fileKey(file) {
  return `${file.name || "clipboard"}-${file.size}-${file.lastModified || 0}-${file.type}`;
}

function addLocalFiles(files) {
  const images = [...files].filter((file) => file.type.startsWith("image/"));
  if (!images.length) {
    showToast("没有可加入的图片");
    return;
  }

  const existingKeys = new Set(state.queue.map((item) => item.localKey).filter(Boolean));
  images.forEach((file) => {
    const key = fileKey(file);
    if (existingKeys.has(key)) return;
    state.queue.push({
      localKey: key,
      file,
      previewUrl: URL.createObjectURL(file),
      name: file.name || `clipboard-${Date.now()}.png`,
      size: file.size,
      status: "local",
      uploading: false,
      fromClipboard: Boolean(file.fromClipboard),
    });
    existingKeys.add(key);
  });
  renderQueue();
  uploadPendingFiles();
}

function documentFileAllowed(file) {
  return /\.(md|markdown|txt|docx|pdf)$/i.test(file.name || "");
}

function addDocumentFiles(files) {
  const documents = [...files].filter(documentFileAllowed);
  if (!documents.length) {
    showToast("没有可加入的文件");
    return;
  }
  const existingKeys = new Set(state.documentQueue.map((item) => item.localKey).filter(Boolean));
  documents.forEach((file) => {
    const key = fileKey(file);
    if (existingKeys.has(key)) return;
    state.documentQueue.push({
      localKey: key,
      file,
      name: file.name || `document-${Date.now()}`,
      size: file.size,
      status: "local",
      uploading: false,
    });
    existingKeys.add(key);
  });
  renderDocumentQueue();
  uploadPendingDocuments();
}

function addTextMaterial() {
  const value = els.textMaterialInput.value.trim();
  if (!value) {
    showToast("请先输入文本材料");
    return;
  }
  state.textMaterials.push({
    id: `text-${Date.now()}-${state.textMaterials.length}`,
    text: value,
  });
  els.textMaterialInput.value = "";
  renderTextMaterials();
  showToast("已加入文本材料");
}

function clearTextMaterials() {
  state.textMaterials = [];
  renderTextMaterials();
}

function addLinkMaterials() {
  const urls = els.linkMaterialInput.value
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!urls.length) {
    showToast("请先输入链接材料");
    return;
  }
  const existing = new Set(state.linkMaterials.map((item) => item.url));
  urls.forEach((url) => {
    if (existing.has(url)) return;
    state.linkMaterials.push({
      id: `link-${Date.now()}-${state.linkMaterials.length}`,
      url,
    });
    existing.add(url);
  });
  els.linkMaterialInput.value = "";
  renderLinkMaterials();
  showToast(`已加入 ${urls.length} 条链接材料`);
}

function clearLinkMaterials() {
  state.linkMaterials = [];
  renderLinkMaterials();
}

function renderTextMaterials() {
  els.textMaterialCount.textContent = `${state.textMaterials.length} 段`;
  if (!state.textMaterials.length) {
    els.textMaterialQueue.className = "queue empty";
    els.textMaterialQueue.textContent = "暂无文本材料";
    return;
  }
  els.textMaterialQueue.className = "queue";
  els.textMaterialQueue.innerHTML = state.textMaterials
    .map((item) => `<div class="material-row"><strong>文本材料</strong><span>${escapeHtml(item.text.slice(0, 160))}</span></div>`)
    .join("");
}

function renderLinkMaterials() {
  els.linkMaterialCount.textContent = `${state.linkMaterials.length} 条`;
  if (!state.linkMaterials.length) {
    els.linkMaterialQueue.className = "queue empty";
    els.linkMaterialQueue.textContent = "暂无链接材料";
    return;
  }
  els.linkMaterialQueue.className = "queue";
  els.linkMaterialQueue.innerHTML = state.linkMaterials
    .map((item) => `<div class="material-row"><strong>链接材料</strong><span>${escapeHtml(item.url)}</span></div>`)
    .join("");
}

function materialLearningPlanItems() {
  return [
    { label: "文本", count: state.textMaterials.length, purpose: "提炼手动记录和摘录中的核心观点" },
    { label: "截图", count: state.queue.length, purpose: "识别图片文字并提炼知识簇" },
    { label: "文档", count: state.documentQueue.length, purpose: "解析结构、规划分段并生成知识文件" },
    { label: "链接", count: state.linkMaterials.length, purpose: "后续解析为网页或媒体材料" },
  ].filter((item) => item.count > 0);
}

function renderUnifiedLearningPlan() {
  const items = materialLearningPlanItems();
  els.unifiedLearningPlan.classList.remove("hidden");
  els.unifiedLearningPlanMeta.textContent = items.length ? `${items.reduce((sum, item) => sum + item.count, 0)} 个材料` : "暂无材料";
  if (!items.length) {
    els.unifiedLearningPlanList.innerHTML = '<div class="queue empty">请先添加文本、截图、文档或链接材料</div>';
    return;
  }
  els.unifiedLearningPlanList.innerHTML = items
    .map(
      (item) => `
        <div class="material-plan-item">
          <strong>${escapeHtml(item.label)} x ${item.count}</strong>
          <span>${escapeHtml(item.purpose)}</span>
        </div>
      `
    )
    .join("");
}

function renderQueue() {
  els.queueCount.textContent = `${state.queue.length} 张`;
  if (!state.queue.length) {
    els.queue.className = "queue empty";
    els.queue.textContent = "暂无图片";
    return;
  }

  els.queue.className = "queue";
  els.queue.innerHTML = "";
  state.queue.forEach((item) => {
    const row = document.createElement("div");
    row.className = "queue-item";
    const src = item.previewUrl || (item.id ? `/api/images/${item.id}/file` : "");
    const title = item.title || item.name || item.image_hash?.slice(0, 12) || "截图";
    const sub = item.error_message || item.image_path || `${Math.max(1, Math.round((item.size || 0) / 1024))} KB`;
    row.innerHTML = `
      <img src="${src}" alt="截图预览" />
      <div>
        <div class="meta-title">${title}</div>
        <div class="meta-sub">${item.duplicate ? "重复图片，已复用记录" : sub}</div>
      </div>
      <div class="status ${item.status || "local"}">${statusLabel(item.status, item.uploading)}</div>
    `;

    const remove = document.createElement("button");
    remove.className = "remove-button";
    remove.type = "button";
    remove.title = "从本轮移除";
    remove.setAttribute("aria-label", "从本轮移除");
    remove.textContent = "x";
    remove.addEventListener("click", () => {
      if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      state.queue = state.queue.filter((queued) => queued !== item);
      renderQueue();
    });
    row.appendChild(remove);
    els.queue.appendChild(row);
  });
}

function renderDocumentQueue() {
  els.documentQueueCount.textContent = `${state.documentQueue.length} 个`;
  if (!state.documentQueue.length) {
    els.documentQueue.className = "queue empty";
    els.documentQueue.textContent = "暂无文件";
    return;
  }
  els.documentQueue.className = "queue";
  els.documentQueue.innerHTML = "";
  state.documentQueue.forEach((item) => {
    const row = document.createElement("div");
    row.className = "queue-item";
    const ext = (item.file_type || item.name?.split(".").pop() || "file").slice(0, 8);
    const sub = item.error_message || item.file_path || `${Math.max(1, Math.round((item.size || 0) / 1024))} KB`;
    const pageInfo = item.page_count ? ` - 共 ${item.page_count} 页/段` : "";
    const rangeValue = item.page_range || item.default_range || "";
    row.innerHTML = `
      <div class="queue-file-icon">${escapeHtml(ext)}</div>
      <div>
        <div class="meta-title">${escapeHtml(item.original_name || item.name || "文件")}</div>
        <div class="meta-sub">${item.duplicate ? "已存在同名内容,复用文件记录" : escapeHtml(sub)}${escapeHtml(pageInfo)}</div>
        ${item.id ? `<input class="page-range-input" data-file-id="${item.id}" type="text" placeholder="页码范围,如 15-37;20-25;30；留空为全文" value="${escapeHtml(rangeValue)}" />` : ""}
      </div>
      <div class="status ${item.status || "local"}">${statusLabel(item.status, item.uploading)}</div>
    `;
    const rangeInput = row.querySelector(".page-range-input");
    if (rangeInput) {
      rangeInput.addEventListener("input", (event) => {
        item.page_range = event.target.value;
        if (item.status === "planned") item.status = "uploaded";
      });
    }
    const remove = document.createElement("button");
    remove.className = "remove-button";
    remove.type = "button";
    remove.title = "移除文件";
    remove.setAttribute("aria-label", "移除文件");
    remove.textContent = "x";
    remove.addEventListener("click", () => {
      state.documentQueue = state.documentQueue.filter((queued) => queued !== item);
      renderDocumentQueue();
    });
    row.appendChild(remove);
    els.documentQueue.appendChild(row);
  });
}

function renderDocumentPlan() {
  const plan = state.documentPlan;
  if (!plan) {
    els.documentPlanPanel.classList.add("hidden");
    els.documentPlanMeta.textContent = "未生成规划";
    els.documentPlanList.innerHTML = "";
    return;
  }
  els.documentPlanPanel.classList.remove("hidden");
  const fileCount = plan.plans?.length || (plan.file_name ? 1 : 0);
  els.documentPlanMeta.textContent = `${fileCount || 1} 个文件 - ${plan.segments?.length || 0} 个主题`;
  els.documentPlanSummary.textContent = plan.summary || "请选择需要生成的知识文件";
  els.documentPlanList.innerHTML = "";
  (plan.segments || []).forEach((segment, index) => {
    const card = document.createElement("label");
    card.className = "plan-card";
    const checked = segment.selected !== false ? "checked" : "";
    const pages = segment.page_ranges || `${segment.page_start || 1}-${segment.page_end || plan.page_count || 1}`;
    card.innerHTML = `
      <input type="checkbox" data-plan-index="${index}" ${checked} />
      <div>
        <div class="plan-card-title">${escapeHtml(segment.title || `主题 ${index + 1}`)}</div>
        <div class="plan-card-meta">${escapeHtml(segment.file_name || "")}</div>
        <div class="plan-card-meta">${escapeHtml(segment.theme || "")}</div>
        <div class="plan-card-meta">页码: ${escapeHtml(String(pages))} - 约 ${escapeHtml(String(segment.estimated_chars || 0))} 字</div>
        <div class="plan-card-reason">${escapeHtml(segment.reason || "")}</div>
      </div>
    `;
    card.querySelector("input").addEventListener("change", (event) => {
      segment.selected = event.target.checked;
    });
    els.documentPlanList.appendChild(card);
  });
}

async function uploadPendingFiles() {
  const pending = state.queue.filter((item) => item.file && !item.id && !item.uploading);
  if (!pending.length) return;

  const pasted = pending.filter((item) => item.fromClipboard);
  const regular = pending.filter((item) => !item.fromClipboard);

  pending.forEach((item) => {
    item.uploading = true;
  });
  renderQueue();

  try {
    if (regular.length) {
      const form = new FormData();
      regular.forEach((item) => form.append("files", item.file, item.name));
      const data = await requestJson("/api/images", { method: "POST", body: form });
      data.items.forEach((serverItem, index) => {
        Object.assign(regular[index], serverItem, {
          file: null,
          uploading: false,
          status: serverItem.status || "uploaded",
        });
      });
    }

    if (pasted.length) {
      const images = await Promise.all(
        pasted.map(async (item) => ({
          filename: item.name,
          content_type: item.file.type || "image/png",
          data_url: await fileToDataUrl(item.file),
        }))
      );
      const data = await requestJson("/api/images/paste", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images }),
      });
      data.items.forEach((serverItem, index) => {
        Object.assign(pasted[index], serverItem, {
          file: null,
          uploading: false,
          status: serverItem.status || "uploaded",
        });
      });
    }

    renderQueue();
    showToast(`已加入本轮 ${pending.length} 张截图`);
  } catch (error) {
    pending.forEach((item) => {
      item.uploading = false;
      item.status = "error";
      item.error_message = error.message;
    });
    renderQueue();
    showToast(error.message);
  }
}

async function uploadPendingDocuments() {
  const pending = state.documentQueue.filter((item) => item.file && !item.id && !item.uploading);
  if (!pending.length) return;
  pending.forEach((item) => {
    item.uploading = true;
  });
  renderDocumentQueue();
  try {
    const form = new FormData();
    pending.forEach((item) => form.append("files", item.file, item.name));
    const data = await requestJson("/api/files", { method: "POST", body: form });
    data.items.forEach((serverItem, index) => {
      Object.assign(pending[index], serverItem, {
        file: null,
        uploading: false,
        status: serverItem.status || "uploaded",
      });
    });
    await loadDocumentPageInfo();
    renderDocumentQueue();
    showToast(`已加入本轮 ${pending.length} 个文件`);
  } catch (error) {
    pending.forEach((item) => {
      item.uploading = false;
      item.status = "error";
      item.error_message = error.message;
    });
    renderDocumentQueue();
    showToast(error.message);
  }
}

async function loadDocumentPageInfo() {
  const ids = state.documentQueue.filter((item) => item.id && !item.page_count).map((item) => item.id);
  if (!ids.length) return;
  const data = await requestJson("/api/files/page-info", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_ids: ids }),
  });
  (data.items || []).forEach((info) => {
    const item = state.documentQueue.find((queued) => queued.id === info.id);
    if (item) {
      item.page_count = info.page_count;
      item.total_chars = info.total_chars;
      item.default_range = info.default_range;
      if (!item.page_range) item.page_range = info.default_range;
    }
  });
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("读取粘贴图片失败"));
    reader.readAsDataURL(file);
  });
}

function knowledgeMatchesFilters(item) {
  const tags = parseTags(item.tags);
  const keyword = state.filters.keyword.trim().toLowerCase();
  const createdDate = (item.created_at || "").slice(0, 10);
  const searchable = [
    item.title,
    item.topic,
    item.markdown_path,
    item.created_at,
    ...tags,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (keyword && !searchable.includes(keyword)) return false;
  if (state.filters.dateFrom && createdDate && createdDate < state.filters.dateFrom) return false;
  if (state.filters.dateTo && createdDate && createdDate > state.filters.dateTo) return false;
  if ((state.filters.dateFrom || state.filters.dateTo) && !createdDate) return false;
  return true;
}

function filteredKnowledge() {
  return state.knowledge.filter(knowledgeMatchesFilters);
}

function filtersActive() {
  return Boolean(state.filters.keyword || state.filters.dateFrom || state.filters.dateTo);
}

function renderKnowledge() {
  const visibleKnowledge = filteredKnowledge();
  els.knowledgeCount.textContent = filtersActive()
    ? `${visibleKnowledge.length}/${state.knowledge.length} 个`
    : `${state.knowledge.length} 个`;
  if (!state.knowledge.length) {
    els.knowledgeList.className = "knowledge-list empty";
    els.knowledgeList.textContent = "暂无知识文件";
    return;
  }
  if (!visibleKnowledge.length) {
    els.knowledgeList.className = "knowledge-list empty";
    els.knowledgeList.textContent = "没有匹配的知识文件";
    return;
  }

  els.knowledgeList.className = "knowledge-list";
  els.knowledgeList.innerHTML = "";
  visibleKnowledge.forEach((item) => {
    const tags = parseTags(item.tags);
    const row = document.createElement("label");
    row.className = "knowledge-item";
    const checked = state.selectedKnowledge.has(item.id) ? "checked" : "";
    row.innerHTML = `
      <input type="checkbox" value="${item.id}" ${checked} />
      <div>
        <div class="meta-title">${item.title || "未命名知识"}</div>
        <div class="meta-sub">${item.created_at || ""}</div>
        <div class="meta-sub">${item.markdown_path || ""}</div>
        <div class="tag-row">${tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}</div>
      </div>
    `;
    const checkbox = row.querySelector("input");
    checkbox.addEventListener("change", (event) => {
      const id = Number(event.target.value);
      if (event.target.checked) {
        state.selectedKnowledge.add(id);
      } else {
        state.selectedKnowledge.delete(id);
      }
    });
    row.addEventListener("dblclick", () => previewKnowledge(item.id));
    els.knowledgeList.appendChild(row);
  });
}

async function generateKnowledge() {
  await uploadPendingFiles();
  if (!activeApiSetting()) {
    showToast("请先在 API 设置中添加并启用 API");
    openApiSettings();
    return;
  }
  const ids = state.queue.filter((item) => item.id).map((item) => item.id);
  if (!ids.length) {
    showToast("请先添加截图");
    return;
  }
  if (state.queue.some((item) => item.uploading)) {
    showToast("图片仍在上传，请稍后再试");
    return;
  }

  els.generateKnowledge.disabled = true;
  startAnalysisTimer();
  try {
    showToast(`开始${parserModeLabel()}...`);
    state.queue = state.queue.map((item) => ({ ...item, status: "processing" }));
    renderQueue();
    const data = await requestJson("/api/knowledge/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: ids, parser_mode: state.parserMode }),
    });
    state.queue = state.queue.map((item) => ({ ...item, status: "ready" }));
    renderQueue();
    await loadKnowledge();
    stopAnalysisTimer();
    const elapsed = formatElapsed(state.analysis.elapsedMs);
    showToast(
      data.skipped
        ? `本轮截图已生成过，已复用知识文件，模式：${parserModeLabel(data.parser_mode || state.parserMode)}，耗时 ${elapsed}`
        : `本轮知识文件生成完成，已保存到知识库，模式：${parserModeLabel(data.parser_mode || state.parserMode)}，耗时 ${elapsed}`
    );
  } catch (error) {
    stopAnalysisTimer();
    state.queue = state.queue.map((item) => ({ ...item, status: "error", error_message: error.message }));
    renderQueue();
    showToast(error.message);
  } finally {
    els.generateKnowledge.disabled = false;
  }
}

async function generateFileKnowledge() {
  await uploadPendingDocuments();
  if (!activeApiSetting()) {
    showToast("请先在 API 设置中添加并启用 API");
    openApiSettings();
    return;
  }
  const ids = state.documentQueue.filter((item) => item.id).map((item) => item.id);
  if (!ids.length) {
    showToast("请先添加文件");
    return;
  }
  if (state.documentQueue.some((item) => item.uploading)) {
    showToast("文件仍在上传，请稍后再试");
    return;
  }

  els.generateFileKnowledge.disabled = true;
  startFileAnalysisTimer();
  try {
    showToast("开始解析文件并生成知识...");
    state.documentQueue = state.documentQueue.map((item) => ({ ...item, status: "processing" }));
    renderDocumentQueue();
    const data = await requestJson("/api/knowledge/generate-from-files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: ids }),
    });
    state.documentQueue = state.documentQueue.map((item) => ({ ...item, status: "ready" }));
    renderDocumentQueue();
    await loadKnowledge();
    stopFileAnalysisTimer();
    const elapsed = formatElapsed(state.fileAnalysis.elapsedMs);
    showToast(data.skipped ? `本轮文件已生成过，已复用知识文件，耗时 ${elapsed}` : `本轮文件知识生成完成，已保存到知识库，耗时 ${elapsed}`);
  } catch (error) {
    stopFileAnalysisTimer();
    state.documentQueue = state.documentQueue.map((item) => ({ ...item, status: "error", error_message: error.message }));
    renderDocumentQueue();
    showToast(error.message);
  } finally {
    els.generateFileKnowledge.disabled = false;
  }
}

async function planFileKnowledge() {
  await uploadPendingDocuments();
  if (!activeApiSetting()) {
    showToast("请先在 API 设置中启用可用 API");
    openApiSettings();
    return;
  }
  const uploaded = state.documentQueue.filter((item) => item.id);
  if (!uploaded.length) {
    showToast("请先选择文件");
    return;
  }
  els.planFileKnowledge.disabled = true;
  startFileAnalysisTimer();
  try {
    showToast("正在按页码范围生成知识文件规划...");
    await loadDocumentPageInfo();
    renderDocumentQueue();
    const files = uploaded.map((item) => ({
      file_id: item.id,
      page_ranges: item.page_range || item.default_range || "",
    }));
    const data = await requestJson("/api/files/plan-ranges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files }),
    });
    state.documentPlan = data.plan || { segments: [] };
    state.documentPlan.plans = data.plans || [];
    const plannedIds = new Set(uploaded.map((item) => item.id));
    state.documentQueue = state.documentQueue.map((item) =>
      plannedIds.has(item.id) ? { ...item, status: "planned" } : item
    );
    renderDocumentQueue();
    renderDocumentPlan();
    stopFileAnalysisTimer();
    showToast(`已生成 ${state.documentPlan.segments.length} 个规划主题`);
  } catch (error) {
    stopFileAnalysisTimer();
    showToast(error.message);
  } finally {
    els.planFileKnowledge.disabled = false;
  }
}

async function generatePlannedKnowledge() {
  const plan = state.documentPlan;
  if (!plan) {
    showToast("请先生成规划");
    return;
  }
  const segments = (plan.segments || []).filter((segment) => segment.selected !== false);
  if (!segments.length) {
    showToast("请至少勾选一个规划主题");
    return;
  }
  els.generatePlannedKnowledge.disabled = true;
  startFileAnalysisTimer({ label: "知识文件生成时间", progressDone: 0, progressTotal: segments.length });
  try {
    showToast(`正在生成选中的知识文件: 0/${segments.length}`);
    const allItems = [];
    let generatedCount = 0;
    for (const segment of segments) {
      const data = await requestJson("/api/knowledge/generate-from-plan-segments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segments: [segment] }),
      });
      generatedCount += data.generated || data.items?.length || 1;
      if (Array.isArray(data.items)) allItems.push(...data.items);
      updateFileAnalysisProgress(Math.min(allItems.length || generatedCount, segments.length), segments.length);
    }
    const generatedIds = new Set(segments.map((segment) => segment.file_id).filter(Boolean));
    state.documentQueue = state.documentQueue.map((item) =>
      generatedIds.has(item.id) ? { ...item, status: "ready" } : item
    );
    renderDocumentQueue();
    await loadKnowledge();
    updateFileAnalysisProgress(segments.length, segments.length);
    stopFileAnalysisTimer();
    const elapsed = formatElapsed(state.fileAnalysis.elapsedMs);
    showToast(`已生成 ${segments.length} 个知识文件，耗时 ${elapsed}`);
  } catch (error) {
    stopFileAnalysisTimer();
    showToast(error.message);
  } finally {
    els.generatePlannedKnowledge.disabled = false;
  }
}

async function deprecatedKnowledgeActionInLegacyShell() {
  const ids = [...state.selectedKnowledge];
  if (!ids.length) {
    showToast("请先选择要处理的知识文件");
    return;
  }
  if (!activeApiSetting()) {
    showToast("请先在 API 设置中添加并启用 API");
    openApiSettings();
    return;
  }
  els.ingestKnowledge.disabled = true;
  try {
    showToast("正在处理选中的知识文件...");
    showToast("当前版本已下线图谱处理入口");
    showToast(failCount ? `已处理 ${okCount} 个文件，失败 ${failCount} 个` : `已生成 ${data.pending_node_ids?.length || 0} 个候选节点`);
  } catch (error) {
    showToast(error.message);
  } finally {
    els.ingestKnowledge.disabled = false;
  }
}

async function deprecatedKnowledgeDeleteInLegacyShell() {
  const ids = [...state.selectedKnowledge];
  if (!ids.length) {
    showToast("请先选择要删除的知识文件");
    return;
  }
  const selectedItems = state.knowledge.filter((item) => state.selectedKnowledge.has(item.id));
  if (!selectedItems.length) {
    showToast("当前版本已下线该删除入口");
    return;
  }
  els.deleteNotIngestedKnowledge.disabled = true;
  try {
    showToast("当前版本已下线该删除入口");
  } catch (error) {
    showToast(error.message);
  } finally {
    els.deleteNotIngestedKnowledge.disabled = false;
  }
}

async function loadKnowledge() {
  const data = await requestJson("/api/knowledge");
  state.knowledge = data.items;
  renderKnowledge();
}

async function previewKnowledge(id) {
  try {
    const data = await requestJson(`/api/knowledge/${id}`);
    state.markdownContent = data.content || "";
    els.previewTitle.textContent = data.item.title || "未命名知识";
    els.markdownPreview.textContent = state.markdownContent;
    els.markdownModal.classList.remove("hidden");
  } catch (error) {
    showToast(error.message);
  }
}

function closeMarkdownPreview() {
  els.markdownModal.classList.add("hidden");
}

async function copyMarkdownContent() {
  try {
    await navigator.clipboard.writeText(state.markdownContent || "");
    showToast("Markdown 已复制");
  } catch {
    showToast("复制失败，可以手动选中文本复制");
  }
}

function clearQueue() {
  state.queue.forEach((item) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  });
  state.queue = [];
  resetAnalysisTimer();
  renderQueue();
}

function clearDocumentQueue() {
  state.documentQueue = [];
  state.documentPlan = null;
  resetFileAnalysisTimer();
  renderDocumentQueue();
  renderDocumentPlan();
}

function filesFromClipboard(event) {
  const files = [...(event.clipboardData?.files || [])].filter((file) => file.type.startsWith("image/"));
  if (files.length) {
    return files.map((file, index) => {
      const pastedFile = new File([file], file.name || `clipboard-${Date.now()}-${index}.png`, {
        type: file.type || "image/png",
      });
      pastedFile.fromClipboard = true;
      return pastedFile;
    });
  }

  const items = [...(event.clipboardData?.items || [])];
  return items
    .filter((item) => item.type.startsWith("image/"))
    .map((item, index) => {
      const file = item.getAsFile();
      if (!file) return null;
      const pastedFile = new File([file], file.name || `clipboard-${Date.now()}-${index}.png`, {
        type: file.type || "image/png",
      });
      pastedFile.fromClipboard = true;
      return pastedFile;
    })
    .filter(Boolean);
}

els.dropzone.addEventListener("click", () => els.fileInput.click());
els.chooseFiles.addEventListener("click", () => els.fileInput.click());
els.clearQueue.addEventListener("click", clearQueue);
els.refineModeTab.addEventListener("click", () => switchPrimaryMode("refine"));
els.miningModeTab.addEventListener("click", () => switchPrimaryMode("mining"));
els.screenshotInputTab.addEventListener("click", () => switchInputTab("screenshots"));
els.fileInputTab.addEventListener("click", () => switchInputTab("files"));
els.mediaInputTab.addEventListener("click", () => {
  navigateToWorkspaceEntry("collect-media", "/collect/media");
});
els.materialTypeCards.forEach((card) => {
  card.addEventListener("click", () => selectMaterialType(card.dataset.materialType));
});
els.globalLibraryTabs.forEach((tab) => {
  tab.addEventListener("click", () => setActiveGlobalLibrary(tab.dataset.libraryKind));
});
els.openLegacyWriterTool?.addEventListener("click", () => {
  window.location.href = "/writer";
});
els.clearGlobalLibrarySelection?.addEventListener("click", () => {
  state.selectedKnowledge.clear();
  renderKnowledge();
  showToast("已清空全局库选择");
});
els.planLearningMaterials.addEventListener("click", renderUnifiedLearningPlan);
els.addTextMaterial.addEventListener("click", addTextMaterial);
els.clearTextMaterials.addEventListener("click", clearTextMaterials);
els.addLinkMaterial.addEventListener("click", addLinkMaterials);
els.clearLinkMaterials.addEventListener("click", clearLinkMaterials);
els.documentDropzone.addEventListener("click", () => els.documentInput.click());
els.chooseDocuments.addEventListener("click", () => els.documentInput.click());
els.clearDocumentQueue.addEventListener("click", clearDocumentQueue);
els.planFileKnowledge.addEventListener("click", planFileKnowledge);
els.generateFileKnowledge.addEventListener("click", generateFileKnowledge);
els.generatePlannedKnowledge.addEventListener("click", generatePlannedKnowledge);
els.createMiningProject.addEventListener("click", () => createMiningProject().catch((error) => showToast(error.message)));
els.saveMiningProjectName.addEventListener("click", () => renameMiningProject().catch((error) => showToast(error.message)));
els.chooseMiningDocuments.addEventListener("click", () => els.miningDocumentInput.click());
els.chooseMiningImages.addEventListener("click", () => els.miningImageInput.click());
els.chooseMiningMedia.addEventListener("click", () => els.miningMediaInput.click());
els.miningDocumentInput.addEventListener("change", (event) => {
  uploadMiningDocuments(event.target.files).catch((error) => showToast(error.message));
  event.target.value = "";
});
els.miningImageInput.addEventListener("change", (event) => {
  uploadMiningImages(event.target.files).catch((error) => showToast(error.message));
  event.target.value = "";
});
els.miningMediaInput.addEventListener("change", (event) => {
  uploadMiningMedia(event.target.files).catch((error) => showToast(error.message));
  event.target.value = "";
});
els.attachMiningMediaUrls.addEventListener("click", () => attachMiningMediaUrls().catch((error) => showToast(error.message)));
els.learnCreationStrategy.addEventListener("click", () => learnCreationStrategy().catch((error) => showToast(error.message)));
els.openWriterTool.addEventListener("click", openWriterTool);
els.openApiSettings.addEventListener("click", openApiSettings);
els.openGlobalSettings?.addEventListener("click", () => {
  if (els.openGlobalSettings.tagName === "BUTTON") openApiSettings();
});
els.closeApiSettings.addEventListener("click", closeApiSettings);
els.apiSettingsModal.addEventListener("click", (event) => {
  if (event.target === els.apiSettingsModal) closeApiSettings();
});
els.apiSettingSelect.addEventListener("change", (event) => {
  const setting = state.apiSettings.items.find((item) => item.id === event.target.value);
  if (setting) {
    fillApiFormFromSetting(setting);
    pushApiLog("info", `已切换到配置「${setting.name}」进行查看或编辑。`);
  }
});
els.apiTemplateSelect.addEventListener("change", (event) => {
  const template = state.apiSettings.templates.find((item) => item.id === event.target.value);
  fillApiFormFromTemplate(template);
  if (template) {
    pushApiLog("info", `已套用模板「${template.name}」，可以继续改写。`);
  }
});
els.newApiSetting.addEventListener("click", () => {
  const template = state.apiSettings.templates.find((item) => item.id === els.apiTemplateSelect.value)
    || state.apiSettings.templates[0];
  fillApiFormFromTemplate(template);
  pushApiLog("info", `已新建空白配置，初始模板为「${template?.name || "默认模板"}」。`);
});
els.clearApiLogs.addEventListener("click", () => {
  state.apiSettings.logs = [];
  renderApiLogs();
  pushApiLog("info", "运行日志已清空。");
});
els.activateApiSetting.addEventListener("click", () => activateSelectedApiSetting().catch((error) => {
  pushApiLog("error", error.message);
  showToast(error.message);
}));
els.deleteApiSetting.addEventListener("click", () => deleteSelectedApiSetting().catch((error) => {
  pushApiLog("error", error.message);
  showToast(error.message);
}));
els.apiSettingForm.addEventListener("submit", (event) => saveApiSetting(event).catch((error) => {
  pushApiLog("error", error.message);
  showToast(error.message);
}));
els.testApiSetting.addEventListener("click", () => testCurrentApiSetting().catch((error) => {
  pushApiLog("error", error.message);
  showToast(error.message);
}));
els.fileInput.addEventListener("change", (event) => {
  addLocalFiles(event.target.files);
  event.target.value = "";
});
els.documentInput.addEventListener("change", (event) => {
  addDocumentFiles(event.target.files);
  event.target.value = "";
});
els.localOcrMode.addEventListener("click", () => {
  state.parserMode = "local_ocr";
  renderParserMode();
  showToast("已切换为本地 PaddleOCR 解析");
});
els.aiVisionMode.addEventListener("click", () => {
  state.parserMode = "ai_vision";
  renderParserMode();
  showToast("已切换为 AI 智能解析");
});
els.generateKnowledge.addEventListener("click", generateKnowledge);
els.refreshKnowledge.addEventListener("click", loadKnowledge);
els.closeMarkdownModal.addEventListener("click", closeMarkdownPreview);
els.copyMarkdown.addEventListener("click", copyMarkdownContent);
els.markdownModal.addEventListener("click", (event) => {
  if (event.target === els.markdownModal) closeMarkdownPreview();
});
els.knowledgePanelHandle.addEventListener("pointerdown", startKnowledgePanelResize);
els.knowledgeKeyword.addEventListener("input", (event) => {
  state.filters.keyword = event.target.value;
  renderKnowledge();
});
els.knowledgeDateFrom.addEventListener("change", (event) => {
  state.filters.dateFrom = event.target.value;
  renderKnowledge();
});
els.knowledgeDateTo.addEventListener("change", (event) => {
  state.filters.dateTo = event.target.value;
  renderKnowledge();
});
els.clearKnowledgeFilters.addEventListener("click", () => {
  state.filters.keyword = "";
  state.filters.dateFrom = "";
  state.filters.dateTo = "";
  els.knowledgeKeyword.value = "";
  els.knowledgeDateFrom.value = "";
  els.knowledgeDateTo.value = "";
  renderKnowledge();
});

["dragenter", "dragover"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("active");
  });
  els.documentDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.documentDropzone.classList.add("active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("active");
  });
  els.documentDropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.documentDropzone.classList.remove("active");
  });
});

els.dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  addLocalFiles(event.dataTransfer.files);
});

els.documentDropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  addDocumentFiles(event.dataTransfer.files);
});

function handlePaste(event) {
  const files = filesFromClipboard(event);
  if (!files.length) return;
  event.preventDefault();
  event.stopPropagation();
  addLocalFiles(files);
  if (event.currentTarget === els.pasteBox) {
    els.pasteBox.value = "";
  }
}

window.addEventListener("paste", handlePaste);
els.pasteBox.addEventListener("paste", handlePaste);
els.dropzone.addEventListener("paste", handlePaste);
window.addEventListener("resize", () => {
  if (!els.knowledgePanel?.style.height) return;
  applyKnowledgePanelHeight(Number.parseFloat(els.knowledgePanel.style.height));
});

Promise.all([loadV2Contracts(), loadApiSettings({ silent: true }), loadKnowledge(), loadMiningProjects()]).catch((error) => showToast(error.message));
renderApiLogs();
renderParserMode();
switchInputTab(state.activeInput);
switchPrimaryMode(state.activeMode);
activateShellSection(shellSectionFromPath());
renderDocumentQueue();
renderTextMaterials();
renderLinkMaterials();
renderDocumentPlan();
renderMiningWorkspace();
renderFileAnalysisTime();
restoreKnowledgePanelHeight();
function unwrapV2(payload) {
  return payload?.data ?? {};
}
