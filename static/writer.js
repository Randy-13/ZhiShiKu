const state = {
  ids: [],
  files: [],
  selectedFileIndex: 0,
  topics: [],
  selectedTopicIndex: -1,
  workspace: "",
  coverPrompt: "",
  contentImagePrompts: [],
  generatedImages: [],
  htmlReady: false,
  digest: "",
  workspaces: [],
  selectedWorkspacePath: "",
  imageApi: {
    items: [],
    templates: [],
    activeId: null,
    editingId: null,
    logs: [],
  },
  logs: [],
};

const els = {
  selectedKnowledgeCount: document.querySelector("#selectedKnowledgeCount"),
  writerKnowledgeList: document.querySelector("#writerKnowledgeList"),
  writerMarkdownPreview: document.querySelector("#writerMarkdownPreview"),
  generateWriterTopics: document.querySelector("#generateWriterTopics"),
  writerTopicList: document.querySelector("#writerTopicList"),
  generateArticle: document.querySelector("#generateArticle"),
  directoryWorkTab: document.querySelector("#directoryWorkTab"),
  articleWorkTab: document.querySelector("#articleWorkTab"),
  imageWorkTab: document.querySelector("#imageWorkTab"),
  formatWorkTab: document.querySelector("#formatWorkTab"),
  publishWorkTab: document.querySelector("#publishWorkTab"),
  logWorkTab: document.querySelector("#logWorkTab"),
  directoryWorkbench: document.querySelector("#directoryWorkbench"),
  articleWorkbench: document.querySelector("#articleWorkbench"),
  imageWorkbench: document.querySelector("#imageWorkbench"),
  formatWorkbench: document.querySelector("#formatWorkbench"),
  publishWorkbench: document.querySelector("#publishWorkbench"),
  logWorkbench: document.querySelector("#logWorkbench"),
  suggestImages: document.querySelector("#suggestImages"),
  confirmGenerateImages: document.querySelector("#confirmGenerateImages"),
  coverPromptEditor: document.querySelector("#coverPromptEditor"),
  contentPromptEditor: document.querySelector("#contentPromptEditor"),
  imagePreviewGrid: document.querySelector("#imagePreviewGrid"),
  imagePreviewStatus: document.querySelector("#imagePreviewStatus"),
  checkMarkdown: document.querySelector("#checkMarkdown"),
  checkCover: document.querySelector("#checkCover"),
  checkHtml: document.querySelector("#checkHtml"),
  checkWechatIp: document.querySelector("#checkWechatIp"),
  wechatIpResult: document.querySelector("#wechatIpResult"),
  preflightPublish: document.querySelector("#preflightPublish"),
  publishPreflight: document.querySelector("#publishPreflight"),
  formatArticle: document.querySelector("#formatArticle"),
  publishDraft: document.querySelector("#publishDraft"),
  writerWorkspace: document.querySelector("#writerWorkspace"),
  articleTitle: document.querySelector("#articleTitle"),
  articleAuthor: document.querySelector("#articleAuthor"),
  articleDigest: document.querySelector("#articleDigest"),
  digestByteCount: document.querySelector("#digestByteCount"),
  truncateDigest: document.querySelector("#truncateDigest"),
  articleMarkdown: document.querySelector("#articleMarkdown"),
  htmlPreview: document.querySelector("#htmlPreview"),
  writerLogs: document.querySelector("#writerLogs"),
  markdownTab: document.querySelector("#markdownTab"),
  revisionForm: document.querySelector("#revisionForm"),
  revisionInstruction: document.querySelector("#revisionInstruction"),
  reviseArticle: document.querySelector("#reviseArticle"),
  revisionMessages: document.querySelector("#revisionMessages"),
  toast: document.querySelector("#toast"),
  imageApiModal: document.querySelector("#imageApiModal"),
  openImageApiSettings: document.querySelector("#openImageApiSettings"),
  closeImageApiSettings: document.querySelector("#closeImageApiSettings"),
  imageApiStatus: document.querySelector("#imageApiStatus"),
  imageApiSelect: document.querySelector("#imageApiSelect"),
  imageApiTemplate: document.querySelector("#imageApiTemplate"),
  imageApiName: document.querySelector("#imageApiName"),
  imageApiProvider: document.querySelector("#imageApiProvider"),
  imageApiBaseUrl: document.querySelector("#imageApiBaseUrl"),
  imageApiModel: document.querySelector("#imageApiModel"),
  imageApiKey: document.querySelector("#imageApiKey"),
  imageApiSize: document.querySelector("#imageApiSize"),
  imageApiQuality: document.querySelector("#imageApiQuality"),
  imageApiTimeout: document.querySelector("#imageApiTimeout"),
  imageApiForm: document.querySelector("#imageApiForm"),
  newImageApiSetting: document.querySelector("#newImageApiSetting"),
  activateImageApiSetting: document.querySelector("#activateImageApiSetting"),
  deleteImageApiSetting: document.querySelector("#deleteImageApiSetting"),
  testImageApi: document.querySelector("#testImageApi"),
  clearImageApiLogs: document.querySelector("#clearImageApiLogs"),
  imageApiLogList: document.querySelector("#imageApiLogList"),
  refreshWorkspaces: document.querySelector("#refreshWorkspaces"),
  continueWorkspace: document.querySelector("#continueWorkspace"),
  workspaceList: document.querySelector("#workspaceList"),
  workspacePreviewTitle: document.querySelector("#workspacePreviewTitle"),
  workspacePreviewStatus: document.querySelector("#workspacePreviewStatus"),
  workspacePreviewChecks: document.querySelector("#workspacePreviewChecks"),
  workspaceArticlePreview: document.querySelector("#workspaceArticlePreview"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 2800);
}

