const zh = {
  requestFailed: "\u8bf7\u6c42\u5931\u8d25",
  local: "\u672c\u5730",
  uploading: "\u4e0a\u4f20\u4e2d",
  uploaded: "\u5df2\u4e0a\u4f20",
  resolving: "\u89e3\u6790\u4e2d",
  resolved: "\u5df2\u89e3\u6790",
  needsLocalFile: "\u9700\u4e0a\u4f20\u672c\u5730\u6587\u4ef6",
  transcribing: "\u63d0\u53d6\u4e2d",
  transcribed: "\u5df2\u63d0\u53d6\u5b57\u5e55",
  processing: "\u751f\u6210\u4e2d",
  ready: "\u5df2\u751f\u6210",
  error: "\u5931\u8d25",
};

const state = {
  queue: [],
  transcripts: [],
  selectedTranscripts: new Set(),
  plan: null,
  knowledge: [],
  asrSettings: null,
};

const els = {
  openAsrSettings: document.querySelector("#openAsrSettings"),
  openHome: document.querySelector("#openHome"),
  refreshKnowledge: document.querySelector("#refreshKnowledge"),
  urlInput: document.querySelector("#urlInput"),
  resolveUrls: document.querySelector("#resolveUrls"),
  loadExamples: document.querySelector("#loadExamples"),
  dropzone: document.querySelector("#dropzone"),
  mediaInput: document.querySelector("#mediaInput"),
  chooseFiles: document.querySelector("#chooseFiles"),
  transcribeMedia: document.querySelector("#transcribeMedia"),
  planMedia: document.querySelector("#planMedia"),
  generateKnowledge: document.querySelector("#generateKnowledge"),
  deleteTranscripts: document.querySelector("#deleteTranscripts"),
  queue: document.querySelector("#queue"),
  queueCount: document.querySelector("#queueCount"),
  transcriptCount: document.querySelector("#transcriptCount"),
  transcriptList: document.querySelector("#transcriptList"),
  planPanel: document.querySelector("#planPanel"),
  planMeta: document.querySelector("#planMeta"),
  planList: document.querySelector("#planList"),
  transcriptModal: document.querySelector("#transcriptModal"),
  transcriptPreviewTitle: document.querySelector("#transcriptPreviewTitle"),
  transcriptFullPreview: document.querySelector("#transcriptFullPreview"),
  closeTranscriptModal: document.querySelector("#closeTranscriptModal"),
  asrSettingsModal: document.querySelector("#asrSettingsModal"),
  closeAsrSettings: document.querySelector("#closeAsrSettings"),
  asrSettingsForm: document.querySelector("#asrSettingsForm"),
  asrSettingsStatus: document.querySelector("#asrSettingsStatus"),
  asrProvider: document.querySelector("#asrProvider"),
  asrBaseUrl: document.querySelector("#asrBaseUrl"),
  asrModel: document.querySelector("#asrModel"),
  asrApiKey: document.querySelector("#asrApiKey"),
  asrTimeout: document.querySelector("#asrTimeout"),
  testAsrSettings: document.querySelector("#testAsrSettings"),
  saveAsrSettings: document.querySelector("#saveAsrSettings"),
  dependencyStatus: document.querySelector("#dependencyStatus"),
  knowledgeCount: document.querySelector("#knowledgeCount"),
  knowledgeList: document.querySelector("#knowledgeList"),
  toast: document.querySelector("#toast"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 2800);
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
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    if (detail && typeof detail === "object") detail = JSON.stringify(detail);
    throw new Error(detail || `${zh.requestFailed}: ${response.status}`);
  }
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

function statusLabel(status) {
  const labels = {
    local: zh.local,
    uploading: zh.uploading,
    uploaded: zh.uploaded,
    resolving: zh.resolving,
    resolved: zh.resolved,
    needs_local_file: zh.needsLocalFile,
    transcribing: zh.transcribing,
    transcribed: zh.transcribed,
    processing: zh.processing,
    ready: zh.ready,
    error: zh.error,
  };
  return labels[status] || status || "\u672a\u77e5";
}

function fileKey(file) {
  return `${file.name}-${file.size}-${file.lastModified || 0}`;
}

function addLocalFiles(files) {
  const existing = new Set(state.queue.map((item) => item.key).filter(Boolean));
  [...files].forEach((file) => {
    const key = fileKey(file);
    if (existing.has(key)) return;
    state.queue.push({
      key,
      file,
      original_name: file.name,
      title: file.name,
      platform: "local",
      status: "local",
      content_type: file.type,
      size: file.size,
      uploading: false,
    });
  });
  renderQueue();
  uploadPendingFiles();
}

