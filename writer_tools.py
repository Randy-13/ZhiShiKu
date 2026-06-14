from __future__ import annotations

import base64
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
from subprocess import TimeoutExpired
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import api_settings
import deepseek_client
import image_api_settings
import storage


WRITER_DIR = storage.WRITER_DIR
_LAST_STORAGE_WRITER_DIR = storage.WRITER_DIR
FORMATTER_SCRIPT = Path(r"C:\Users\Bo Yang\.codex\skills\wechat-article-formatter\scripts\markdown_to_html.py")
CODE_BLOCK_SCRIPT = Path(r"C:\Users\Bo Yang\.codex\skills\wechat-article-formatter\scripts\convert-code-blocks.py")
PUBLISHER_SCRIPT = Path(r"C:\Users\Bo Yang\.codex\skills\wechat-draft-publisher\publisher.py")
WECHAT_CONFIG_FILE = Path(os.path.expanduser("~/.wechat-publisher/config.json"))
WECHAT_TOKEN_CACHE_FILE = Path(os.path.expanduser("~/.wechat-publisher/token_cache.json"))
WECHAT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
WECHAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_PROMPT_RETRY_MAX_CHARS = 1200
EMPHASIS_PATTERNS = (
    "关键变化",
    "关键变量",
    "产业拐点",
    "规模化",
    "可复制",
    "可靠性",
    "重新定价",
    "体验开始成熟",
    "数据飞轮",
    "共识开始前移",
)

DEFAULT_WRITING_STRATEGY = """微信公众号文章默认写文策略
- 面向普通读者，用一个清晰的问题开篇，不写成研报摘要。
- 选题必须来自已导入的原文库、重点库或视角库文件，核心判断要能回到来源材料。
- 结构遵循：问题提出 -> 关键事实 -> 变量拆解 -> 影响判断 -> 读者行动建议。
- 保持有观点、有节奏、短句优先，避免堆概念、堆引用、堆行业黑话。
- 标题要具体、有冲突或变化感，但不能夸大材料没有支撑的结论。
- 正文保留 Markdown，第一张图为封面图占位：![封面图](cover.png)。
"""

DEFAULT_DESIGN_STRATEGY = """微信公众号文章默认美编策略
- 生成适合公众号粘贴发布的 HTML，层级清楚，阅读节奏舒展。
- 保留标题、摘要、正文小标题、重点句和图片，不增加无来源的新内容。
- 重点句可以适度强调，但不要把全文做成花哨海报。
- 图片使用项目内生成的本地路径，由发布预检再转换为公众号可用资源。
- 整体风格偏科技/财经：克制、清晰、专业，适合长文阅读。
"""

PM_RESEARCH_DESIGN_STRATEGY = """PM 研究型美编策略
- 本策略只参考 pm-search、pm-fulltext、pm-paper-detail、pm-export 等 PM skills 的资料组织方式，不把它们当作 HTML formatter。
- 页面目标是把文章整理成可复盘的研究笔记：结论先行、证据链清晰、来源可追踪、适合反复查阅。
- 结构建议：核心结论 -> 关键证据 -> 对比表格/变量拆解 -> 风险与反例 -> 后续检索问题 -> 来源附录。
- 版式保持工作台风格：信息密度高但分区清楚，使用小标题、编号列表、引用块、表格和少量强调句，不做营销海报式装饰。
- 对来自 PM 检索或论文详情的内容，保留题名、作者/机构、时间、链接或本地引用路径；没有来源的判断必须标成推断。
- 图片只作为解释结构和关系的辅助，不替代证据；不要让配图压过结论和来源。
- 导出时优先保证 Markdown/HTML 可复制、可二次编辑、可追溯，而不是追求视觉复杂度。
"""


def wechat_config_file() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())) / ".wechat-publisher" / "config.json"


def wechat_token_cache_file() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())) / ".wechat-publisher" / "token_cache.json"


def wechat_config() -> dict[str, str]:
    config_file = wechat_config_file()
    if not config_file.exists():
        return {}
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "appid": (config.get("appid") or "").strip(),
        "appsecret": (config.get("appsecret") or "").strip(),
    }


def clear_wechat_token_cache(reason: str = "") -> bool:
    token_file = wechat_token_cache_file()
    if token_file.exists():
        token_file.unlink()
        return True
    return False