async function requestJson(url, options = {}) {
  const startedAt = performance.now();
  const method = options.method || "GET";
  const shouldLogTiming = url.startsWith("/api/writer");
  if (shouldLogTiming) addLog(`${method} ${url} 等待响应...`);
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
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || JSON.stringify(item)).join("；");
    if (detail && typeof detail === "object") detail = JSON.stringify(detail);
    if (shouldLogTiming) finishStep(startedAt, `${method} ${url} 失败：${detail || response.status}`, "error");
    throw new Error(detail || `请求失败：${response.status}`);
  }
  if (shouldLogTiming) finishStep(startedAt, `${method} ${url} 已完成`);
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function addLog(message, level = "info") {
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  state.logs.push(`[${time}] ${level.toUpperCase()} ${message}`);
  if (state.logs.length > 200) state.logs = state.logs.slice(-200);
  els.writerLogs.textContent = state.logs.join("\n");
}

function startStep(message) {
  addLog(`${message}，等待中...`);
  return performance.now();
}

function finishStep(startedAt, message, level = "success") {
  const seconds = ((performance.now() - startedAt) / 1000).toFixed(1);
  addLog(`${message}（耗时 ${seconds} 秒）`, level);
}

function utf8Bytes(value) {
  return new TextEncoder().encode(value || "").length;
}

function truncateUtf8(value, maxBytes) {
  let result = "";
  for (const char of value || "") {
    if (utf8Bytes(result + char) > maxBytes) break;
    result += char;
  }
  return result;
}

function updateDigestPreview() {
  if (!els.articleDigest) return;
  const bytes = utf8Bytes(els.articleDigest.value);
  els.digestByteCount.textContent = `${bytes} / 120 字节`;
  els.digestByteCount.classList.toggle("over", bytes > 120);
}

function setDigest(value) {
  state.digest = value || "";
  if (els.articleDigest) {
    els.articleDigest.value = state.digest;
    updateDigestPreview();
  }
}

function readDigest() {
  state.digest = els.articleDigest ? els.articleDigest.value.trim() : state.digest;
  updateDigestPreview();
  return state.digest;
}

function renderImageApiLogs() {
  if (!els.imageApiLogList) return;
  if (!state.imageApi.logs.length) {
    els.imageApiLogList.textContent = "暂无日志";
    return;
  }
  els.imageApiLogList.innerHTML = "";
  state.imageApi.logs.forEach((entry) => {
    const row = document.createElement("article");
    row.className = "api-log-item";
    row.innerHTML = `
      <div class="api-log-meta">
        <span>${escapeHtml(entry.time)}</span>
        <span class="api-log-level ${entry.level}">${escapeHtml(entry.label)}</span>
      </div>
      <div class="api-log-message">${escapeHtml(entry.message)}</div>
    `;
    els.imageApiLogList.appendChild(row);
  });
  els.imageApiLogList.scrollTop = els.imageApiLogList.scrollHeight;
}

function pushImageApiLog(level, message) {
  const labels = {
    info: "进行中",
    success: "成功",
    error: "失败",
  };
  state.imageApi.logs.push({
    time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    level,
    label: labels[level] || "记录",
    message,
  });
  if (state.imageApi.logs.length > 120) {
    state.imageApi.logs = state.imageApi.logs.slice(-120);
  }
  renderImageApiLogs();
}