async function uploadPendingFiles() {
  const pending = state.queue.filter((item) => item.file && !item.id && !item.uploading);
  if (!pending.length) return;
  pending.forEach((item) => {
    item.uploading = true;
    item.status = "uploading";
  });
  renderQueue();
  try {
    const form = new FormData();
    pending.forEach((item) => form.append("files", item.file, item.original_name));
    const data = await requestJson("/api/media/upload", { method: "POST", body: form });
    data.items.forEach((serverItem, index) => {
      Object.assign(pending[index], serverItem, { file: null, uploading: false });
    });
    renderQueue();
    await loadTranscripts();
    showToast(`\u5df2\u4e0a\u4f20 ${pending.length} \u4e2a\u6587\u4ef6`);
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

async function resolveUrls() {
  const urls = els.urlInput.value.split(/\s+/).map((item) => item.trim()).filter(Boolean);
  if (!urls.length) {
    showToast("\u8bf7\u5148\u7c98\u8d34\u94fe\u63a5");
    return;
  }
  els.resolveUrls.disabled = true;
  try {
    for (const url of urls) {
      const placeholder = { title: url, source_url: url, platform: "url", status: "resolving" };
      state.queue.unshift(placeholder);
      renderQueue();
      try {
        const data = await requestJson("/api/media/resolve-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        Object.assign(placeholder, data.item);
      } catch (error) {
        Object.assign(placeholder, { status: "error", error_message: error.message });
      }
      renderQueue();
    }
    showToast("\u94fe\u63a5\u89e3\u6790\u5b8c\u6210");
  } finally {
    els.resolveUrls.disabled = false;
  }
}

async function transcribeMedia() {
  await uploadPendingFiles();
  const targets = state.queue.filter((item) => item.id && item.transcript_kind === "none" && !["error", "needs_local_file"].includes(item.status));
  if (!targets.length) {
    showToast("\u961f\u5217\u4e2d\u6ca1\u6709\u5f85\u63d0\u53d6\u5b57\u5e55\u7684\u89c6\u9891");
    return;
  }
  els.transcribeMedia.disabled = true;
  let successCount = 0;
  try {
    for (const item of targets) {
      item.status = "transcribing";
      item.error_message = null;
      renderQueue();
      const data = await requestJson("/api/media/transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ media_ids: [item.id] }),
      });
      const result = (data.items || [])[0];
      if (result.ok) {
        successCount += 1;
        state.queue = state.queue.filter((queued) => queued !== item);
        loadDependencies().catch(() => {});
      } else {
        Object.assign(item, { status: "error", error_message: result.error });
      }
      renderQueue();
      await loadTranscripts();
    }
    showToast(`\u5b57\u5e55\u63d0\u53d6\u5b8c\u6210\uff1a${successCount}/${targets.length}`);
  } catch (error) {
    renderQueue();
    showToast(error.message);
  } finally {
    els.transcribeMedia.disabled = false;
  }
}

async function loadTranscripts() {
  const data = await requestJson("/api/media/transcripts");
  state.transcripts = data.items || [];
  const available = new Set(state.transcripts.map((item) => item.id));
  state.selectedTranscripts = new Set([...state.selectedTranscripts].filter((id) => available.has(id)));
  renderTranscripts();
}

async function openTranscriptPreview(mediaId) {
  try {
    const data = await requestJson(`/api/media/${mediaId}/transcript`);
    const item = data.item || {};
    els.transcriptPreviewTitle.textContent = item.title || item.original_name || "\u5b57\u5e55\u6587\u4ef6";
    els.transcriptFullPreview.textContent = data.content || "";
    els.transcriptModal.classList.remove("hidden");
  } catch (error) {
    showToast(error.message);
  }
}

function closeTranscriptPreview() {
  els.transcriptModal.classList.add("hidden");
}

function fillAsrSettingsForm(item = {}) {
  els.asrProvider.value = item.provider || "dashscope";
  els.asrBaseUrl.value = item.base_url || "https://dashscope.aliyuncs.com/api/v1";
  els.asrModel.value = item.model || "paraformer-v2";
  els.asrApiKey.value = "";
  els.asrTimeout.value = item.timeout || 300;
  const keyText = item.api_key_masked ? `Key: ${item.api_key_masked}` : "\u672a\u914d\u7f6e Key";
  els.asrSettingsStatus.textContent = `${item.configured ? "\u5df2\u914d\u7f6e" : "\u672a\u914d\u7f6e"} · ${keyText}`;
}

async function loadAsrSettings() {
  const data = await requestJson("/api/asr-settings");
  state.asrSettings = data.item || {};
  fillAsrSettingsForm(state.asrSettings);
}

function collectAsrPayload() {
  let provider = els.asrProvider.value;
  const baseUrl = els.asrBaseUrl.value.trim();
  let model = els.asrModel.value.trim();
  if (baseUrl.includes("dashscope.aliyuncs.com") || model.toLowerCase().includes("fun-asr")) {
    provider = "dashscope";
    els.asrProvider.value = "dashscope";
  }
  if (provider === "dashscope" && model.toLowerCase() === "fun-asr") {
    model = "paraformer-v2";
    els.asrModel.value = model;
  }
  return {
    provider,
    base_url: baseUrl,
    model,
    api_key: els.asrApiKey.value.trim(),
    timeout: Number(els.asrTimeout.value || 300),
  };
}

function openAsrSettings() {
  loadAsrSettings().catch((error) => showToast(error.message));
  els.asrSettingsModal.classList.remove("hidden");
}

function closeAsrSettings() {
  els.asrSettingsModal.classList.add("hidden");
}

async function saveAsrSettings(event) {
  event.preventDefault();
  els.saveAsrSettings.disabled = true;
  try {
    const data = await requestJson("/api/asr-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectAsrPayload()),
    });
    state.asrSettings = data.item || {};
    fillAsrSettingsForm(state.asrSettings);
    await loadDependencies();
    showToast("ASR \u8bbe\u7f6e\u5df2\u4fdd\u5b58");
  } catch (error) {
    showToast(error.message);
  } finally {
    els.saveAsrSettings.disabled = false;
  }
}

async function testAsrSettings() {
  els.testAsrSettings.disabled = true;
  try {
    const data = await requestJson("/api/asr-settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectAsrPayload()),
    });
    showToast(data.message || "ASR \u914d\u7f6e\u53ef\u7528");
  } catch (error) {
    showToast(error.message);
  } finally {
    els.testAsrSettings.disabled = false;
  }
}

