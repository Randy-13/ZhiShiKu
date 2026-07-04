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
from dataclasses import dataclass, field
from subprocess import TimeoutExpired
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:  # pragma: no cover - production venv normally includes bs4
    BeautifulSoup = None  # type: ignore[assignment]
    Comment = None  # type: ignore[assignment]

import api_settings
import deepseek_client
import image_api_settings
import storage
from src import db as database


WECHAT_ALLOWED_TAGS = {
    "section", "p", "span", "strong", "em", "blockquote", "ul", "ol", "li",
    "table", "thead", "tbody", "tr", "th", "td", "img", "br", "pre", "code",
    "h1", "h2", "h3", "hr",
}
WECHAT_FORBIDDEN_TAGS = {"script", "iframe", "style", "link", "svg", "canvas", "video", "audio", "object", "embed"}
WECHAT_ALLOWED_STYLE_PROPS = {
    "background", "background-color", "border", "border-bottom", "border-left", "border-radius",
    "box-sizing", "color", "display", "font-family", "font-size", "font-style", "font-weight",
    "height", "letter-spacing", "line-height", "margin", "margin-bottom", "margin-left",
    "margin-right", "margin-top", "max-width", "min-width", "overflow", "padding",
    "padding-bottom", "padding-left", "padding-right", "padding-top", "text-align",
    "vertical-align", "white-space", "width", "word-break",
}
WECHAT_HTML_MAX_CHARS = 180000

DESIGN_THEME_PRESETS: dict[str, dict[str, str]] = {
    "tech": {"accent": "#2f6f5e", "accent_soft": "#e8f2ed", "ink": "#18231e", "muted": "#6d756f", "line": "#d8e3dc", "surface": "#fffdf8", "paper": "#f7f2e8", "warn": "#9a641f", "error": "#a63d32", "marker": "#fff1b8", "divider": "- - -"},
    "research": {"accent": "#345f8f", "accent_soft": "#e8eef7", "ink": "#172033", "muted": "#687386", "line": "#d8dfec", "surface": "#fbfcff", "paper": "#f3f6fb", "warn": "#8b641d", "error": "#94443d", "marker": "#e9f0ff", "divider": "section"},
    "column": {"accent": "#7a4c30", "accent_soft": "#f3e8df", "ink": "#271b15", "muted": "#796b60", "line": "#e2d4c7", "surface": "#fffaf4", "paper": "#f6eee5", "warn": "#9a641f", "error": "#a63d32", "marker": "#ffe7c4", "divider": "- - -"},
    "xiumi": {"accent": "#bd5b73", "accent_soft": "#fde9ef", "ink": "#23191c", "muted": "#7b6870", "line": "#efd0da", "surface": "#fff8fa", "paper": "#f8edf1", "warn": "#a56a21", "error": "#b63d47", "marker": "#ffe1ea", "divider": "star"},
}


@dataclass
class MarkdownBlock:
    kind: str
    text: str = ""
    level: int = 0
    ordered: bool = False
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    src: str = ""
    alt: str = ""


@dataclass
class WechatDesignIntent:
    theme: str = "tech"
    emphasis_density: str = "medium"
    decoration_level: str = "medium"
    paragraph_rhythm: str = "comfortable"
    quote_style: str = "card"
    divider_style: str = "soft"
    image_style: str = "rounded"
    components: list[str] = field(default_factory=lambda: [
        "title_card", "section_divider", "quote_card", "highlight_sentence", "data_card",
        "step_block", "risk_note", "conclusion_box", "image_caption", "footer_action",
    ])

    def as_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "emphasis_density": self.emphasis_density,
            "decoration_level": self.decoration_level,
            "paragraph_rhythm": self.paragraph_rhythm,
            "quote_style": self.quote_style,
            "divider_style": self.divider_style,
            "image_style": self.image_style,
            "components": list(self.components),
        }


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
CONTENT_IMAGE_NAME_RE = re.compile(r"^content[_-]?(\d+)(\.[A-Za-z0-9]+)$", re.I)
CONTENT_IMAGE_MARKDOWN_RE = re.compile(r"\n*!\[[^\]]*\]\([^\)]*content[_-]?\d+\.[^\)]*\)\n*", re.I)
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


def canonical_content_image_filename(index: int, suffix: str = ".png") -> str:
    clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"content-{int(index)}{clean_suffix.lower()}"


def canonical_content_image_alias(name: str) -> str | None:
    match = CONTENT_IMAGE_NAME_RE.fullmatch(Path(str(name)).name)
    if not match:
        return None
    return canonical_content_image_filename(int(match.group(1)), match.group(2))


def _replace_path_name(path_text: str, filename: str) -> str:
    normalized = str(path_text or "").replace("\\", "/")
    if not normalized:
        return filename
    prefix, sep, _name = normalized.rpartition("/")
    return f"{prefix}{sep}{filename}" if sep else filename

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


def _safe_wechat_account_key(account_key: str | None) -> str:
    value = (account_key or "").strip()
    if not value:
        return ""
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("._")[:80]


def wechat_config_dir(account_key: str | None = None) -> Path:
    key = _safe_wechat_account_key(account_key)
    if key:
        return storage.ROOT / "auth" / "wechat_publisher" / key
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())) / ".wechat-publisher"


def wechat_config_file(account_key: str | None = None) -> Path:
    return wechat_config_dir(account_key) / "config.json"


def wechat_token_cache_file(account_key: str | None = None) -> Path:
    return wechat_config_dir(account_key) / "token_cache.json"


def wechat_user_config_exists(account_key: str | None) -> bool:
    return bool(_safe_wechat_account_key(account_key)) and wechat_config_file(account_key).exists()


def wechat_config(account_key: str | None = None) -> dict[str, str]:
    config_file = wechat_config_file(account_key) if account_key else wechat_config_file()
    if not config_file.exists():
        return {}
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "appid": (config.get("appid") or "").strip(),
        "appsecret": (config.get("appsecret") or "").strip(),
        "account_name": (config.get("account_name") or config.get("name") or "").strip(),
        "author": (config.get("author") or "").strip(),
        "owner_user_id": (config.get("owner_user_id") or "").strip(),
        "owner_username": (config.get("owner_username") or "").strip(),
        "updated_at": (config.get("updated_at") or "").strip(),
    }


def default_wechat_author(account_key: str | None = None) -> str:
    config = wechat_config(account_key) if account_key else wechat_config()
    if not config.get("author") and account_key:
        config = wechat_config()
    return config.get("author") or "Bobo"


def resolve_publish_author(author: str | None = None, account_key: str | None = None) -> str:
    cleaned = (author or "").strip()
    return cleaned or default_wechat_author(account_key)


def _redact_appsecret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}{'*' * 8}{value[-4:]}"