function parseIds() {
  const params = new URLSearchParams(window.location.search);
  state.ids = (params.get("ids") || "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter(Boolean);
}

function renderFiles() {
  els.selectedKnowledgeCount.textContent = `${state.files.length} 个`;
  if (!state.files.length) {
    els.writerKnowledgeList.className = "writer-list empty";
    els.writerKnowledgeList.textContent = "没有加载到知识文件";
    return;
  }
  els.writerKnowledgeList.className = "writer-list";
  els.writerKnowledgeList.innerHTML = "";
  state.files.forEach((file, index) => {
    const item = file.item || {};
    const row = document.createElement("article");
    row.className = `writer-file-item ${index === state.selectedFileIndex ? "active" : ""}`;
    row.innerHTML = `
      <div class="writer-file-title">${escapeHtml(item.title || file.filename)}</div>
      <div class="writer-file-meta">${escapeHtml(item.created_at || "")}</div>
      <div class="writer-file-meta">${escapeHtml(item.markdown_path || file.filename)}</div>
    `;
    row.addEventListener("click", () => {
      state.selectedFileIndex = index;
      renderFiles();
      renderMarkdownPreview();
    });
    els.writerKnowledgeList.appendChild(row);
  });
  renderMarkdownPreview();
}

function renderMarkdownPreview() {
  const file = state.files[state.selectedFileIndex];
  els.writerMarkdownPreview.textContent = file?.content || "选择左侧知识文件查看 Markdown。";
}

function renderTopics() {
  if (!state.topics.length) {
    els.writerTopicList.className = "writer-topic-list empty";
    els.writerTopicList.textContent = "暂无选题建议";
    return;
  }
  els.writerTopicList.className = "writer-topic-list";
  els.writerTopicList.innerHTML = "";
  state.topics.forEach((topic, index) => {
    const card = document.createElement("article");
    card.className = `writer-topic-item ${index === state.selectedTopicIndex ? "active" : ""}`;
    card.innerHTML = `
      <div class="writer-topic-title">${escapeHtml(topic.title || "未命名选题")}</div>
      <div class="writer-topic-meta">${escapeHtml(topic.angle || "")}</div>
      <div class="writer-topic-meta">${escapeHtml(topic.reason || "")}</div>
    `;
    card.addEventListener("click", () => {
      state.selectedTopicIndex = index;
      renderTopics();
      addLog(`已选择选题：${topic.title}`);
    });
    els.writerTopicList.appendChild(card);
  });
}

function selectedTopic() {
  return state.topics[state.selectedTopicIndex] || null;
}

function showWorkbench(name) {
  els.directoryWorkbench.classList.toggle("hidden", name !== "directory");
  els.articleWorkbench.classList.toggle("hidden", name !== "article");
  els.imageWorkbench.classList.toggle("hidden", name !== "image");
  els.formatWorkbench.classList.toggle("hidden", name !== "format");
  els.publishWorkbench.classList.toggle("hidden", name !== "publish");
  els.logWorkbench.classList.toggle("hidden", name !== "log");
  els.directoryWorkTab.classList.toggle("active", name === "directory");
  els.articleWorkTab.classList.toggle("active", name === "article");
  els.imageWorkTab.classList.toggle("active", name === "image");
  els.formatWorkTab.classList.toggle("active", name === "format");
  els.publishWorkTab.classList.toggle("active", name === "publish");
  els.logWorkTab.classList.toggle("active", name === "log");
  if (name === "publish") updatePublishChecklist();
}

function renderWorkspaceList() {
  if (!state.workspaces.length) {
    els.workspaceList.className = "workspace-list empty";
    els.workspaceList.textContent = "暂无工作文件";
    return;
  }
  els.workspaceList.className = "workspace-list";
  els.workspaceList.innerHTML = "";
  state.workspaces.forEach((item) => {
    const row = document.createElement("article");
    row.className = `workspace-item ${item.workspace === state.selectedWorkspacePath ? "active" : ""}`;
    row.innerHTML = `
      <div class="workspace-item-title">${escapeHtml(item.title || item.name)}</div>
      <div class="workspace-item-meta">${escapeHtml(item.workspace)}</div>
      <div class="workspace-item-footer">
        <span class="workspace-status ${item.published ? "published" : "unpublished"}">${item.published ? "已发布" : "未发布"}</span>
        <span>${escapeHtml(item.updated_at || "")}</span>
      </div>
    `;
    row.addEventListener("click", () => selectWorkspace(item.workspace));
    els.workspaceList.appendChild(row);
  });
}

function renderWorkspaceChecks(data) {
  const checks = data?.checks || {};
  const labels = [
    ["markdown", "文章 Markdown"],
    ["cover", "封面图"],
    ["html", "HTML 排版"],
    ["published", "发布完成"],
  ];
  els.workspacePreviewChecks.innerHTML = labels
    .map(([key, label]) => `<span>${label}</span><strong class="${checks[key] ? "ok" : "miss"}">${checks[key] ? "已完成" : "未完成"}</strong>`)
    .join("");
}

async function loadWorkspaces() {
  const data = await requestJson("/api/writer/workspaces");
  state.workspaces = data.items || [];
  renderWorkspaceList();
  addLog(`已加载 ${state.workspaces.length} 个写文工作目录。`);
}

async function selectWorkspace(path) {
  state.selectedWorkspacePath = path;
  renderWorkspaceList();
  const data = await requestJson(`/api/writer/workspace?path=${encodeURIComponent(path)}`);
  els.workspacePreviewTitle.textContent = data.title || data.name || "未命名工作文件";
  els.workspacePreviewStatus.textContent = data.published ? "已发布" : "未发布";
  els.workspaceArticlePreview.value = data.article_markdown || "";
  renderWorkspaceChecks(data);
  addLog(`已读取工作目录：${data.workspace}`);
}

function restoreWorkspace(data) {
  state.workspace = data.workspace;
  state.generatedImages = data.images || [];
  state.htmlReady = Boolean(data.checks?.html);
  state.coverPrompt = "";
  state.contentImagePrompts = [];
  setDigest(data.publish_result?.digest || state.digest || "");
  els.articleTitle.value = data.title || data.name || "";
  els.articleMarkdown.value = data.article_markdown || els.workspaceArticlePreview.value || "";
  els.writerWorkspace.textContent = `工作目录：${data.workspace}`;
  if (data.html) {
    els.htmlPreview.srcdoc = data.html;
  }
  updatePromptEditors();
  renderImagePreviews();
  updatePublishChecklist();
}

async function continueWorkspace() {
  if (!state.selectedWorkspacePath) {
    showToast("请先选择一个工作文件");
    return;
  }
  const data = await requestJson(`/api/writer/workspace?path=${encodeURIComponent(state.selectedWorkspacePath)}`);
  restoreWorkspace(data);
  if (els.workspaceArticlePreview.value.trim() && els.workspaceArticlePreview.value !== data.article_markdown) {
    els.articleMarkdown.value = els.workspaceArticlePreview.value;
    addLog("已使用目录预览区的编辑内容作为当前 Markdown。");
  }
  addLog(`继续发布检查：Markdown ${data.checks.markdown ? "已完成" : "缺失"}，封面 ${data.checks.cover ? "已完成" : "缺失"}，HTML ${data.checks.html ? "已完成" : "缺失"}，发布 ${data.checks.published ? "已完成" : "未完成"}。`);
  showWorkbench(data.checks.html ? "publish" : "article");
}

function updatePromptEditors() {
  els.coverPromptEditor.value = state.coverPrompt || "";
  els.contentPromptEditor.value = (state.contentImagePrompts || []).join("\n");
}

function readPromptEditors() {
  state.coverPrompt = els.coverPromptEditor.value.trim();
  state.contentImagePrompts = els.contentPromptEditor.value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function imageUrl(path) {
  return `/api/writer/file?path=${encodeURIComponent(path)}`;
}

function renderImagePreviews() {
  if (!state.generatedImages.length) {
    els.imagePreviewGrid.className = "image-preview-grid empty";
    els.imagePreviewGrid.textContent = "暂无图片";
    els.imagePreviewStatus.textContent = "暂无图片";
    updatePublishChecklist();
    return;
  }
  els.imagePreviewGrid.className = "image-preview-grid";
  els.imagePreviewGrid.innerHTML = "";
  state.generatedImages.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "image-preview-card";
    card.innerHTML = `
      <img src="${imageUrl(item.path)}" alt="生成图片 ${index + 1}" />
      <div class="image-preview-meta">
        <strong>${index === 0 ? "封面图" : `内容配图 ${index}`}</strong>
        <span>${escapeHtml(item.path || "")}</span>
      </div>
    `;
    els.imagePreviewGrid.appendChild(card);
  });
  els.imagePreviewStatus.textContent = `${state.generatedImages.length} 张`;
  updatePublishChecklist();
}