async function deleteSelectedTranscripts() {
  const ids = [...state.selectedTranscripts];
  if (!ids.length) {
    showToast("\u8bf7\u5148\u52fe\u9009\u8981\u5220\u9664\u7684\u5b57\u5e55\u6587\u4ef6");
    return;
  }
  els.deleteTranscripts.disabled = true;
  try {
    const data = await requestJson("/api/media/delete-transcripts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_ids: ids }),
    });
    state.selectedTranscripts.clear();
    state.transcripts = data.items || [];
    state.plan = null;
    renderTranscripts();
    renderPlan();
    showToast(`\u5df2\u5220\u9664 ${(data.deleted || []).length} \u4e2a\u5b57\u5e55\u6587\u4ef6`);
  } catch (error) {
    showToast(error.message);
  } finally {
    els.deleteTranscripts.disabled = false;
  }
}

async function planMedia() {
  const ids = [...state.selectedTranscripts];
  if (!ids.length) {
    showToast("\u8bf7\u5148\u52fe\u9009\u5b57\u5e55\u6587\u4ef6");
    return;
  }
  els.planMedia.disabled = true;
  try {
    const data = await requestJson("/api/media/plan-ranges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_ids: ids }),
    });
    state.plan = data.plan || { segments: [] };
    renderPlan();
    showToast(`\u5df2\u751f\u6210 ${state.plan.segments.length} \u4e2a\u89c4\u5212\u6bb5`);
  } catch (error) {
    showToast(error.message);
  } finally {
    els.planMedia.disabled = false;
  }
}

async function generateKnowledge() {
  const segments = (state.plan?.segments || []).filter((segment) => segment.selected !== false);
  if (!segments.length) {
    showToast("\u8bf7\u5148\u751f\u6210\u89c4\u5212\u5e76\u52fe\u9009\u81f3\u5c11\u4e00\u4e2a\u6587\u672c\u6bb5");
    return;
  }
  els.generateKnowledge.disabled = true;
  try {
    const data = await requestJson("/api/knowledge/generate-from-media-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments }),
    });
    await loadKnowledge();
    showToast(`\u5df2\u751f\u6210 ${data.generated || 0} \u4e2a\u77e5\u8bc6\u6587\u4ef6`);
  } catch (error) {
    showToast(error.message);
  } finally {
    els.generateKnowledge.disabled = false;
  }
}