def wechat_binding_status(account_key: str | None, username: str = "") -> dict[str, Any]:
    config_file = wechat_config_file(account_key)
    config = wechat_config(account_key)
    token_file = wechat_token_cache_file(account_key)
    token_cache: dict[str, Any] = {}
    if token_file.exists():
        try:
            token_cache = json.loads(token_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            token_cache = {}
    configured = bool(config.get("appid") and config.get("appsecret"))
    return {
        "configured": configured,
        "account_key": _safe_wechat_account_key(account_key),
        "username": username,
        "account_name": config.get("account_name") or "",
        "author": default_wechat_author(account_key),
        "appid": config.get("appid", ""),
        "appid_masked": redact_appid(config.get("appid", "")),
        "appsecret": _redact_appsecret(config.get("appsecret", "")) if configured else "",
        "config_path": str(config_file),
        "token_cached": bool(token_cache.get("access_token")),
        "token_updated_at": token_cache.get("updated_at", ""),
        "updated_at": config.get("updated_at") or "",
    }


def save_wechat_binding(
    account_key: str,
    username: str = "",
    *,
    appid: str,
    appsecret: str | None = None,
    account_name: str = "",
    author: str = "Bobo",
) -> dict[str, Any]:
    key = _safe_wechat_account_key(account_key)
    if not key:
        raise ValueError("Missing WeChat binding account key")
    existing = wechat_config(key)
    cleaned_appid = appid.strip()
    cleaned_secret = (appsecret or "").strip() or existing.get("appsecret", "")
    if not cleaned_appid or not cleaned_secret:
        raise ValueError("微信公众号 AppID 和 AppSecret 都必须填写")
    config_file = wechat_config_file(key)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "appid": cleaned_appid,
        "appsecret": cleaned_secret,
        "account_name": account_name.strip(),
        "author": author.strip() or "Bobo",
        "owner_user_id": account_key,
        "owner_username": username,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    config_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    clear_wechat_token_cache("config changed", account_key=key)
    return wechat_binding_status(key, username)


def wechat_account_key_for_context(context: dict[str, Any]) -> str | None:
    user = context.get("user") or {}
    user_id = str(user.get("id") or "") if isinstance(user, dict) else ""
    if not user_id:
        return None
    return user_id


def clear_wechat_token_cache(reason: str = "", account_key: str | None = None) -> bool:
    token_file = wechat_token_cache_file(account_key)
    if token_file.exists():
        token_file.unlink()
        return True
    return False


def invalidate_stale_wechat_token_cache(account_key: str | None = None) -> bool:
    token_file = wechat_token_cache_file(account_key)
    config = wechat_config(account_key)
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


WRITING_STRATEGY_DEFAULT_ID = "default-wechat-article"


def writing_strategies_file() -> Path:
    return writer_dir() / "writing_strategies.json"


def _default_writing_strategy_preset() -> dict[str, Any]:
    now = "builtin"
    return {
        "id": WRITING_STRATEGY_DEFAULT_ID,
        "name": "微信公众号文章默认写文策略",
        "body": DEFAULT_WRITING_STRATEGY.strip(),
        "readonly": True,
        "created_at": now,
        "updated_at": now,
    }


def _normalize_writing_strategy_preset(item: dict[str, Any]) -> dict[str, Any]:
    strategy_id = str(item.get("id") or "").strip() or uuid4().hex
    readonly = strategy_id == WRITING_STRATEGY_DEFAULT_ID or bool(item.get("readonly"))
    return {
        "id": strategy_id,
        "name": str(item.get("name") or "").strip() or "未命名写文策略",
        "body": str(item.get("body") or "").strip(),
        "readonly": readonly,
        "created_at": str(item.get("created_at") or datetime.now().isoformat(timespec="seconds")),
        "updated_at": str(item.get("updated_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _read_custom_writing_strategies() -> list[dict[str, Any]]:
    path = writing_strategies_file()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    raw_items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = _normalize_writing_strategy_preset(raw)
        if item["id"] == WRITING_STRATEGY_DEFAULT_ID:
            continue
        if item["body"]:
            item["readonly"] = False
            items.append(item)
    return items


def _write_custom_writing_strategies(items: list[dict[str, Any]]) -> None:
    path = writing_strategies_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": [item for item in items if item.get("id") != WRITING_STRATEGY_DEFAULT_ID]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_writing_strategies() -> dict[str, Any]:
    default = _default_writing_strategy_preset()
    custom = sorted(_read_custom_writing_strategies(), key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"default_id": WRITING_STRATEGY_DEFAULT_ID, "items": [default, *custom]}


def save_writing_strategy(name: str, body: str, strategy_id: str | None = None) -> dict[str, Any]:
    clean_name = name.strip()
    clean_body = body.strip()
    if not clean_name:
        raise ValueError("写文策略名称不能为空")
    if not clean_body:
        raise ValueError("写文策略正文不能为空")
    if strategy_id == WRITING_STRATEGY_DEFAULT_ID:
        raise ValueError("默认写文策略不能覆盖")

    now = datetime.now().isoformat(timespec="seconds")
    items = _read_custom_writing_strategies()
    target_id = (strategy_id or "").strip() or uuid4().hex
    saved: dict[str, Any] | None = None
    for item in items:
        if item["id"] != target_id:
            continue
        item.update({"name": clean_name, "body": clean_body, "readonly": False, "updated_at": now})
        saved = item
        break
    if saved is None:
        saved = {
            "id": target_id,
            "name": clean_name,
            "body": clean_body,
            "readonly": False,
            "created_at": now,
            "updated_at": now,
        }
        items.append(saved)
    _write_custom_writing_strategies(items)
    return saved


def delete_writing_strategy(strategy_id: str) -> None:
    clean_id = strategy_id.strip()
    if clean_id == WRITING_STRATEGY_DEFAULT_ID:
        raise ValueError("默认写文策略不能删除")
    items = _read_custom_writing_strategies()
    next_items = [item for item in items if item["id"] != clean_id]
    if len(next_items) == len(items):
        raise FileNotFoundError(f"写文策略不存在：{strategy_id}")
    _write_custom_writing_strategies(next_items)


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
    article_ref = project.get("article_path")
    if article_ref is not None:
        article_path = storage.resolve_root_path(str(article_ref)) if article_ref else None
        project["article_markdown"] = article_path.read_text(encoding="utf-8") if article_path and article_path.exists() else ""
    else:
        project["article_markdown"] = (workspace / "article.md").read_text(encoding="utf-8") if (workspace / "article.md").exists() else ""
    html_ref = project.get("html_path")
    if html_ref:
        html_path = storage.resolve_root_path(str(html_ref)) if html_ref else None
    else:
        html_path = workspace / "formatted_wechat.html"
        if not html_path.exists():
            html_path = workspace / "formatted.html"
    project["html"] = html_path.read_text(encoding="utf-8") if html_path and html_path.exists() else ""
    project["html_path"] = _relative(html_path) if html_path and html_path.exists() else ""
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
    _sync_project_metadata(project, workspace)


def _sync_project_metadata(project: dict[str, Any], workspace: Path) -> None:
    if database.configured_backend() != "mysql":
        return
    now = str(project.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    metadata = {
        key: value
        for key, value in project.items()
        if key not in {"article_markdown", "html"}
    }
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO writer_projects (
                id, owner_user_id, workspace_id, name, project_type, status,
                workspace_path, article_path, html_path, metadata_json,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                owner_user_id = VALUES(owner_user_id),
                workspace_id = VALUES(workspace_id),
                name = VALUES(name),
                project_type = VALUES(project_type),
                status = VALUES(status),
                workspace_path = VALUES(workspace_path),
                article_path = VALUES(article_path),
                html_path = VALUES(html_path),
                metadata_json = VALUES(metadata_json),
                updated_at = VALUES(updated_at)
            """,
            (
                str(project["id"]),
                str(project.get("owner_user_id") or "") or None,
                str(project.get("workspace_id") or "") or None,
                str(project.get("name") or ""),
                str(project.get("type") or "article"),
                str(project.get("status") or "active"),
                storage.storage_relative(workspace),
                str(project.get("article_path") or ""),
                str(project.get("html_path") or ""),
                json.dumps(metadata, ensure_ascii=False),
                str(project.get("created_at") or now),
                now,
            ),
        )
        conn.commit()


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


def infer_wechat_design_intent(design_strategy: str = "", theme: str = "tech") -> WechatDesignIntent:
    text = (design_strategy or "").lower()
    selected = theme if theme in DESIGN_THEME_PRESETS else "tech"
    if any(key in text for key in ("xiumi", "showy", "decor", "rich", "ornament", "秀米", "装饰", "卡片")):
        selected = "xiumi"
    elif any(key in text for key in ("research", "pm", "paper", "evidence", "研究", "证据", "论文")):
        selected = "research"
    elif any(key in text for key in ("column", "opinion", "story", "观点", "专栏", "叙事")):
        selected = "column"
    density = "high" if any(key in text for key in ("high", "dense", "多", "丰富", "重点")) else "medium"
    decoration = "high" if selected == "xiumi" or any(key in text for key in ("秀米", "装饰", "丰富")) else "medium"
    rhythm = "compact" if any(key in text for key in ("compact", "dense", "紧凑", "高密度")) else "comfortable"
    return WechatDesignIntent(
        theme=selected,
        emphasis_density=density,
        decoration_level=decoration,
        paragraph_rhythm=rhythm,
        quote_style="ribbon" if selected == "xiumi" else "card",
        divider_style="ornament" if selected == "xiumi" else "soft",
        image_style="framed" if selected in {"xiumi", "column"} else "rounded",
    )


def parse_markdown_article(markdown_text: str) -> tuple[str, list[MarkdownBlock]]:
    title = ""
    blocks: list[MarkdownBlock] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_ordered = False
    code_lines: list[str] = []
    in_code = False
    table_rows: list[list[str]] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(MarkdownBlock("paragraph", text=" ".join(item.strip() for item in paragraph if item.strip())))
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_ordered
        if list_items:
            blocks.append(MarkdownBlock("list", ordered=list_ordered, items=list_items))
            list_items = []
            list_ordered = False

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            blocks.append(MarkdownBlock("table", rows=table_rows))
            table_rows = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            blocks.append(MarkdownBlock("code", text="\n".join(code_lines)))
            code_lines = []

    for raw in markdown_text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                flush_list()
                flush_table()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            flush_table()
            continue
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
        if image_match:
            flush_paragraph()
            flush_list()
            flush_table()
            alt, src = image_match.groups()
            blocks.append(MarkdownBlock("image", alt=alt.strip(), src=src.strip()))
            continue
        if stripped in {"---", "***", "===", "[SEC]"}:
            flush_paragraph()
            flush_list()
            flush_table()
            blocks.append(MarkdownBlock("divider"))
            continue
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            flush_table()
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            if level == 1 and not title:
                title = text
            else:
                blocks.append(MarkdownBlock("heading", text=text, level=level))
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            flush_list()
            flush_table()
            blocks.append(MarkdownBlock("quote", text=stripped.lstrip("> ").strip()))
            continue
        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+(?:[.)]|、)\s*(.+)$", stripped)
        if unordered or ordered:
            flush_paragraph()
            flush_table()
            is_ordered = bool(ordered)
            item_text = (ordered or unordered).group(1).strip()  # type: ignore[union-attr]
            if list_items and list_ordered != is_ordered:
                flush_list()
            list_ordered = is_ordered
            list_items.append(item_text)
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
                table_rows.append(cells)
            continue
        flush_table()
        paragraph.append(stripped)
    flush_paragraph()
    flush_list()
    flush_table()
    if in_code:
        flush_code()
    return title, blocks


def render_inline_wechat(text: str, palette: dict[str, str]) -> str:
    escaped = html.escape(text or "")
    strong_style = f"font-weight:700;color:{palette['ink']};background:linear-gradient(transparent 62%,{palette['marker']} 0);padding:0 2px;"
    mark_style = f"background:{palette['marker']};color:{palette['ink']};padding:0 4px;border-radius:4px;"
    blue_style = f"background:{palette['accent_soft']};color:{palette['accent']};padding:0 4px;border-radius:4px;"
    pink_style = f"background:#fde8ef;color:{palette['error']};padding:0 4px;border-radius:4px;"
    green_style = f"background:#e7f3eb;color:{palette['accent']};padding:0 4px;border-radius:4px;"
    replacements = [
        (r"\*\*(.+?)\*\*", f'<strong style="{strong_style}">\\1</strong>'),
        (r"==(.+?)==", f'<span style="{mark_style}">\\1</span>'),
        (r"\+\+(.+?)\+\+", f'<span style="{blue_style}">\\1</span>'),
        (r"%%(.+?)%%", f'<span style="{pink_style}">\\1</span>'),
        (r"&amp;&amp;(.+?)&amp;&amp;", f'<span style="{green_style}">\\1</span>'),
        (r"!!(.+?)!!", f'<strong style="color:{palette["error"]};font-weight:700;">\\1</strong>'),
        (r"@@(.+?)@@", f'<strong style="color:{palette["accent"]};font-weight:700;">\\1</strong>'),
    ]
    for pattern, repl in replacements:
        escaped = re.sub(pattern, repl, escaped)
    return escaped


def wechat_html_from_markdown(markdown_text: str, design_strategy: str = "", theme: str = "tech") -> dict[str, Any]:
    title, blocks = parse_markdown_article(markdown_text)
    intent = infer_wechat_design_intent(design_strategy, theme)
    palette = DESIGN_THEME_PRESETS[intent.theme]
    paragraph_margin = "18px 0" if intent.paragraph_rhythm == "comfortable" else "12px 0"
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head><meta charset=\"utf-8\" /></head>",
        "<body>",
        f'<section data-fl-design-theme="{html.escape(intent.theme)}" style="max-width:680px;margin:0 auto;padding:24px 18px;background:{palette["surface"]};color:{palette["ink"]};font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',\'Microsoft YaHei\',sans-serif;line-height:1.85;box-sizing:border-box;">',
    ]
    if title:
        parts.append(
            f'<section data-fl-component="title_card" style="margin:0 0 28px;padding:22px 18px;border:1px solid {palette["line"]};border-left:5px solid {palette["accent"]};border-radius:12px;background:{palette["paper"]};box-sizing:border-box;">'
            f'<p style="margin:0 0 8px;color:{palette["accent"]};font-size:13px;font-weight:700;letter-spacing:1px;">FigureLearning</p>'
            f'<h1 style="margin:0;color:{palette["ink"]};font-size:24px;line-height:1.35;font-weight:800;">{render_inline_wechat(title, palette)}</h1>'
            "</section>"
        )
    section_index = 0
    paragraph_index = 0
    for block in blocks:
        if block.kind == "heading":
            section_index += 1
            parts.append(
                f'<section data-fl-component="section_divider" style="margin:30px 0 16px;padding:0 0 0 12px;border-left:4px solid {palette["accent"]};box-sizing:border-box;">'
                f'<p style="margin:0 0 4px;color:{palette["muted"]};font-size:12px;">{section_index:02d} / {palette["divider"]}</p>'
                f'<h2 style="margin:0;color:{palette["ink"]};font-size:20px;line-height:1.45;font-weight:800;">{render_inline_wechat(block.text, palette)}</h2>'
                "</section>"
            )
        elif block.kind == "paragraph":
            paragraph_index += 1
            component = "highlight_sentence" if paragraph_index % (2 if intent.emphasis_density == "high" else 4) == 0 else "paragraph"
            if component == "highlight_sentence":
                parts.append(
                    f'<p data-fl-component="highlight_sentence" style="margin:{paragraph_margin};padding:12px 14px;border-radius:10px;background:{palette["accent_soft"]};color:{palette["ink"]};font-size:15.5px;line-height:1.85;">{render_inline_wechat(block.text, palette)}</p>'
                )
            else:
                parts.append(f'<p style="margin:{paragraph_margin};color:{palette["ink"]};font-size:15.5px;line-height:1.85;">{render_inline_wechat(block.text, palette)}</p>')
        elif block.kind == "quote":
            parts.append(
                f'<blockquote data-fl-component="quote_card" style="margin:22px 0;padding:14px 16px;border-left:4px solid {palette["accent"]};background:{palette["accent_soft"]};border-radius:8px;color:{palette["ink"]};box-sizing:border-box;">'
                f'<p style="margin:0;font-size:15.5px;line-height:1.85;">{render_inline_wechat(block.text, palette)}</p></blockquote>'
            )
        elif block.kind == "list":
            tag = "ol" if block.ordered else "ul"
            attrs = 'data-fl-component="step_block"' if block.ordered else 'data-fl-component="data_card"'
            parts.append(f'<{tag} {attrs} style="margin:18px 0;padding:14px 18px 14px 32px;border:1px solid {palette["line"]};border-radius:10px;background:{palette["paper"]};color:{palette["ink"]};line-height:1.85;">')
            for item in block.items:
                parts.append(f'<li style="margin:6px 0;padding-left:2px;">{render_inline_wechat(item, palette)}</li>')
            parts.append(f"</{tag}>")
        elif block.kind == "image":
            parts.append(
                f'<section data-fl-component="image_caption" style="margin:24px 0;text-align:center;">'
                f'<img src="{html.escape(block.src)}" alt="{html.escape(block.alt)}" style="display:block;max-width:100%;height:auto;margin:0 auto;border-radius:10px;border:1px solid {palette["line"]};box-sizing:border-box;" />'
                f'<p style="margin:8px 0 0;color:{palette["muted"]};font-size:12px;line-height:1.6;">{html.escape(block.alt or "article image")}</p>'
                "</section>"
            )
        elif block.kind == "table":
            parts.append(f'<section data-fl-component="data_card" style="margin:22px 0;overflow:auto;"><table style="width:100%;border-collapse:collapse;font-size:14px;color:{palette["ink"]};">')
            for row_index, row in enumerate(block.rows):
                tag = "th" if row_index == 0 else "td"
                parts.append("<tr>")
                for cell in row:
                    parts.append(f'<{tag} style="border:1px solid {palette["line"]};padding:8px 10px;text-align:left;background:{palette["accent_soft"] if row_index == 0 else palette["surface"]};">{render_inline_wechat(cell, palette)}</{tag}>')
                parts.append("</tr>")
            parts.append("</table></section>")
        elif block.kind == "code":
            parts.append(f'<pre style="margin:20px 0;padding:14px;border-radius:10px;background:#17201c;color:#f8faf8;overflow:auto;"><code>{html.escape(block.text)}</code></pre>')
        elif block.kind == "divider":
            parts.append(f'<p data-fl-component="section_divider" style="margin:28px 0;text-align:center;color:{palette["accent"]};font-size:13px;">{palette["divider"]}</p>')
    parts.append(
        f'<section data-fl-component="footer_action" style="margin:34px 0 0;padding:16px;border-top:1px solid {palette["line"]};color:{palette["muted"]};font-size:13px;line-height:1.7;">'
        "全文完。发布前请在公众号草稿箱中二次确认图片、缩进和段落节奏。</section>"
    )
    parts.append("</section></body></html>")
    html_text = "\n".join(parts)
    sanitized, report = sanitize_wechat_html(html_text)
    return {
        "html": sanitized,
        "intent": intent.as_dict(),
        "blocks": len(blocks),
        "sanitize_report": report,
    }


def local_html_images(html_text: str, base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_text or "", flags=re.I):
        image_path = resolve_html_image_src(src, base_dir)
        if image_path:
            paths.append(image_path.resolve())
    return paths


def resolve_html_image_src(src: str, base_dir: Path) -> Path | None:
    if not src or src.startswith(("http://", "https://", "data:")):
        return None
    normalized = src.replace("\\", "/")
    candidates: list[Path] = []
    if normalized.startswith("/"):
        candidates.append(storage.STORAGE_ROOT / normalized.lstrip("/"))
        candidates.append(storage.ROOT / normalized.lstrip("/"))
    path = Path(normalized)
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(base_dir / path)
        candidates.append(storage.STORAGE_ROOT / path)
        candidates.append(storage.ROOT / path)
        alias_name = canonical_content_image_alias(path.name)
        if alias_name:
            alias_path = path.with_name(alias_name)
            candidates.append(base_dir / alias_path)
            candidates.append(storage.STORAGE_ROOT / alias_path)
            candidates.append(storage.ROOT / alias_path)
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


def publish_image_identity(image_path: Path) -> str | None:
    name = image_path.name.lower()
    if name.startswith("cover.") and image_path.suffix.lower() in WECHAT_IMAGE_EXTENSIONS:
        return "cover"
    return canonical_content_image_alias(name)


def prune_non_article_publish_images(html_text: str, base_dir: Path) -> str:
    seen_content: set[str] = set()
    if BeautifulSoup is None:
        def replace(match: re.Match[str]) -> str:
            src = match.group(2)
            image_path = resolve_html_image_src(src, base_dir)
            if not image_path:
                return match.group(0)
            identity = publish_image_identity(image_path)
            if identity == "cover":
                return ""
            if identity and identity in seen_content:
                return ""
            if identity:
                seen_content.add(identity)
            return match.group(0)

        return re.sub(r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>', replace, html_text, flags=re.I)

    soup = BeautifulSoup(html_text or "", "html.parser")
    for img in list(soup.find_all("img")):
        src = str(img.get("src") or "")
        image_path = resolve_html_image_src(src, base_dir)
        if not image_path:
            continue
        identity = publish_image_identity(image_path)
        remove = identity == "cover" or bool(identity and identity in seen_content)
        if identity and identity != "cover":
            seen_content.add(identity)
        if not remove:
            continue
        container = img.find_parent(["section", "figure", "p"])
        if container and len(container.find_all("img")) == 1:
            container.decompose()
        else:
            img.decompose()
    return str(soup)


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


def _clean_wechat_style(style: str) -> str:
    cleaned: list[str] = []
    for raw_part in (style or "").split(";"):
        if ":" not in raw_part:
            continue
        key, value = raw_part.split(":", 1)
        prop = key.strip().lower()
        val = value.strip()
        if not prop or prop not in WECHAT_ALLOWED_STYLE_PROPS:
            continue
        if "javascript:" in val.lower() or "expression(" in val.lower():
            continue
        cleaned.append(f"{prop}:{val}")
    return ";".join(cleaned)


def _normalize_wechat_lists(soup: BeautifulSoup, report: dict[str, Any]) -> None:
    """Render lists as plain rows so WeChat does not create empty bullet items."""
    for list_tag in list(soup.find_all(["ul", "ol"])):
        ordered = (list_tag.name or "").lower() == "ol"
        rows = []
        for index, item in enumerate(list_tag.find_all("li", recursive=False), start=1):
            for block_child in list(item.find_all(["p", "section"], recursive=False)):
                block_child.unwrap()
            inner_html = "".join(str(child) for child in item.contents).strip()
            if not inner_html or inner_html in {"<br/>", "<br>"}:
                continue
            marker = f"{index}." if ordered else "•"
            row = BeautifulSoup(
                (
                    '<p data-fl-list-row="1" '
                    'style="margin:8px 0;color:#201b16;font-size:15.5px;line-height:1.85;">'
                    f'<span style="display:inline-block;width:22px;color:#201b16;font-weight:700;vertical-align:top;">{html.escape(marker)}</span>'
                    '<span style="display:inline-block;width:calc(100% - 28px);vertical-align:top;">'
                    f"{inner_html}</span></p>"
                ),
                "html.parser",
            )
            if row.p:
                rows.append(row.p)
        if not rows:
            list_tag.decompose()
            continue
        container = soup.new_tag("section")
        container["data-fl-component"] = "wechat_list"
        container["style"] = _clean_wechat_style(
            str(list_tag.get("style", ""))
            or "margin:18px 0;padding:14px 18px;border:1px solid #ddd1bf;border-radius:10px;background:#fffaf1;"
        )
        if "padding" not in container["style"]:
            container["style"] = (container["style"] + ";padding:14px 18px").strip(";")
        for row in rows:
            container.append(row)
        list_tag.replace_with(container)
        report["normalized_lists"] = int(report.get("normalized_lists") or 0) + 1
        report["normalized_list_items"] = int(report.get("normalized_list_items") or 0) + len(rows)


def sanitize_wechat_html(html_text: str) -> tuple[str, dict[str, Any]]:
    report: dict[str, Any] = {
        "removed_tags": [],
        "stripped_attrs": [],
        "normalized_paragraphs": 0,
        "normalized_lists": 0,
        "normalized_list_items": 0,
        "image_count": 0,
        "local_image_count": 0,
        "remote_image_count": 0,
        "data_image_count": 0,
        "empty_image_count": 0,
        "forbidden_tag_count": 0,
        "ok": True,
    }
    if BeautifulSoup is None:
        sanitized = re.sub(r"<\s*(script|iframe|style|link|svg|canvas|video|audio|object|embed)\b.*?</\s*\1\s*>", "", html_text, flags=re.I | re.S)
        sanitized = re.sub(r"\s+on[a-z]+\s*=\s*(['\"]).*?\1", "", sanitized, flags=re.I | re.S)
        report["ok"] = not bool(re.search(r"<\s*(script|iframe|style|link|svg|canvas|video|audio|object|embed)\b", sanitized, flags=re.I))
        return sanitized, report

    soup = BeautifulSoup(html_text or "", "html.parser")
    if Comment is not None:
        for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
            node.extract()
    for tag in list(soup.find_all(True)):
        name = (tag.name or "").lower()
        if name in WECHAT_FORBIDDEN_TAGS:
            report["removed_tags"].append(name)
            report["forbidden_tag_count"] += 1
            tag.decompose()
            continue
        if name not in WECHAT_ALLOWED_TAGS and name not in {"html", "body", "head", "meta", "title"}:
            report["removed_tags"].append(name)
            tag.unwrap()
            continue
        for attr in list(tag.attrs):
            lower = attr.lower()
            if lower.startswith("on") or lower in {"class", "id"}:
                report["stripped_attrs"].append(f"{name}.{attr}")
                del tag.attrs[attr]
                continue
            if lower == "style":
                clean_style = _clean_wechat_style(str(tag.attrs[attr]))
                if clean_style:
                    tag.attrs[attr] = clean_style
                else:
                    del tag.attrs[attr]
                continue
            if name == "img" and lower in {"src", "alt"}:
                continue
            if lower.startswith("data-fl-"):
                continue
            report["stripped_attrs"].append(f"{name}.{attr}")
            del tag.attrs[attr]
        if name == "p":
            report["normalized_paragraphs"] += 1
            style = _clean_wechat_style(str(tag.get("style", "")))
            if "line-height" not in style:
                style = (style + ";line-height:1.85").strip(";")
            if "text-indent" in style:
                style = re.sub(r"(?:^|;)text-indent:[^;]+", "", style).strip(";")
            tag["style"] = style
        if name == "img":
            report["image_count"] += 1
            src = str(tag.get("src") or "").strip()
            if not src:
                report["empty_image_count"] += 1
            elif src.startswith("data:"):
                report["data_image_count"] += 1
            elif src.startswith(("http://", "https://")):
                report["remote_image_count"] += 1
            else:
                report["local_image_count"] += 1
            style = _clean_wechat_style(str(tag.get("style", "")))
            if "max-width" not in style:
                style = (style + ";max-width:100%").strip(";")
            if "height" not in style:
                style = (style + ";height:auto").strip(";")
            tag["style"] = style
    sanitized = str(soup)
    report["ok"] = not report["forbidden_tag_count"] and not report["data_image_count"] and not report["empty_image_count"]
    return sanitized, report


def inspect_wechat_html_for_publish(html_text: str, base_dir: Path) -> dict[str, Any]:
    sanitized, sanitize_report = sanitize_wechat_html(html_text)
    srcs = re.findall(r'<img[^>]+src=["\']([^"\']*)["\']', sanitized or "", flags=re.I)
    missing: list[str] = []
    data_images: list[str] = []
    remote_images: list[str] = []
    local_paths: list[str] = []
    for src in srcs:
        if not src:
            missing.append(src)
            continue
        if src.startswith("data:"):
            data_images.append(src[:48])
            continue
        if src.startswith(("http://", "https://")):
            remote_images.append(src)
            continue
        resolved = resolve_html_image_src(src, base_dir)
        if not resolved:
            missing.append(src)
            continue
        local_paths.append(str(resolved))
    forbidden_found = sorted(set(re.findall(r"<\s*(script|iframe|style|link|svg|canvas|video|audio|object|embed)\b", html_text or "", flags=re.I)))
    abnormal_indent = bool(re.search(r"text-indent\s*:\s*(?!0\b)[^;\"']+", html_text or "", flags=re.I))
    return {
        "sanitized_html": sanitized,
        "sanitize_report": sanitize_report,
        "image_src_count": len(srcs),
        "local_image_paths": sorted(set(local_paths)),
        "remote_images": remote_images,
        "missing_images": missing,
        "data_images": data_images,
        "forbidden_tags": forbidden_found,
        "abnormal_indent": abnormal_indent,
        "html_chars": len(sanitized),
        "ok": not missing and not data_images and not forbidden_found and not abnormal_indent and len(sanitized) <= WECHAT_HTML_MAX_CHARS,
    }


def prepare_html_for_publish(workspace: Path, html_path: Path) -> Path:
    html_text = html_path.read_text(encoding="utf-8")
    html_text = normalize_publish_image_paths(html_text, html_path.parent)
    html_text = prune_non_article_publish_images(html_text, html_path.parent)
    html_text, sanitize_report = sanitize_wechat_html(add_publish_emphasis(html_text))
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html_text, "html.parser")
        _normalize_wechat_lists(soup, sanitize_report)
        html_text = str(soup)
    output_path = workspace / "publish_ready.html"
    output_path.write_text(html_text, encoding="utf-8")
    (workspace / "publish_ready_sanitize_report.json").write_text(
        json.dumps(sanitize_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def wechat_access_token(timeout: float = 20, account_key: str | None = None) -> str:
    token_file = wechat_token_cache_file(account_key)
    config = wechat_config(account_key)
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
    refreshed = refresh_wechat_access_token(timeout=timeout, account_key=account_key)
    if not refreshed.get("ok"):
        raise RuntimeError(str(refreshed.get("message") or "微信 access_token 获取失败"))
    cached = json.loads(token_file.read_text(encoding="utf-8"))
    return str(cached["access_token"])


def _wechat_request_json(url: str, payload: dict[str, Any], timeout: float = 60, account_key: str | None = None) -> dict[str, Any]:
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
            clear_wechat_token_cache("40001 from built-in publisher", account_key=account_key)
        raise RuntimeError(f"微信接口错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def _wechat_upload_file(url: str, file_path: Path, field_name: str, timeout: float = 120, account_key: str | None = None) -> dict[str, Any]:
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
            clear_wechat_token_cache("40001 from built-in upload", account_key=account_key)
        raise RuntimeError(f"微信上传错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def _wechat_upload_cover(access_token: str, cover: Path, account_key: str | None = None) -> str:
    url = "https://api.weixin.qq.com/cgi-bin/material/add_material?type=image&access_token=" + urllib.parse.quote(access_token)
    data = _wechat_upload_file(url, cover, "media", account_key=account_key)
    media_id = data.get("media_id")
    if not media_id:
        raise RuntimeError(f"微信封面上传未返回 media_id：{json.dumps(data, ensure_ascii=False)}")
    return str(media_id)


def _wechat_upload_content_image(access_token: str, image_path: Path, account_key: str | None = None) -> str:
    url = "https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=" + urllib.parse.quote(access_token)
    data = _wechat_upload_file(url, image_path, "media", account_key=account_key)
    image_url = data.get("url")
    if not image_url:
        raise RuntimeError(f"微信正文图片上传未返回 url：{json.dumps(data, ensure_ascii=False)}")
    return str(image_url)


def _replace_local_images_with_wechat_urls(html_text: str, base_dir: Path, access_token: str, account_key: str | None = None) -> tuple[str, list[dict[str, str]]]:
    uploaded: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        before, src, after = match.groups()
        image_path = resolve_html_image_src(src, base_dir)
        if not image_path:
            return match.group(0)
        if image_path.suffix.lower() not in WECHAT_IMAGE_EXTENSIONS:
            raise RuntimeError(f"Unsupported WeChat content image type: {image_path}")
        if image_path.stat().st_size > WECHAT_IMAGE_MAX_BYTES:
            raise RuntimeError(f"WeChat content image exceeds 10MB: {image_path}")
        image_url = (
            _wechat_upload_content_image(access_token, image_path, account_key=account_key)
            if account_key
            else _wechat_upload_content_image(access_token, image_path)
        )
        uploaded.append({"path": str(image_path), "url": image_url})
        return f'<img{before}src="{html.escape(image_url)}"{after}>'

    html_text = re.sub(r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>', replace, html_text, flags=re.I)
    return html_text, uploaded


def prepare_publish_html_with_wechat_images(
    workspace: Path,
    html_path: Path,
    access_token: str,
    account_key: str | None = None,
) -> tuple[Path, str, list[dict[str, str]]]:
    publish_html_path = prepare_html_for_publish(workspace, html_path)
    source_html = html_path.read_text(encoding="utf-8")
    (workspace / "publish_source_html_snapshot.html").write_text(source_html, encoding="utf-8")
    html_text = publish_html_path.read_text(encoding="utf-8")
    before_report = inspect_wechat_html_for_publish(html_text, publish_html_path.parent)
    expected_local_count = len(before_report.get("local_image_paths") or [])
    html_text, uploaded_images = _replace_local_images_with_wechat_urls(html_text, publish_html_path.parent, access_token, account_key=account_key)
    html_text, sanitize_report = sanitize_wechat_html(html_text)
    publish_html_path.write_text(html_text, encoding="utf-8")
    after_report = inspect_wechat_html_for_publish(html_text, publish_html_path.parent)
    mapping_report = {
        "source_content_path": _relative(html_path),
        "publish_content_path": _relative(publish_html_path),
        "expected_local_image_count": expected_local_count,
        "uploaded_image_count": len(uploaded_images),
        "replacement_count": len(uploaded_images),
        "uploaded_images": uploaded_images,
        "before": {key: value for key, value in before_report.items() if key != "sanitized_html"},
        "after": {key: value for key, value in after_report.items() if key != "sanitized_html"},
        "sanitize_after_upload": sanitize_report,
        "ok": expected_local_count == len(uploaded_images) and not after_report.get("missing_images") and not after_report.get("data_images"),
    }
    (workspace / "publish_image_uploads.json").write_text(
        json.dumps(mapping_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return publish_html_path, html_text, uploaded_images


def publish_image_upload_report(workspace: Path) -> dict[str, Any]:
    report_path = workspace / "publish_image_uploads.json"
    if not report_path.exists():
        return {}
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "path": _relative(report_path), "error": "publish_image_uploads.json is not readable"}
    if isinstance(data, dict):
        data["path"] = _relative(report_path)
        return data
    return {"ok": False, "path": _relative(report_path), "error": "publish_image_uploads.json is not an object"}


def attach_publish_image_warning(result: dict[str, Any], workspace: Path) -> dict[str, Any]:
    report = publish_image_upload_report(workspace)
    if not report:
        return result
    expected = int(report.get("expected_local_image_count") or 0)
    uploaded = int(report.get("uploaded_image_count") or 0)
    replaced = int(report.get("replacement_count") or 0)
    result["image_upload_report"] = report
    result["uploaded_content_image_count"] = uploaded
    result["replaced_content_image_count"] = replaced
    if expected != uploaded or uploaded != replaced or not report.get("ok", False):
        result["warning"] = (
            f"Content image upload mismatch: expected {expected}, uploaded {uploaded}, replaced {replaced}. "
            "Open publish_image_uploads.json for the exact mapping."
        )
    return result


def publish_draft_builtin(
    workspace: Path,
    title: str,
    author: str = "",
    digest: str | None = None,
    cover_path: str | None = None,
    account_key: str | None = None,
) -> dict[str, Any]:
    author = resolve_publish_author(author, account_key)
    digest = truncate_utf8(digest, 120)
    invalidated_token = invalidate_stale_wechat_token_cache(account_key=account_key)
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    if not html_path.exists():
        raise FileNotFoundError("formatted.html 不存在，请先执行美编排版")
    cover = Path(cover_path) if cover_path else workspace / "cover.png"
    if not cover.is_absolute():
        cover = storage.ROOT / cover
    if not cover.exists():
        raise FileNotFoundError(f"找不到封面图：{cover}")

    access_token = wechat_access_token(account_key=account_key) if account_key else wechat_access_token()
    thumb_media_id = _wechat_upload_cover(access_token, cover, account_key=account_key) if account_key else _wechat_upload_cover(access_token, cover)
    publish_html_path, html_text, uploaded_images = prepare_publish_html_with_wechat_images(workspace, html_path, access_token, account_key=account_key)
    payload = {
        "articles": [
            {
                "title": title,
                "author": author,
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
    data = _wechat_request_json(url, payload, timeout=120, account_key=account_key) if account_key else _wechat_request_json(url, payload, timeout=120)
    media_id = data.get("media_id")
    result = {
        "returncode": 0,
        "stdout": json.dumps(data, ensure_ascii=False),
        "stderr": "",
        "author": author,
        "content_path": _relative(publish_html_path),
        "source_content_path": _relative(html_path),
        "invalidated_token_cache": invalidated_token,
        "cover_path": _relative(cover) if cover.exists() else str(cover),
        "thumb_media_id": thumb_media_id,
        "media_id": media_id,
        "uploaded_content_images": uploaded_images,
        "publisher": "builtin",
        "wechat_account_key": _safe_wechat_account_key(account_key),
        "wechat_account": wechat_binding_status(account_key).get("account_name") if account_key else wechat_config().get("account_name", ""),
    }
    attach_publish_image_warning(result, workspace)
    result_path = workspace / "publish_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["path"] = _relative(result_path)
    return result


def publish_preflight(
    workspace: Path,
    title: str,
    author: str = "",
    digest: str | None = None,
    cover_path: str | None = None,
    account_key: str | None = None,
) -> dict[str, Any]:
    author = resolve_publish_author(author, account_key)
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
    publish_sanitize: dict[str, Any] = {}
    publish_html_path = html_path
    html_text = ""
    if html_path.exists():
        publish_sanitize = sanitize_publish_html_preview(workspace)
        publish_html_path = workspace / "publish_ready.html"
        html_text = publish_html_path.read_text(encoding="utf-8") if publish_html_path.exists() else ""
    config: dict[str, Any] = {}
    config_file = wechat_config_file(account_key) if account_key else wechat_config_file()
    token_cache_file = wechat_token_cache_file(account_key) if account_key else wechat_token_cache_file()
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
    elif not account_key:
        config = wechat_config()
    token_cache: dict[str, Any] = {}
    if token_cache_file.exists():
        try:
            token_cache = json.loads(token_cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            token_cache = {}
    config_ready = bool(config.get("appid") and config.get("appsecret"))
    wechat_api_check: dict[str, Any] | None = (
        refresh_wechat_access_token(account_key=account_key) if account_key else refresh_wechat_access_token()
    ) if config_ready else None
    publish_inspection = publish_sanitize.get("publish_inspection") or (
        inspect_wechat_html_for_publish(html_text, publish_html_path.parent) if publish_html_path.exists() else {
        "ok": False,
        "local_image_paths": [],
        "missing_images": [],
        "data_images": [],
        "remote_images": [],
        "forbidden_tags": [],
        "abnormal_indent": False,
        "html_chars": 0,
        "sanitize_report": {},
        }
    )
    content_image_paths = sorted({str(path) for path in publish_inspection.get("local_image_paths", [])})
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
            "ok": publish_html_path.exists() and bool(html_text.strip()),
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
            "ok": utf8_len(author) <= 20,
            "detail": f"{author}，{utf8_len(author)} 字节，publisher 会按 20 字节保护",
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
            "key": "missing_images",
            "label": "正文图片路径可解析",
            "ok": not publish_inspection.get("missing_images"),
            "detail": "全部图片路径可解析" if not publish_inspection.get("missing_images") else "无法解析：" + ", ".join(map(str, publish_inspection.get("missing_images", [])[:5])),
        },
        {
            "key": "data_images",
            "label": "正文图片不使用 data URI",
            "ok": not publish_inspection.get("data_images"),
            "detail": "未发现 data: 图片" if not publish_inspection.get("data_images") else f"{len(publish_inspection.get('data_images', []))} 张 data: 图片无法写入草稿箱",
        },
        {
            "key": "remote_images",
            "label": "正文图片不依赖外链",
            "ok": not publish_inspection.get("remote_images"),
            "detail": "未发现外链图片" if not publish_inspection.get("remote_images") else f"{len(publish_inspection.get('remote_images', []))} 张外链图片建议先转存到微信",
        },
        {
            "key": "wechat_html_sanitize",
            "label": "HTML 标签与段落兼容性",
            "ok": not publish_inspection.get("forbidden_tags") and not publish_inspection.get("abnormal_indent"),
            "detail": (
                "未发现禁用标签或异常首行缩进"
                if not publish_inspection.get("forbidden_tags") and not publish_inspection.get("abnormal_indent")
                else f"禁用标签：{publish_inspection.get('forbidden_tags')}; 异常缩进：{publish_inspection.get('abnormal_indent')}"
            ),
        },
        {
            "key": "html_size",
            "label": "HTML 内容大小",
            "ok": int(publish_inspection.get("html_chars") or 0) <= WECHAT_HTML_MAX_CHARS,
            "detail": f"{publish_inspection.get('html_chars', 0)} 字符 / {WECHAT_HTML_MAX_CHARS} 上限",
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
    result = {
        "ok": not blocking,
        "checks": checks,
        "blocking": blocking,
        "digest": safe_digest,
        "digest_original_bytes": utf8_len(original_digest),
        "digest_bytes": utf8_len(safe_digest),
        "digest_truncated": digest_was_truncated,
        "wechat_account": wechat_binding_status(account_key) if account_key else {
            "configured": config_ready,
            "account_key": "",
            "account_name": config.get("account_name", ""),
            "author": config.get("author") or author or "Bobo",
            "appid": redact_appid(config.get("appid", "")),
            "config_path": str(config_file),
        },
        "publish_sanitize": publish_sanitize,
        "publish_inspection": {key: value for key, value in publish_inspection.items() if key != "sanitized_html"},
        "flow": [
            "1. 获取 access_token：GET /cgi-bin/token?grant_type=client_credential",
            "2. 上传封面永久素材：POST /cgi-bin/material/add_material?type=image，得到 thumb_media_id",
            "3. 上传正文本地图片并替换为微信图片 URL",
            "4. 新建草稿：POST /cgi-bin/draft/add，提交 title/author/digest/content/thumb_media_id",
            "5. 保存 publish_result.json，便于目录中断点续跑",
        ],
    }
    (workspace / "publish_preflight_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def sanitize_publish_html_preview(workspace: Path) -> dict[str, Any]:
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    if not html_path.exists():
        raise FileNotFoundError("formatted.html 不存在，请先执行美编排版")
    publish_html_path = prepare_html_for_publish(workspace, html_path)
    html_text = publish_html_path.read_text(encoding="utf-8")
    inspection = inspect_wechat_html_for_publish(html_text, publish_html_path.parent)
    result = {
        "ok": bool(inspection.get("ok")),
        "content_path": _relative(publish_html_path),
        "source_content_path": _relative(html_path),
        "html_chars": len(html_text),
        "publish_inspection": {key: value for key, value in inspection.items() if key != "sanitized_html"},
        "message": "Prepared sanitized publish_ready.html without uploading images.",
    }
    (workspace / "publish_sanitize_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def refresh_wechat_access_token(timeout: float = 20, account_key: str | None = None) -> dict[str, Any]:
    config_file = wechat_config_file(account_key)
    config = wechat_config(account_key)
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
    clear_wechat_token_cache("force refresh", account_key=account_key)
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
        token_file = wechat_token_cache_file(account_key)
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
            "account_key": _safe_wechat_account_key(account_key),
            "account_name": config.get("account_name", ""),
        }
    errmsg = data.get("errmsg", "")
    match = re.search(r"invalid ip ([0-9.]+)", errmsg)
    ip = match.group(1) if match else ""
    return {
        "ok": False,
        "message": f"微信接口返回错误：{data.get('errcode')} {errmsg}",
        "ip": ip,
        "raw": json.dumps(data, ensure_ascii=False),
        "account_key": _safe_wechat_account_key(account_key),
        "account_name": config.get("account_name", ""),
    }


def check_wechat_publish_ip(timeout: float = 20, account_key: str | None = None) -> dict[str, Any]:
    return refresh_wechat_access_token(timeout=timeout, account_key=account_key)


def _image_endpoint(setting: dict[str, Any]) -> str:
    return image_api_settings.image_endpoint(setting)


def _image_protocol(setting: dict[str, Any]) -> str:
    return image_api_settings.normalize_protocol(
        setting.get("protocol"),
        setting.get("provider"),
        setting.get("base_url"),
    )


def _image_payload(setting: dict[str, Any], prompt: str) -> dict[str, Any]:
    protocol = _image_protocol(setting)
    if protocol == image_api_settings.MINIMAX_PROTOCOL:
        response_format = str(setting.get("response_format") or "base64").strip() or "base64"
        return {
            "model": setting["model"],
            "prompt": prompt,
            "aspect_ratio": image_api_settings.normalize_aspect_ratio(setting.get("aspect_ratio"), setting.get("size")),
            "response_format": response_format,
        }

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
    suffix = "。主题明确，构图简洁，少量简体中文，适合公众号配图。"
    keep = max(12, max_chars - len(suffix))
    return (
        text[:keep].rstrip()
        + suffix
    )


def _is_disconnect_or_transient_image_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return 500 <= exc.code < 600
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "remotedisconnected" in text
        or "remote end closed connection" in text
        or "stream disconnected" in text
        or "connection reset" in text
        or "proxyerror" in text
    )


def _image_bypass_env_proxy(setting: dict[str, Any]) -> bool:
    provider = str(setting.get("provider") or "").strip().lower()
    base_url = str(setting.get("base_url") or "").strip().lower()
    return provider == "onefake" or "onefaka.com" in base_url


def _post_image_json(
    endpoint: str,
    payload: dict[str, Any],
    setting: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    request_payload = {key: value for key, value in payload.items() if key != "_protocol"}
    body = json.dumps(request_payload, ensure_ascii=True).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {setting['api_key']}",
        "Content-Type": "application/json",
    }
    if _image_bypass_env_proxy(setting):
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(30.0, timeout)), trust_env=False) as client:
            response = client.post(endpoint, content=body, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"图片 API 返回错误 {response.status_code}: {response.text[:1000]}")
        return response.json()

    request = urllib.request.Request(
        endpoint,
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _image_request_summary(endpoint: str, payload: dict[str, Any], prompt: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "protocol": payload.get("_protocol", ""),
        "model": payload.get("model"),
        "size": payload.get("size"),
        "quality": payload.get("quality", ""),
        "aspect_ratio": payload.get("aspect_ratio", ""),
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


def _write_generated_image_response(data: dict[str, Any], output_path: Path, timeout: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response_data = data.get("data")
    if isinstance(response_data, dict):
        image_base64 = response_data.get("image_base64")
        if isinstance(image_base64, list) and image_base64:
            output_path.write_bytes(base64.b64decode(str(image_base64[0])))
            return
        if isinstance(image_base64, str) and image_base64:
            output_path.write_bytes(base64.b64decode(image_base64))
            return

    first = (response_data or [{}])[0] if isinstance(response_data, list) else {}
    if isinstance(first, dict) and first.get("b64_json"):
        output_path.write_bytes(base64.b64decode(first["b64_json"]))
    elif isinstance(first, dict) and first.get("url"):
        _download_image(first["url"], output_path, timeout)
    else:
        raise RuntimeError(f"图片 API 返回结构中没有可用图片：{json.dumps(data, ensure_ascii=False)[:500]}")


def generate_image(prompt: str, output_path: Path, setting: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = setting or image_api_settings.active_setting()
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("图片提示词不能为空")

    endpoint = _image_endpoint(resolved)
    payload = _image_payload(resolved, prompt)
    payload["_protocol"] = _image_protocol(resolved)
    timeout = float(resolved.get("timeout") or 120)

    def request_once(current_payload: dict[str, Any]) -> dict[str, Any]:
        return _post_image_json(endpoint, current_payload, resolved, timeout)

    retry_used = False
    try:
        try:
            data = request_once(payload)
        except Exception as exc:
            should_retry = isinstance(exc, urllib.error.HTTPError) and 500 <= exc.code < 600 and len(prompt) > IMAGE_PROMPT_RETRY_MAX_CHARS
            if not should_retry:
                summary = _image_request_summary(endpoint, payload, prompt)
                if isinstance(exc, urllib.error.HTTPError):
                    detail = exc.read().decode("utf-8", "replace")
                    raise RuntimeError(
                        f"图片 API 返回错误 {exc.code}: {detail}; request={json.dumps(summary, ensure_ascii=False)}"
                    ) from exc
                raise
            retry_prompt = _compact_image_prompt(prompt)
            retry_payload = _image_payload(resolved, retry_prompt)
            retry_payload["_protocol"] = _image_protocol(resolved)
            try:
                data = request_once(retry_payload)
                prompt = retry_prompt
                payload = retry_payload
                retry_used = True
            except Exception as retry_exc:
                summary = _image_request_summary(endpoint, retry_payload, retry_prompt)
                if isinstance(retry_exc, urllib.error.HTTPError):
                    retry_detail = retry_exc.read().decode("utf-8", "replace")
                    raise RuntimeError(
                        "图片 API 返回错误 "
                        f"{retry_exc.code}: {retry_detail}; 已因上游连接异常自动改用精简提示词重试；"
                        f"request={json.dumps(summary, ensure_ascii=False)}"
                    ) from retry_exc
                raise RuntimeError(
                    "图片 API 调用失败："
                    f"{retry_exc}; 已因上游连接异常自动改用精简提示词重试；"
                    f"request={json.dumps(summary, ensure_ascii=False)}"
                ) from retry_exc
    except RuntimeError:
        raise
    except Exception as exc:
        summary = _image_request_summary(endpoint, payload, prompt)
        raise RuntimeError(
            f"图片 API 调用失败：{exc}; request={json.dumps(summary, ensure_ascii=False)}"
        ) from exc

    _write_generated_image_response(data, output_path, timeout)

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
    normalized_content_images = []
    for item in content_images:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        index = int(normalized_item.get("index") or 0)
        alias_name = canonical_content_image_alias(str(normalized_item.get("filename") or ""))
        if index > 0:
            alias_name = canonical_content_image_filename(index, Path(alias_name or normalized_item.get("filename") or "content.png").suffix or ".png")
        if alias_name:
            normalized_item["filename"] = alias_name
            if normalized_item.get("path"):
                normalized_item["path"] = _replace_path_name(str(normalized_item["path"]), alias_name)
        normalized_content_images.append(normalized_item)
    content_images = sorted(
        normalized_content_images,
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


def clear_writer_image_metadata(workspace: Path) -> dict[str, Any]:
    return _write_writer_image_metadata(workspace, {})


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


def _metadata_prompt_matches(metadata: dict[str, Any], kind: str, prompt: str, index: int | None = None) -> bool:
    if kind == "cover":
        item = metadata.get("cover")
    else:
        item = next(
            (
                existing for existing in metadata.get("content_images", [])
                if int(existing.get("index") or 0) == int(index or 0)
            ),
            None,
        )
    return isinstance(item, dict) and str(item.get("prompt") or "") == prompt


def generate_writer_image_item(
    workspace: Path,
    kind: str,
    prompt: str,
    index: int | None = None,
    aspect_ratio: str | None = None,
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
        filename = canonical_content_image_filename(index)
        image_path = workspace / filename
    else:
        raise ValueError(f"未知图片类型：{kind}")

    item = _existing_image_item(image_path, prompt) if _metadata_prompt_matches(metadata, kind, prompt, index) else None
    if item is None:
        try:
            setting = None
            clean_aspect_ratio = str(aspect_ratio or "").strip()
            if clean_aspect_ratio:
                setting = {**image_api_settings.active_setting(), "aspect_ratio": clean_aspect_ratio}
            item = generate_image(prompt, image_path, setting=setting)
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
    cover_aspect_ratio: str | None = None,
    content_aspect_ratio: str | None = None,
) -> dict[str, Any]:
    if cover_prompt:
        generate_writer_image_item(workspace, "cover", cover_prompt, aspect_ratio=cover_aspect_ratio)
    for index, prompt in enumerate(content_prompts or [], start=1):
        if prompt.strip():
            generate_writer_image_item(workspace, "content", prompt, index=index, aspect_ratio=content_aspect_ratio)
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
    prompt_by_name = {}
    for item in metadata.get("content_images", []):
        filename = item.get("filename")
        if not filename:
            continue
        prompt = item.get("prompt", "")
        prompt_by_name[filename] = prompt
        alias = canonical_content_image_alias(str(filename))
        if alias:
            prompt_by_name[alias] = prompt
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
    text = CONTENT_IMAGE_MARKDOWN_RE.sub("\n", text)
    text = re.sub(r"\n*!\[[^\]]*\]\((?:[^\)]*[\\/])?cover\.(?:png|jpe?g|webp|bmp)[^\)]*\)\n*", "\n", text, flags=re.I)
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
    list_mode: str | None = None
    in_code = False
    code_lines: list[str] = []

    def close_list() -> None:
        nonlocal list_mode
        if list_mode == "ul":
            body.append("</ul>")
        elif list_mode == "ol":
            body.append("</ol>")
        list_mode = None

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
                close_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not line.strip():
            close_list()
            continue
        if line.startswith("# "):
            title = title or line[2:].strip()
            continue
        if line.startswith("## "):
            close_list()
            body.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            close_list()
            body.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith(("- ", "* ")):
            if list_mode != "ul":
                close_list()
                body.append("<ul>")
                list_mode = "ul"
            body.append(f"<li>{html.escape(line[2:].strip())}</li>")
            continue
        ordered_match = re.match(r"^\d+(?:[.)]|、)\s*(.*)$", line)
        if ordered_match:
            if list_mode != "ol":
                close_list()
                body.append("<ol>")
                list_mode = "ol"
            body.append(f"<li>{html.escape(ordered_match.group(1).strip())}</li>")
            continue
        close_list()
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            alt, src = image_match.groups()
            body.append(
                f'<p><img src="{html.escape(src)}" alt="{html.escape(alt)}" '
                'style="max-width:100%;border-radius:8px;" /></p>'
            )
            continue
        body.append(f"<p>{html.escape(line)}</p>")
    close_list()
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
    try:
        rendered = wechat_html_from_markdown(
            article_path.read_text(encoding="utf-8"),
            design_strategy=design_strategy or DEFAULT_DESIGN_STRATEGY,
            theme=theme,
        )
        html_text = str(rendered["html"])
        html_path.write_text(html_text, encoding="utf-8")
        (workspace / "design_intent.json").write_text(
            json.dumps(rendered.get("intent") or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (workspace / "format_sanitize_report.json").write_text(
            json.dumps(rendered.get("sanitize_report") or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "path": _relative(html_path),
            "absolute_path": str(html_path),
            "html": html_text,
            "stdout": "generated by controlled WeChat template renderer",
            "stderr": "",
            "fallback": False,
            "ai_formatted": False,
            "template_formatted": True,
            "design_intent": rendered.get("intent"),
            "sanitize_report": rendered.get("sanitize_report"),
            "message": "已使用受控模板渲染器生成微信兼容 HTML。",
        }
    except Exception as exc:
        ai_error = str(exc)
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
    author: str = "",
    digest: str | None = None,
    cover_path: str | None = None,
    account_key: str | None = None,
) -> dict[str, Any]:
    author = resolve_publish_author(author, account_key)
    digest = truncate_utf8(digest, 120)
    if account_key or not PUBLISHER_SCRIPT.exists():
        return publish_draft_builtin(workspace, title, author=author, digest=digest, cover_path=cover_path, account_key=account_key)
    invalidated_token = invalidate_stale_wechat_token_cache(account_key=account_key)
    html_path = workspace / "formatted_wechat.html"
    if not html_path.exists():
        html_path = workspace / "formatted.html"
    if not html_path.exists():
        raise FileNotFoundError("formatted.html 不存在，请先执行美编排版")
    cover = Path(cover_path) if cover_path else workspace / "cover.png"
    if not cover.is_absolute():
        cover = storage.ROOT / cover
    access_token = wechat_access_token(account_key=account_key) if account_key else wechat_access_token()
    publish_html_path, _html_text, uploaded_images = prepare_publish_html_with_wechat_images(workspace, html_path, access_token, account_key=account_key)

    command = [
        str(PUBLISHER_SCRIPT),
        "--title",
        title,
        "--content",
        str(publish_html_path),
        "--author",
        author,
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
            "author": author,
            "content_path": _relative(publish_html_path),
            "source_content_path": _relative(html_path),
            "uploaded_content_images": uploaded_images,
            "cover_path": _relative(cover) if cover.exists() else str(cover),
            "timeout": True,
            "timeout_seconds": exc.timeout,
            "command": [str(sys.executable), *command],
        }
        attach_publish_image_warning(result, workspace)
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
        "author": author,
        "content_path": _relative(publish_html_path),
        "source_content_path": _relative(html_path),
        "invalidated_token_cache": invalidated_token,
        "cover_path": _relative(cover) if cover.exists() else str(cover),
        "uploaded_content_images": uploaded_images,
    }
    attach_publish_image_warning(result, workspace)
    media_ids = re.findall(r"media_id[:：]\s*([A-Za-z0-9_\-]+)", completed.stdout + "\n" + completed.stderr)
    if media_ids:
        result["media_id"] = media_ids[-1]
    result_path = workspace / "publish_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["path"] = _relative(result_path)
    if completed.returncode != 0:
        raw = (completed.stderr or completed.stdout or "").strip()
        if "错误码40001" in raw or "errcode\":40001" in raw or "AppSecret错误" in raw:
            clear_wechat_token_cache("40001 from publisher", account_key=account_key)
            raise RuntimeError(
                "微信返回 40001。已自动清除本地 access_token 缓存。"
                "如果 AppID/AppSecret 确认正确，请在发布页点击“检测微信IP”刷新 token 后再发布。原始错误："
                + raw
            )
        if "not in whitelist" in raw or "invalid ip" in raw:
            raise RuntimeError("微信 IP 白名单错误：" + raw)
        raise RuntimeError(raw or "转入草稿箱失败")
    return result
