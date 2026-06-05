from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl

import api_settings
import asr_settings
import deepseek_client
import document_parser
import image_api_settings
import media_parser
import ocr_client
import storage
import web_settings
import writer_tools
from markdown_writer import render_knowledge_markdown
from src.materials.entities import MaterialType
from src.shared.app_shell import GLOBAL_LIBRARIES, PRIMARY_SECTIONS, WORKSPACE_ENTRIES
from src.shared.responses import success_payload


router = APIRouter(prefix="/api/v2", tags=["v2-contracts"])


class CollectTextRequest(BaseModel):
    content: str
    title: str = ""


class CollectWebLinkRequest(BaseModel):
    url: HttpUrl
    title: str = ""


class InspectLinkRequest(BaseModel):
    url: HttpUrl


class CollectQueueItem(BaseModel):
    id: int | None = None
    content: str = ""
    url: str = ""
    title: str = ""
    link_type: str = ""
    extraction_strategy: str = ""
    access_status: str = ""


class CollectRawMarkdownRequest(BaseModel):
    material_type: str
    title: str = ""
    items: list[CollectQueueItem]


class LearnRefineKnowledgeClusterRequest(BaseModel):
    raw_paths: list[str]
    title: str = ""


class LearnSaveFocusRequest(BaseModel):
    raw_paths: list[str]
    markdown: str
    title: str = ""


class LibrarySourceRequest(BaseModel):
    library: str
    markdown_path: str
    title: str = ""


class MinePerspectiveProfile(BaseModel):
    id: str = ""
    name: str
    role: str = ""
    target_subject: str = ""
    purpose: str = ""
    focus_dimensions: list[str] = []
    analysis_questions: list[str] = []
    output_style: str = ""
    evidence_rule: str = ""


class MineInterpretRequest(BaseModel):
    sources: list[LibrarySourceRequest]
    perspective: MinePerspectiveProfile


class MineSavePerspectiveRequest(BaseModel):
    sources: list[LibrarySourceRequest]
    perspective: MinePerspectiveProfile
    markdown: str
    title: str = ""


class CreateProjectRequest(BaseModel):
    name: str
    project_type: str = "article"
    description: str = ""


class UpdateCreateProjectRequest(BaseModel):
    name: str | None = None
    project_type: str | None = None
    description: str | None = None


class CreateProjectFilesRequest(BaseModel):
    files: list[LibrarySourceRequest]


class CreateWriterTopicRequest(BaseModel):
    library_files: list[LibrarySourceRequest] | None = None


class CreateWriterArticleRequest(BaseModel):
    topic: dict[str, object]
    library_files: list[LibrarySourceRequest] | None = None


class CreateWriterReviseRequest(BaseModel):
    markdown: str
    instruction: str
    library_files: list[LibrarySourceRequest] | None = None


class CreateWriterFormatRequest(BaseModel):
    markdown: str | None = None
    theme: str = "tech"


class CreateWriterPublishPreflightRequest(BaseModel):
    title: str = ""
    author: str = "Bobo"
    digest: str | None = None
    cover_path: str | None = None


class WebSettingsRequest(BaseModel):
    app_name: str = "知识酷"
    workspace_name: str = "Research OS"
    default_route: str = "/collect"
    global_library_refresh_seconds: int = 8
    right_library_visible: bool = True
    language: str = "zh-CN"


class ApiSettingRequest(BaseModel):
    id: str | None = None
    name: str = ""
    provider: str = "compatible"
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    make_active: bool = True


class SettingActiveRequest(BaseModel):
    id: str


class ApiSettingTestRequest(BaseModel):
    id: str | None = None
    setting: ApiSettingRequest | None = None


class AsrSettingRequest(BaseModel):
    provider: str = "compatible"
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    timeout: float | None = None


@router.get("/material-types")
def material_types() -> dict[str, object]:
    return success_payload(
        data=[
            {"id": MaterialType.TEXT.value, "label": "Text"},
            {"id": MaterialType.SCREENSHOT.value, "label": "Screenshot"},
            {"id": MaterialType.DOCUMENT.value, "label": "Document"},
            {"id": MaterialType.MEDIA.value, "label": "Media"},
            {"id": MaterialType.LINK.value, "label": "Link"},
        ]
    )


@router.get("/app-shell")
def app_shell() -> dict[str, object]:
    return success_payload(
        data={
            "primarySections": [
                {
                    "id": section.id,
                    "label": section.label,
                    "navLabel": section.nav_label,
                    "navDescription": section.nav_description,
                    "route": section.route,
                    "priority": section.priority,
                    "purpose": section.purpose,
                }
                for section in PRIMARY_SECTIONS
            ],
            "workspaceEntries": [
                {
                    "id": entry.id,
                    "label": entry.label,
                    "route": entry.route,
                    "shellSection": entry.shell_section,
                    "capabilityId": entry.capability_id,
                    "priority": entry.priority,
                    "surface": entry.surface,
                }
                for entry in WORKSPACE_ENTRIES
            ],
            "globalLibraries": [
                {
                    "id": library.id,
                    "label": library.label,
                    "sourceModule": library.source_module,
                    "defaultStatus": library.default_status,
                    "purpose": library.purpose,
                }
                for library in GLOBAL_LIBRARIES
            ],
        }
    )


@router.get("/settings/overview")
def settings_overview() -> dict[str, object]:
    web = _safe_payload(web_settings.payload)
    llm = _safe_payload(api_settings.list_payload)
    asr = _safe_payload(asr_settings.list_payload)
    image = _safe_payload(image_api_settings.list_payload)
    return success_payload(
        data={
            "sections": [
                _single_setting_section("web", "Web", web),
                _list_settings_section("llm", "LLM", llm),
                _single_setting_section("asr", "ASR", asr),
                _list_settings_section("image", "Image generation", image),
            ]
        }
    )


@router.get("/settings/web")
def settings_web() -> dict[str, object]:
    return success_payload(data=web_settings.payload())


@router.post("/settings/web")
def save_settings_web(request: WebSettingsRequest) -> dict[str, object]:
    return success_payload(data={"ok": True, "item": web_settings.save_setting(request.model_dump())})


@router.get("/settings/api")
def settings_api() -> dict[str, object]:
    return success_payload(data=api_settings.list_payload())


@router.post("/settings/api")
def save_settings_api(request: ApiSettingRequest) -> dict[str, object]:
    try:
        item = api_settings.save_setting(request.model_dump())
        return success_payload(data={"ok": True, "item": item, **api_settings.list_payload()})
    except ValueError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/api/active")