function renderQueue() {
  els.queueCount.textContent = `${state.queue.length} \u4e2a`;
  if (!state.queue.length) {
    els.queue.className = "queue empty";
    els.queue.textContent = "\u6682\u65e0\u5a92\u4f53";
    return;
  }
  els.queue.className = "queue";
  els.queue.innerHTML = "";
  state.queue.forEach((item) => {
    const row = document.createElement("article");
    row.className = "media-item";
    const source = item.canonical_url || item.source_url || item.file_path || item.original_name || "";
    const duration = item.duration_seconds ? `${Math.round(item.duration_seconds)} \u79d2` : "\u65f6\u957f\u672a\u77e5";
    row.innerHTML = `
      <div class="platform">${escapeHtml(item.platform || "local")}</div>
      <div>
        <div class="title">${escapeHtml(item.title || item.original_name || "\u672a\u547d\u540d\u5a92\u4f53")}</div>
        <div class="meta">${escapeHtml(source)}</div>
        <div class="meta">${escapeHtml(duration)} · \u5b57\u5e55\uff1a${escapeHtml(item.transcript_kind || "none")}</div>
        ${item.error_message ? `<div class="meta error-text">${escapeHtml(item.error_message)}</div>` : ""}
        <span class="status ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
      </div>
    `;
    els.queue.appendChild(row);
  });
}

function renderTranscripts() {
  els.transcriptCount.textContent = `${state.transcripts.length} \u4e2a`;
  if (!state.transcripts.length) {
    els.transcriptList.className = "transcript-list empty";
    els.transcriptList.textContent = "\u6682\u65e0\u5b57\u5e55\u6587\u4ef6";
    return;
  }
  els.transcriptList.className = "transcript-list";
  els.transcriptList.innerHTML = "";
  state.transcripts.forEach((item) => {
    const card = document.createElement("article");
    card.className = "transcript-item";
    const checked = state.selectedTranscripts.has(item.id) ? "checked" : "";
    card.innerHTML = `
      <input type="checkbox" ${checked} />
      <div>
        <div class="title">${escapeHtml(item.title || item.original_name || "\u672a\u547d\u540d\u5b57\u5e55")}</div>
        <div class="meta">${escapeHtml(item.platform || "local")} · ${escapeHtml(item.transcript_kind || "")}</div>
        <div class="meta">${escapeHtml(item.transcript_path || "")}</div>
      </div>
    `;
    const checkbox = card.querySelector("input");
    checkbox.addEventListener("change", (event) => {
      if (event.target.checked) state.selectedTranscripts.add(item.id);
      else state.selectedTranscripts.delete(item.id);
    });
    card.addEventListener("dblclick", (event) => {
      if (event.target.closest("input")) return;
      openTranscriptPreview(item.id);
    });
    els.transcriptList.appendChild(card);
  });
}

function renderPlan() {
  const segments = state.plan?.segments || [];
  els.planMeta.textContent = segments.length ? `${segments.length} \u4e2a\u6587\u672c\u6bb5` : "\u672a\u751f\u6210\u89c4\u5212";
  if (!segments.length) {
    els.planList.className = "plan-list empty";
    els.planList.textContent = "\u8bf7\u5148\u52fe\u9009\u5b57\u5e55\u5e76\u751f\u6210\u89c4\u5212";
    return;
  }
  els.planList.className = "plan-list";
  els.planList.innerHTML = "";
  segments.forEach((segment, index) => {
    const card = document.createElement("label");
    card.className = "plan-card";
    const checked = segment.selected !== false ? "checked" : "";
    card.innerHTML = `
      <input type="checkbox" data-index="${index}" ${checked} />
      <div>
        <div class="title">${escapeHtml(segment.title)}</div>
        <div class="meta">${escapeHtml(segment.time_ranges || "")}</div>
        <div class="meta">${escapeHtml(segment.theme || segment.reason || "")}</div>
      </div>
    `;
    card.querySelector("input").addEventListener("change", (event) => {
      segment.selected = event.target.checked;
    });
    els.planList.appendChild(card);
  });
}

async function loadKnowledge() {
  const data = await requestJson("/api/knowledge");
  state.knowledge = data.items || [];
  renderKnowledge();
}