function updatePublishChecklist() {
  if (!els.checkMarkdown) return;
  els.checkMarkdown.textContent = els.articleMarkdown.value.trim() ? "已生成" : "未生成";
  els.checkCover.textContent = state.generatedImages.some((item) => /cover\.(png|jpg|jpeg|webp)$/i.test(item.path || item.name || ""))
    ? "已生成"
    : "未生成";
  els.checkHtml.textContent = state.htmlReady ? "已生成" : "未生成";
}

function renderPublishPreflight(data) {
  const checks = data.checks || [];
  if (!checks.length) {
    els.publishPreflight.className = "publish-preflight empty";
    els.publishPreflight.textContent = "尚未执行发布预检";
    return;
  }
  els.publishPreflight.className = `publish-preflight ${data.ok ? "ok" : "failed"}`;
  els.publishPreflight.innerHTML = `
    <div class="preflight-status">${data.ok ? "预检通过，可以转入草稿箱" : "预检未通过，请先处理红色项目"}</div>
    <div class="preflight-list">
      ${checks.map((item) => `
        <article class="${item.ok ? "ok" : item.optional ? "warn" : "failed"}">
          <strong>${escapeHtml(item.ok ? "通过" : item.optional ? "提醒" : "阻断")} · ${escapeHtml(item.label)}</strong>
          <span>${escapeHtml(item.detail || "")}</span>
        </article>
      `).join("")}
    </div>
    <details>
      <summary>微信官方接口调用顺序</summary>
      <ol>${(data.flow || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>
    </details>
  `;
}