def invalidate_stale_wechat_token_cache() -> bool:
    token_file = wechat_token_cache_file()
    config = wechat_config()
    if not token_file.exists() or not config.get("appid"):
        return False
    try:
        cache = json.loads(token_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        token_file.unlink()
        return True
    cache_appid = cache.get("appid")
    if cache_appid and cache_appid == config["appid"]:
        return False
    token_file.unlink()
    return True


def safe_slug(value: str, fallback: str = "article") -> str:
    text = (value or "").strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|#\r\n\t]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return text[:48] or fallback


def writer_dir() -> Path:
    global WRITER_DIR, _LAST_STORAGE_WRITER_DIR
    if WRITER_DIR == _LAST_STORAGE_WRITER_DIR:
        WRITER_DIR = storage.WRITER_DIR
    _LAST_STORAGE_WRITER_DIR = storage.WRITER_DIR
    return WRITER_DIR


def dated_workspace(topic: str) -> Path:
    root = writer_dir() / datetime.now().strftime("%Y-%m-%d") / safe_slug(topic)
    root.mkdir(parents=True, exist_ok=True)
    return root


def projects_dir() -> Path:
    return writer_dir() / "projects"


def create_project(
    name: str,
    project_type: str = "article",
    description: str = "",
    writing_strategy: str = "",
    design_strategy: str = "",
    owner_user_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    clean_type = project_type if project_type in {"article", "image_text", "short_video", "long_video"} else "article"
    title = (name or "").strip() or "未命名创作项目"
    project_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{safe_slug(title, 'project')}-{uuid4().hex[:6]}"
    workspace = projects_dir() / project_id
    workspace.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    project = {
        "id": project_id,
        "name": title,
        "type": clean_type,
        "description": description.strip(),
        "writing_strategy": (writing_strategy or DEFAULT_WRITING_STRATEGY).strip(),
        "design_strategy": (design_strategy or DEFAULT_DESIGN_STRATEGY).strip(),
        "status": "active",
        "workspace": _relative(workspace),
        "created_at": now,
        "updated_at": now,
        "library_files": [],
        "topic": None,
        "owner_user_id": owner_user_id or "",
        "workspace_id": workspace_id or "",
    }
    _write_project(project)
    return project


def list_projects(owner_user_id: str | None = None, include_ownerless: bool = True) -> list[dict[str, Any]]:
    if not projects_dir().exists():
        return []
    projects = []
    for project_file in projects_dir().glob("*/project.json"):
        try:
            project = json.loads(project_file.read_text(encoding="utf-8"))
            owner = str(project.get("owner_user_id") or "")
            if owner_user_id and owner != owner_user_id and not (include_ownerless and not owner):
                continue
            projects.append(project)
        except json.JSONDecodeError:
            continue
    return sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True)


def load_project(project_id: str, owner_user_id: str | None = None, include_ownerless: bool = True) -> dict[str, Any]:
    project_file = _project_file(project_id)
    if not project_file.exists():
        raise FileNotFoundError(f"创作项目不存在：{project_id}")
    project = json.loads(project_file.read_text(encoding="utf-8"))
    owner = str(project.get("owner_user_id") or "")
    if owner_user_id and owner != owner_user_id and not (include_ownerless and not owner):
        raise FileNotFoundError(f"创作项目不存在：{project_id}")
    workspace = resolve_project_workspace(project_id)
    project["workspace"] = _relative(workspace)
    project["article_markdown"] = (workspace / "article.md").read_text(encoding="utf-8") if (workspace / "article.md").exists() else ""
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    project["html"] = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    project["html_path"] = _relative(html_path) if html_path.exists() else ""
    return project


def update_project(project_id: str, **updates: Any) -> dict[str, Any]:
    project = load_project(project_id)
    if "type" in updates and updates["type"] not in {"article", "image_text", "short_video", "long_video"}:
        updates["type"] = "article"
    project.update({key: value for key, value in updates.items() if value is not None})
    project["updated_at"] = datetime.now().isoformat(timespec="seconds")
    project.pop("article_markdown", None)
    _write_project(project)
    return load_project(project_id)


def set_project_library_files(project_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    normalized = []
    for item in files:
        library = str(item.get("library") or "").strip()
        markdown_path = str(item.get("markdown_path") or "").strip()
        if not library or not markdown_path or markdown_path in seen:
            continue
        seen.add(markdown_path)
        normalized.append(
            {
                "library": library,
                "knowledge_id": item.get("knowledge_id"),
                "markdown_path": markdown_path,
                "title": str(item.get("title") or Path(markdown_path).stem),
            }
        )
    return update_project(project_id, library_files=normalized)


def resolve_project_workspace(project_id: str) -> Path:
    if not project_id or "/" in project_id or "\\" in project_id or ".." in project_id:
        raise ValueError("项目 ID 不合法")
    workspace = (projects_dir() / project_id).resolve()
    root = projects_dir().resolve()
    if root not in workspace.parents and workspace != root:
        raise ValueError("项目目录不在 writer/projects 中")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _project_file(project_id: str) -> Path:
    return resolve_project_workspace(project_id) / "project.json"


def _write_project(project: dict[str, Any]) -> None:
    project_id = str(project["id"])
    workspace = resolve_project_workspace(project_id)
    project["workspace"] = _relative(workspace)
    (workspace / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_workspace(path: str | None) -> Path:
    if not path:
        raise ValueError("缺少写文工作目录")
    workspace = Path(path)
    if not workspace.is_absolute():
        workspace = storage.ROOT / workspace
    workspace = workspace.resolve()
    writer_root = writer_dir().resolve()
    if writer_root not in workspace.parents and workspace != writer_root:
        raise ValueError("写文工作目录不在 writer/ 下")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def selected_markdowns(ids: list[int]) -> list[dict[str, Any]]:
    results = []
    for item, content in storage.read_markdown_for_ids(ids):
        path = storage.resolve_root_path(item.get("markdown_path"))
        results.append(
            {
                "item": item,
                "filename": path.name if path else f"knowledge-{item['id']}.md",
                "content": content,
            }
        )
    return results


def write_article(workspace: Path, markdown: str, filename: str = "article.md") -> Path:
    path = workspace / filename
    path.write_text(markdown or "", encoding="utf-8")
    return path


def _relative(path: Path) -> str:
    return storage.storage_relative(path)


def article_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def workspace_status(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    article_path = workspace / "article.md"
    cover_path = workspace / "cover.png"
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    publish_path = workspace / "publish_result.json"
    markdown = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
    publish_result: dict[str, Any] | None = None
    if publish_path.exists():
        try:
            publish_result = json.loads(publish_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            publish_result = {"raw": publish_path.read_text(encoding="utf-8", errors="replace")}
    published = bool(
        publish_result
        and (
            publish_result.get("media_id")
            or publish_result.get("returncode") == 0
        )
    )
    image_paths = []
    for pattern in ("cover.*", "content-*.*"):
        for image_path in sorted(workspace.glob(pattern)):
            if image_path.is_file() and image_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                image_paths.append(image_path)
    return {
        "workspace": _relative(workspace),
        "name": workspace.name,
        "date": workspace.parent.name,
        "title": article_title(markdown, workspace.name),
        "updated_at": datetime.fromtimestamp(workspace.stat().st_mtime).isoformat(timespec="seconds"),
        "status": "published" if published else "unpublished",
        "published": published,
        "checks": {
            "markdown": article_path.exists(),
            "cover": cover_path.exists(),
            "html": html_path.exists(),
            "published": published,
        },
        "paths": {
            "article": _relative(article_path) if article_path.exists() else None,
            "cover": _relative(cover_path) if cover_path.exists() else None,
            "html": _relative(html_path) if html_path.exists() else None,
            "publish_result": _relative(publish_path) if publish_path.exists() else None,
            "images": [_relative(path) for path in image_paths],
        },
    }


def list_workspaces() -> list[dict[str, Any]]:
    root = writer_dir()
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for date_dir in sorted(root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for workspace in sorted(date_dir.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
            if workspace.is_dir():
                items.append(workspace_status(workspace))
    return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)


def load_workspace(workspace: Path) -> dict[str, Any]:
    status = workspace_status(workspace)
    paths = status["paths"]
    article_markdown = ""
    html_content = ""
    publish_result = None
    article_path = paths.get("article")
    html_path = paths.get("html")
    publish_path = paths.get("publish_result")
    if article_path:
        article_markdown = resolve_writer_file(article_path).read_text(encoding="utf-8")
    if html_path:
        html_content = resolve_writer_file(html_path).read_text(encoding="utf-8")
    if publish_path:
        try:
            publish_result = json.loads(resolve_writer_file(publish_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            publish_result = None
    return {
        **status,
        "article_markdown": article_markdown,
        "html": html_content,
        "publish_result": publish_result,
        "images": [
            {"path": path, "name": Path(path).name}
            for path in paths.get("images", [])
        ],
    }


def utf8_len(value: str | None) -> int:
    return len((value or "").encode("utf-8"))


def truncate_utf8(value: str | None, max_bytes: int) -> str:
    text = value or ""
    if utf8_len(text) <= max_bytes:
        return text
    result: list[str] = []
    used = 0
    for char in text:
        char_len = len(char.encode("utf-8"))
        if used + char_len > max_bytes:
            break
        result.append(char)
        used += char_len
    return "".join(result).rstrip()


def redact_appid(appid: str) -> str:
    appid = appid or ""
    if len(appid) <= 8:
        return appid[:3] + "***" if appid else ""
    return appid[:6] + "***" + appid[-3:]


def local_html_images(html_text: str, base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_text or "", flags=re.I):
        if src.startswith(("http://", "https://", "data:")):
            continue
        image_path = Path(src.lstrip("/"))
        if not image_path.is_absolute():
            candidate = storage.ROOT / image_path
            if not candidate.exists():
                candidate = base_dir / image_path
            image_path = candidate
        if image_path.exists():
            paths.append(image_path.resolve())
    return paths


def resolve_html_image_src(src: str, base_dir: Path) -> Path | None:
    if not src or src.startswith(("http://", "https://", "data:")):
        return None
    normalized = src.replace("\\", "/")
    candidates: list[Path] = []
    if normalized.startswith("/"):
        candidates.append(storage.ROOT / normalized.lstrip("/"))
    path = Path(normalized)
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(base_dir / path)
        candidates.append(storage.ROOT / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def normalize_publish_image_paths(html_text: str, base_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        before, src, after = match.groups()
        image_path = resolve_html_image_src(src, base_dir)
        if not image_path:
            return match.group(0)
        return f'<img{before}src="{html.escape(str(image_path))}"{after}>'

    return re.sub(r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>', replace, html_text, flags=re.I)


def style_existing_strong(html_text: str) -> str:
    strong_style = "font-weight:700;color:#0f8f76;background:#edf8f5;padding:0 3px;border-radius:3px;"

    def replace(match: re.Match[str]) -> str:
        attrs, text = match.groups()
        if "style=" in attrs:
            return match.group(0)
        return f'<strong{attrs} style="{strong_style}">{text}</strong>'

    return re.sub(r"<strong([^>]*)>(.*?)</strong>", replace, html_text, flags=re.I | re.S)


def add_publish_emphasis(html_text: str, limit: int = 18) -> str:
    if "<strong" in html_text.lower():
        return style_existing_strong(html_text)
    count = 0
    strong_style = "font-weight:700;color:#0f8f76;background:#edf8f5;padding:0 3px;border-radius:3px;"

    def emphasize_paragraph(match: re.Match[str]) -> str:
        nonlocal count
        if count >= limit:
            return match.group(0)
        attrs, inner = match.groups()
        if "<" in inner:
            return match.group(0)
        for phrase in EMPHASIS_PATTERNS:
            if phrase in inner:
                inner = inner.replace(phrase, f'<strong style="{strong_style}">{phrase}</strong>', 1)
                count += 1
                return f"<p{attrs}>{inner}</p>"
        if "不是" in inner and "而是" in inner:
            inner = re.sub(r"(不是[^，。；]{2,30}，?而是[^，。；]{2,36})", f'<strong style="{strong_style}">\\1</strong>', inner, count=1)
            if "<strong" in inner:
                count += 1
                return f"<p{attrs}>{inner}</p>"
        return match.group(0)

    return re.sub(r"<p([^>]*)>(.*?)</p>", emphasize_paragraph, html_text, flags=re.I | re.S)


def prepare_html_for_publish(workspace: Path, html_path: Path) -> Path:
    html_text = html_path.read_text(encoding="utf-8")
    html_text = normalize_publish_image_paths(html_text, html_path.parent)
    html_text = add_publish_emphasis(html_text)
    output_path = workspace / "publish_ready.html"
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def wechat_access_token(timeout: float = 20) -> str:
    token_file = wechat_token_cache_file()
    config = wechat_config()
    now = time.time()
    if token_file.exists():
        try:
            cached = json.loads(token_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
        if (
            cached.get("access_token")
            and cached.get("appid") == config.get("appid")
            and float(cached.get("expires_at") or 0) > now + 120
        ):
            return str(cached["access_token"])
    refreshed = refresh_wechat_access_token(timeout=timeout)
    if not refreshed.get("ok"):
        raise RuntimeError(str(refreshed.get("message") or "微信 access_token 获取失败"))
    cached = json.loads(token_file.read_text(encoding="utf-8"))
    return str(cached["access_token"])


def _wechat_request_json(url: str, payload: dict[str, Any], timeout: float = 60) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"微信接口返回 HTTP {exc.code}: {raw}") from exc
    data = json.loads(raw)
    if data.get("errcode"):
        if data.get("errcode") == 40001:
            clear_wechat_token_cache("40001 from built-in publisher")
        raise RuntimeError(f"微信接口错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def _wechat_upload_file(url: str, file_path: Path, field_name: str, timeout: float = 120) -> dict[str, Any]:
    boundary = f"----zhishiku-{uuid4().hex}"
    mime = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body = header + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"微信上传接口返回 HTTP {exc.code}: {raw}") from exc
    data = json.loads(raw)
    if data.get("errcode"):
        if data.get("errcode") == 40001:
            clear_wechat_token_cache("40001 from built-in upload")
        raise RuntimeError(f"微信上传错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def _wechat_upload_cover(access_token: str, cover: Path) -> str:
    url = "https://api.weixin.qq.com/cgi-bin/material/add_material?type=image&access_token=" + urllib.parse.quote(access_token)
    data = _wechat_upload_file(url, cover, "media")
    media_id = data.get("media_id")
    if not media_id:
        raise RuntimeError(f"微信封面上传未返回 media_id：{json.dumps(data, ensure_ascii=False)}")
    return str(media_id)


def _wechat_upload_content_image(access_token: str, image_path: Path) -> str:
    url = "https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=" + urllib.parse.quote(access_token)
    data = _wechat_upload_file(url, image_path, "media")
    image_url = data.get("url")
    if not image_url:
        raise RuntimeError(f"微信正文图片上传未返回 url：{json.dumps(data, ensure_ascii=False)}")
    return str(image_url)


def _replace_local_images_with_wechat_urls(html_text: str, base_dir: Path, access_token: str) -> tuple[str, list[dict[str, str]]]:
    uploaded: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        before, src, after = match.groups()
        image_path = resolve_html_image_src(src, base_dir)
        if not image_path:
            return match.group(0)
        image_url = _wechat_upload_content_image(access_token, image_path)
        uploaded.append({"path": str(image_path), "url": image_url})
        return f'<img{before}src="{html.escape(image_url)}"{after}>'

    html_text = re.sub(r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>', replace, html_text, flags=re.I)
    return html_text, uploaded


def publish_draft_builtin(
    workspace: Path,
    title: str,
    author: str = "Bobo",
    digest: str | None = None,
    cover_path: str | None = None,
) -> dict[str, Any]:
    digest = truncate_utf8(digest, 120)
    invalidated_token = invalidate_stale_wechat_token_cache()
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    if not html_path.exists():
        raise FileNotFoundError("formatted.html 不存在，请先执行美编排版")
    publish_html_path = prepare_html_for_publish(workspace, html_path)
    cover = Path(cover_path) if cover_path else workspace / "cover.png"
    if not cover.is_absolute():
        cover = storage.ROOT / cover
    if not cover.exists():
        raise FileNotFoundError(f"找不到封面图：{cover}")

    access_token = wechat_access_token()
    thumb_media_id = _wechat_upload_cover(access_token, cover)
    html_text = publish_html_path.read_text(encoding="utf-8")
    html_text, uploaded_images = _replace_local_images_with_wechat_urls(html_text, publish_html_path.parent, access_token)
    publish_html_path.write_text(html_text, encoding="utf-8")
    payload = {
        "articles": [
            {
                "title": title,
                "author": author or "Bobo",
                "digest": digest or "",
                "content": html_text,
                "thumb_media_id": thumb_media_id,
                "show_cover_pic": 0,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    url = "https://api.weixin.qq.com/cgi-bin/draft/add?access_token=" + urllib.parse.quote(access_token)
    data = _wechat_request_json(url, payload, timeout=120)
    media_id = data.get("media_id")
    result = {
        "returncode": 0,
        "stdout": json.dumps(data, ensure_ascii=False),
        "stderr": "",
        "author": author or "Bobo",
        "content_path": _relative(publish_html_path),
        "source_content_path": _relative(html_path),
        "invalidated_token_cache": invalidated_token,
        "cover_path": _relative(cover) if cover.exists() else str(cover),
        "thumb_media_id": thumb_media_id,
        "media_id": media_id,
        "uploaded_content_images": uploaded_images,
        "publisher": "builtin",
    }
    result_path = workspace / "publish_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["path"] = _relative(result_path)
    return result


def publish_preflight(
    workspace: Path,
    title: str,
    author: str = "Bobo",
    digest: str | None = None,
    cover_path: str | None = None,
) -> dict[str, Any]:
    original_digest = digest or ""
    safe_digest = truncate_utf8(original_digest, 120)
    digest_was_truncated = safe_digest != original_digest
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    article_path = workspace / "article.md"
    cover = Path(cover_path) if cover_path else workspace / "cover.png"
    if not cover.is_absolute():
        cover = storage.ROOT / cover
    html_text = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    config: dict[str, Any] = {}
    config_file = wechat_config_file()
    token_cache_file = wechat_token_cache_file()
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    token_cache: dict[str, Any] = {}
    if token_cache_file.exists():
        try:
            token_cache = json.loads(token_cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            token_cache = {}
    config_ready = bool(config.get("appid") and config.get("appsecret"))
    wechat_api_check: dict[str, Any] | None = refresh_wechat_access_token() if config_ready else None
    content_image_paths = sorted({str(path) for path in local_html_images(html_text, html_path.parent)})
    checks = [
        {
            "key": "wechat_config",
            "label": "微信 AppID/AppSecret 配置",
            "ok": bool(config.get("appid") and config.get("appsecret")),
            "detail": f"配置文件：{config_file}; AppID：{redact_appid(config.get('appid', '')) or '未配置'}",
        },
        {
            "key": "publisher_script",
            "label": "草稿发布脚本",
            "ok": True,
            "detail": str(PUBLISHER_SCRIPT) if PUBLISHER_SCRIPT.exists() else "内置微信草稿发布器可用",
            "optional": not PUBLISHER_SCRIPT.exists(),
        },
        {
            "key": "article_markdown",
            "label": "文章 Markdown",
            "ok": article_path.exists(),
            "detail": _relative(article_path) if article_path.exists() else "缺少 article.md",
        },
        {
            "key": "html",
            "label": "微信公众号 HTML",
            "ok": html_path.exists() and bool(html_text.strip()),
            "detail": f"{_relative(html_path) if html_path.exists() else '缺少 formatted.html'}; {len(html_text)} 字符",
        },
        {
            "key": "cover",
            "label": "封面图 thumb_media_id 前置素材",
            "ok": cover.exists() and cover.suffix.lower() in WECHAT_IMAGE_EXTENSIONS and cover.stat().st_size <= WECHAT_IMAGE_MAX_BYTES,
            "detail": (
                f"{cover}; {cover.stat().st_size // 1024} KB"
                if cover.exists()
                else "未找到封面图，微信草稿可能无法获得 thumb_media_id"
            ),
        },
        {
            "key": "title",
            "label": "标题长度",
            "ok": bool((title or "").strip()) and len(title or "") <= 64 and utf8_len(title) <= 192,
            "detail": f"{len(title or '')} 字符 / {utf8_len(title)} 字节，官方草稿字段建议不超过 64 字符",
        },
        {
            "key": "author",
            "label": "作者长度",
            "ok": utf8_len(author or "Bobo") <= 20,
            "detail": f"{author or 'Bobo'}，{utf8_len(author or 'Bobo')} 字节，publisher 会按 20 字节保护",
        },
        {
            "key": "digest",
            "label": "摘要长度",
            "ok": True,
            "detail": (
                f"{utf8_len(original_digest)} 字节，已自动截断为 {utf8_len(safe_digest)} 字节"
                if digest_was_truncated
                else f"{utf8_len(safe_digest)} 字节，符合 120 字节限制"
            ),
            "optional": digest_was_truncated,
            "fixed": digest_was_truncated,
        },
        {
            "key": "content_images",
            "label": "正文本地图片",
            "ok": all(Path(path).suffix.lower() in WECHAT_IMAGE_EXTENSIONS for path in content_image_paths),
            "detail": f"{len(content_image_paths)} 张，将在发布时上传为微信图片 URL",
        },
        {
            "key": "token_cache",
            "label": "access_token 缓存",
            "ok": bool(token_cache.get("access_token")),
            "detail": (
                f"已有缓存，更新时间：{token_cache.get('updated_at', '未知')}"
                if token_cache.get("access_token")
                else "无缓存；发布时会按官方 /cgi-bin/token 接口获取"
            ),
            "optional": True,
        },
        {
            "key": "wechat_api",
            "label": "微信 access_token / IP 白名单验证",
            "ok": bool(wechat_api_check and wechat_api_check.get("ok")),
            "detail": (
                str(wechat_api_check.get("message") or "微信接口验证通过")
                if wechat_api_check
                else "配置 AppID/AppSecret 后再验证 access_token 和 IP 白名单状态"
            ),
            "optional": not config_ready,
            "ip": str((wechat_api_check or {}).get("ip") or ""),
            "raw": str((wechat_api_check or {}).get("raw") or ""),
        },
    ]
    blocking = [item for item in checks if not item.get("ok") and not item.get("optional")]
    return {
        "ok": not blocking,
        "checks": checks,
        "blocking": blocking,
        "digest": safe_digest,
        "digest_original_bytes": utf8_len(original_digest),
        "digest_bytes": utf8_len(safe_digest),
        "digest_truncated": digest_was_truncated,
        "flow": [
            "1. 获取 access_token：GET /cgi-bin/token?grant_type=client_credential",
            "2. 上传封面永久素材：POST /cgi-bin/material/add_material?type=image，得到 thumb_media_id",
            "3. 上传正文本地图片并替换为微信图片 URL",
            "4. 新建草稿：POST /cgi-bin/draft/add，提交 title/author/digest/content/thumb_media_id",
            "5. 保存 publish_result.json，便于目录中断点续跑",
        ],
    }


def refresh_wechat_access_token(timeout: float = 20) -> dict[str, Any]:
    config_file = wechat_config_file()
    config = wechat_config()
    if not config_file.exists():
        return {
            "ok": False,
            "message": f"未找到微信配置文件：{config_file}",
            "ip": "",
            "raw": "",
        }
    appid = config.get("appid", "")
    secret = config.get("appsecret", "")
    if not appid or not secret:
        return {"ok": False, "message": "微信 AppID/AppSecret 未配置完整", "ip": "", "raw": ""}
    clear_wechat_token_cache("force refresh")
    url = (
        "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential"
        + "&appid="
        + urllib.parse.quote(appid)
        + "&secret="
        + urllib.parse.quote(secret)
    )
    try:
        raw = urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8", "replace")
    except Exception as exc:
        return {"ok": False, "message": f"微信 token 接口调用失败：{exc}", "ip": "", "raw": ""}
    data = json.loads(raw)
    if data.get("access_token"):
        token_file = wechat_token_cache_file()
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(
            json.dumps(
                {
                    "access_token": data["access_token"],
                    "expires_at": __import__("time").time() + data.get("expires_in", 7200),
                    "updated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                    "appid": appid,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "message": "微信 token 接口已通过，当前出口 IP 已在白名单中，并已刷新本地 token 缓存。",
            "ip": "",
            "raw": json.dumps({"expires_in": data.get("expires_in")}, ensure_ascii=False),
        }
    errmsg = data.get("errmsg", "")
    match = re.search(r"invalid ip ([0-9.]+)", errmsg)
    ip = match.group(1) if match else ""
    return {
        "ok": False,
        "message": f"微信接口返回错误：{data.get('errcode')} {errmsg}",
        "ip": ip,
        "raw": json.dumps(data, ensure_ascii=False),
    }


def check_wechat_publish_ip(timeout: float = 20) -> dict[str, Any]:
    return refresh_wechat_access_token(timeout=timeout)


def _image_endpoint(setting: dict[str, Any]) -> str:
    base = setting["base_url"].rstrip("/")
    if base.endswith("/images/generations"):
        return base
    return base + "/images/generations"


def _image_payload(setting: dict[str, Any], prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": setting["model"],
        "prompt": prompt,
        "n": 1,
    }
    size = str(setting.get("size") or "").strip()
    quality = str(setting.get("quality") or "auto").strip()
    known_quality_values = {"auto", "standard", "hd", "high", "medium", "low"}
    size = (
        size.replace("\u00d7", "x")
        .replace("\uff58", "x")
        .replace("\uff38", "x")
        .replace("*", "x")
        .replace(" ", "")
    )
    if size.lower() in known_quality_values and not quality:
        quality = size
        size = "1024x1024"
    if not size or size.lower() in {"auto", "default", "none"}:
        size = "1024x1024"
    payload["size"] = size
    if quality:
        payload["quality"] = quality
    response_format = str(setting.get("response_format") or "").strip()
    if response_format:
        payload["response_format"] = response_format
    return payload


def _compact_image_prompt(prompt: str, max_chars: int = IMAGE_PROMPT_RETRY_MAX_CHARS) -> str:
    text = re.sub(r"\s+", " ", (prompt or "").strip())
    if len(text) <= max_chars:
        return text
    keep = max_chars - 72
    return (
        text[:keep].rstrip()
        + "。画面保持主题明确、元素克制、少量简体中文文字，适合微信公众号配图。"
    )


def _image_request_summary(endpoint: str, payload: dict[str, Any], prompt: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "model": payload.get("model"),
        "size": payload.get("size"),
        "quality": payload.get("quality", ""),
        "response_format": payload.get("response_format", ""),
        "prompt_chars": len(prompt or ""),
    }


def _download_image(url: str, output_path: Path, timeout: float) -> None:
    if url.startswith("data:image/"):
        _header, _sep, data = url.partition(",")
        output_path.write_bytes(base64.b64decode(data))
        return
    with urllib.request.urlopen(url, timeout=timeout) as response:
        output_path.write_bytes(response.read())


def generate_image(prompt: str, output_path: Path, setting: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = setting or image_api_settings.active_setting()
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("图片提示词不能为空")

    endpoint = _image_endpoint(resolved)
    payload = _image_payload(resolved, prompt)
    timeout = float(resolved.get("timeout") or 120)

    def request_once(current_payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(current_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {resolved['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))

    retry_used = False
    try:
        try:
            data = request_once(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            should_retry = 500 <= exc.code < 600 and len(prompt) > IMAGE_PROMPT_RETRY_MAX_CHARS
            if not should_retry:
                summary = _image_request_summary(endpoint, payload, prompt)
                raise RuntimeError(
                    f"图片 API 返回错误 {exc.code}: {detail}; request={json.dumps(summary, ensure_ascii=False)}"
                ) from exc
            retry_prompt = _compact_image_prompt(prompt)
            retry_payload = _image_payload(resolved, retry_prompt)
            try:
                data = request_once(retry_payload)
                prompt = retry_prompt
                payload = retry_payload
                retry_used = True
            except urllib.error.HTTPError as retry_exc:
                retry_detail = retry_exc.read().decode("utf-8", "replace")
                summary = _image_request_summary(endpoint, retry_payload, retry_prompt)
                raise RuntimeError(
                    "图片 API 返回错误 "
                    f"{retry_exc.code}: {retry_detail}; 已因上游 {exc.code} 自动改用精简提示词重试；"
                    f"request={json.dumps(summary, ensure_ascii=False)}"
                ) from retry_exc
    except RuntimeError:
        raise
    except Exception as exc:
        summary = _image_request_summary(endpoint, payload, prompt)
        raise RuntimeError(
            f"图片 API 调用失败：{exc}; request={json.dumps(summary, ensure_ascii=False)}"
        ) from exc

    first = (data.get("data") or [{}])[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if first.get("b64_json"):
        output_path.write_bytes(base64.b64decode(first["b64_json"]))
    elif first.get("url"):
        _download_image(first["url"], output_path, timeout)
    else:
        raise RuntimeError(f"图片 API 返回结构中没有 b64_json 或 url：{json.dumps(data, ensure_ascii=False)[:500]}")

    return {
        "path": _relative(output_path),
        "absolute_path": str(output_path),
        "prompt": prompt,
        "model": resolved.get("model", ""),
        "retry_used": retry_used,
    }

def _existing_image_item(path: Path, prompt: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return {
        "path": _relative(path),
        "absolute_path": str(path),
        "prompt": prompt,
        "reused_existing": True,
    }


def _image_metadata_path(workspace: Path) -> Path:
    return workspace / "image_metadata.json"


def _normalize_image_metadata(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    data = metadata or {}
    content_images = data.get("content_images") if isinstance(data.get("content_images"), list) else []
    errors = data.get("errors") if isinstance(data.get("errors"), list) else []
    cover = data.get("cover") if isinstance(data.get("cover"), dict) else None
    content_images = sorted(
        [item for item in content_images if isinstance(item, dict)],
        key=lambda item: int(item.get("index") or 0),
    )
    items = []
    if cover:
        items.append(cover)
    items.extend(content_images)
    return {
        "items": items,
        "cover": cover,
        "content_images": content_images,
        "errors": [item for item in errors if isinstance(item, dict)],
        "partial": bool(errors),
        "ok": not bool(errors),
    }


def load_writer_image_metadata(workspace: Path) -> dict[str, Any]:
    path = _image_metadata_path(workspace)
    if not path.exists():
        return _normalize_image_metadata()
    try:
        return _normalize_image_metadata(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return _normalize_image_metadata({"errors": [{"kind": "metadata", "message": "image_metadata.json 格式不可读"}]})


def _write_writer_image_metadata(workspace: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_image_metadata(metadata)
    _image_metadata_path(workspace).write_text(
        json.dumps(
            {
                "cover": normalized["cover"],
                "content_images": normalized["content_images"],
                "errors": normalized["errors"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return normalized


def generate_writer_image_item(
    workspace: Path,
    kind: str,
    prompt: str,
    index: int | None = None,
) -> dict[str, Any]:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("图片提示词不能为空")
    metadata = load_writer_image_metadata(workspace)
    errors = [
        item for item in metadata["errors"]
        if not (item.get("kind") == kind and (kind == "cover" or int(item.get("index") or 0) == int(index or 0)))
    ]
    metadata["errors"] = errors

    if kind == "cover":
        filename = "cover.png"
        image_path = workspace / filename
    elif kind == "content":
        if not index or index < 1:
            raise ValueError("正文配图 index 必须从 1 开始")
        filename = f"content-{index}.png"
        image_path = workspace / filename
    else:
        raise ValueError(f"未知图片类型：{kind}")

    item = _existing_image_item(image_path, prompt)
    if item is None:
        try:
            item = generate_image(prompt, image_path)
        except Exception as exc:
            message = f"生成封面图失败：{exc}" if kind == "cover" else f"生成正文配图 {index} 失败：{exc}"
            metadata["errors"].append({"kind": kind, "index": index, "message": message})
            item = _existing_image_item(image_path, prompt)

    if item:
        record = {"filename": filename, "prompt": prompt, "path": item["path"]}
        if kind == "content":
            record["index"] = index
            remaining = [
                existing for existing in metadata["content_images"]
                if int(existing.get("index") or 0) != int(index or 0)
            ]
            metadata["content_images"] = [*remaining, record]
        else:
            metadata["cover"] = record

    return _write_writer_image_metadata(workspace, metadata)


def generate_writer_images(
    workspace: Path,
    cover_prompt: str | None = None,
    content_prompts: list[str] | None = None,
) -> dict[str, Any]:
    if cover_prompt:
        generate_writer_image_item(workspace, "cover", cover_prompt)
    for index, prompt in enumerate(content_prompts or [], start=1):
        if prompt.strip():
            generate_writer_image_item(workspace, "content", prompt, index=index)
    return load_writer_image_metadata(workspace)


def content_images(workspace: Path) -> list[Path]:
    return [
        path
        for path in sorted(workspace.glob("content-*.*"))
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    ]


def content_image_items(workspace: Path) -> list[dict[str, Any]]:
    metadata_path = workspace / "image_metadata.json"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
    prompt_by_name = {
        item.get("filename"): item.get("prompt", "")
        for item in metadata.get("content_images", [])
        if item.get("filename")
    }
    items = []
    for index, path in enumerate(content_images(workspace), start=1):
        items.append(
            {
                "index": index,
                "path": path,
                "prompt": prompt_by_name.get(path.name, ""),
            }
        )
    return items


def image_prompt_keywords(prompt: str) -> list[str]:
    stop_words = {
        "简体中文",
        "少量文字",
        "准确可读",
        "公众号",
        "封面",
        "配图",
        "风格",
        "构图",
        "主体",
        "图片",
        "文字",
        "高清",
        "科技感",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}|[\u4e00-\u9fff]{2,}", prompt or "")
    result = []
    for word in words:
        if word in stop_words or len(word) > 14:
            continue
        if word not in result:
            result.append(word)
    return result[:12]


def strip_existing_content_images(markdown_text: str) -> str:
    text = re.sub(r"\n*!\[内容配图\d*\]\([^\)]*content-\d+\.[^\)]*\)\n*", "\n", markdown_text or "")
    text = re.sub(r"\n*## 内容配图\s*\n+(?=(## |\Z))", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def best_image_insert_line(lines: list[str], keywords: list[str], used_lines: set[int], fallback_ratio: float) -> int:
    candidates = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("![") or stripped.startswith("# "):
            continue
        score = 0
        for keyword in keywords:
            if keyword and keyword in stripped:
                score += 3 if len(keyword) >= 3 else 1
        if stripped.startswith(("## ", "### ")):
            score += 1
        if index in used_lines:
            score -= 5
        if score > 0:
            candidates.append((score, -abs(index - int(len(lines) * fallback_ratio)), index))
    if candidates:
        return max(candidates)[2]
    fallback = max(0, min(len(lines) - 1, int(len(lines) * fallback_ratio)))
    while fallback in used_lines and fallback < len(lines) - 1:
        fallback += 1
    return fallback


def ensure_content_images_in_markdown(workspace: Path, markdown_text: str) -> str:
    items = content_image_items(workspace)
    if not items:
        return markdown_text
    text = strip_existing_content_images(markdown_text)
    lines = text.splitlines()
    used_lines: set[int] = set()
    insertions: list[tuple[int, str]] = []
    total = len(items)
    for position, item in enumerate(items, start=1):
        image_path = item["path"]
        relative = _relative(image_path).replace("\\", "/")
        keywords = image_prompt_keywords(item.get("prompt", ""))
        fallback_ratio = 0.35 + (position - 1) * (0.45 / max(1, total - 1))
        line_index = best_image_insert_line(lines, keywords, used_lines, fallback_ratio)
        used_lines.add(line_index)
        insertions.append((line_index, f"![内容配图{position}](/{relative})"))
    for line_index, image_markdown in sorted(insertions, reverse=True):
        lines.insert(line_index + 1, "")
        lines.insert(line_index + 2, image_markdown)
        lines.insert(line_index + 3, "")
    return "\n".join(lines).strip() + "\n"


def resolve_writer_file(path: str) -> Path:
    resolved = storage.resolve_root_path(path)
    if not resolved:
        raise ValueError("缺少文件路径")
    resolved = resolved.resolve()
    writer_root = writer_dir().resolve()
    if writer_root not in resolved.parents and resolved != writer_root:
        raise ValueError("只能预览 writer/ 下的文件")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    return resolved


def _run_python(command: list[str], cwd: Path | None = None, timeout: float = 180) -> subprocess.CompletedProcess[str]:
    env = dict(**__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, *command],
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def fallback_markdown_to_html(markdown_text: str, title: str = "") -> str:
    lines = markdown_text.splitlines()
    body: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                body.append('<pre style="background:#111827;color:#f9fafb;padding:14px;border-radius:8px;overflow:auto;"><code>')
                body.append(html.escape("\n".join(code_lines)))
                body.append("</code></pre>")
                code_lines = []
                in_code = False
            else:
                if in_list:
                    body.append("</ul>")
                    in_list = False
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not line.strip():
            if in_list:
                body.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            title = title or line[2:].strip()
            continue
        if line.startswith("## "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            if in_list:
                body.append("</ul>")
                in_list = False
            body.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith(("- ", "* ")):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{html.escape(line[2:].strip())}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            alt, src = image_match.groups()
            body.append(
                f'<p><img src="{html.escape(src)}" alt="{html.escape(alt)}" '
                'style="max-width:100%;border-radius:8px;" /></p>'
            )
            continue
        body.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        body.append("</ul>")
    if in_code:
        body.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title or "公众号文章")}</title>
</head>
<body>
  <section style="max-width:680px;margin:0 auto;padding:24px 18px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;line-height:1.85;color:#17201c;">
    {''.join(body)}
  </section>
</body>
</html>
"""


def format_article(
    workspace: Path,
    markdown: str | None = None,
    theme: str = "tech",
    design_strategy: str = "",
    use_ai: bool = True,
) -> dict[str, Any]:
    if markdown is not None:
        article_path = write_article(workspace, ensure_content_images_in_markdown(workspace, markdown))
    else:
        article_path = workspace / "article.md"
        if article_path.exists():
            write_article(
                workspace,
                ensure_content_images_in_markdown(workspace, article_path.read_text(encoding="utf-8")),
            )
    if not article_path.exists():
        raise FileNotFoundError("article.md 不存在，请先生成文章")

    html_path = workspace / "formatted.html"
    ai_error = ""
    if use_ai and design_strategy.strip():
        try:
            html_text = deepseek_client.design_wechat_article_html(
                article_path.read_text(encoding="utf-8"),
                design_strategy=design_strategy or DEFAULT_DESIGN_STRATEGY,
                setting=api_settings.active_setting(),
            )
            html_text = add_publish_emphasis(html_text)
            html_path.write_text(html_text, encoding="utf-8")
            return {
                "path": _relative(html_path),
                "absolute_path": str(html_path),
                "html": html_text,
                "stdout": "generated by API design formatter",
                "stderr": "",
                "fallback": False,
                "ai_formatted": True,
                "message": "已调用 API 按美编策略生成公众号 HTML。",
            }
        except Exception as exc:
            ai_error = str(exc)

    if not FORMATTER_SCRIPT.exists():
        html_text = fallback_markdown_to_html(article_path.read_text(encoding="utf-8"))
        html_text = add_publish_emphasis(html_text)
        html_path.write_text(html_text, encoding="utf-8")
        return {
            "path": _relative(html_path),
            "absolute_path": str(html_path),
            "html": html_text,
            "stdout": "",
            "stderr": f"API design formatter failed: {ai_error}; formatter script not found: {FORMATTER_SCRIPT}" if ai_error else f"formatter script not found: {FORMATTER_SCRIPT}",
            "fallback": True,
            "ai_formatted": False,
            "message": "API 美编不可用，已使用内置基础 HTML 兜底。" if ai_error else "未找到外部 formatter 脚本，已使用内置美编生成 HTML。",
        }

    try:
        __import__("markdown")
    except ImportError:
        html_path.write_text(
            fallback_markdown_to_html(article_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        html_text = html_path.read_text(encoding="utf-8")
        return {
            "path": _relative(html_path),
            "absolute_path": str(html_path),
            "html": html_text,
            "stdout": "",
            "stderr": f"API design formatter failed: {ai_error}; No module named 'markdown'" if ai_error else "No module named 'markdown'",
            "fallback": True,
            "ai_formatted": False,
            "message": "formatter missing markdown dependency; generated HTML with built-in fallback formatter.",
        }
    completed = _run_python(
        [str(FORMATTER_SCRIPT), "--input", str(article_path), "--theme", theme, "--output", str(html_path)],
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or "美编排版失败")

    if CODE_BLOCK_SCRIPT.exists() and html_path.exists():
        post_path = workspace / "formatted_wechat.html"
        converted = _run_python([str(CODE_BLOCK_SCRIPT), str(html_path), str(post_path)], timeout=120)
        if converted.returncode == 0 and post_path.exists():
            html_path = post_path

    html = html_path.read_text(encoding="utf-8")
    html = add_publish_emphasis(html)
    html_path.write_text(html, encoding="utf-8")
    return {
        "path": _relative(html_path),
        "absolute_path": str(html_path),
        "html": html,
        "stdout": completed.stdout,
        "stderr": f"API design formatter failed: {ai_error}; {completed.stderr}".strip("; ") if ai_error else completed.stderr,
        "ai_formatted": False,
    }


def publish_draft(
    workspace: Path,
    title: str,
    author: str = "Bobo",
    digest: str | None = None,
    cover_path: str | None = None,
) -> dict[str, Any]:
    digest = truncate_utf8(digest, 120)
    if not PUBLISHER_SCRIPT.exists():
        return publish_draft_builtin(workspace, title, author=author, digest=digest, cover_path=cover_path)
    invalidated_token = invalidate_stale_wechat_token_cache()
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    if not html_path.exists():
        raise FileNotFoundError("formatted.html 不存在，请先执行美编排版")
    publish_html_path = prepare_html_for_publish(workspace, html_path)
    cover = Path(cover_path) if cover_path else workspace / "cover.png"
    if not cover.is_absolute():
        cover = storage.ROOT / cover

    command = [
        str(PUBLISHER_SCRIPT),
        "--title",
        title,
        "--content",
        str(publish_html_path),
        "--author",
        author or "Bobo",
    ]
    if cover.exists():
        command.extend(["--cover", str(cover)])
    if digest:
        command.extend(["--digest", digest])

    try:
        completed = _run_python(command, cwd=PUBLISHER_SCRIPT.parent, timeout=360)
    except TimeoutExpired as exc:
        result = {
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "author": author or "Bobo",
            "content_path": _relative(publish_html_path),
            "source_content_path": _relative(html_path),
            "cover_path": _relative(cover) if cover.exists() else str(cover),
            "timeout": True,
            "timeout_seconds": exc.timeout,
            "command": [str(sys.executable), *command],
        }
        result_path = workspace / "publish_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"转入草稿箱超时（{int(exc.timeout)}秒）。已保存发布检查结果：{_relative(result_path)}。"
            "这通常是微信发布脚本等待网络、授权或接口响应过久导致，请稍后在目录中继续发布。"
        ) from exc
    result = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "author": author or "Bobo",
        "content_path": _relative(publish_html_path),
        "source_content_path": _relative(html_path),
        "invalidated_token_cache": invalidated_token,
        "cover_path": _relative(cover) if cover.exists() else str(cover),
    }
    media_ids = re.findall(r"media_id[:：]\s*([A-Za-z0-9_\-]+)", completed.stdout + "\n" + completed.stderr)
    if media_ids:
        result["media_id"] = media_ids[-1]
    result_path = workspace / "publish_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["path"] = _relative(result_path)
    if completed.returncode != 0:
        raw = (completed.stderr or completed.stdout or "").strip()
        if "错误码40001" in raw or "errcode\":40001" in raw or "AppSecret错误" in raw:
            clear_wechat_token_cache("40001 from publisher")
            raise RuntimeError(
                "微信返回 40001。已自动清除本地 access_token 缓存。"
                "如果 AppID/AppSecret 确认正确，请在发布页点击“检测微信IP”刷新 token 后再发布。原始错误："
                + raw
            )
        if "not in whitelist" in raw or "invalid ip" in raw:
            raise RuntimeError("微信 IP 白名单错误：" + raw)
        raise RuntimeError(raw or "转入草稿箱失败")
    return result