function renderKnowledge() {
  const items = state.knowledge.slice(0, 12);
  els.knowledgeCount.textContent = `${state.knowledge.length} \u4e2a`;
  if (!items.length) {
    els.knowledgeList.className = "knowledge-list empty";
    els.knowledgeList.textContent = "\u6682\u65e0\u77e5\u8bc6\u6587\u4ef6";
    return;
  }
  els.knowledgeList.className = "knowledge-list";
  els.knowledgeList.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "knowledge-item compact";
    row.innerHTML = `
      <div>
        <div class="title">${escapeHtml(item.title || "\u672a\u547d\u540d\u77e5\u8bc6")}</div>
        <div class="meta">${escapeHtml(item.created_at || "")}</div>
        <div class="meta">${escapeHtml(item.markdown_path || "")}</div>
      </div>
    `;
    els.knowledgeList.appendChild(row);
  });
}

async function loadDependencies() {
  const data = await requestJson("/api/media/dependencies");
  els.dependencyStatus.innerHTML = "";
  Object.entries(data).forEach(([name, info]) => {
    const row = document.createElement("article");
    const stateClass = info.available ? "ok" : info.configured ? "warning" : "missing";
    const stateText = info.available ? "\u6b63\u5e38" : info.configured ? "\u5f85\u68c0\u6d4b" : "\u9700\u914d\u7f6e";
    const label = info.label || name;
    row.innerHTML = `
      <strong>${escapeHtml(label)}\uff1a${stateText}</strong>
      <div class="meta">${escapeHtml(info.purpose || "")}</div>
      ${info.detail ? `<div class="meta">${escapeHtml(info.detail)}</div>` : ""}
      ${info.auth ? `<div class="meta">auth: ${escapeHtml(info.auth)}</div>` : ""}
      ${info.model ? `<div class="meta">model: ${escapeHtml(info.model)}</div>` : ""}
      ${info.message ? `<div class="meta">${escapeHtml(info.message)}</div>` : ""}
    `;
    row.className = `dependency-item ${stateClass}`;
    els.dependencyStatus.appendChild(row);
  });
}

els.openAsrSettings.addEventListener("click", openAsrSettings);
els.openHome.addEventListener("click", () => {
  window.location.href = "/";
});
els.refreshKnowledge.addEventListener("click", () => loadKnowledge().catch((error) => showToast(error.message)));
els.resolveUrls.addEventListener("click", resolveUrls);
els.loadExamples.addEventListener("click", () => {
  els.urlInput.value = [
    "https://v.douyin.com/zXGKv6QWCM4/",
    "https://www.bilibili.com/video/BV1A7V36BEc9?t=25.8",
  ].join("\n");
});
els.chooseFiles.addEventListener("click", () => els.mediaInput.click());
els.mediaInput.addEventListener("change", (event) => {
  addLocalFiles(event.target.files);
  event.target.value = "";
});
els.transcribeMedia.addEventListener("click", transcribeMedia);
els.planMedia.addEventListener("click", planMedia);
els.generateKnowledge.addEventListener("click", generateKnowledge);
els.deleteTranscripts.addEventListener("click", deleteSelectedTranscripts);
els.closeTranscriptModal.addEventListener("click", closeTranscriptPreview);
els.closeAsrSettings.addEventListener("click", closeAsrSettings);
els.asrSettingsForm.addEventListener("submit", saveAsrSettings);
els.testAsrSettings.addEventListener("click", testAsrSettings);
els.transcriptModal.addEventListener("click", (event) => {
  if (event.target === els.transcriptModal) closeTranscriptPreview();
});
els.asrSettingsModal.addEventListener("click", (event) => {
  if (event.target === els.asrSettingsModal) closeAsrSettings();
});

["dragenter", "dragover"].forEach((name) => {
  els.dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("active");
  });
});
["dragleave", "drop"].forEach((name) => {
  els.dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("active");
  });
});
els.dropzone.addEventListener("drop", (event) => addLocalFiles(event.dataTransfer.files));
els.dropzone.addEventListener("click", () => els.mediaInput.click());

renderQueue();
renderTranscripts();
renderPlan();
loadDependencies().catch((error) => {
  els.dependencyStatus.textContent = error.message;
});
loadAsrSettings().catch((error) => showToast(error.message));
loadTranscripts().catch((error) => showToast(error.message));
loadKnowledge().catch((error) => showToast(error.message));