async function runPublishPreflight() {
  if (!state.workspace) {
    showToast("请先生成文章并美编排版");
    return null;
  }
  setBusy(els.preflightPublish, true, "预检中...");
  try {
    const data = await requestJson("/api/writer/publish/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: state.workspace,
        title: els.articleTitle.value.trim() || "未命名文章",
        author: els.articleAuthor.value.trim() || "Bobo",
        digest: readDigest(),
      }),
    });
    renderPublishPreflight(data);
    addLog(data.ok ? "发布预检通过。" : "发布预检未通过，请查看发布页检查项。", data.ok ? "success" : "error");
    return data;
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
    return null;
  } finally {
    setBusy(els.preflightPublish, false);
  }
}

function renderWechatIpResult(data) {
  els.wechatIpResult.className = `wechat-ip-result ${data.ok ? "ok" : data.ip ? "failed" : "warn"}`;
  els.wechatIpResult.innerHTML = `
    <strong>${data.ok ? "白名单已通过" : data.ip ? `需要加入白名单的 IP：${escapeHtml(data.ip)}` : "未获得 IP"}</strong>
    <span>${escapeHtml(data.message || "")}</span>
    ${data.raw ? `<code>${escapeHtml(data.raw)}</code>` : ""}
  `;
}

async function checkWechatIp() {
  setBusy(els.checkWechatIp, true, "检测中...");
  try {
    const data = await requestJson("/api/writer/publish/ip-check");
    renderWechatIpResult(data);
    addLog(data.ip ? `微信返回的白名单 IP：${data.ip}` : data.message, data.ok ? "success" : data.ip ? "error" : "warn");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.checkWechatIp, false);
  }
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = label || "处理中...";
  } else if (button.dataset.originalText) {
    button.textContent = button.dataset.originalText;
  }
}

async function loadSession() {
  parseIds();
  if (!state.ids.length) {
    showToast("请先从知识库勾选知识文件");
    addLog("未收到知识文件 id，请返回知识库勾选。", "error");
    return;
  }
  const data = await requestJson(`/api/writer/session?ids=${state.ids.join(",")}`);
  state.files = data.items || [];
  renderFiles();
  addLog(`已加载 ${state.files.length} 个知识文件。`);
}

async function generateTopics() {
  setBusy(els.generateWriterTopics, true, "生成中...");
  try {
    addLog("开始基于所选知识文件生成选题建议。");
    const data = await requestJson("/api/writer/topics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: state.ids }),
    });
    state.topics = data.suggestions || [];
    state.selectedTopicIndex = state.topics.length ? 0 : -1;
    renderTopics();
    addLog(`生成 ${state.topics.length} 条选题建议。`, "success");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.generateWriterTopics, false);
  }
}

async function generateArticle() {
  const topic = selectedTopic();
  if (!topic) {
    showToast("请先选择一个选题");
    return;
  }
  setBusy(els.generateArticle, true, "写作中...");
  try {
    addLog(`开始生成文章：${topic.title}`);
    const data = await requestJson("/api/writer/article", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_ids: state.ids, topic }),
    });
    state.workspace = data.workspace;
    state.coverPrompt = data.cover_prompt || "";
    state.contentImagePrompts = data.content_image_prompts || [];
    setDigest(data.digest || "");
    els.articleTitle.value = data.title || topic.title || "";
    els.articleMarkdown.value = data.markdown || "";
    els.writerWorkspace.textContent = `工作目录：${data.workspace}`;
    updatePromptEditors();
    updatePublishChecklist();
    showWorkbench("article");
    showTab("markdown");
    addLog(`文章已生成并保存：${data.article_path}`, "success");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.generateArticle, false);
  }
}

async function suggestImages() {
  if (!state.workspace) {
    showToast("请先生成文章");
    return;
  }
  setBusy(els.suggestImages, true, "建议中...");
  try {
    addLog("开始生成配图建议，暂不调用图片 API。");
    const data = await requestJson("/api/writer/image-suggestions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        markdown: els.articleMarkdown.value,
        topic: selectedTopic(),
      }),
    });
    state.coverPrompt = data.cover_prompt || state.coverPrompt;
    state.contentImagePrompts = data.content_image_prompts || [];
    updatePromptEditors();
    addLog(data.rationale || "配图建议已生成，可修改后再确认生成图片。", "success");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.suggestImages, false);
  }
}