def activate_settings_api(request: SettingActiveRequest) -> dict[str, object]:
    try:
        item = api_settings.set_active(request.id)
        return success_payload(data={"ok": True, "item": item, **api_settings.list_payload()})
    except (KeyError, ValueError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.delete("/settings/api/{setting_id}")
def delete_settings_api(setting_id: str) -> dict[str, object]:
    try:
        api_settings.delete_setting(setting_id)
        return success_payload(data={"ok": True, **api_settings.list_payload()})
    except KeyError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/api/test")
def test_settings_api(request: ApiSettingTestRequest) -> dict[str, object]:
    try:
        setting = _resolve_api_test_setting(request)
        return success_payload(data={"ok": True, "diagnostic": deepseek_client.diagnose(setting)})
    except Exception as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/settings/asr")
def settings_asr() -> dict[str, object]:
    return success_payload(data=asr_settings.list_payload())


@router.post("/settings/asr")
def save_settings_asr(request: AsrSettingRequest) -> dict[str, object]:
    try:
        item = asr_settings.save_setting(request.model_dump())
        return success_payload(data={"ok": True, "item": item, **asr_settings.list_payload()})
    except ValueError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/asr/test")
def test_settings_asr(request: AsrSettingRequest) -> dict[str, object]:
    try:
        payload = request.model_dump()
        if not payload.get("api_key"):
            payload["api_key"] = asr_settings.load_setting().get("api_key")
        saved = asr_settings.save_setting(payload)
        setting = asr_settings.active_setting()
        message = f"{setting.get('provider')} / {setting.get('model')} 配置字段完整。"
        asr_settings.mark_test_result(True, message)
        return success_payload(data={"ok": True, "item": saved, "message": message})
    except (ValueError, RuntimeError) as exc:
        asr_settings.mark_test_result(False, str(exc))
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/libraries/{library_id}/files")
def library_files(library_id: str, pending_focus: bool = False) -> dict[str, object]:
    return success_payload(data={"items": _list_library_files(library_id, pending_focus=pending_focus)})


@router.post("/collect/text")
def collect_text(request: CollectTextRequest) -> dict[str, object]:
    content = request.content.strip()
    if not content:
        return success_payload(data={"ok": False, "error": "文本不能为空"})

    title = request.title.strip() or _title_from_text(content, "文本原料")
    item = _write_raw_markdown(material_type="text", title=title, body=content, source="手动输入")
    return success_payload(data={"ok": True, "item": item})


@router.post("/collect/web-link")
def collect_web_link(request: CollectWebLinkRequest) -> dict[str, object]:
    url = str(request.url)
    title = request.title.strip()
    try:
        fetched = _extract_link_text(url, CollectQueueItem(url=url, title=title))
        title = title or fetched["title"] or url
        body = _render_link_markdown_block(1, url, title, fetched)
        fetch_error = ""
    except (OSError, UnicodeDecodeError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        title = title or url
        fetch_error = str(exc)
        body = f"网页链接：{url}\n\n读取失败：{fetch_error}"

    item = _write_raw_markdown(
        material_type="web_link",
        title=title,
        body=body,
        source=url,
        extra_meta={"读取状态": "失败" if fetch_error else "成功"},
    )
    if fetch_error:
        item["fetch_error"] = fetch_error
    return success_payload(data={"ok": True, "item": item})


@router.post("/collect/inspect-link")
def inspect_link(request: InspectLinkRequest) -> dict[str, object]:
    return success_payload(data={"ok": True, "item": _inspect_link(str(request.url))})


@router.post("/collect/raw-markdown")
def collect_raw_markdown(request: CollectRawMarkdownRequest) -> dict[str, object]:
    if not request.items:
        return success_payload(data={"ok": False, "error": "待分析队列不能为空"})

    material_type = request.material_type.strip()
    title = request.title.strip() or _default_raw_title(material_type, request.items)
    try:
        body, sources, errors = _extract_queue_text(material_type, request.items)
    except (KeyError, ValueError, OSError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})

    if not body.strip():
        error = "未提取到可保存的文本"
        if errors:
            error = f"{error}；" + "；".join(errors[:3])
        return success_payload(data={"ok": False, "error": error, "errors": errors})

    body = _clean_raw_markdown_body(body)
    polish_meta = _polish_raw_material(material_type, body, title)
    if polish_meta["markdown"]:
        body = polish_meta["markdown"]
    if polish_meta["title"]:
        title = polish_meta["title"]
    title = _resolve_raw_title(request.title, title, body)

    item = _write_raw_markdown(
        material_type=material_type,
        title=title,
        body=body,
        source="; ".join(sources)[:1000] if sources else material_type,
        extra_meta={
            "队列数量": str(len(request.items)),
            "失败数量": str(len(errors)),
            **polish_meta["extra_meta"],
        },
    )
    return success_payload(data={"ok": True, "item": item, "errors": errors, "polish": polish_meta["response"]})


@router.post("/learn/refine-knowledge-cluster")
def learn_refine_knowledge_cluster(request: LearnRefineKnowledgeClusterRequest) -> dict[str, object]:
    if not request.raw_paths:
        return success_payload(data={"ok": False, "error": "请先从原料库选择待处理文件"})

    try:
        sources = [_read_raw_material_file(path) for path in request.raw_paths]
        combined_raw_text = _combine_raw_material_sources(sources)
        if not combined_raw_text.strip():
            return success_payload(data={"ok": False, "error": "选中的原料文件没有可学习文本"})

        source_hash = hashlib.sha256(
            "|".join(item["relative_path"] for item in sources).encode("utf-8")
        ).hexdigest()
        existing = storage.get_knowledge_by_hash(source_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return success_payload(data={"ok": True, "item": existing, "skipped": True})

        setting = api_settings.active_setting()
        knowledge, learned_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=setting,
        )
        _ = learned_raw_text
        if request.title.strip():
            knowledge.title = request.title.strip()
        markdown = _render_focus_markdown(knowledge, sources)
        return success_payload(
            data={
                "ok": True,
                "source_files": sources,
                "source_hash": source_hash,
                "cluster_count": len(knowledge.clusters),
                "markdown": markdown,
                "existing_item": existing,
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/learn/focus-file")
def learn_save_focus_file(request: LearnSaveFocusRequest) -> dict[str, object]:
    if not request.raw_paths:
        return success_payload(data={"ok": False, "error": "请先选择本次重点库文件对应的原料"})
    markdown = request.markdown.strip()
    if not markdown:
        return success_payload(data={"ok": False, "error": "重点库 Markdown 不能为空"})

    try:
        sources = [_read_raw_material_file(path) for path in request.raw_paths]
        source_hash = _raw_sources_hash(sources)
        entry = storage.create_or_update_knowledge_entry(
            [],
            source_hash,
            source_type="raw_materials",
            source_ids=[item["relative_path"] for item in sources],
        )
        title = request.title.strip() or _markdown_title(markdown) or "focus-knowledge"
        markdown_path = storage.markdown_path_for(title, source_hash, entry.get("created_at"))
        markdown_path.write_text(markdown, encoding="utf-8")
        meta = _markdown_meta(markdown)
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=str(markdown_path.relative_to(storage.ROOT)),
            title=title,
            topic=meta.get("主题") or "",
            tags=json.dumps(_tags_from_meta(meta), ensure_ascii=False),
            status="ready",
            error_message=None,
            graph_status="not_ingested",
            graph_error_message=None,
        )
        return success_payload(
            data={
                "ok": True,
                "item": updated,
                "source_files": sources,
                "source_hash": source_hash,
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/mine/perspectives")
def mine_perspectives() -> dict[str, object]:
    return success_payload(data={"items": _list_perspective_profiles()})


@router.post("/mine/perspectives")
def mine_save_perspective(profile: MinePerspectiveProfile) -> dict[str, object]:
    saved = storage.upsert_perspective_profile(profile.model_dump())
    return success_payload(data={"ok": True, "item": saved, "items": _list_perspective_profiles()})


@router.delete("/mine/perspectives/{profile_id}")
def mine_delete_perspective(profile_id: str) -> dict[str, object]:
    if not profile_id.startswith("custom_"):
        return success_payload(data={"ok": False, "error": "预设视角不能删除，请先复制为自定义视角"})
    try:
        deleted = storage.delete_perspective_profile(profile_id)
    except KeyError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})
    return success_payload(data={"ok": True, "item": deleted, "items": _list_perspective_profiles()})


@router.post("/mine/interpret")
def mine_interpret(request: MineInterpretRequest) -> dict[str, object]:
    if not request.sources:
        return success_payload(data={"ok": False, "error": "请先从全局库勾选原料库或重点库文件加入待解读队列"})
    try:
        sources = [_read_mine_source(item) for item in request.sources]
        setting = api_settings.active_setting()
        result = deepseek_client.interpret_from_perspective(
            sources,
            request.perspective.model_dump(),
            setting=setting,
        )
        markdown = _render_perspective_markdown(result, request.perspective, sources)
        return success_payload(
            data={
                "ok": True,
                "markdown": markdown,
                "source_files": sources,
                "title": result.title,
                "perspective": request.perspective.model_dump(),
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/mine/perspective-file")
def mine_save_perspective_file(request: MineSavePerspectiveRequest) -> dict[str, object]:
    if not request.sources:
        return success_payload(data={"ok": False, "error": "视角解读必须保留来源文件"})
    markdown = request.markdown.strip()
    if not markdown:
        return success_payload(data={"ok": False, "error": "视角 Markdown 不能为空"})
    try:
        sources = [_read_mine_source(item) for item in request.sources]
        title = request.title.strip() or _markdown_title(markdown) or f"{request.perspective.name}视角解读"
        source_hash = hashlib.sha256(
            "|".join(f"{item['library']}:{item['relative_path']}" for item in sources).encode("utf-8")
        ).hexdigest()
        now = datetime.now().isoformat(timespec="seconds")
        dated_dir = storage.MINING_DIR / datetime.now().strftime("%Y-%m-%d")
        dated_dir.mkdir(parents=True, exist_ok=True)
        path = dated_dir / f"{storage.safe_filename(title, fallback='perspective')}_{source_hash[:8]}.md"
        path.write_text(markdown, encoding="utf-8")
        return success_payload(
            data={
                "ok": True,
                "item": {
                    "title": title,
                    "library": "perspective",
                    "status": "已解读",
                    "source": request.perspective.name,
                    "perspective": request.perspective.model_dump(),
                    "markdown_path": str(path.relative_to(storage.ROOT)),
                    "created_at": now,
                    "source_files": sources,
                    "hash": source_hash,
                },
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/create/projects")
def create_projects() -> dict[str, object]:
    return success_payload(data={"items": writer_tools.list_projects()})


@router.post("/create/projects")
def create_project(request: CreateProjectRequest) -> dict[str, object]:
    project = writer_tools.create_project(
        name=request.name,
        project_type=request.project_type,
        description=request.description,
    )
    return success_payload(data={"item": project})


@router.get("/create/projects/{project_id}")
def read_create_project(project_id: str) -> dict[str, object]:
    return success_payload(data={"item": writer_tools.load_project(project_id)})


@router.patch("/create/projects/{project_id}")
def update_create_project(project_id: str, request: UpdateCreateProjectRequest) -> dict[str, object]:
    updates: dict[str, object] = {}
    if request.name is not None:
        updates["name"] = request.name.strip() or "未命名创作项目"
    if request.project_type is not None:
        updates["type"] = request.project_type
    if request.description is not None:
        updates["description"] = request.description.strip()
    project = writer_tools.update_project(project_id, **updates)
    return success_payload(data={"item": project})


@router.post("/create/projects/{project_id}/library-files")
def update_create_project_files(project_id: str, request: CreateProjectFilesRequest) -> dict[str, object]:
    sources = [_read_create_source(item) for item in request.files]
    project = writer_tools.set_project_library_files(project_id, sources)
    return success_payload(data={"item": project})


@router.post("/create/projects/{project_id}/writer/topics")
def create_writer_topics(project_id: str, request: CreateWriterTopicRequest) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
    sources = _project_writer_sources(project, request.library_files)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    setting = api_settings.active_setting()
    result = deepseek_client.generate_topics(_writer_markdown_files(sources), setting=setting)
    return success_payload(data={"ok": True, **result.model_dump()})


@router.post("/create/projects/{project_id}/writer/article")
def create_writer_article(project_id: str, request: CreateWriterArticleRequest) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
    if project.get("type") != "article":
        return success_payload(data={"ok": False, "error": "当前只实现文章项目，图文和视频创作暂未开放"})
    sources = _project_writer_sources(project, request.library_files)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    setting = api_settings.active_setting()
    result = deepseek_client.generate_wechat_article(
        request.topic,
        _writer_markdown_files(sources),
        setting=setting,
    )
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, result.markdown)
    project = writer_tools.update_project(project_id, topic=request.topic)
    return success_payload(
        data={
            "ok": True,
            **result.model_dump(),
            "project": project,
            "workspace": str(workspace.relative_to(storage.ROOT)),
            "article_path": str(article_path.relative_to(storage.ROOT)),
        }
    )


@router.post("/create/projects/{project_id}/writer/revise")
def create_writer_revise(project_id: str, request: CreateWriterReviseRequest) -> dict[str, object]:
    if not request.instruction.strip():
        return success_payload(data={"ok": False, "error": "请填写修改要求"})
    project = writer_tools.load_project(project_id)
    sources = _project_writer_sources(project, request.library_files)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    setting = api_settings.active_setting()
    result = deepseek_client.revise_wechat_article(
        request.markdown,
        request.instruction,
        _writer_markdown_files(sources),
        setting=setting,
    )
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, result.markdown)
    version_path = writer_tools.write_article(
        workspace,
        result.markdown,
        f"article_revised_{datetime.now().strftime('%H%M%S')}.md",
    )
    project = writer_tools.update_project(project_id)
    return success_payload(
        data={
            "ok": True,
            **result.model_dump(),
            "project": project,
            "workspace": str(workspace.relative_to(storage.ROOT)),
            "article_path": str(article_path.relative_to(storage.ROOT)),
            "version_path": str(version_path.relative_to(storage.ROOT)),
        }
    )


@router.post("/create/projects/{project_id}/writer/format")
def create_writer_format(project_id: str, request: CreateWriterFormatRequest) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
    if project.get("type") != "article":
        return success_payload(data={"ok": False, "error": "当前只实现文章项目，图文和视频创作暂未开放"})
    workspace = writer_tools.resolve_project_workspace(project_id)
    result = writer_tools.format_article(workspace, markdown=request.markdown, theme=request.theme)
    project = writer_tools.update_project(project_id)
    return success_payload(
        data={
            "ok": True,
            "project": project,
            "workspace": str(workspace.relative_to(storage.ROOT)),
            **result,
        }
    )


@router.post("/create/projects/{project_id}/writer/publish/preflight")
def create_writer_publish_preflight(project_id: str, request: CreateWriterPublishPreflightRequest) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
    workspace = writer_tools.resolve_project_workspace(project_id)
    title = request.title.strip() or project.get("name") or "未命名文章"
    result = writer_tools.publish_preflight(
        workspace,
        title,
        author=request.author or "Bobo",
        digest=request.digest,
        cover_path=request.cover_path,
    )
    return success_payload(
        data={
            "project": project,
            "workspace": str(workspace.relative_to(storage.ROOT)),
            **result,
        }
    )


@router.post("/create/projects/{project_id}/writer/publish")
def create_writer_publish(project_id: str, request: CreateWriterPublishPreflightRequest) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
    workspace = writer_tools.resolve_project_workspace(project_id)
    title = request.title.strip() or project.get("name") or "未命名文章"
    preflight = writer_tools.publish_preflight(
        workspace,
        title,
        author=request.author or "Bobo",
        digest=request.digest,
        cover_path=request.cover_path,
    )
    if not preflight.get("ok"):
        return success_payload(
            data={
                "ok": False,
                "error": "发布预检未通过",
                "project": project,
                "workspace": str(workspace.relative_to(storage.ROOT)),
                "preflight": preflight,
            }
        )
    result = writer_tools.publish_draft(
        workspace,
        title,
        author=request.author or "Bobo",
        digest=request.digest,
        cover_path=request.cover_path,
    )
    return success_payload(
        data={
            "ok": True,
            "project": writer_tools.load_project(project_id),
            "workspace": str(workspace.relative_to(storage.ROOT)),
            "preflight": preflight,
            **result,
        }
    )


def _list_settings_section(section_id: str, label: str, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("error"):
        return _settings_error_section(section_id, label, payload["error"])
    items = payload.get("items") or []
    active_id = payload.get("active_id")
    active = next((item for item in items if item.get("id") == active_id), None)
    return {
        "id": section_id,
        "label": label,
        "configured": bool(active or items),
        "activeId": active_id,
        "activeName": active.get("name") if active else "",
        "itemCount": len(items),
    }


def _resolve_api_test_setting(request: ApiSettingTestRequest) -> dict[str, object]:
    if request.setting:
        payload = request.setting.model_dump()
        if payload.get("id") and not payload.get("api_key"):
            existing = api_settings.get_setting(payload["id"])
            if existing:
                payload["api_key"] = existing.get("api_key")
        return {
            "id": payload.get("id") or "temporary",
            "name": payload.get("name") or "临时 API",
            "provider": payload.get("provider") or "compatible",
            "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
            "model": (payload.get("model") or "").strip(),
            "api_key": (payload.get("api_key") or "").strip(),
            "timeout": payload.get("timeout") or 60,
            "max_retries": payload.get("max_retries") or 0,
        }
    if request.id:
        setting = api_settings.get_setting(request.id)
        if setting is None:
            raise KeyError("API 配置不存在")
        return setting
    return api_settings.active_setting()


def _single_setting_section(section_id: str, label: str, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("error"):
        return _settings_error_section(section_id, label, payload["error"])
    item = payload.get("item") or {}
    return {
        "id": section_id,
        "label": label,
        "configured": bool(item.get("configured")),
        "activeId": item.get("provider") or "",
        "activeName": item.get("model") or item.get("provider") or "",
        "itemCount": 1 if item else 0,
    }


def _safe_payload(loader) -> dict[str, object]:
    try:
        return loader()
    except OSError as exc:
        return {"error": exc.__class__.__name__}


def _settings_error_section(section_id: str, label: str, error: object) -> dict[str, object]:
    return {
        "id": section_id,
        "label": label,
        "configured": False,
        "activeId": "",
        "activeName": "",
        "itemCount": 0,
        "error": str(error),
    }


def _list_library_files(library_id: str, pending_focus: bool = False) -> list[dict[str, object]]:
    roots = {
        "raw": storage.ROOT / "raw_materials",
        "focus": storage.KNOWLEDGE_DIR,
        "perspective": storage.MINING_DIR,
    }
    root = roots.get(library_id)
    if root is None:
        raise ValueError(f"Unsupported library: {library_id}")
    if not root.exists():
        return []

    files = sorted(root.rglob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    items = [_library_file_payload(path, library_id) for path in files[:200]]
    if library_id == "raw" and pending_focus:
        processed_paths = _processed_raw_material_paths()
        items = [item for item in items if item.get("markdown_path") not in processed_paths]
    return items


def _library_file_payload(path: Path, library_id: str) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    title = _markdown_title(text) or path.stem
    meta = _markdown_meta(text)
    stat = path.stat()
    relative_path = str(path.relative_to(storage.ROOT))
    material_type = meta.get("材料类型") or meta.get("material_type") or ""
    tags = [material_type] if material_type else []
    return {
        "id": relative_path,
        "title": title,
        "library": library_id,
        "status": meta.get("状态") or _default_library_status(library_id),
        "source": meta.get("来源") or meta.get("Source") or "",
        "material_type": material_type,
        "markdown_path": relative_path,
        "created_at": meta.get("收集时间") or datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "size": stat.st_size,
        "tags": tags,
    }


def _markdown_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _markdown_meta(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines()[1:30]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            if stripped and meta:
                break
            continue
        content = stripped[2:].strip()
        if "：" in content:
            key, value = content.split("：", 1)
        elif ":" in content:
            key, value = content.split(":", 1)
        else:
            continue
        meta[key.strip()] = value.strip()
    return meta


def _default_library_status(library_id: str) -> str:
    return {"raw": "未处理", "focus": "已提炼", "perspective": "已解读"}.get(library_id, "")


def _default_perspective_profiles() -> list[dict[str, object]]:
    return [
        {
            "id": "writer",
            "name": "作家视角",
            "role": "观察文本如何组织信息、制造节奏和形成表达张力",
            "target_subject": "原文表达、叙事顺序、论证结构、可复用写法",
            "purpose": "从材料中拆出可迁移的创作逻辑，而不是复述内容",
            "focus_dimensions": ["文字组织逻辑", "节奏与转折", "标题/开头/结尾写法", "事实与观点的排列方式"],
            "analysis_questions": ["这份材料如何从信息进入观点？", "哪些表达能被后续文章复用？", "原文的叙事节奏在哪里发生变化？"],
            "output_style": "偏创作方法论，保留原文引用标记",
            "evidence_rule": "每个判断必须引用 S1/S2 等来源编号",
        },
        {
            "id": "investor",
            "name": "投资者视角",
            "role": "识别材料中的市场信号、产业变化和风险线索",
            "target_subject": "需求信号、竞争格局、商业化路径、风险边界",
            "purpose": "判断材料透露出的投资启发和可继续验证的问题",
            "focus_dimensions": ["需求信号", "产业链位置", "竞争格局", "风险与不确定性", "后续验证问题"],
            "analysis_questions": ["材料里哪些信息暗示需求变化？", "哪些主体可能受益或受压？", "还缺少哪些验证材料？"],
            "output_style": "偏研判，明确区分事实、推断和待验证问题",
            "evidence_rule": "推断必须回扣原文证据，不能引入材料外事实",
        },
        {
            "id": "student",
            "name": "学生视角",
            "role": "判断材料与学习、技能、就业和作业任务的关系",
            "target_subject": "知识点、技能映射、就业相关度、学习路径",
            "purpose": "把材料转成可学习、可练习、可用于任务的问题",
            "focus_dimensions": ["核心概念", "技能要求", "就业相关度", "可练习任务", "误区"],
            "analysis_questions": ["这份材料对学习者最重要的知识是什么？", "它关联哪些岗位或作业能力？", "可以设计什么练习来内化？"],
            "output_style": "偏学习指导，清晰列出可行动练习",
            "evidence_rule": "学习建议必须对应材料中的具体信息",
        },
        {
            "id": "founder",
            "name": "创业者视角",
            "role": "从材料中寻找用户问题、产品机会和落地约束",
            "target_subject": "用户痛点、解决方案、市场入口、资源约束",
            "purpose": "发现可转化为产品/服务/项目的机会假设",
            "focus_dimensions": ["用户痛点", "产品机会", "商业入口", "执行约束", "MVP假设"],
            "analysis_questions": ["材料里出现了什么未被满足的需求？", "这些需求可以被什么产品形态承接？", "最小验证动作是什么？"],
            "output_style": "偏机会拆解，输出假设和验证动作",
            "evidence_rule": "每个机会必须标明来自哪段材料信号",
        },
        {
            "id": "industry_researcher",
            "name": "行业研究员视角",
            "role": "建立行业底层结构、关键变量和趋势解释框架",
            "target_subject": "行业结构、供需变量、政策/技术/资本因素、趋势路径",
            "purpose": "把材料沉淀成后续研究可复用的行业判断框架",
            "focus_dimensions": ["行业结构", "关键变量", "趋势路径", "数据口径", "研究缺口"],
            "analysis_questions": ["材料揭示了哪些行业底层变量？", "哪些信息可以形成研究假设？", "后续需要补哪些数据或来源？"],
            "output_style": "偏研究备忘录，强调变量、因果链和缺口",
            "evidence_rule": "变量和因果链必须以材料证据为起点",
        },
    ]


def _list_perspective_profiles() -> list[dict[str, object]]:
    defaults = []
    for item in _default_perspective_profiles():
        profile = dict(item)
        profile["origin"] = "preset"
        profile["readonly"] = True
        defaults.append(profile)
    custom = storage.list_perspective_profiles()
    custom_ids = {item.get("id") for item in custom}
    return [*custom, *[item for item in defaults if item.get("id") not in custom_ids]]


def _read_mine_source(source: LibrarySourceRequest) -> dict[str, str]:
    library = source.library.strip()
    if library not in {"raw", "focus"}:
        raise ValueError("挖掘队列当前只支持原料库和重点库文件")
    candidate = Path(source.markdown_path)
    if not source.markdown_path.strip() or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"只能选择库内相对路径：{source.markdown_path}")
    expected_root = "raw_materials" if library == "raw" else "knowledge"
    if not candidate.parts or candidate.parts[0] != expected_root:
        raise ValueError(f"{library} 文件路径不属于 {expected_root}：{source.markdown_path}")
    path = storage.ROOT / candidate
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
        raise FileNotFoundError(f"挖掘来源文件不存在：{source.markdown_path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "library": library,
        "title": source.title.strip() or _markdown_title(text) or path.stem,
        "relative_path": str(candidate),
        "text": text,
    }


def _read_create_source(source: LibrarySourceRequest) -> dict[str, str]:
    library = source.library.strip()
    allowed_roots = {
        "raw": "raw_materials",
        "focus": "knowledge",
        "perspective": "mining",
    }
    expected_root = allowed_roots.get(library)
    if expected_root is None:
        raise ValueError("创作项目只支持原料库、重点库和视角库文件")
    candidate = Path(source.markdown_path)
    if not source.markdown_path.strip() or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"只能选择库内相对路径：{source.markdown_path}")
    if not candidate.parts or candidate.parts[0] != expected_root:
        raise ValueError(f"{library} 文件路径不属于 {expected_root}：{source.markdown_path}")
    path = storage.ROOT / candidate
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
        raise FileNotFoundError(f"创作来源文件不存在：{source.markdown_path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "library": library,
        "title": source.title.strip() or _markdown_title(text) or path.stem,
        "markdown_path": str(candidate),
        "relative_path": str(candidate),
        "text": text,
    }


def _project_writer_sources(project: dict[str, object], request_files: list[LibrarySourceRequest] | None) -> list[dict[str, str]]:
    if request_files is not None:
        return [_read_create_source(item) for item in request_files]
    files = project.get("library_files") or []
    return [_read_create_source(LibrarySourceRequest(**item)) for item in files]


def _writer_markdown_files(sources: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(Path(source["relative_path"]).name, source["text"]) for source in sources]


def _render_perspective_markdown(result, perspective: MinePerspectiveProfile, sources: list[dict[str, str]]) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    tags = "、".join(result.tags or [perspective.name])
    sections = [
        f"# {result.title}",
        "",
        f"- 视角：{perspective.name}",
        f"- 角色定位：{perspective.role}",
        f"- 关注对象：{perspective.target_subject}",
        f"- 解读时间：{now}",
        "- 状态：已解读",
        f"- 标签：{tags}",
        "",
        "## 来源文件",
        "",
    ]
    for index, source in enumerate(sources, start=1):
        sections.append(f"- [S{index}] {source['title']}（{source['library']}：{source['relative_path']}）")
    sections.extend(
        [
            "",
            "## 视角设定",
            "",
            f"- 核心目的：{perspective.purpose}",
            f"- 输出风格：{perspective.output_style}",
            f"- 证据规则：{perspective.evidence_rule}",
            "- 关注维度：",
            *[f"  - {item}" for item in perspective.focus_dimensions],
            "- 判断问题：",
            *[f"  - {item}" for item in perspective.analysis_questions],
            "",
            "## 解读摘要",
            "",
            result.summary.strip() or "暂无摘要。",
            "",
            "## 视角解读",
            "",
        ]
    )
    if result.findings:
        for finding in result.findings:
            refs = "、".join(finding.evidence_refs) if finding.evidence_refs else "请补充引用"
            sections.extend([f"### {finding.dimension}", "", finding.interpretation.strip(), "", f"- 引用：{refs}", ""])
    else:
        sections.extend(["暂无可保存的视角解读。", ""])
    sections.extend(["## 创作启发", ""])
    sections.extend(f"- {item}" for item in result.writing_implications) if result.writing_implications else sections.append("- 暂无。")
    sections.extend(["", "## 风险与边界", ""])
    sections.extend(f"- {item}" for item in result.risks_and_limits) if result.risks_and_limits else sections.append("- 暂无。")
    sections.append("")
    return "\n".join(sections)


def _processed_raw_material_paths() -> set[str]:
    storage.init_storage()
    processed: set[str] = set()
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT source_ids
            FROM knowledge_entries
            WHERE source_type = 'raw_materials'
              AND status = 'ready'
              AND source_ids IS NOT NULL
            """
        ).fetchall()
    for row in rows:
        try:
            values = json.loads(row["source_ids"] or "[]")
        except json.JSONDecodeError:
            values = []
        processed.update(str(value) for value in values if value)
    return processed


def _read_raw_material_file(relative_path: str) -> dict[str, str]:
    candidate = Path(relative_path)
    if not relative_path.strip():
        raise ValueError("原料文件路径不能为空")
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"只能选择原料库相对路径：{relative_path}")
    if not candidate.parts or candidate.parts[0] != "raw_materials":
        raise ValueError(f"只能选择原料库文件：{relative_path}")
    path = storage.ROOT / candidate
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"原料文件不存在：{relative_path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f"原料库只支持 Markdown 文件：{relative_path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "title": _markdown_title(text) or path.stem,
        "relative_path": str(candidate),
        "text": text,
    }


def _combine_raw_material_sources(sources: list[dict[str, str]]) -> str:
    blocks = []
    for index, source in enumerate(sources, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[R{index}: {source['title']}]",
                    f"Path: {source['relative_path']}",
                    "",
                    source["text"].strip(),
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def _raw_sources_hash(sources: list[dict[str, str]]) -> str:
    return hashlib.sha256("|".join(item["relative_path"] for item in sources).encode("utf-8")).hexdigest()


def _render_focus_markdown(knowledge, sources: list[dict[str, str]]) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    tags = "、".join(knowledge.tags) if knowledge.tags else "未标注"
    sections = [
        f"# {knowledge.title}",
        "",
        "- 来源：原料库",
        f"- 导入时间：{now}",
        f"- 主题：{knowledge.topic}",
        f"- 标签：{tags}",
        f"- 原子知识点数量：{len(knowledge.clusters)}",
        "",
        "## 原文引用",
        "",
    ]
    for index, source in enumerate(sources, start=1):
        sections.append(f"- [R{index}] {source['title']}：{source['relative_path']}")
    sections.extend(["", "## 核心知识簇", ""])
    if knowledge.clusters:
        for index, cluster in enumerate(knowledge.clusters, start=1):
            sections.extend(
                [
                    f"### {index}. {cluster.name}",
                    f"- 领域：{cluster.domain}",
                    f"- 出现次数：{cluster.occurrence_count}",
                    f"- 信息含义：{cluster.meaning}",
                    "- 关键信息元：",
                    *[f"  - {value}" for value in cluster.key_information],
                    "- 引用：请保留或补充对应 [R] 标记",
                    "",
                ]
            )
    else:
        sections.extend(["未提取出可独立解释的知识簇。", ""])
    sections.extend(
        [
            "## 外化思考",
            "",
            knowledge.investment_insights.strip() or "暂无。",
            "",
        ]
    )
    return "\n".join(sections)


def _tags_from_meta(meta: dict[str, str]) -> list[str]:
    raw = meta.get("标签") or ""
    if not raw or raw == "未标注":
        return []
    return [item.strip() for item in re.split(r"[、,，;；]", raw) if item.strip()]


def _polish_raw_material(material_type: str, body: str, fallback_title: str) -> dict[str, object]:
    response = {
        "enabled": False,
        "status": "skipped",
        "title": "",
        "error": "",
    }
    result = {
        "title": "",
        "markdown": "",
        "response": response,
        "extra_meta": {},
    }
    if material_type != "screenshot" or len(body.strip()) < 12:
        return result

    response["enabled"] = True
    try:
        polished = deepseek_client.polish_raw_material(
            body,
            material_type=material_type,
            setting=api_settings.active_setting(),
        )
    except Exception as exc:
        response["status"] = "failed"
        response["error"] = deepseek_client.explain_error(exc)
        return result

    title = _compact_raw_topic(polished.title or fallback_title)
    markdown = _clean_raw_markdown_body(polished.markdown or body)
    if title:
        result["title"] = title
        response["title"] = title
    if markdown:
        result["markdown"] = markdown
    response["status"] = "completed"
    result["extra_meta"] = {"raw_polish": "llm"}
    return result


def _write_raw_markdown(
    *,
    material_type: str,
    title: str,
    body: str,
    source: str,
    extra_meta: dict[str, str] | None = None,
) -> dict[str, object]:
    storage.init_storage()
    now = datetime.now().isoformat(timespec="seconds")
    content_hash = hashlib.sha256(f"{material_type}|{source}|{body}".encode("utf-8")).hexdigest()
    dated_dir = storage.ROOT / "raw_materials" / datetime.now().strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    path = dated_dir / f"{storage.safe_filename(title, fallback='raw-material')}_{content_hash[:8]}.md"
    meta = {
        "材料类型": material_type,
        "来源": source,
        "收集时间": now,
        "状态": "原文级 Markdown",
    }
    if extra_meta:
        meta.update(extra_meta)
    lines = [f"# {title}", ""]
    lines.extend(f"- {key}：{value}" for key, value in meta.items())
    lines.extend(["", body.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "title": title,
        "material_type": material_type,
        "source": source,
        "markdown_path": str(path.relative_to(storage.ROOT)),
        "created_at": now,
        "hash": content_hash,
    }


def _extract_queue_text(material_type: str, items: list[CollectQueueItem]) -> tuple[str, list[str], list[str]]:
    if material_type == "text":
        blocks = []
        for index, item in enumerate(items, start=1):
            content = item.content.strip()
            if content:
                blocks.append(f"[Text {index}: {item.title or '手动输入'}]\n{content}")
        return "\n\n---\n\n".join(blocks), [item.title or "手动输入" for item in items], []

    if material_type == "web_link":
        return _extract_web_link_queue(items)

    if material_type == "screenshot":
        screenshots = [storage.get_screenshot(int(item.id)) for item in items if item.id is not None]
        image_paths = []
        for screenshot in screenshots:
            path = storage.resolve_root_path(screenshot.get("image_path"))
            if path:
                image_paths.append(path)
        return ocr_client.recognize_screenshots(image_paths), [item.get("image_path") or "" for item in screenshots], []

    if material_type == "document":
        return _extract_document_queue(items)

    if material_type == "media":
        return _extract_media_queue(items)

    raise ValueError(f"不支持的材料类型：{material_type}")


def _extract_web_link_queue(items: list[CollectQueueItem]) -> tuple[str, list[str], list[str]]:
    blocks: list[str] = []
    sources: list[str] = []
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        url = item.url.strip()
        if not url:
            continue
        sources.append(url)
        try:
            fetched = _extract_link_text(url, item)
            block_title = str(fetched.get("title") or "").strip() or item.title or url
            blocks.append(_render_link_markdown_block(index, url, block_title, fetched))
        except (OSError, UnicodeDecodeError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append(f"{url}: {exc}")
    return "\n\n---\n\n".join(blocks), sources, errors


def _extract_document_queue(items: list[CollectQueueItem]) -> tuple[str, list[str], list[str]]:
    files = [storage.get_source_file(int(item.id)) for item in items if item.id is not None]
    blocks: list[str] = []
    sources: list[str] = []
    errors: list[str] = []
    for index, item in enumerate(files, start=1):
        try:
            file_path = storage.ROOT / str(item["file_path"])
            text = document_parser.extract_text(file_path)
            name = str(item.get("original_name") or file_path.name)
            sources.append(name)
            blocks.append(f"[File {index}: {name}]\n{text}")
            storage.update_source_file(int(item["id"]), status="ready", error_message=None)
        except Exception as exc:
            name = str(item.get("original_name") or item.get("file_path") or item.get("id"))
            errors.append(f"{name}: {exc}")
            try:
                storage.update_source_file(int(item["id"]), status="error", error_message=str(exc))
            except Exception:
                pass
    return "\n\n---\n\n".join(blocks), sources, errors


def _extract_media_queue(items: list[CollectQueueItem]) -> tuple[str, list[str], list[str]]:
    media_items = [storage.get_media_source(int(item.id)) for item in items if item.id is not None]
    blocks = []
    sources = []
    errors: list[str] = []
    for media_item in media_items:
        media_id = int(media_item["id"])
        label = str(media_item.get("title") or media_item.get("original_name") or media_item.get("source_url") or media_id)
        try:
            storage.update_media_source(media_id, status="transcribing", error_message=None)
            transcript, _ = _ensure_media_transcript_with_platform_import(media_item)
            refreshed = storage.get_media_source(media_id)
            blocks.append(media_parser.format_media_transcript(refreshed, transcript))
            sources.append(str(refreshed.get("canonical_url") or refreshed.get("source_url") or refreshed.get("original_name") or ""))
            storage.update_media_source(media_id, status="ready", error_message=None)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            try:
                storage.update_media_source(media_id, status="error", error_message=str(exc))
            except Exception:
                pass
    return "\n\n---\n\n".join(blocks), sources, errors


def _ensure_media_transcript_with_platform_import(media_item: dict) -> tuple[str, str]:
    try:
        return media_parser.ensure_transcript(media_item)
    except Exception as exc:
        if media_item.get("platform") != "douyin":
            raise
        video_id = media_parser.extract_douyin_video_id(
            str(media_item.get("canonical_url") or media_item.get("source_url") or "")
        )
        if not video_id:
            raise
        _import_douyin_detail_with_browser(video_id, str(media_item.get("canonical_url") or media_item.get("source_url") or ""))
        refreshed = storage.get_media_source(int(media_item["id"]))
        try:
            return media_parser.ensure_transcript(refreshed)
        except Exception as retry_exc:
            raise retry_exc from exc


def _default_raw_title(material_type: str, items: list[CollectQueueItem]) -> str:
    first = next((item for item in items if item.title or item.content or item.url), None)
    if first:
        value = first.title or first.url or _title_from_text(first.content, "")
        if value:
            return value[:60]
    labels = {
        "text": "文本原料",
        "screenshot": "截图原料",
        "document": "文档原料",
        "media": "音视频原料",
        "web_link": "网页链接原料",
    }
    return labels.get(material_type, "原料")


def _resolve_raw_title(request_title: str, fallback_title: str, body: str) -> str:
    candidate = _extract_topic_from_raw_markdown(body)
    current = request_title.strip() or fallback_title.strip()
    if candidate and (_is_generic_raw_title(current) or len(current) > 60):
        return candidate
    return current or candidate or "raw-material"


def _is_generic_raw_title(title: str) -> bool:
    normalized = title.strip().lower()
    if not normalized:
        return True
    if normalized.startswith(("http://", "https://")):
        return True
    if re.fullmatch(r"douyin\s+\d+", normalized):
        return True
    generic_tokens = (
        "test",
        "web link",
        "web_link",
        "link",
        "url",
        "raw",
        "material",
        "screenshot",
        "clip",
        "截图",
        "原料",
        "文本原料",
        "截图原料",
        "文档原料",
        "网页链接原料",
    )
    return any(token in normalized for token in generic_tokens)


def _extract_topic_from_raw_markdown(body: str) -> str:
    for raw_line in body.splitlines():
        line = _normalize_markdown_line(raw_line)
        if not line or _is_raw_metadata_line(line):
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if _looks_like_url(line):
            continue
        if _is_generic_raw_title(line):
            continue
        if len(line) < 4:
            continue
        return _compact_raw_topic(line)
    return ""


def _compact_raw_topic(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in (r"^(.{12,48}?[。！？!?])", r"^(.{18,42}?[，,；;：:])"):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip("，,；;：: ")
    return text[:36].strip()


def _clean_raw_markdown_body(body: str) -> str:
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_markdown_line(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^\s*[-*]\s+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_raw_metadata_line(line: str) -> bool:
    prefixes = (
        "[Web Link ",
        "[Text ",
        "[File ",
        "[Media:",
        "[Platform:",
        "[Source:",
        "[Duration:",
        "[Transcript Source:",
        "URL:",
        "Source:",
        "Type:",
        "Status:",
        "Strategy:",
        "Author:",
        "Published At:",
        "Link Type:",
        "Access Status:",
        "Extraction Strategy:",
    )
    return line.startswith(prefixes)


def _looks_like_url(text: str) -> bool:
    return bool(re.match(r"^https?://", text.strip(), flags=re.IGNORECASE))


def _inspect_link(url: str) -> dict[str, object]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    platform = _platform_link_type(host)
    if platform:
        return {
            "url": url,
            "final_url": url,
            "title": url,
            "link_type": platform,
            "extraction_strategy": "specialized_tool_or_browser",
            "access_status": "needs_specialized_extractor",
            "source": host,
            "notes": _platform_note(platform),
        }
    if path.endswith(".pdf"):
        return {
            "url": url,
            "final_url": url,
            "title": _path_name(path) or url,
            "link_type": "pdf",
            "extraction_strategy": "download_and_parse_document",
            "access_status": "unknown",
            "source": host,
            "notes": "PDF/报告/论文链接，将下载后按文档流程解析。",
        }

    try:
        fetched = _fetch_url_bytes(url, max_bytes=400_000)
    except urllib.error.HTTPError as exc:
        status = "login_or_restricted" if exc.code in {401, 403} else "unreachable"
        return _restricted_link_payload(url, host, status, f"HTTP {exc.code}")
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return _restricted_link_payload(url, host, "unreachable", str(exc))

    content_type = str(fetched["content_type"]).lower()
    final_url = str(fetched["final_url"])
    final_host = urllib.parse.urlparse(final_url).netloc
    if "application/pdf" in content_type or urllib.parse.urlparse(final_url).path.lower().endswith(".pdf"):
        return {
            "url": url,
            "final_url": final_url,
            "title": _path_name(urllib.parse.urlparse(final_url).path) or url,
            "link_type": "pdf",
            "extraction_strategy": "download_and_parse_document",
            "access_status": "accessible",
            "source": final_host,
            "content_type": content_type,
            "notes": "已识别为 PDF，将按文档解析流程提取文字。",
        }

    html_text = _decode_response_text(bytes(fetched["body"]), content_type)
    title = _html_title(html_text) or url
    link_type = "public_webpage"
    status = "accessible"
    strategy = "direct_fetch"
    notes = ""
    if _looks_like_login_wall(html_text, final_url):
        link_type = "login_required"
        status = "login_or_restricted"
        strategy = "reuse_logged_in_browser"
        notes = "页面疑似登录墙/权限墙，后续应优先复用已登录浏览器会话。"
    elif _looks_like_dynamic_page(html_text):
        link_type = "dynamic_webpage"
        status = "needs_browser_rendering"
        strategy = "browser_automation"
        notes = "页面疑似 JavaScript 动态渲染，需要浏览器自动化等待和滚动后提取。"

    return {
        "url": url,
        "final_url": final_url,
        "title": title,
        "link_type": link_type,
        "extraction_strategy": strategy,
        "access_status": status,
        "source": final_host,
        "content_type": content_type,
        "author": _extract_meta(html_text, ["author", "article:author"]),
        "published_at": _extract_meta(html_text, ["article:published_time", "publishdate", "date", "pubdate"]),
        "notes": notes,
    }


def _extract_link_text(url: str, item: CollectQueueItem) -> dict[str, str]:
    inspection = _inspect_link(url)
    link_type = str(inspection.get("link_type") or item.link_type or "")
    if link_type == "platform_wechat":
        return _extract_wechat_article_text(url)
    if link_type in {"platform_douyin", "platform_bilibili", "platform_wechat_channels"}:
        raise ValueError("音视频平台链接请放入「音视频」入口读取，不应作为普通网页链接提取。")
    if link_type == "pdf":
        return _extract_pdf_link_text(url, inspection)
    if str(inspection.get("access_status")) in {"login_or_restricted", "needs_browser_rendering", "needs_specialized_extractor"}:
        return {
            "title": str(inspection.get("title") or item.title or url),
            "text": str(inspection.get("notes") or "当前链接需要浏览器自动化或专门平台工具处理。"),
            "source": str(inspection.get("source") or ""),
            "author": str(inspection.get("author") or ""),
            "published_at": str(inspection.get("published_at") or ""),
            "link_type": link_type,
            "access_status": str(inspection.get("access_status") or ""),
            "extraction_strategy": str(inspection.get("extraction_strategy") or ""),
        }
    fetched = _fetch_webpage_text(url)
    fetched.update(
        {
            "source": str(inspection.get("source") or ""),
            "author": str(inspection.get("author") or ""),
            "published_at": str(inspection.get("published_at") or ""),
            "link_type": link_type or "public_webpage",
            "access_status": str(inspection.get("access_status") or "accessible"),
            "extraction_strategy": str(inspection.get("extraction_strategy") or "direct_fetch"),
        }
    )
    return fetched


def _extract_pdf_link_text(url: str, inspection: dict[str, object]) -> dict[str, str]:
    fetched = _fetch_url_bytes(url, max_bytes=25_000_000)
    content = bytes(fetched["body"])
    content_hash = hashlib.sha256(content).hexdigest()
    pdf_dir = storage.DOCUMENT_DIR / datetime.now().strftime("%Y-%m-%d") / "linked"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    name = storage.safe_filename(str(inspection.get("title") or "linked-pdf"), fallback="linked-pdf")
    path = pdf_dir / f"{name}_{content_hash[:8]}.pdf"
    path.write_bytes(content)
    text = document_parser.extract_text(path)
    return {
        "title": str(inspection.get("title") or path.name),
        "text": text,
        "source": str(inspection.get("source") or ""),
        "author": "",
        "published_at": "",
        "link_type": "pdf",
        "access_status": "accessible",
        "extraction_strategy": "download_and_parse_document",
    }


def _extract_douyin_link_text(url: str) -> dict[str, str]:
    resolved = media_parser.resolve_url(url)
    item = storage.create_remote_media_source(
        platform=resolved.platform,
        source_url=resolved.source_url,
        canonical_url=resolved.canonical_url,
        title=resolved.title,
        duration_seconds=resolved.duration_seconds,
        status=resolved.status,
        error_message=resolved.error_message,
    )
    if resolved.error_message:
        raise ValueError(resolved.error_message)

    try:
        storage.update_media_source(int(item["id"]), status="transcribing", error_message=None)
        transcript, kind = _ensure_media_transcript_with_platform_import(item)
        refreshed = storage.get_media_source(int(item["id"]))
        formatted = media_parser.format_media_transcript(refreshed, transcript)
    except Exception as exc:
        storage.update_media_source(int(item["id"]), status="error", error_message=str(exc))
        raise ValueError(str(exc)) from exc

    return {
        "title": str(refreshed.get("title") or resolved.title or "Douyin video"),
        "text": formatted,
        "source": str(resolved.canonical_url or url),
        "author": "",
        "published_at": "",
        "link_type": "platform_douyin",
        "access_status": "accessible",
        "extraction_strategy": f"media_parser_{kind}",
    }


def _import_douyin_detail_with_browser(video_id: str, url: str) -> Path:
    command = _agent_browser_command()
    connection_args = _agent_browser_connection_args(command)
    subprocess.run(
        [command, *connection_args, "open", url],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=45,
        check=False,
    )
    time.sleep(5)
    payload = _agent_browser_json(
        command,
        connection_args,
        "network",
        "requests",
        "--filter",
        "aweme/v1/web/aweme/detail",
        "--type",
        "xhr",
        "--status",
        "200",
    )
    requests = payload.get("data", {}).get("requests", []) if isinstance(payload, dict) else []
    matches = [request for request in requests if video_id in str(request.get("url") or "")]
    if not matches:
        raise RuntimeError(
            f"No captured Douyin aweme/detail response found for {video_id}. "
            "Open the Douyin video in the browser first and wait until it finishes loading."
        )
    request_id = str(matches[-1].get("requestId") or "")
    detail_payload = _agent_browser_json(command, connection_args, "network", "request", request_id)
    body = detail_payload.get("data", {}).get("responseBody") if isinstance(detail_payload, dict) else ""
    if not body:
        raise RuntimeError(f"Captured Douyin request {request_id} has no response body.")
    data = json.loads(str(body))
    output_dir = storage.MEDIA_DIR / "douyin_detail"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_id}.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _agent_browser_json(command: str, connection_args: list[str], *args: str) -> dict[str, object]:
    completed = subprocess.run(
        [command, *connection_args, *args, "--json"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def _extract_wechat_article_text(url: str) -> dict[str, str]:
    data = _browser_extract_article_payload(url)
    title = _collapse_space(str(data.get("title") or "微信公众号文章"))
    account_name = _collapse_space(str(data.get("account_name") or "mp.weixin.qq.com"))
    author = _collapse_space(str(data.get("author") or ""))
    published_at = _collapse_space(str(data.get("published_at") or ""))
    summary = _collapse_space(str(data.get("summary") or ""))
    content = _collapse_space_multiline(str(data.get("content") or ""))
    if len(content) < 80:
        raise ValueError("微信公众号正文提取为空或过短，请确认浏览器会话已登录且页面可访问")
    text_parts = []
    if summary:
        text_parts.extend(["摘要：", summary, ""])
    text_parts.append(content)
    return {
        "title": title,
        "text": "\n".join(text_parts),
        "source": account_name,
        "author": author,
        "published_at": published_at,
        "link_type": "platform_wechat",
        "access_status": "accessible",
        "extraction_strategy": "browser_harness_wechat_dom",
    }


def _browser_extract_article_payload(url: str) -> dict[str, object]:
    try:
        return _browser_harness_extract_article_payload(url)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _agent_browser_extract_article_payload(url)


def _browser_harness_extract_article_payload(url: str) -> dict[str, object]:
    code = f"""
import json
new_tab({json.dumps(url, ensure_ascii=False)})
wait_for_load()
payload = js(r'''
(() => {{
  const clean = s => (s || "").replace(/\\s+/g, " ").trim();
  const pickText = selectors => {{
    for (const selector of selectors) {{
      const el = document.querySelector(selector);
      if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
    }}
    return "";
  }};
  const meta = name => {{
    const el = document.querySelector(`meta[property="${{name}}"], meta[name="${{name}}"]`);
    return el ? el.getAttribute("content") : "";
  }};
  const ps = Array.from(document.querySelectorAll("article p, main p, .article p, .post p, .content p, p"))
    .map(p => clean(p.innerText)).filter(t => t.length > 20);
  const site = meta("og:site_name") || location.hostname.replace(/^www\\./, "");
  return JSON.stringify({{
    url: location.href,
    title: pickText(["#activity-name", "h1"]) || document.title || meta("og:title"),
    account_name: pickText(["#js_name", ".profile_nickname"]) || site,
    author: pickText(["#js_author_name", "[rel=author]", ".author", ".byline"]) || meta("author") || "",
    published_at: pickText(["#publish_time", "#js_publish_time", "time"]) || meta("article:published_time") || meta("date") || "",
    summary: meta("og:description") || meta("description") || "",
    content: pickText(["#js_content", ".rich_media_content", "article", "main"]) || ps.join("\\n\\n") || document.body.innerText || ""
  }});
}})()
''')
print(payload)
"""
    completed = subprocess.run(
        ["browser-harness"],
        input=code,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=60,
    )
    output = completed.stdout.strip().splitlines()
    if not output:
        raise ValueError("browser-harness 没有返回页面内容")
    return json.loads(output[-1])


def _agent_browser_extract_article_payload(url: str) -> dict[str, object]:
    command = _agent_browser_command()
    connection_args = _agent_browser_connection_args(command)
    subprocess.run(
        [command, *connection_args, "open", url],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=60,
    )
    subprocess.run(
        [command, *connection_args, "wait", "3000"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=20,
    )
    js_code = r'''
(() => {
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  const pickText = selectors => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
    }
    return "";
  };
  const meta = name => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return el ? el.getAttribute("content") : "";
  };
  const ps = Array.from(document.querySelectorAll("article p, main p, .article p, .post p, .content p, p"))
    .map(p => clean(p.innerText)).filter(t => t.length > 20);
  const site = meta("og:site_name") || location.hostname.replace(/^www\./, "");
  return JSON.stringify({
    url: location.href,
    title: pickText(["#activity-name", "h1"]) || document.title || meta("og:title"),
    account_name: pickText(["#js_name", ".profile_nickname"]) || site,
    author: pickText(["#js_author_name", "[rel=author]", ".author", ".byline"]) || meta("author") || "",
    published_at: pickText(["#publish_time", "#js_publish_time", "time"]) || meta("article:published_time") || meta("date") || "",
    summary: meta("og:description") || meta("description") || "",
    content: pickText(["#js_content", ".rich_media_content", "article", "main"]) || ps.join("\n\n") || document.body.innerText || ""
  });
})()
'''
    completed = subprocess.run(
        [command, *connection_args, "eval", js_code],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=60,
    )
    return _parse_agent_browser_json(completed.stdout)


def _agent_browser_command() -> str:
    found = shutil.which("agent-browser")
    if found:
        return found
    windows_path = r"C:\Users\Bo Yang\AppData\Roaming\npm\agent-browser.cmd"
    if Path(windows_path).exists():
        return windows_path
    raise FileNotFoundError("未找到 browser-harness 或 agent-browser，无法复用浏览器提取微信公众号正文")


def _agent_browser_connection_args(command: str) -> list[str]:
    probe = subprocess.run(
        [command, "--auto-connect", "get", "url"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
    )
    if probe.returncode == 0:
        return ["--auto-connect"]
    _launch_edge_remote_debugging()
    return ["--cdp", "9222"]


def _launch_edge_remote_debugging() -> None:
    edge_path = _edge_executable()
    user_data_dir = storage.ROOT / "browser_profile" / "edge-remote-debugging"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            edge_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)


def _edge_executable() -> str:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("未找到 Microsoft Edge，无法启动浏览器自动化提取微信公众号")


def _parse_agent_browser_json(output: str) -> dict[str, object]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        candidate = line
        if candidate.startswith("=>"):
            candidate = candidate[2:].strip()
        if (candidate.startswith('"') and candidate.endswith('"')) or (candidate.startswith("'") and candidate.endswith("'")):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                candidate = candidate.strip("\"'")
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError("agent-browser 没有返回可解析的文章 JSON")


def _render_link_markdown_block(index: int, url: str, title: str, fetched: dict[str, str]) -> str:
    lines = [f"## {title}", ""]
    lines.append(f"- URL: {url}")
    if fetched.get("source"):
        lines.append(f"- Source: {fetched['source']}")
    if fetched.get("link_type"):
        lines.append(f"- Link Type: {fetched['link_type']}")
    if fetched.get("access_status"):
        lines.append(f"- Access Status: {fetched['access_status']}")
    if fetched.get("extraction_strategy"):
        lines.append(f"- Extraction Strategy: {fetched['extraction_strategy']}")
    if fetched.get("author"):
        lines.append(f"- Author: {fetched['author']}")
    if fetched.get("published_at"):
        lines.append(f"- Published At: {fetched['published_at']}")
    lines.extend(["", _clean_extracted_article_text(fetched.get("text", ""), title)])
    return "\n".join(lines)


def _clean_extracted_article_text(text: str, title: str) -> str:
    lines = []
    seen_blank = False
    title_seen = False
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            if lines and not seen_blank:
                lines.append("")
                seen_blank = True
            continue
        normalized = re.sub(r"\s+", " ", line)
        if normalized == title and not title_seen:
            title_seen = True
            continue
        lines.append(normalized)
        seen_blank = False
    return "\n".join(lines).strip()


def _platform_link_type(host: str) -> str:
    if "mp.weixin.qq.com" in host:
        return "platform_wechat"
    if "channels.weixin.qq.com" in host:
        return "platform_wechat_channels"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "platform_xiaohongshu"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "platform_douyin"
    if "bilibili.com" in host or "b23.tv" in host:
        return "platform_bilibili"
    if "webofscience.com" in host or "webofknowledge.com" in host:
        return "platform_web_of_science"
    return ""


def _platform_note(link_type: str) -> str:
    notes = {
        "platform_wechat": "微信公众号链接应使用公众号/浏览器自动化提取，避免只抓到壳页面。",
        "platform_xiaohongshu": "小红书链接应使用小红书专门工具或已登录浏览器会话。",
        "platform_douyin": "抖音链接应使用抖音/媒体解析工具或浏览器自动化。",
        "platform_web_of_science": "Web of Science 应复用已登录浏览器会话，避免凭据和权限问题。",
    }
    return notes.get(link_type, "该平台建议使用专门工具或浏览器自动化。")


def _restricted_link_payload(url: str, host: str, status: str, note: str) -> dict[str, object]:
    return {
        "url": url,
        "final_url": url,
        "title": url,
        "link_type": "login_required" if status == "login_or_restricted" else "unreachable",
        "extraction_strategy": "reuse_logged_in_browser" if status == "login_or_restricted" else "manual_review",
        "access_status": status,
        "source": host,
        "notes": note,
    }


def _fetch_url_bytes(url: str, max_bytes: int) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FigureLearning ResearchOS/0.1",
            "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return {
            "body": response.read(max_bytes),
            "content_type": response.headers.get("content-type", ""),
            "final_url": response.geturl(),
        }


def _fetch_webpage_text(url: str) -> dict[str, str]:
    fetched = _fetch_url_bytes(url, max_bytes=2_000_000)
    content_type = str(fetched["content_type"])
    html_text = _decode_response_text(bytes(fetched["body"]), content_type)
    title = _html_title(html_text)
    text = _html_to_text(html_text)
    if not text.strip():
        raise ValueError("网页正文为空")
    return {"title": title, "text": text}


def _decode_response_text(raw: bytes, content_type: str) -> str:
    encoding = _encoding_from_content_type(content_type) or "utf-8"
    return raw.decode(encoding, errors="replace")


def _encoding_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([\w.-]+)", content_type, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _html_title(html_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _collapse_space(_strip_tags(match.group(1)))[:120]


def _html_to_text(html_text: str) -> str:
    html_text = _main_content_hint(html_text)
    cleaned = re.sub(r"<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"</(p|div|section|article|li|h[1-6]|br|blockquote|figcaption)>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = _strip_tags(cleaned)
    lines = [_collapse_space(line) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def _main_content_hint(html_text: str) -> str:
    patterns = [
        r"<article[^>]*>(.*?)</article>",
        r"<main[^>]*>(.*?)</main>",
        r"<div[^>]+class=[\"'][^\"']*(content|article|post|entry)[^\"']*[\"'][^>]*>(.*?)</div>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(match.lastindex or 1)
    return html_text


def _extract_meta(html_text: str, names: list[str]) -> str:
    for name in names:
        patterns = [
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.IGNORECASE)
            if match:
                return html.unescape(match.group(1)).strip()
    return ""


def _looks_like_login_wall(html_text: str, final_url: str) -> bool:
    lower = (html_text + " " + final_url).lower()
    markers = ["login", "sign in", "signin", "登录", "请登录", "权限", "unauthorized", "forbidden"]
    return any(marker in lower for marker in markers)


def _looks_like_dynamic_page(html_text: str) -> bool:
    text = _html_to_text(html_text)
    script_count = len(re.findall(r"<script\b", html_text, flags=re.IGNORECASE))
    return len(text) < 180 and script_count >= 5


def _strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(value.replace("&nbsp;", " "))


def _collapse_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _collapse_space_multiline(value: str) -> str:
    lines = [_collapse_space(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _title_from_text(content: str, fallback: str) -> str:
    for line in content.splitlines():
        title = _collapse_space(line)
        if title:
            return title[:60]
    return fallback


def _path_name(path: str) -> str:
    return urllib.parse.unquote(path.rsplit("/", 1)[-1]).strip()
