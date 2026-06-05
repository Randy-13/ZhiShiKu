async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data?.error?.message || data?.detail || `Request failed: ${response.status}`);
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

function renderSettingsOverview(sections) {
  const list = document.querySelector("#settingsOverviewList");
  const meta = document.querySelector("#settingsOverviewMeta");
  const configured = sections.filter((section) => section.configured).length;
  const errored = sections.filter((section) => section.error).length;
  meta.textContent = errored ? `${configured}/${sections.length} 已配置，${errored} 项需检查` : `${configured}/${sections.length} 已配置`;
  list.innerHTML = sections
    .map(
      (section) => `
        <article class="settings-status-card ${section.configured ? "configured" : ""}">
          <div>
            <strong>${escapeHtml(section.label)}</strong>
            <span>${escapeHtml(section.activeName || "未配置")}</span>
          </div>
          <small>${section.error ? `需检查：${escapeHtml(section.error)}` : `${section.itemCount} 个配置`}</small>
        </article>
      `
    )
    .join("");
}

requestJson("/api/v2/settings/overview")
  .then((payload) => renderSettingsOverview(payload.data.sections || []))
  .catch((error) => {
    document.querySelector("#settingsOverviewMeta").textContent = "加载失败";
    document.querySelector("#settingsOverviewList").innerHTML = `<div class="queue empty">${escapeHtml(error.message)}</div>`;
  });