async function generateImages() {
  if (!state.workspace) {
    showToast("请先生成文章");
    return;
  }
  readPromptEditors();
  if (!state.coverPrompt && !state.contentImagePrompts.length) {
    showToast("请先填写或生成配图提示词");
    return;
  }
  setBusy(els.confirmGenerateImages, true, "生成中...");
  try {
    addLog("开始调用图片 API 生成封面和内容配图。");
    const data = await requestJson("/api/writer/images", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: state.workspace,
        cover_prompt: state.coverPrompt,
        content_image_prompts: state.contentImagePrompts,
      }),
    });
    state.generatedImages = data.items || [];
    renderImagePreviews();
    state.generatedImages.forEach((item) => addLog(`图片已生成：${item.path}`, "success"));
    if (!(data.items || []).length) addLog("没有需要生成的图片提示词。");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.confirmGenerateImages, false);
  }
}

async function formatArticle() {
  if (!state.workspace) {
    showToast("请先生成文章");
    return;
  }
  setBusy(els.formatArticle, true, "排版中...");
  try {
    addLog("开始执行微信公众号 HTML 美编排版。");
    const data = await requestJson("/api/writer/format", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: state.workspace, markdown: els.articleMarkdown.value, theme: "tech" }),
    });
    els.htmlPreview.srcdoc = data.html || "";
    state.htmlReady = true;
    updatePublishChecklist();
    showWorkbench("format");
    addLog(`${data.message || "HTML 已生成"}：${data.path}`, "success");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.formatArticle, false);
  }
}

async function publishDraft() {
  if (!state.workspace) {
    showToast("请先生成文章并美编排版");
    return;
  }
  const preflight = await runPublishPreflight();
  if (!preflight?.ok) {
    showToast("发布预检未通过");
    return;
  }
  setBusy(els.publishDraft, true, "发布中...");
  try {
    addLog("开始转入微信公众号草稿箱。");
    const data = await requestJson("/api/writer/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace: state.workspace,
        title: els.articleTitle.value.trim() || "未命名文章",
        author: els.articleAuthor.value.trim() || "Bobo",
        digest: readDigest(),
      }),
    });
    addLog(`草稿箱发布完成：${data.media_id || data.path || "已返回结果"}`, "success");
    showToast("已转入草稿箱");
  } catch (error) {
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.publishDraft, false);
  }
}

function appendRevision(role, text) {
  const item = document.createElement("article");
  item.className = role;
  item.textContent = text;
  els.revisionMessages.appendChild(item);
  els.revisionMessages.scrollTop = els.revisionMessages.scrollHeight;
}

async function reviseArticle(event) {
  event.preventDefault();
  const instruction = els.revisionInstruction.value.trim();
  if (!instruction) {
    showToast("请填写修改要求");
    return;
  }
  appendRevision("user", instruction);
  els.revisionInstruction.value = "";
  setBusy(els.reviseArticle, true, "修改中...");
  try {
    addLog(`开始修改文章：${instruction}`);
    const data = await requestJson("/api/writer/revise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_ids: state.ids,
        markdown: els.articleMarkdown.value,
        instruction,
        workspace: state.workspace,
      }),
    });
    state.workspace = data.workspace;
    if (data.cover_prompt) state.coverPrompt = data.cover_prompt;
    if ((data.content_image_prompts || []).length) state.contentImagePrompts = data.content_image_prompts;
    els.articleMarkdown.value = data.markdown || "";
    els.writerWorkspace.textContent = `工作目录：${data.workspace}`;
    updatePromptEditors();
    updatePublishChecklist();
    appendRevision("assistant", data.change_summary || "文章已按要求修改。");
    addLog(`修改稿已保存：${data.version_path}`, "success");
  } catch (error) {
    appendRevision("assistant", `修改失败：${error.message}`);
    addLog(error.message, "error");
    showToast(error.message);
  } finally {
    setBusy(els.reviseArticle, false);
  }
}

function showTab(name) {
  els.articleMarkdown.classList.toggle("hidden", name !== "markdown");
  els.markdownTab.classList.toggle("active", name === "markdown");
}

function activeImageApi() {
  return state.imageApi.items.find((item) => item.id === state.imageApi.activeId) || null;
}

function renderImageApiSettings() {
  els.imageApiSelect.innerHTML = "";
  if (!state.imageApi.items.length) {
    els.imageApiSelect.innerHTML = '<option value="">暂无配置</option>';
  } else {
    state.imageApi.items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${item.name} · ${item.model}${item.id === state.imageApi.activeId ? " · 当前" : ""}`;
      els.imageApiSelect.appendChild(option);
    });
  }
  els.imageApiTemplate.innerHTML = "";
  state.imageApi.templates.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.name;
    els.imageApiTemplate.appendChild(option);
  });
  const active = activeImageApi();
  els.imageApiStatus.textContent = active ? `当前：${active.name} / ${active.model}` : "未设置图片 API";
  if (active) fillImageApiForm(active);
  else fillImageApiTemplate(state.imageApi.templates[0]);
}

function fillImageApiTemplate(template) {
  if (!template) return;
  state.imageApi.editingId = null;
  els.imageApiName.value = template.name || "";
  els.imageApiProvider.value = template.provider || "compatible";
  els.imageApiBaseUrl.value = template.base_url || "";
  els.imageApiModel.value = template.model || "";
  els.imageApiKey.value = "";
  els.imageApiKey.placeholder = template.api_key_placeholder || "API Key";
  els.imageApiSize.value = template.size || "1024x1024";
  els.imageApiQuality.value = template.quality || "auto";
  els.imageApiTimeout.value = "120";
}

function fillImageApiForm(setting) {
  state.imageApi.editingId = setting.id;
  els.imageApiSelect.value = setting.id;
  els.imageApiName.value = setting.name || "";
  els.imageApiProvider.value = setting.provider || "compatible";
  els.imageApiBaseUrl.value = setting.base_url || "";
  els.imageApiModel.value = setting.model || "";
  els.imageApiKey.value = "";
  els.imageApiKey.placeholder = setting.api_key_masked ? `留空则保留 ${setting.api_key_masked}` : "API Key";
  els.imageApiSize.value = setting.size || "1024x1024";
  els.imageApiQuality.value = setting.quality || "auto";
  els.imageApiTimeout.value = setting.timeout || 120;
}

function imageApiPayload() {
  return {
    id: state.imageApi.editingId,
    name: els.imageApiName.value.trim(),
    provider: els.imageApiProvider.value,
    base_url: els.imageApiBaseUrl.value.trim(),
    model: els.imageApiModel.value.trim(),
    api_key: els.imageApiKey.value.trim(),
    size: els.imageApiSize.value.trim(),
    quality: els.imageApiQuality.value.trim(),
    timeout: Number(els.imageApiTimeout.value || 120),
    make_active: true,
  };
}

async function loadImageApiSettings() {
  pushImageApiLog("info", "正在加载图片 API 配置...");
  const data = await requestJson("/api/image-api-settings");
  state.imageApi.items = data.items || [];
  state.imageApi.templates = data.templates || [];
  state.imageApi.activeId = data.active_id || null;
  renderImageApiSettings();
  const active = activeImageApi();
  if (active) {
    pushImageApiLog("success", `已加载 ${state.imageApi.items.length} 个配置，当前为「${active.name}」。`);
  } else {
    pushImageApiLog("info", "尚未设置图片 API，已加载模板供改写。");
  }
}

function openImageApiSettings() {
  els.imageApiModal.classList.remove("hidden");
  pushImageApiLog("info", "已打开图片 API 设置面板。");
  loadImageApiSettings().catch((error) => {
    pushImageApiLog("error", error.message);
    showToast(error.message);
  });
}

function closeImageApiSettings() {
  els.imageApiModal.classList.add("hidden");
  pushImageApiLog("info", "已关闭图片 API 设置面板。");
}

async function saveImageApiSetting(event) {
  event.preventDefault();
  const payload = imageApiPayload();
  pushImageApiLog("info", `${payload.id ? "正在更新" : "正在保存"}图片 API 配置「${payload.name || "未命名配置"}」...`);
  const data = await requestJson("/api/image-api-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.imageApi.items = data.items || [];
  state.imageApi.activeId = data.active_id || data.item?.id || null;
  renderImageApiSettings();
  pushImageApiLog("success", `配置「${data.item?.name || payload.name}」已保存并启用，模型为 ${data.item?.model || payload.model}。`);
  showToast("图片 API 已保存并启用");
}

async function activateImageApiSetting() {
  const id = els.imageApiSelect.value;
  if (!id) {
    pushImageApiLog("error", "没有可启用的图片 API 配置。");
    return;
  }
  const selected = state.imageApi.items.find((item) => item.id === id);
  pushImageApiLog("info", `正在切换当前图片 API 到「${selected?.name || id}」...`);
  const data = await requestJson("/api/image-api-settings/active", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  state.imageApi.items = data.items || [];
  state.imageApi.activeId = data.active_id || id;
  renderImageApiSettings();
  pushImageApiLog("success", `当前图片 API 已切换为「${selected?.name || id}」。`);
  showToast("图片 API 已切换");
}

async function deleteImageApiSetting() {
  const id = els.imageApiSelect.value;
  if (!id) {
    pushImageApiLog("error", "没有可删除的图片 API 配置。");
    return;
  }
  const selected = state.imageApi.items.find((item) => item.id === id);
  pushImageApiLog("info", `正在删除图片 API 配置「${selected?.name || id}」...`);
  const data = await requestJson(`/api/image-api-settings/${encodeURIComponent(id)}`, { method: "DELETE" });
  state.imageApi.items = data.items || [];
  state.imageApi.activeId = data.active_id || null;
  renderImageApiSettings();
  pushImageApiLog("success", `配置「${selected?.name || id}」已删除。`);
  showToast("图片 API 已删除");
}

async function testImageApiSetting() {
  const payload = imageApiPayload();
  pushImageApiLog("info", `正在测试图片 API 配置：${payload.name || payload.model || "未命名配置"}...`);
  const data = await requestJson("/api/image-api-settings/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setting: payload }),
  });
  if (data.ok === "true") {
    pushImageApiLog("success", `${data.message || "配置字段完整"}\nEndpoint: ${data.endpoint || ""}`);
  } else {
    pushImageApiLog("error", data.error || "图片 API 配置不可用");
  }
  showToast(data.ok === "true" ? data.message || "图片 API 配置可用" : data.error || "图片 API 配置不可用");
}

els.generateWriterTopics.addEventListener("click", generateTopics);
els.generateArticle.addEventListener("click", generateArticle);
els.directoryWorkTab.addEventListener("click", () => {
  showWorkbench("directory");
  loadWorkspaces().catch((error) => {
    addLog(error.message, "error");
    showToast(error.message);
  });
});
els.articleWorkTab.addEventListener("click", () => showWorkbench("article"));
els.imageWorkTab.addEventListener("click", () => showWorkbench("image"));
els.formatWorkTab.addEventListener("click", () => showWorkbench("format"));
els.publishWorkTab.addEventListener("click", () => showWorkbench("publish"));
els.logWorkTab.addEventListener("click", () => showWorkbench("log"));
els.suggestImages.addEventListener("click", suggestImages);
els.confirmGenerateImages.addEventListener("click", generateImages);
els.refreshWorkspaces.addEventListener("click", () => loadWorkspaces().catch((error) => showToast(error.message)));
els.continueWorkspace.addEventListener("click", () => continueWorkspace().catch((error) => {
  addLog(error.message, "error");
  showToast(error.message);
}));
els.checkWechatIp.addEventListener("click", checkWechatIp);
els.preflightPublish.addEventListener("click", runPublishPreflight);
els.formatArticle.addEventListener("click", formatArticle);
els.publishDraft.addEventListener("click", publishDraft);
els.revisionForm.addEventListener("submit", reviseArticle);
els.markdownTab.addEventListener("click", () => showTab("markdown"));
els.articleDigest.addEventListener("input", readDigest);
els.truncateDigest.addEventListener("click", () => {
  setDigest(truncateUtf8(els.articleDigest.value, 120));
  showToast("摘要已截断到 120 字节以内");
});
els.openImageApiSettings.addEventListener("click", openImageApiSettings);
els.closeImageApiSettings.addEventListener("click", closeImageApiSettings);
els.imageApiModal.addEventListener("click", (event) => {
  if (event.target === els.imageApiModal) closeImageApiSettings();
});
els.imageApiSelect.addEventListener("change", (event) => {
  const item = state.imageApi.items.find((setting) => setting.id === event.target.value);
  if (item) {
    fillImageApiForm(item);
    pushImageApiLog("info", `已切换到配置「${item.name}」进行查看或编辑。`);
  }
});
els.imageApiTemplate.addEventListener("change", (event) => {
  const item = state.imageApi.templates.find((setting) => setting.id === event.target.value);
  fillImageApiTemplate(item);
  if (item) pushImageApiLog("info", `已套用模板「${item.name}」，可以继续改写。`);
});
els.newImageApiSetting.addEventListener("click", () => {
  fillImageApiTemplate(state.imageApi.templates[0]);
  pushImageApiLog("info", "已新建空白图片 API 配置。");
});
els.clearImageApiLogs.addEventListener("click", () => {
  state.imageApi.logs = [];
  renderImageApiLogs();
  pushImageApiLog("info", "运行日志已清空。");
});
els.imageApiForm.addEventListener("submit", (event) => saveImageApiSetting(event).catch((error) => {
  pushImageApiLog("error", error.message);
  showToast(error.message);
}));
els.activateImageApiSetting.addEventListener("click", () => activateImageApiSetting().catch((error) => {
  pushImageApiLog("error", error.message);
  showToast(error.message);
}));
els.deleteImageApiSetting.addEventListener("click", () => deleteImageApiSetting().catch((error) => {
  pushImageApiLog("error", error.message);
  showToast(error.message);
}));
els.testImageApi.addEventListener("click", () => testImageApiSetting().catch((error) => {
  pushImageApiLog("error", error.message);
  showToast(error.message);
}));

Promise.all([loadSession(), loadImageApiSettings()]).catch((error) => {
  addLog(error.message, "error");
  showToast(error.message);
});
renderImageApiLogs();
