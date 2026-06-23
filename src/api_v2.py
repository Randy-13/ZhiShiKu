from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
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
from media_transcriber import transcribe_audio_url
from src.materials.entities import MaterialType
from src.auth import (
    create_invitation,
    current_context,
    list_invitations,
    list_users,
    login,
    logout,
    register_with_invite,
    update_user_status,
)
from src import jobs as job_service
from src import quotas as quota_service
from src.settings_helpers import (
    activate_list_setting,
    delete_list_setting,
    resolve_api_test_setting,
    resolve_image_api_test_setting,
    save_list_setting,
    test_asr_setting_payload,
)
from src.shared.app_shell import GLOBAL_LIBRARIES, PRIMARY_SECTIONS, WORKSPACE_ENTRIES
from src.shared.responses import success_payload


router = APIRouter(prefix="/api/v2", tags=["v2-contracts"])
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


class CollectTextRequest(BaseModel):
    content: str
    title: str = ""


class CollectWebLinkRequest(BaseModel):
    url: HttpUrl
    title: str = ""


class InspectLinkRequest(BaseModel):
    url: HttpUrl


class BrowserExtractLinkRequest(BaseModel):
    url: HttpUrl
    title: str = ""
    wait_ms: int = 3000
    scroll_times: int = 5
    scroll_pause_ms: int = 800
    selector: str = ""


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
    parser_mode: str | None = None


class CollectRawFileRequest(BaseModel):
    material_type: str = "text"
    title: str
    note: str = ""
    markdown: str
    source: str = ""


class CollectReadableDraftRequest(BaseModel):
    material_type: str
    title: str = ""
    items: list[CollectQueueItem]
    parser_mode: str | None = None


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


class LibraryFileUpdateRequest(BaseModel):
    title: str
    note: str = ""
    markdown: str


class TrashSelectionRequest(BaseModel):
    trash_paths: list[str]


class MinePerspectiveProfile(BaseModel):
    id: str = ""
    name: str
    positioning: str = ""
    core_goal: str = ""
    stance: str = ""
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


class AuthLoginRequest(BaseModel):
    identifier: str
    password: str


class AuthRegisterInviteRequest(BaseModel):
    invite_code: str
    email: str
    username: str
    password: str


class AdminInvitationRequest(BaseModel):
    role: str = "member"
    max_uses: int = 1
    days: int = 14


class AdminUserStatusRequest(BaseModel):
    status: str


class JobCreateRequest(BaseModel):
    kind: str
    payload: dict[str, object] = {}
    auto_start: bool = True


class MediaTranscriptJobRequest(BaseModel):
    media_ids: list[int]


class WriterImageGenerateJobRequest(BaseModel):
    project_id: str
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []


class WriterImageItemJobRequest(BaseModel):
    project_id: str
    kind: str
    prompt: str
    index: int | None = None


class WriterPublishPreflightJobRequest(BaseModel):
    project_id: str
    title: str = ""
    author: str = "Bobo"
    digest: str | None = None
    cover_path: str | None = None


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


class ImageApiSettingRequest(BaseModel):
    id: str | None = None
    name: str = ""
    provider: str = "compatible"
    protocol: str | None = None
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    timeout: float | None = None
    size: str | None = None
    quality: str | None = None
    aspect_ratio: str | None = None
    response_format: str | None = None
    make_active: bool = True


class SettingActiveRequest(BaseModel):
    id: str


class ApiSettingTestRequest(BaseModel):
    id: str | None = None
    setting: ApiSettingRequest | None = None


class ImageApiSettingTestRequest(BaseModel):
    id: str | None = None
    setting: ImageApiSettingRequest | None = None
    real_test: bool = False
    prompt: str | None = None


class AsrSettingRequest(BaseModel):
    provider: str = "compatible"
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    timeout: float | None = None


@auth_router.get("/me")
def auth_me(request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        return success_payload(data=current_context(request, conn))


@auth_router.post("/login")
def auth_login(payload: AuthLoginRequest, request: Request, response: Response) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        return success_payload(data=login(conn, response, payload.identifier, payload.password, request))


@auth_router.post("/logout")
def auth_logout(request: Request, response: Response) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        return success_payload(data=logout(conn, response, request))


@auth_router.post("/register-with-invite")
def auth_register_with_invite(payload: AuthRegisterInviteRequest, request: Request, response: Response) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        return success_payload(
            data=register_with_invite(
                conn,
                response,
                request,
                invite_code=payload.invite_code,
                email=payload.email,
                username=payload.username,
                password=payload.password,
            )
        )


@auth_router.post("/admin/invitations")
def auth_admin_create_invitation(payload: AdminInvitationRequest, request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        if context["user"]["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以创建邀请码")
        return success_payload(data=create_invitation(conn, role=payload.role, max_uses=payload.max_uses, days=payload.days))


@auth_router.get("/admin/users")
def auth_admin_users(request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        if context["user"]["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view users")
        return success_payload(data={"items": list_users(conn)})


@auth_router.post("/admin/users/{user_id}/status")
def auth_admin_update_user_status(user_id: str, payload: AdminUserStatusRequest, request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        user = context["user"]
        if user["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can manage users")
        return success_payload(data={"item": update_user_status(conn, user_id, payload.status, user["id"])})


@auth_router.get("/admin/invitations")
def auth_admin_invitations(request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        if context["user"]["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can view invitations")
        return success_payload(data={"items": list_invitations(conn)})


@jobs_router.get("")
def jobs_list(request: Request, limit: int = 30) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        return success_payload(data={"items": job_service.list_jobs(conn, user_id=context["user"]["id"], limit=limit)})


@jobs_router.post("")
def jobs_create(payload: JobCreateRequest, request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    if not payload.kind.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务类型不能为空")
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        kind = payload.kind.strip()
        _validate_supported_job(kind)
        _validate_job_payload(kind, payload.payload, context, require_executable=payload.auto_start)
        _enforce_concurrent_jobs(conn, context)
        _consume_job_quota(conn, context, kind, payload.payload)
        item = job_service.create_job(
            conn,
            user_id=context["user"]["id"],
            workspace_id=context["workspace"]["id"],
            kind=kind,
            payload=payload.payload,
        )
        if payload.auto_start:
            background_tasks.add_task(_run_job, item["id"], context)
        return success_payload(data={"item": item})


@jobs_router.get("/{job_id}")
def jobs_detail(job_id: str, request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        try:
            item = job_service.get_job(conn, user_id=context["user"]["id"], job_id=job_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在") from exc
        return success_payload(data={"item": item})


@jobs_router.post("/{job_id}/cancel")
def jobs_cancel(job_id: str, request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        try:
            item = job_service.cancel_job(conn, user_id=context["user"]["id"], job_id=job_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在") from exc
        return success_payload(data={"item": item})


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
def app_shell(request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        auth_context = current_context(request, conn)
    return success_payload(
        data={
            "auth": auth_context,
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


@router.get("/quotas/me")
def quota_status(request: Request) -> dict[str, object]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
        user_id, workspace_id = quota_service.user_ids(context)
        return success_payload(
            data={
                "deploymentMode": context.get("deploymentMode"),
                "enforced": quota_service.is_enforced(context),
                "daily": {
                    "link_parse_daily": quota_service.check_daily(conn, user_id=user_id, workspace_id=workspace_id, key="link_parse_daily"),
                    "llm_generate_daily": quota_service.check_daily(conn, user_id=user_id, workspace_id=workspace_id, key="llm_generate_daily"),
                },
                "jobs": {
                    "concurrent_jobs": quota_service.check_concurrent_jobs(conn, user_id=user_id),
                },
                "uploads": {
                    "single_upload_bytes": {
                        "limit": quota_service.DEFAULT_LIMITS["single_upload_bytes"],
                    },
                    "storage_bytes": quota_service.check_storage(conn, user_id=user_id),
                },
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
        return success_payload(data={"ok": True, **save_list_setting(api_settings, request.model_dump())})
    except ValueError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/api/active")
def activate_settings_api(request: SettingActiveRequest) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **activate_list_setting(api_settings, request.id)})
    except (KeyError, ValueError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.delete("/settings/api/{setting_id}")
def delete_settings_api(setting_id: str) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **delete_list_setting(api_settings, setting_id)})
    except KeyError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/api/test")
def test_settings_api(request: ApiSettingTestRequest) -> dict[str, object]:
    try:
        setting = resolve_api_test_setting(request, not_found_message="API 配置不存在")
        diagnostic = deepseek_client.diagnose(setting)
        return success_payload(data={**diagnostic, "ok": diagnostic.get("ok", "true")})
    except Exception as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/settings/image")
def settings_image() -> dict[str, object]:
    return success_payload(data=image_api_settings.list_payload())


@router.post("/settings/image")
def save_settings_image(request: ImageApiSettingRequest) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **save_list_setting(image_api_settings, request.model_dump())})
    except ValueError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/image/active")
def activate_settings_image(request: SettingActiveRequest) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **activate_list_setting(image_api_settings, request.id)})
    except (KeyError, ValueError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.delete("/settings/image/{setting_id}")
def delete_settings_image(setting_id: str) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **delete_list_setting(image_api_settings, setting_id)})
    except KeyError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/image/test")
def test_settings_image(request: ImageApiSettingTestRequest) -> dict[str, object]:
    try:
        setting = resolve_image_api_test_setting(request, not_found_message="图片 API 配置不存在")
        diagnostic = image_api_settings.diagnose(setting)
        if request.real_test and diagnostic.get("ok") == "true":
            output_dir = storage.WRITER_DIR / "_api_tests"
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            output_path = output_dir / f"image_api_test_{stamp}.png"
            result = writer_tools.generate_image(
                request.prompt or "一张简洁的测试图，白色背景，中心写有少量简体中文文字：测试",
                output_path,
                setting=setting,
            )
            diagnostic = {
                **diagnostic,
                "real_test": "true",
                "generated_path": storage.storage_relative(output_path),
                "message": f"图片 API 字段诊断通过，并已真实生成测试图片：{result.get('path')}",
            }
        return success_payload(data={**diagnostic, "ok": diagnostic.get("ok", "true")})
    except Exception as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/settings/asr")
def settings_asr() -> dict[str, object]:
    return success_payload(data=asr_settings.list_payload())


@router.post("/settings/asr")
def save_settings_asr(request: AsrSettingRequest) -> dict[str, object]:
    try:
        return success_payload(data={"ok": True, **save_list_setting(asr_settings, request.model_dump())})
    except ValueError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.post("/settings/asr/test")
def test_settings_asr(request: AsrSettingRequest) -> dict[str, object]:
    try:
        return success_payload(
            data={
                **test_asr_setting_payload(request.model_dump(), transcribe_audio_url_fn=transcribe_audio_url),
            }
        )
    except (ValueError, RuntimeError) as exc:
        asr_settings.mark_test_result(False, str(exc))
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/libraries/{library_id}/files")
def library_files(library_id: str, request: Request, pending_focus: bool = False) -> dict[str, object]:
    return success_payload(data={"items": _list_library_files(library_id, pending_focus=pending_focus, context=_request_context(request))})


@router.get("/libraries/{library_id}/file")
def library_file(library_id: str, markdown_path: str, request: Request) -> dict[str, object]:
    item, text = _read_library_file(library_id, markdown_path, context=_request_context(request))
    return success_payload(data={"item": item, "markdown": text})


@router.post("/libraries/{library_id}/file")
def update_library_file(library_id: str, markdown_path: str, request: LibraryFileUpdateRequest, http_request: Request) -> dict[str, object]:
    if not request.markdown.strip():
        return success_payload(data={"ok": False, "error": "Markdown 正文不能为空"})
    path = _resolve_library_markdown_path(library_id, markdown_path)
    text = _replace_markdown_title(request.markdown, request.title.strip() or _markdown_title(request.markdown) or path.stem)
    text = _replace_markdown_note(text, request.note)
    path.write_text(text, encoding="utf-8")
    item = _library_file_payload(path, library_id)
    if request.note.strip():
        item["note"] = request.note.strip()
    return success_payload(data={"ok": True, "item": item, "markdown": text})


@router.delete("/libraries/{library_id}/file")
def delete_library_file(library_id: str, markdown_path: str, request: Request) -> dict[str, object]:
    context = _request_context(request)
    path = _resolve_library_markdown_path(library_id, markdown_path)
    _assert_library_file_visible(path, context)
    trashed_path = _move_library_file_to_trash(library_id, path)
    return success_payload(
        data={
            "ok": True,
            "item": {
                "library": library_id,
                "markdown_path": storage.storage_relative(path),
                "trash_path": storage.storage_relative(trashed_path),
            },
            "trash": _trash_status(),
        }
    )


@router.get("/settings/trash")
def settings_trash_status(request: Request) -> dict[str, object]:
    status_payload = _trash_status()
    if not _local_diagnostics_visible(request):
        return success_payload(data={**status_payload, "path": "", "items": [], "redacted": True})
    return success_payload(data={**status_payload, "items": _list_trash_files(), "redacted": False})


@router.post("/settings/trash/delete")
def delete_selected_trash_files(request: TrashSelectionRequest, http_request: Request) -> dict[str, object]:
    _require_local_diagnostics(http_request)
    result = _delete_trash_paths(request.trash_paths)
    return success_payload(data={"ok": True, **result, **_trash_status(), "items": _list_trash_files()})


@router.post("/settings/trash/restore")
def restore_selected_trash_files(request: TrashSelectionRequest, http_request: Request) -> dict[str, object]:
    _require_local_diagnostics(http_request)
    result = _restore_trash_paths(request.trash_paths)
    return success_payload(data={"ok": True, **result, **_trash_status(), "items": _list_trash_files()})


@router.delete("/settings/trash")
def clear_settings_trash(request: Request) -> dict[str, object]:
    _require_local_diagnostics(request)
    status = _trash_status()
    deleted_files = int(status["file_count"])
    deleted_bytes = int(status["size_bytes"])
    manifest = _load_trash_manifest()
    remaining_manifest: dict[str, dict[str, object]] = {}
    failed_sources: list[str] = []
    for source, entry in manifest.items():
        source_path = Path(source)
        try:
            if source_path.exists():
                _unlink_writable(source_path)
        except OSError:
            remaining_manifest[source] = entry
            failed_sources.append(source)
    if storage.TRASH_DIR.exists():
        for child in storage.TRASH_DIR.iterdir():
            if child.name == ".trash_manifest.json":
                continue
            if child.is_dir():
                _rmtree_writable(child)
            else:
                _unlink_writable(child)
    storage.TRASH_DIR.mkdir(parents=True, exist_ok=True)
    if remaining_manifest:
        _save_trash_manifest(remaining_manifest)
    else:
        _trash_manifest_path().unlink(missing_ok=True)
    return success_payload(
        data={
            "ok": True,
            "deleted_files": deleted_files,
            "deleted_bytes": deleted_bytes,
            "failed_sources": failed_sources,
            **_trash_status(),
        }
    )


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
def inspect_link(request: InspectLinkRequest, http_request: Request) -> dict[str, object]:
    _consume_daily_quota(_request_context(http_request), "link_parse_daily", "链接解析")
    return success_payload(data={"ok": True, "item": _inspect_link(str(request.url))})


@router.post("/collect/browser-extract-link")
def browser_extract_link(request: BrowserExtractLinkRequest, http_request: Request) -> dict[str, object]:
    _consume_daily_quota(_request_context(http_request), "link_parse_daily", "链接解析")
    url = str(request.url)
    inspection = _inspect_link(url)
    link_type = str(inspection.get("link_type") or "")
    if link_type in {"platform_douyin", "platform_bilibili", "platform_wechat_channels"}:
        return success_payload(data={"ok": False, "error": "音视频平台链接请放入「音视频」入口读取。"})
    if link_type == "pdf":
        return success_payload(data={"ok": False, "error": "PDF 链接请使用文档解析流程，不需要浏览器提取。"})

    try:
        fetched = _browser_extract_webpage_text(
            url=url,
            title=request.title,
            wait_ms=request.wait_ms,
            scroll_times=request.scroll_times,
            scroll_pause_ms=request.scroll_pause_ms,
            selector=request.selector,
        )
    except (OSError, subprocess.CalledProcessError, FileNotFoundError, TimeoutError, ValueError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})

    title = request.title.strip() or fetched.get("title") or str(inspection.get("title") or url)
    markdown = _render_link_markdown_block(1, url, title, fetched)
    return success_payload(
        data={
            "ok": True,
            "title": title,
            "note": f"浏览器提取：等待 {fetched.get('wait_ms', request.wait_ms)}ms，滚动 {fetched.get('scroll_times', request.scroll_times)} 次。",
            "markdown": markdown,
            "source": fetched.get("source") or str(inspection.get("source") or url),
            "item": fetched,
        }
    )


@router.post("/collect/raw-markdown")
def collect_raw_markdown(request: CollectRawMarkdownRequest, http_request: Request) -> dict[str, object]:
    if not request.items:
        return success_payload(data={"ok": False, "error": "待分析队列不能为空"})

    material_type = request.material_type.strip()
    title = request.title.strip() or _default_raw_title(material_type, request.items)
    try:
        body, sources, errors = _extract_queue_text(material_type, request.items, parser_mode=request.parser_mode)
    except (KeyError, ValueError, OSError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})

    if not body.strip():
        error = "未提取到可保存的文本"
        if errors:
            error = f"{error}；" + "；".join(errors[:3])
        return success_payload(data={"ok": False, "error": error, "errors": errors})

    body = _clean_raw_markdown_body(body)
    context = _request_context(http_request)
    _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
    polish_meta = _polish_raw_material(material_type, body, title)
    if polish_meta["markdown"]:
        body = polish_meta["markdown"]
    if polish_meta["title"]:
        title = polish_meta["title"]
    title = _resolve_raw_title(request.title, title, body)

    owner_meta = _owner_meta(context)
    item = _write_raw_markdown(
        material_type=material_type,
        title=title,
        body=body,
        source="; ".join(sources)[:1000] if sources else material_type,
        extra_meta={
            "队列数量": str(len(request.items)),
            "失败数量": str(len(errors)),
            **owner_meta,
            **polish_meta["extra_meta"],
        },
    )
    return success_payload(data={"ok": True, "item": item, "errors": errors, "polish": polish_meta["response"]})


@router.post("/collect/raw-file")
def collect_raw_file(request: CollectRawFileRequest, http_request: Request) -> dict[str, object]:
    title = request.title.strip() or _markdown_title(request.markdown) or "raw-material"
    markdown = request.markdown.strip()
    if not markdown:
        return success_payload(data={"ok": False, "error": "原文 Markdown 不能为空"})

    material_type = request.material_type.strip() or "text"
    source = request.source.strip() or material_type
    extra_meta = {"人工备注": request.note.strip()} if request.note.strip() else {}
    extra_meta.update(_owner_meta(_request_context(http_request)))
    item = _write_raw_markdown(
        material_type=material_type,
        title=title,
        body=markdown,
        source=source,
        extra_meta=extra_meta,
    )
    return success_payload(data={"ok": True, "item": item})


@router.post("/collect/readable-draft")
def collect_readable_draft(request: CollectReadableDraftRequest, http_request: Request) -> dict[str, object]:
    return success_payload(data=_build_readable_draft(request, context=_request_context(http_request)))


def _build_readable_draft(request: CollectReadableDraftRequest, context: dict[str, object]) -> dict[str, object]:
    if not request.items:
        return {"ok": False, "error": "待处理队列不能为空"}

    material_type = request.material_type.strip()
    title = request.title.strip() or _default_raw_title(material_type, request.items)
    try:
        body, sources, errors = _extract_queue_text(material_type, request.items, parser_mode=request.parser_mode)
    except (KeyError, ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}

    if not body.strip():
        error = "未提取到可生成原文草稿的文本"
        if errors:
            error = f"{error}：" + "；".join(errors[:3])
        return {"ok": False, "error": error, "errors": errors}

    body = _clean_raw_markdown_body(body)
    _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
    polish_meta = (
        _polish_screenshot_readable_draft(body, title)
        if material_type == "screenshot"
        else _polish_raw_material(material_type, body, title)
    )
    if polish_meta["markdown"]:
        body = polish_meta["markdown"]
    if polish_meta["title"]:
        title = polish_meta["title"]
    title = _resolve_raw_title(request.title, title, body)

    note_parts = []
    if sources:
        note_parts.append(f"来源材料：{'；'.join(sources[:5])}")
    if errors:
        note_parts.append(f"提取异常：{'；'.join(errors[:3])}")

    return {
        "ok": True,
        "title": title,
        "note": " ".join(part for part in note_parts if part).strip(),
        "markdown": body,
        "source": "; ".join(sources)[:1000] if sources else material_type,
        "errors": errors,
        "polish": polish_meta["response"],
    }


@router.post("/learn/refine-knowledge-cluster")
def learn_refine_knowledge_cluster(request: LearnRefineKnowledgeClusterRequest, http_request: Request) -> dict[str, object]:
    if not request.raw_paths:
        return success_payload(data={"ok": False, "error": "请先从原料库选择待处理文件"})

    try:
        context = _request_context(http_request)
        sources = [_read_raw_material_file(path, context=context) for path in request.raw_paths]
        combined_raw_text = _combine_raw_material_sources(sources)
        if not combined_raw_text.strip():
            return success_payload(data={"ok": False, "error": "选中的原料文件没有可学习文本"})

        source_hash = hashlib.sha256(
            "|".join(item["relative_path"] for item in sources).encode("utf-8")
        ).hexdigest()
        existing = storage.get_knowledge_by_hash(source_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return success_payload(data={"ok": True, "item": existing, "skipped": True})

        _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
        knowledge, learned_raw_text = deepseek_client.generate_knowledge_from_text(combined_raw_text)
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
def learn_save_focus_file(request: LearnSaveFocusRequest, http_request: Request) -> dict[str, object]:
    if not request.raw_paths:
        return success_payload(data={"ok": False, "error": "请先选择本次重点库文件对应的原料"})
    markdown = request.markdown.strip()
    if not markdown:
        return success_payload(data={"ok": False, "error": "重点库 Markdown 不能为空"})

    try:
        context = _request_context(http_request)
        owner_meta = _owner_meta(context)
        sources = [_read_raw_material_file(path, context=context) for path in request.raw_paths]
        source_hash = _raw_sources_hash(sources)
        entry = storage.create_or_update_knowledge_entry(
            [],
            source_hash,
            source_type="raw_materials",
            source_ids=[item["relative_path"] for item in sources],
            owner_user_id=owner_meta.get("owner_user_id") or None,
            workspace_id=owner_meta.get("workspace_id") or None,
        )
        title = request.title.strip() or _markdown_title(markdown) or "focus-knowledge"
        markdown_path = storage.markdown_path_for(title, source_hash, entry.get("created_at"))
        markdown = _with_owner_meta(markdown, owner_meta)
        markdown_path.write_text(markdown, encoding="utf-8")
        meta = _markdown_meta(markdown)
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=title,
            topic=meta.get("主题") or "",
            tags=json.dumps(_tags_from_meta(meta), ensure_ascii=False),
            status="ready",
            error_message=None,
            owner_user_id=owner_meta.get("owner_user_id") or None,
            workspace_id=owner_meta.get("workspace_id") or None,
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
def mine_perspectives(request: Request) -> dict[str, object]:
    context = _request_context(request)
    return success_payload(data={"items": _list_perspective_profiles(context=context)})


@router.post("/mine/perspectives")
def mine_save_perspective(profile: MinePerspectiveProfile, request: Request) -> dict[str, object]:
    context = _request_context(request)
    owner_meta = _owner_meta(context)
    saved = storage.upsert_perspective_profile(
        profile.model_dump(),
        owner_user_id=owner_meta.get("owner_user_id") or None,
        workspace_id=owner_meta.get("workspace_id") or None,
    )
    return success_payload(data={"ok": True, "item": saved, "items": _list_perspective_profiles(context=context)})


@router.delete("/mine/perspectives/{profile_id}")
def mine_delete_perspective(profile_id: str, request: Request) -> dict[str, object]:
    if not profile_id.startswith("custom_"):
        return success_payload(data={"ok": False, "error": "预设视角不能删除，请先复制为自定义视角"})
    try:
        context = _request_context(request)
        deleted = storage.delete_perspective_profile(profile_id, owner_user_id=_owner_meta(context).get("owner_user_id") or None)
    except KeyError as exc:
        return success_payload(data={"ok": False, "error": str(exc)})
    return success_payload(data={"ok": True, "item": deleted, "items": _list_perspective_profiles(context=context)})


@router.post("/mine/interpret")
def mine_interpret(request: MineInterpretRequest, http_request: Request) -> dict[str, object]:
    if not request.sources:
        return success_payload(data={"ok": False, "error": "请先从全局库勾选原料库或重点库文件加入待解读队列"})
    try:
        context = _request_context(http_request)
        sources = [_read_mine_source(item, context=context) for item in request.sources]
        _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
        result = deepseek_client.interpret_from_perspective(sources, request.perspective.model_dump())
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
def mine_save_perspective_file(request: MineSavePerspectiveRequest, http_request: Request) -> dict[str, object]:
    if not request.sources:
        return success_payload(data={"ok": False, "error": "视角解读必须保留来源文件"})
    markdown = request.markdown.strip()
    if not markdown:
        return success_payload(data={"ok": False, "error": "视角 Markdown 不能为空"})
    try:
        context = _request_context(http_request)
        owner_meta = _owner_meta(context)
        sources = [_read_mine_source(item, context=context) for item in request.sources]
        title = request.title.strip() or _markdown_title(markdown) or f"{request.perspective.name}视角解读"
        source_hash = hashlib.sha256(
            "|".join(f"{item['library']}:{item['relative_path']}" for item in sources).encode("utf-8")
        ).hexdigest()
        now = datetime.now().isoformat(timespec="seconds")
        dated_dir = storage.MINING_DIR / datetime.now().strftime("%Y-%m-%d")
        dated_dir.mkdir(parents=True, exist_ok=True)
        path = dated_dir / f"{storage.safe_filename(title, fallback='perspective')}_{source_hash[:8]}.md"
        markdown = _with_owner_meta(markdown, owner_meta)
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
                    "markdown_path": storage.storage_relative(path),
                    "created_at": now,
                    "source_files": sources,
                    "hash": source_hash,
                },
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        return success_payload(data={"ok": False, "error": str(exc)})


@router.get("/create/projects")
def create_projects(request: Request) -> dict[str, object]:
    owner_user_id, include_ownerless = _writer_project_scope(_request_context(request))
    return success_payload(data={"items": writer_tools.list_projects(owner_user_id=owner_user_id, include_ownerless=include_ownerless)})


@router.post("/create/projects")
def create_project(request: CreateProjectRequest, http_request: Request) -> dict[str, object]:
    owner_meta = _owner_meta(_request_context(http_request))
    project = writer_tools.create_project(
        name=request.name,
        project_type=request.project_type,
        description=request.description,
        owner_user_id=owner_meta.get("owner_user_id") or None,
        workspace_id=owner_meta.get("workspace_id") or None,
    )
    return success_payload(data={"item": project})


@router.get("/create/projects/{project_id}")
def read_create_project(project_id: str, request: Request) -> dict[str, object]:
    return success_payload(data={"item": _load_writer_project(project_id, _request_context(request))})


@router.patch("/create/projects/{project_id}")
def update_create_project(project_id: str, request: UpdateCreateProjectRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    _load_writer_project(project_id, context)
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
def update_create_project_files(project_id: str, request: CreateProjectFilesRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    _load_writer_project(project_id, context)
    sources = [_read_create_source(item, context=context) for item in request.files]
    project = writer_tools.set_project_library_files(project_id, sources)
    return success_payload(data={"item": project})


@router.post("/create/projects/{project_id}/writer/topics")
def create_writer_topics(project_id: str, request: CreateWriterTopicRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    project = _load_writer_project(project_id, context)
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
    result = deepseek_client.generate_topics(
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
    )
    return success_payload(data={"ok": True, **result.model_dump()})


@router.post("/create/projects/{project_id}/writer/article")
def create_writer_article(project_id: str, request: CreateWriterArticleRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    project = _load_writer_project(project_id, context)
    if project.get("type") != "article":
        return success_payload(data={"ok": False, "error": "当前只实现文章项目，图文和视频创作暂未开放"})
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
    result = deepseek_client.generate_wechat_article(
        request.topic,
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
    )
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, result.markdown)
    project = writer_tools.update_project(project_id, topic=request.topic)
    return success_payload(
        data={
            "ok": True,
            **result.model_dump(),
            "project": project,
            "workspace": storage.storage_relative(workspace),
            "article_path": storage.storage_relative(article_path),
        }
    )


@router.post("/create/projects/{project_id}/writer/revise")
def create_writer_revise(project_id: str, request: CreateWriterReviseRequest, http_request: Request) -> dict[str, object]:
    if not request.instruction.strip():
        return success_payload(data={"ok": False, "error": "请填写修改要求"})
    context = _request_context(http_request)
    project = _load_writer_project(project_id, context)
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return success_payload(data={"ok": False, "error": "请先从全局库加入库文件"})
    _consume_daily_quota(context, "llm_generate_daily", "AI 生成")
    result = deepseek_client.revise_wechat_article(
        request.markdown,
        request.instruction,
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
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
            "workspace": storage.storage_relative(workspace),
            "article_path": storage.storage_relative(article_path),
            "version_path": storage.storage_relative(version_path),
        }
    )


@router.post("/create/projects/{project_id}/writer/format")
def create_writer_format(project_id: str, request: CreateWriterFormatRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    project = _load_writer_project(project_id, context)
    if project.get("type") != "article":
        return success_payload(data={"ok": False, "error": "当前只实现文章项目，图文和视频创作暂未开放"})
    workspace = writer_tools.resolve_project_workspace(project_id)
    result = writer_tools.format_article(workspace, markdown=request.markdown, theme=request.theme)
    project = writer_tools.update_project(project_id)
    return success_payload(
        data={
            "ok": True,
            "project": project,
            "workspace": storage.storage_relative(workspace),
            **result,
        }
    )


@router.post("/create/projects/{project_id}/writer/publish/preflight")
def create_writer_publish_preflight(project_id: str, request: CreateWriterPublishPreflightRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    _require_local_or_admin(context, "公网内测普通用户不能操作公众号发布预检")
    project = _load_writer_project(project_id, context)
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
            "workspace": storage.storage_relative(workspace),
            **result,
        }
    )


@router.post("/create/projects/{project_id}/writer/publish")
def create_writer_publish(project_id: str, request: CreateWriterPublishPreflightRequest, http_request: Request) -> dict[str, object]:
    context = _request_context(http_request)
    _require_local_or_admin(context, "公网内测普通用户不能发布到服务器公众号")
    project = _load_writer_project(project_id, context)
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
                "workspace": storage.storage_relative(workspace),
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
            "project": _load_writer_project(project_id, context),
            "workspace": storage.storage_relative(workspace),
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


def _local_diagnostics_visible(request: Request) -> bool:
    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        return context["deploymentMode"] == "local" or context["user"]["role"] == "admin"
    except HTTPException:
        return False


def _require_local_diagnostics(request: Request) -> None:
    if not _local_diagnostics_visible(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="普通 cloud 用户不能操作本地诊断文件")


def _request_context(request: Request) -> dict[str, object]:
    with storage.connect() as conn:
        return current_context(request, conn)


def _require_local_or_admin(context: dict[str, object], detail: str) -> None:
    user = context.get("user") or {}
    if context.get("deploymentMode") == "local" or (isinstance(user, dict) and user.get("role") == "admin"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _quota_detail(label: str, status_payload: dict[str, object]) -> str:
    used = status_payload.get("used", 0)
    limit = status_payload.get("limit", 0)
    return f"{label}今日额度已用完（{used}/{limit}）"


def _consume_daily_quota(context: dict[str, object], key: str, label: str) -> None:
    with storage.connect() as conn:
        _consume_daily_quota_in_conn(conn, context, key, label)


def _enforce_concurrent_jobs(conn, context: dict[str, object]) -> None:
    if not quota_service.is_enforced(context):
        return
    user_id, _workspace_id = quota_service.user_ids(context)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    result = quota_service.check_concurrent_jobs(conn, user_id=user_id)
    if not result["allowed"]:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=_quota_detail("并发任务", result))


LLM_JOB_KINDS = {"learn_refine", "mine_interpret", "writer_topics", "writer_article", "writer_revise"}
IMAGE_JOB_KINDS = {"image_generate", "writer_image_item"}
PUBLISH_JOB_KINDS = {"publish_preflight"}
SUPPORTED_JOB_KINDS = {"readable_draft", "media_transcript", *LLM_JOB_KINDS, *IMAGE_JOB_KINDS, *PUBLISH_JOB_KINDS}


def _validate_supported_job(kind: str) -> None:
    if kind.strip() not in SUPPORTED_JOB_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"暂不支持的任务类型：{kind}")


def _consume_daily_quota_in_conn(conn, context: dict[str, object], key: str, label: str) -> None:
    if not quota_service.is_enforced(context):
        return
    user_id, workspace_id = quota_service.user_ids(context)
    if not user_id or not workspace_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    result = quota_service.consume_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key)
    if not result["allowed"]:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=_quota_detail(label, result))
    conn.commit()


def _consume_job_quota(conn, context: dict[str, object], kind: str, payload: object | None = None) -> None:
    if kind == "learn_refine":
        if isinstance(payload, dict):
            _request, _sources, _combined_raw_text, _source_hash, existing = _learn_refine_job_inputs(payload, context)
            if existing and existing.get("markdown_path") and existing.get("status") == "ready":
                return
        _consume_daily_quota_in_conn(conn, context, "llm_generate_daily", "AI 生成")
        return
    if kind in LLM_JOB_KINDS:
        _consume_daily_quota_in_conn(conn, context, "llm_generate_daily", "AI 生成")


def _job_payload_dict(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务 payload 必须是对象")
    return payload


def _job_project_id(payload: dict[str, object]) -> str:
    project_id = str(payload.get("project_id") or payload.get("projectId") or "").strip()
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务缺少 project_id")
    return project_id


def _validate_job_payload(kind: str, payload: object, context: dict[str, object], *, require_executable: bool = True) -> None:
    payload_dict = _job_payload_dict(payload)
    try:
        if kind == "readable_draft":
            if require_executable:
                CollectReadableDraftRequest.model_validate(payload_dict)
            return
        if kind == "learn_refine":
            _learn_refine_job_inputs(payload_dict, context)
            return
        if kind == "mine_interpret":
            _mine_interpret_job_inputs(payload_dict, context)
            return
        if kind == "media_transcript":
            request = MediaTranscriptJobRequest.model_validate(payload_dict)
            _validate_media_job_items(request.media_ids, context)
            return
        if kind == "image_generate":
            project = _load_writer_project(_job_project_id(payload_dict), context)
            request = WriterImageGenerateJobRequest.model_validate(payload_dict)
            cover_prompt = request.cover_prompt or project.get("cover_prompt")
            content_prompts = request.content_image_prompts or project.get("content_image_prompts") or []
            if not cover_prompt and not content_prompts:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="璇峰厛鐢熸垚鎴栧～鍐欓厤鍥炬彁绀鸿瘝")
            return
        if kind == "writer_image_item":
            _load_writer_project(_job_project_id(payload_dict), context)
            request = WriterImageItemJobRequest.model_validate(payload_dict)
            if request.kind not in {"cover", "content"}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image kind must be cover or content")
            if not request.prompt.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="璇峰～鍐欓厤鍥炬彁绀鸿瘝")
            if request.kind == "content" and (request.index is None or request.index < 1):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content image index must be greater than 0")
            return
        if kind == "publish_preflight":
            _require_local_or_admin(context, "公网内测普通用户不能操作公众号发布预检")
            _load_writer_project(_job_project_id(payload_dict), context)
            WriterPublishPreflightJobRequest.model_validate(payload_dict)
            return
        if kind == "writer_topics":
            project = _load_writer_project(_job_project_id(payload_dict), context)
            request = CreateWriterTopicRequest.model_validate(payload_dict)
            if not _project_writer_sources(project, request.library_files, context=context):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先从全局库加入库文件")
            return
        if kind == "writer_article":
            project = _load_writer_project(_job_project_id(payload_dict), context)
            if project.get("type") != "article":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前只实现文章项目，图文和视频创作暂未开放")
            request = CreateWriterArticleRequest.model_validate(payload_dict)
            if not _project_writer_sources(project, request.library_files, context=context):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先从全局库加入库文件")
            return
        if kind == "writer_revise":
            project = _load_writer_project(_job_project_id(payload_dict), context)
            request = CreateWriterReviseRequest.model_validate(payload_dict)
            if not request.instruction.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写修改要求")
            if not _project_writer_sources(project, request.library_files, context=context):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先从全局库加入库文件")
            return
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"暂不支持的任务类型：{kind}")


def _run_job(job_id: str, context: dict[str, object]) -> None:
    storage.init_storage()
    with storage.connect() as conn:
        if not job_service.start_job(conn, job_id=job_id):
            return
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return
        job = job_service.job_row_to_dict(row)
    try:
        result = _execute_job(job, context)
        if result.get("ok") is False:
            raise ValueError(str(result.get("error") or "任务处理失败"))
        with storage.connect() as conn:
            job_service.complete_job(conn, job_id=job_id, result=result, message="任务处理完成")
    except Exception as exc:
        with storage.connect() as conn:
            job_service.fail_job(conn, job_id=job_id, error=str(exc))


def _execute_job(job: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    kind = str(job.get("kind") or "")
    payload = job.get("payload") or {}
    if kind == "readable_draft" and isinstance(payload, dict):
        request = CollectReadableDraftRequest.model_validate(payload)
        return _build_readable_draft(request, context=context)
    if kind == "learn_refine" and isinstance(payload, dict):
        return _execute_learn_refine_job(payload, context)
    if kind == "mine_interpret" and isinstance(payload, dict):
        return _execute_mine_interpret_job(payload, context)
    if kind == "media_transcript" and isinstance(payload, dict):
        return _execute_media_transcript_job(payload, context)
    if kind == "image_generate" and isinstance(payload, dict):
        return _execute_writer_images_job(payload, context)
    if kind == "writer_image_item" and isinstance(payload, dict):
        return _execute_writer_image_item_job(payload, context)
    if kind == "publish_preflight" and isinstance(payload, dict):
        return _execute_publish_preflight_job(payload, context)
    if kind == "writer_topics" and isinstance(payload, dict):
        return _execute_writer_topics_job(payload, context)
    if kind == "writer_article" and isinstance(payload, dict):
        return _execute_writer_article_job(payload, context)
    if kind == "writer_revise" and isinstance(payload, dict):
        return _execute_writer_revise_job(payload, context)
    raise ValueError(f"暂不支持的任务类型：{kind}")


def _learn_refine_job_inputs(
    payload: dict[str, object],
    context: dict[str, object],
) -> tuple[LearnRefineKnowledgeClusterRequest, list[dict[str, str]], str, str, dict[str, object] | None]:
    request = LearnRefineKnowledgeClusterRequest.model_validate(payload)
    if not request.raw_paths:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先从原文库选择待处理文件")
    try:
        sources = [_read_raw_material_file(path, context=context) for path in request.raw_paths]
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    combined_raw_text = _combine_raw_material_sources(sources)
    if not combined_raw_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="閫変腑鐨勫師鏂欐枃浠舵病鏈夊彲瀛︿範鏂囨湰")
    source_hash = _raw_sources_hash(sources)
    existing = storage.get_knowledge_by_hash(source_hash)
    return request, sources, combined_raw_text, source_hash, existing


def _execute_learn_refine_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    request, sources, combined_raw_text, source_hash, existing = _learn_refine_job_inputs(payload, context)
    if existing and existing.get("markdown_path") and existing.get("status") == "ready":
        return {"ok": True, "item": existing, "skipped": True}
    knowledge, learned_raw_text = deepseek_client.generate_knowledge_from_text(combined_raw_text)
    _ = learned_raw_text
    if request.title.strip():
        knowledge.title = request.title.strip()
    markdown = _render_focus_markdown(knowledge, sources)
    return {
        "ok": True,
        "source_files": sources,
        "source_hash": source_hash,
        "cluster_count": len(knowledge.clusters),
        "markdown": markdown,
        "existing_item": existing,
    }


def _mine_interpret_job_inputs(
    payload: dict[str, object],
    context: dict[str, object],
) -> tuple[MineInterpretRequest, list[dict[str, str]]]:
    request = MineInterpretRequest.model_validate(payload)
    if not request.sources:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先从全局库勾选原文库或重点库文件加入待解读队列")
    try:
        sources = [_read_mine_source(item, context=context) for item in request.sources]
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return request, sources


def _execute_mine_interpret_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    request, sources = _mine_interpret_job_inputs(payload, context)
    result = deepseek_client.interpret_from_perspective(sources, request.perspective.model_dump())
    markdown = _render_perspective_markdown(result, request.perspective, sources)
    return {
        "ok": True,
        "markdown": markdown,
        "source_files": sources,
        "title": result.title,
        "perspective": request.perspective.model_dump(),
    }


def _media_item_visible(item: dict[str, object], context: dict[str, object]) -> bool:
    user = context.get("user") or {}
    if not isinstance(user, dict):
        return False
    if context.get("deploymentMode") == "local" or user.get("role") == "admin":
        return True
    return bool(item.get("owner_user_id") and str(item.get("owner_user_id")) == str(user.get("id") or ""))


def _assert_media_item_visible(item: dict[str, object], context: dict[str, object]) -> None:
    if not _media_item_visible(item, context):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体文件不存在")


def _validate_media_job_items(media_ids: list[int], context: dict[str, object]) -> None:
    if not media_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择音视频素材")
    for media_id in media_ids:
        try:
            item = storage.get_media_source(int(media_id))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体文件不存在") from exc
        _assert_media_item_visible(item, context)


def _execute_media_transcript_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    request = MediaTranscriptJobRequest.model_validate(payload)
    _validate_media_job_items(request.media_ids, context)
    results: list[dict[str, object]] = []
    for media_id in request.media_ids:
        try:
            item = storage.get_media_source(int(media_id))
            _assert_media_item_visible(item, context)
            storage.update_media_source(int(media_id), status="transcribing", error_message=None)
            transcript, transcript_kind = _ensure_media_transcript_with_platform_import(item)
            refreshed = storage.get_media_source(int(media_id))
            formatted = media_parser.format_media_transcript(refreshed, transcript)
            storage.update_media_source(int(media_id), status="ready", error_message=None)
            refreshed = storage.get_media_source(int(media_id))
            results.append(
                {
                    "ok": True,
                    "item": refreshed,
                    "transcript": formatted,
                    "transcript_kind": transcript_kind,
                }
            )
        except Exception as exc:
            try:
                updated = storage.update_media_source(int(media_id), status="error", error_message=str(exc))
            except Exception:
                updated = {"id": media_id}
            results.append({"ok": False, "item": updated, "error": str(exc)})
    return {"ok": any(item.get("ok") for item in results), "items": results}


def _execute_writer_images_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    request = WriterImageGenerateJobRequest.model_validate(payload)
    project = _load_writer_project(request.project_id, context)
    cover_prompt = request.cover_prompt or project.get("cover_prompt")
    content_prompts = request.content_image_prompts or project.get("content_image_prompts") or []
    if not cover_prompt and not content_prompts:
        return {"ok": False, "error": "璇峰厛鐢熸垚鎴栧～鍐欓厤鍥炬彁绀鸿瘝"}
    workspace = writer_tools.resolve_project_workspace(request.project_id)
    images = writer_tools.generate_writer_images(
        workspace,
        cover_prompt=str(cover_prompt) if cover_prompt else None,
        content_prompts=[str(item) for item in content_prompts],
    )
    project = writer_tools.update_project(request.project_id, images=images)
    return {
        "ok": True,
        "project_id": request.project_id,
        "project": project,
        "images": images,
        "partial": bool(images.get("partial")),
    }


def _execute_writer_image_item_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    request = WriterImageItemJobRequest.model_validate(payload)
    _load_writer_project(request.project_id, context)
    if request.kind not in {"cover", "content"}:
        return {"ok": False, "error": "Image kind must be cover or content"}
    if not request.prompt.strip():
        return {"ok": False, "error": "璇峰～鍐欓厤鍥炬彁绀鸿瘝"}
    if request.kind == "content" and (request.index is None or request.index < 1):
        return {"ok": False, "error": "Content image index must be greater than 0"}
    workspace = writer_tools.resolve_project_workspace(request.project_id)
    images = writer_tools.generate_writer_image_item(
        workspace,
        request.kind,
        request.prompt,
        index=request.index,
    )
    project = writer_tools.update_project(request.project_id, images=images)
    return {
        "ok": True,
        "project_id": request.project_id,
        "project": project,
        "images": images,
        "partial": bool(images.get("partial")),
    }


def _execute_publish_preflight_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    _require_local_or_admin(context, "公网内测普通用户不能操作公众号发布预检")
    request = WriterPublishPreflightJobRequest.model_validate(payload)
    project = _load_writer_project(request.project_id, context)
    workspace = writer_tools.resolve_project_workspace(request.project_id)
    title = request.title.strip() or project.get("name") or "未命名文章"
    result = writer_tools.publish_preflight(
        workspace,
        str(title),
        author=request.author or "Bobo",
        digest=request.digest,
        cover_path=request.cover_path,
    )
    return {
        "ok": True,
        "project_id": request.project_id,
        "project": project,
        "workspace": storage.storage_relative(workspace),
        "preflight": result,
    }


def _execute_writer_topics_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    project_id = _job_project_id(payload)
    request = CreateWriterTopicRequest.model_validate(payload)
    project = _load_writer_project(project_id, context)
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return {"ok": False, "error": "请先从全局库加入库文件"}
    result = deepseek_client.generate_topics(
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
    )
    return {"ok": True, "project_id": project_id, "project": project, **result.model_dump()}


def _execute_writer_article_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    project_id = _job_project_id(payload)
    request = CreateWriterArticleRequest.model_validate(payload)
    project = _load_writer_project(project_id, context)
    if project.get("type") != "article":
        return {"ok": False, "error": "当前只实现文章项目，图文和视频创作暂未开放"}
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return {"ok": False, "error": "请先从全局库加入库文件"}
    result = deepseek_client.generate_wechat_article(
        request.topic,
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
    )
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, result.markdown)
    project = writer_tools.update_project(project_id, topic=request.topic)
    return {
        "ok": True,
        "project_id": project_id,
        **result.model_dump(),
        "project": project,
        "workspace": storage.storage_relative(workspace),
        "article_path": storage.storage_relative(article_path),
    }


def _execute_writer_revise_job(payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    project_id = _job_project_id(payload)
    request = CreateWriterReviseRequest.model_validate(payload)
    if not request.instruction.strip():
        return {"ok": False, "error": "请填写修改要求"}
    project = _load_writer_project(project_id, context)
    sources = _project_writer_sources(project, request.library_files, context=context)
    if not sources:
        return {"ok": False, "error": "请先从全局库加入库文件"}
    result = deepseek_client.revise_wechat_article(
        request.markdown,
        request.instruction,
        _writer_markdown_files(sources),
        setting=deepseek_client.current_setting(),
    )
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, result.markdown)
    version_path = writer_tools.write_article(
        workspace,
        result.markdown,
        f"article_revised_{datetime.now().strftime('%H%M%S')}.md",
    )
    project = writer_tools.update_project(project_id)
    return {
        "ok": True,
        "project_id": project_id,
        **result.model_dump(),
        "project": project,
        "workspace": storage.storage_relative(workspace),
        "article_path": storage.storage_relative(article_path),
        "version_path": storage.storage_relative(version_path),
    }


def _owner_meta(context: dict[str, object]) -> dict[str, str]:
    user = context.get("user") or {}
    workspace = context.get("workspace") or {}
    if not isinstance(user, dict) or not isinstance(workspace, dict):
        return {}
    return {
        "owner_user_id": str(user.get("id") or ""),
        "workspace_id": str(workspace.get("id") or ""),
    }


def _writer_project_scope(context: dict[str, object]) -> tuple[str | None, bool]:
    user = context.get("user") or {}
    if context.get("deploymentMode") == "cloud" and isinstance(user, dict) and user.get("role") != "admin":
        return str(user.get("id") or ""), False
    return None, True


def _load_writer_project(project_id: str, context: dict[str, object]) -> dict[str, object]:
    owner_user_id, include_ownerless = _writer_project_scope(context)
    try:
        return writer_tools.load_project(project_id, owner_user_id=owner_user_id, include_ownerless=include_ownerless)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作项目不存在") from exc


def _library_file_visible(path: Path, context: dict[str, object]) -> bool:
    user = context.get("user") or {}
    if not isinstance(user, dict):
        return False
    if context.get("deploymentMode") == "local" or user.get("role") == "admin":
        return True
    text = path.read_text(encoding="utf-8", errors="ignore")
    meta = _markdown_meta(text)
    owner = meta.get("owner_user_id") or meta.get("Owner User ID")
    if owner and owner == user.get("id"):
        return True
    relative_path = storage.storage_relative(path)
    if not relative_path:
        return False
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT owner_user_id FROM knowledge_entries WHERE markdown_path = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
            (relative_path,),
        ).fetchone()
    return bool(row and row["owner_user_id"] and row["owner_user_id"] == user.get("id"))


def _assert_library_file_visible(path: Path, context: dict[str, object]) -> None:
    if not _library_file_visible(path, context):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="库文件不存在")


def _list_library_files(library_id: str, pending_focus: bool = False, context: dict[str, object] | None = None) -> list[dict[str, object]]:
    roots = _library_scan_roots(library_id)
    if not roots:
        raise ValueError(f"Unsupported library: {library_id}")

    trashed_sources = _trashed_source_paths()
    seen: set[object] = set()
    files: list[Path] = []
    for root in roots:
        try:
            if not root.exists():
                continue
            root_files = list(root.rglob("*.md"))
        except OSError:
            continue
        for path in root_files:
            resolved = path.resolve()
            if str(resolved) in trashed_sources:
                continue
            try:
                identity: object = path.relative_to(root)
            except ValueError:
                identity = resolved
            if identity in seen or resolved in seen:
                continue
            seen.add(identity)
            seen.add(resolved)
            if context is not None and not _library_file_visible(path, context):
                continue
            files.append(path)
    files = sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)
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
    relative_path = storage.storage_relative(path)
    material_type = meta.get("材料类型") or meta.get("material_type") or ""
    tags = [material_type] if material_type else []
    note = meta.get("人工备注") or meta.get("备注") or meta.get("note") or ""
    return {
        "id": relative_path,
        "title": title,
        "library": library_id,
        "status": meta.get("状态") or _default_library_status(library_id),
        "source": meta.get("来源") or meta.get("Source") or "",
        "note": note,
        "material_type": material_type,
        "markdown_path": relative_path,
        "created_at": meta.get("收集时间") or datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "size": stat.st_size,
        "tags": tags,
    }


def _read_library_file(library_id: str, markdown_path: str, context: dict[str, object] | None = None) -> tuple[dict[str, object], str]:
    path = _resolve_library_markdown_path(library_id, markdown_path)
    if context is not None:
        _assert_library_file_visible(path, context)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _library_file_payload(path, library_id), text


def _move_library_file_to_trash(library_id: str, path: Path) -> Path:
    library_name = {"raw": "raw", "focus": "focus", "perspective": "perspective"}.get(library_id, library_id)
    relative_path: Path | None = None
    for root in _library_scan_roots(library_id):
        try:
            relative_path = path.resolve().relative_to(root.resolve())
            break
        except ValueError:
            continue
    if relative_path is None:
        relative_path = Path(path.name)
    target = storage.TRASH_DIR / library_name / relative_path
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        target = target.with_name(f"{target.stem}_{stamp}{target.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:
        pass
    try:
        os.replace(path, target)
    except OSError:
        shutil.copy2(path, target)
        try:
            path.chmod(path.stat().st_mode | stat.S_IWRITE)
        except OSError:
            pass
        try:
            path.unlink()
        except OSError as exc:
            _record_trashed_source(path, target, exc)
    return target


def _trash_manifest_path() -> Path:
    return storage.TRASH_DIR / ".trash_manifest.json"


def _load_trash_manifest() -> dict[str, dict[str, object]]:
    path = _trash_manifest_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _save_trash_manifest(payload: dict[str, dict[str, object]]) -> None:
    path = _trash_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _trashed_source_paths() -> set[str]:
    return set(_load_trash_manifest().keys())


def _record_trashed_source(source_path: Path, trash_path: Path, error: OSError) -> None:
    manifest = _load_trash_manifest()
    resolved = str(source_path.resolve())
    manifest[resolved] = {
        "source_path": resolved,
        "trash_path": str(trash_path.resolve()),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "delete_error": str(error),
    }
    _save_trash_manifest(manifest)


def _trash_library_roots() -> dict[str, Path]:
    return {
        "raw": storage.RAW_MATERIAL_DIR,
        "focus": storage.KNOWLEDGE_DIR,
        "perspective": storage.MINING_DIR,
    }


def _resolve_trash_path(trash_path: str) -> Path:
    normalized = trash_path.replace("\\", "/").strip()
    candidate = Path(normalized)
    if not normalized or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"垃圾箱路径无效：{trash_path}")
    path = storage.TRASH_DIR.joinpath(*candidate.parts).resolve()
    root = storage.TRASH_DIR.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"垃圾箱路径越界：{trash_path}")
    return path


def _trash_relative(path: Path) -> str:
    return str(path.resolve().relative_to(storage.TRASH_DIR.resolve()))


def _trash_source_for(trash_path: Path) -> str:
    resolved_trash = str(trash_path.resolve())
    for source, entry in _load_trash_manifest().items():
        if str(entry.get("trash_path") or "") == resolved_trash:
            return source
    return ""


def _make_writable(path: Path) -> None:
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _unlink_writable(path: Path) -> None:
    if path.exists():
        _make_writable(path)
        path.unlink()


def _rmtree_writable(path: Path) -> None:
    def handle_remove_error(func, failed_path, _exc_info):
        failed = Path(failed_path)
        _make_writable(failed)
        func(failed_path)

    shutil.rmtree(path, onerror=handle_remove_error)


def _list_trash_files() -> list[dict[str, object]]:
    storage.TRASH_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, object]] = []
    for path in storage.TRASH_DIR.rglob("*.md"):
        if path.name == ".trash_manifest.json":
            continue
        try:
            relative = path.resolve().relative_to(storage.TRASH_DIR.resolve())
        except ValueError:
            continue
        parts = relative.parts
        library = parts[0] if parts else ""
        if library not in {"raw", "focus", "perspective"}:
            library = ""
        text = path.read_text(encoding="utf-8", errors="ignore")
        stat_result = path.stat()
        items.append(
            {
                "id": str(relative),
                "trash_path": str(relative),
                "title": _markdown_title(text) or path.stem,
                "library": library,
                "source_path": _trash_source_for(path),
                "deleted_at": datetime.fromtimestamp(stat_result.st_mtime).isoformat(timespec="seconds"),
                "size": stat_result.st_size,
            }
        )
    return sorted(items, key=lambda item: str(item.get("deleted_at") or ""), reverse=True)


def _delete_trash_paths(trash_paths: list[str]) -> dict[str, object]:
    manifest = _load_trash_manifest()
    deleted: list[str] = []
    errors: list[dict[str, str]] = []
    for item in trash_paths:
        try:
            path = _resolve_trash_path(item)
            source_path = _trash_source_for(path)
            if path.exists() and path.is_file():
                _unlink_writable(path)
            if source_path:
                source = Path(source_path)
                if source.exists():
                    _unlink_writable(source)
                manifest.pop(source_path, None)
            deleted.append(item)
        except OSError as exc:
            errors.append({"path": item, "error": str(exc)})
    _save_trash_manifest(manifest) if manifest else _trash_manifest_path().unlink(missing_ok=True)
    return {"deleted": deleted, "errors": errors}


def _restore_trash_paths(trash_paths: list[str]) -> dict[str, object]:
    manifest = _load_trash_manifest()
    restored: list[str] = []
    errors: list[dict[str, str]] = []
    roots = _trash_library_roots()
    for item in trash_paths:
        try:
            path = _resolve_trash_path(item)
            source_path = _trash_source_for(path)
            if source_path and Path(source_path).exists():
                manifest.pop(source_path, None)
                if path.exists():
                    path.unlink()
                restored.append(item)
                continue
            relative = path.resolve().relative_to(storage.TRASH_DIR.resolve())
            parts = relative.parts
            if len(parts) < 2 or parts[0] not in roots:
                raise ValueError(f"无法判断恢复目标库：{item}")
            target = roots[parts[0]].joinpath(*parts[1:])
            if target.exists():
                stamp = datetime.now().strftime("%Y%m%d%H%M%S")
                target = target.with_name(f"{target.stem}_{stamp}{target.suffix}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, target)
            restored.append(item)
        except (OSError, ValueError) as exc:
            errors.append({"path": item, "error": str(exc)})
    _save_trash_manifest(manifest) if manifest else _trash_manifest_path().unlink(missing_ok=True)
    return {"restored": restored, "errors": errors}


def _trash_status() -> dict[str, object]:
    storage.TRASH_DIR.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in storage.TRASH_DIR.rglob("*"):
        if path.is_file() and path.name != ".trash_manifest.json":
            files.append(path)
    size_bytes = sum(path.stat().st_size for path in files)
    latest = max((path.stat().st_mtime for path in files), default=0)
    return {
        "path": str(storage.TRASH_DIR),
        "file_count": len(files),
        "size_bytes": size_bytes,
        "updated_at": datetime.fromtimestamp(latest).isoformat(timespec="seconds") if latest else "",
    }


def _resolve_library_markdown_path(library_id: str, markdown_path: str) -> Path:
    roots = _library_roots()
    root = roots.get(library_id)
    if root is None:
        raise ValueError(f"Unsupported library: {library_id}")
    normalized = markdown_path.replace("\\", "/").strip()
    candidate = Path(normalized)
    if not normalized or ".." in candidate.parts:
        raise ValueError(f"只能读取库内路径：{markdown_path}")
    if candidate.is_absolute():
        path = candidate
    else:
        path = root.joinpath(*candidate.parts)
        if not path.exists():
            path = storage.STORAGE_ROOT.joinpath(*candidate.parts)
        if not path.exists():
            path = storage.ROOT.joinpath(*candidate.parts)
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
        raise FileNotFoundError(f"库文件不存在：{markdown_path}")
    resolved_path = path.resolve()
    allowed_roots = [candidate.resolve() for candidate in _library_scan_roots(library_id)]
    if not any(candidate in resolved_path.parents or resolved_path == candidate for candidate in allowed_roots):
        raise ValueError(f"文件路径越界：{markdown_path}")
    return path


def _library_roots() -> dict[str, Path]:
    return {
        "raw": storage.RAW_MATERIAL_DIR,
        "focus": storage.KNOWLEDGE_DIR,
        "perspective": storage.MINING_DIR,
    }


def _library_scan_roots(library_id: str) -> list[Path]:
    roots = _library_roots()
    root = roots.get(library_id)
    if root is None:
        return []
    candidates = [root]
    legacy_roots = {
        "raw": storage.ROOT / "raw_materials",
        "focus": storage.ROOT / "knowledge",
        "perspective": storage.ROOT / "mining",
    }
    legacy_root = legacy_roots.get(library_id)
    if legacy_root is not None:
        candidates.append(legacy_root)
    if storage.ROOT == storage.DEFAULT_ROOT:
        system_roots = {
            "raw": storage.SYSTEM_DATA_DIR / "raw_materials",
            "focus": storage.SYSTEM_DATA_DIR / "knowledge",
            "perspective": storage.SYSTEM_DATA_DIR / "mining",
        }
        system_root = system_roots.get(library_id)
        if system_root is not None:
            candidates.append(system_root)
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(candidate)
    return unique

def _replace_markdown_title(markdown: str, title: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = text.split("\n") if text else []
    if lines and lines[0].strip().startswith("# "):
        lines[0] = f"# {title}"
        return "\n".join(lines).strip() + "\n"
    return f"# {title}\n\n{text}".strip() + "\n"


def _replace_markdown_note(markdown: str, note: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not note.strip():
        return text + "\n"
    lines = text.split("\n") if text else []
    note_line = f"- 人工备注：{note.strip()}"
    for index, line in enumerate(lines[:30]):
        stripped = line.strip()
        if stripped.startswith("- 人工备注：") or stripped.startswith("- 备注：") or stripped.startswith("- note:"):
            lines[index] = note_line
            return "\n".join(lines).strip() + "\n"
    insert_at = 1 if lines and lines[0].strip().startswith("# ") else 0
    while insert_at < len(lines) and lines[insert_at].strip().startswith("- "):
        insert_at += 1
    lines.insert(insert_at, note_line)
    return "\n".join(lines).strip() + "\n"


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


def _with_owner_meta(markdown: str, owner_meta: dict[str, str]) -> str:
    clean_meta = {key: value for key, value in owner_meta.items() if value}
    if not clean_meta:
        return markdown
    text = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    existing = _markdown_meta(text)
    lines = text.splitlines()
    insert_at = 1 if lines and lines[0].startswith("#") else 0
    additions = [f"- {key}：{value}" for key, value in clean_meta.items() if key not in existing]
    if not additions:
        return text
    if insert_at < len(lines) and lines[insert_at].strip():
        additions.append("")
    return "\n".join([*lines[:insert_at], *additions, *lines[insert_at:]]).strip() + "\n"


def _default_library_status(library_id: str) -> str:
    return {"raw": "未处理", "focus": "已提炼", "perspective": "已解读"}.get(library_id, "")


def _default_perspective_profiles() -> list[dict[str, object]]:
    return [
        {
            "id": "writer",
            "name": "作家视角",
            "positioning": "扮演文件原创作者或专业写作者，关注全文创作逻辑、内容取舍和表达张力。",
            "core_goal": "解释创作初衷，梳理内容逻辑，提炼可迁移的表达方法。",
            "stance": "维护内容核心逻辑，重视行文设计、叙事节奏和表达取舍；不从外部投资价值或市场投机角度解读。",
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
            "positioning": "扮演一级/二级市场职业投资人，关注商业变现、风险评估和成本收益。",
            "core_goal": "识别机会、判断风险、估算回报，并形成投/不投/观望的决策线索。",
            "stance": "极度功利、优先避险，重视落地性、现金流和增长空间；不关注纯文学修饰或无落地路径的理论空谈。",
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
            "positioning": "扮演普通在校大学生，具备基础认知、学习求知和入门理解能力。",
            "core_goal": "读懂核心内容，提炼知识点，总结收获、疑问和个人学习启发。",
            "stance": "零基础友好，重理解和学以致用，关注个人成长；不追求高阶商业博弈或过深专业术语。",
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
            "positioning": "扮演创业者，关注用户问题、产品机会、市场入口和落地约束。",
            "core_goal": "从材料中发现可转化为产品、服务或项目的机会假设。",
            "stance": "务实落地，优先验证真实需求和最小可行动作；排斥脱离执行约束的空泛机会判断。",
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
            "positioning": "扮演专职行业研究员，具备政策、产业链、竞品和数据研判能力。",
            "core_goal": "拆解行业逻辑，提炼趋势，形成后续研究可复用的判断框架。",
            "stance": "客观中立，重数据、重逻辑、重行业对标；不关注情绪化表达和非行业相关冗余内容。",
            "role": "建立行业底层结构、关键变量和趋势解释框架",
            "target_subject": "行业结构、供需变量、政策/技术/资本因素、趋势路径",
            "purpose": "把材料沉淀成后续研究可复用的行业判断框架",
            "focus_dimensions": ["行业结构", "关键变量", "趋势路径", "数据口径", "研究缺口"],
            "analysis_questions": ["材料揭示了哪些行业底层变量？", "哪些信息可以形成研究假设？", "后续需要补哪些数据或来源？"],
            "output_style": "偏研究备忘录，强调变量、因果链和缺口",
            "evidence_rule": "变量和因果链必须以材料证据为起点",
        },
    ]


def _list_perspective_profiles(context: dict[str, object] | None = None) -> list[dict[str, object]]:
    defaults = []
    for item in _default_perspective_profiles():
        profile = dict(item)
        profile["origin"] = "preset"
        profile["readonly"] = True
        defaults.append(profile)
    owner_user_id = None
    include_ownerless = True
    if context is not None and context.get("deploymentMode") == "cloud":
        user = context.get("user") or {}
        if isinstance(user, dict) and user.get("role") != "admin":
            owner_user_id = str(user.get("id") or "")
            include_ownerless = False
    custom = storage.list_perspective_profiles(owner_user_id=owner_user_id, include_ownerless=include_ownerless)
    custom_ids = {item.get("id") for item in custom}
    return [*custom, *[item for item in defaults if item.get("id") not in custom_ids]]


def _read_mine_source(source: LibrarySourceRequest, context: dict[str, object] | None = None) -> dict[str, str]:
    library = source.library.strip()
    if library not in {"raw", "focus"}:
        raise ValueError("挖掘队列当前只支持原料库和重点库文件")
    path = _resolve_library_markdown_path(library, source.markdown_path)
    if context is not None:
        _assert_library_file_visible(path, context)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "library": library,
        "title": source.title.strip() or _markdown_title(text) or path.stem,
        "relative_path": storage.storage_relative(path),
        "text": text,
    }


def _read_create_source(source: LibrarySourceRequest, context: dict[str, object] | None = None) -> dict[str, str]:
    library = source.library.strip()
    if library not in {"raw", "focus", "perspective"}:
        raise ValueError("创作项目只支持原料库、重点库和视角库文件")
    path = _resolve_library_markdown_path(library, source.markdown_path)
    if context is not None:
        _assert_library_file_visible(path, context)
    text = path.read_text(encoding="utf-8", errors="ignore")
    relative_path = storage.storage_relative(path)
    return {
        "library": library,
        "title": source.title.strip() or _markdown_title(text) or path.stem,
        "markdown_path": relative_path,
        "relative_path": relative_path,
        "text": text,
    }

def _project_writer_sources(
    project: dict[str, object],
    request_files: list[LibrarySourceRequest] | None,
    context: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    if request_files is not None:
        return [_read_create_source(item, context=context) for item in request_files]
    files = project.get("library_files") or []
    return [_read_create_source(LibrarySourceRequest(**item), context=context) for item in files]


def _writer_markdown_files(sources: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(Path(source["relative_path"]).name, source["text"]) for source in sources]


def _render_perspective_markdown(result, perspective: MinePerspectiveProfile, sources: list[dict[str, str]]) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    tags = "、".join(result.tags or [perspective.name])
    core_facts = result.core_facts or result.findings or []
    deep_analysis = result.deep_analysis or []
    risks = result.risks_and_questions or result.risks_and_limits or []
    conclusions = result.conclusion_and_actions or result.writing_implications or []
    sections = [
        f"# {result.title}",
        "",
        f"- 视角：{perspective.name}",
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
            "## 解读摘要",
            "",
            result.summary.strip() or "暂无摘要。",
            "",
            "## 视角立场与标准",
            "",
            result.criteria.strip() or "请补充该视角下的判断标准与取舍原则。",
            "",
            "## 原文信息提炼",
            "",
        ]
    )
    if core_facts:
        for finding in core_facts:
            refs = "、".join(finding.evidence_refs) if finding.evidence_refs else "请补充引用"
            sections.extend([f"### {finding.dimension}", "", finding.interpretation.strip(), "", f"- 引用：{refs}", ""])
    else:
        sections.extend(["暂无可保存的原文提炼。", ""])
    sections.extend(["## 专属分析", ""])
    if deep_analysis:
        for finding in deep_analysis:
            refs = "、".join(finding.evidence_refs) if finding.evidence_refs else "请补充引用"
            sections.extend([f"### {finding.dimension}", "", finding.interpretation.strip(), "", f"- 引用：{refs}", ""])
    else:
        sections.append("暂无专属分析。")
    sections.extend(["", "## 风险疑问", ""])
    sections.extend(f"- {item}" for item in risks) if risks else sections.append("- 暂无。")
    sections.extend(["", "## 结论建议", ""])
    sections.extend(f"- {item}" for item in conclusions) if conclusions else sections.append("- 暂无。")
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


def _read_raw_material_file(relative_path: str, context: dict[str, object] | None = None) -> dict[str, str]:
    path = _resolve_library_markdown_path("raw", relative_path)
    if context is not None:
        _assert_library_file_visible(path, context)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {
        "title": _markdown_title(text) or path.stem,
        "relative_path": storage.storage_relative(path),
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


def _polish_screenshot_readable_draft(body: str, fallback_title: str) -> dict[str, object]:
    clean_body = _strip_screenshot_ocr_wrappers(body)
    polish_meta = _polish_raw_material("screenshot", clean_body, fallback_title)
    if polish_meta["markdown"]:
        polish_meta["markdown"] = _strip_screenshot_ocr_wrappers(str(polish_meta["markdown"]))
        return polish_meta

    response = polish_meta["response"] if isinstance(polish_meta.get("response"), dict) else {}
    if not response.get("status") or response.get("status") == "skipped":
        response["status"] = "local_ordered_without_llm"
    polish_meta["response"] = response
    polish_meta["markdown"] = clean_body
    return polish_meta


def _strip_screenshot_ocr_wrappers(text: str) -> str:
    blocks = re.split(r"\n\s*---\s*\n", text)
    cleaned_blocks: list[str] = []
    for block in blocks:
        value = block.strip()
        if not value:
            continue
        if re.search(r"(?im)^Recognized text:\s*$", value):
            value = re.split(r"(?im)^Recognized text:\s*$", value, maxsplit=1)[-1]
        lines = []
        for line in value.splitlines():
            stripped = line.strip()
            if re.fullmatch(r"\[Screenshot\s+\d+\]", stripped, flags=re.I):
                continue
            if re.match(r"(?i)^(Title hint|Topic hint):", stripped):
                continue
            if re.match(r"(?i)^Recognized text:\s*$", stripped):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        if cleaned:
            cleaned_blocks.append(cleaned)
    return _clean_raw_markdown_body("\n\n".join(cleaned_blocks))


def _polish_raw_material(material_type: str, body: str, fallback_title: str, preserve_order: bool = False) -> dict[str, object]:
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
    if preserve_order or material_type != "screenshot" or len(body.strip()) < 12:
        if preserve_order:
            response["status"] = "skipped_order_preserved"
        return result

    response["enabled"] = True
    try:
        polished = deepseek_client.polish_raw_material(body, material_type=material_type)
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
    dated_dir = storage.RAW_MATERIAL_DIR / datetime.now().strftime("%Y-%m-%d")
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
        "markdown_path": storage.storage_relative(path),
        "created_at": now,
        "hash": content_hash,
    }


def _extract_queue_text(material_type: str, items: list[CollectQueueItem], parser_mode: str | None = None) -> tuple[str, list[str], list[str]]:
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
        return _extract_document_queue(items, parser_mode=parser_mode)

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


def _document_visual_recognizer(image_paths: list[Path]) -> str:
    return deepseek_client.recognize_screenshots_with_ai(
        image_paths,
        setting=deepseek_client.current_setting(),
    )


def _extract_document_queue(items: list[CollectQueueItem], parser_mode: str | None = None) -> tuple[str, list[str], list[str]]:
    files = [storage.get_source_file(int(item.id)) for item in items if item.id is not None]
    blocks: list[str] = []
    sources: list[str] = []
    errors: list[str] = []
    prefer_visual = parser_mode == "ai_vision"
    for index, item in enumerate(files, start=1):
        try:
            file_path = storage.resolve_root_path(str(item["file_path"]))
            if not file_path or not file_path.exists():
                raise FileNotFoundError(f"uploaded file not found: {item['file_path']}")
            text = document_parser.extract_text(
                file_path,
                visual_recognizer=_document_visual_recognizer,
                prefer_visual=prefer_visual,
            )
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


def _extract_link_text(url: str, item: CollectQueueItem, allow_browser: bool = True) -> dict[str, str]:
    inspection = _inspect_link(url)
    link_type = str(inspection.get("link_type") or item.link_type or "")
    if link_type == "platform_wechat":
        return _extract_wechat_article_text(url)
    if link_type in {"platform_douyin", "platform_bilibili", "platform_wechat_channels"}:
        raise ValueError("音视频平台链接请放入「音视频」入口读取，不应作为普通网页链接提取。")
    if link_type == "pdf":
        return _extract_pdf_link_text(url, inspection)
    if str(inspection.get("access_status")) in {"login_or_restricted", "needs_browser_rendering", "needs_specialized_extractor"}:
        try:
            fetched = _agent_reach_fetch_webpage_text(url)
            fetched.update(
                {
                    "source": str(inspection.get("source") or fetched.get("source") or ""),
                    "author": str(inspection.get("author") or fetched.get("author") or ""),
                    "published_at": str(inspection.get("published_at") or fetched.get("published_at") or ""),
                    "link_type": link_type or "public_webpage",
                    "access_status": "accessible",
                    "extraction_strategy": str(fetched.get("extraction_strategy") or "agent_reach_jina_reader"),
                }
            )
            return fetched
        except Exception as exc:
            logger.warning("Agent Reach web reader failed for restricted link %s: %s", url, exc)
        if allow_browser:
            try:
                fetched = _browser_extract_webpage_text(
                    url,
                    title=item.title,
                    wait_ms=3000,
                    scroll_times=5,
                    scroll_pause_ms=800,
                    selector="",
                    allow_static_fallback=False,
                )
                fetched.update(
                    {
                        "source": str(inspection.get("source") or fetched.get("source") or ""),
                        "author": str(inspection.get("author") or fetched.get("author") or ""),
                        "published_at": str(inspection.get("published_at") or fetched.get("published_at") or ""),
                        "link_type": link_type or str(fetched.get("link_type") or "browser_webpage"),
                        "access_status": "accessible",
                        "extraction_strategy": str(fetched.get("extraction_strategy") or "browser_automation_wait_scroll"),
                    }
                )
                return fetched
            except Exception as exc:
                logger.warning("Browser extraction failed for classified link %s: %s", url, exc)
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
            "access_status": str(fetched.get("access_status") or inspection.get("access_status") or "accessible"),
            "extraction_strategy": str(fetched.get("extraction_strategy") or inspection.get("extraction_strategy") or "direct_fetch"),
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


def _browser_extract_webpage_text(
    url: str,
    title: str = "",
    wait_ms: int = 3000,
    scroll_times: int = 5,
    scroll_pause_ms: int = 800,
    selector: str = "",
    allow_static_fallback: bool = True,
) -> dict[str, str]:
    try:
        data = _browser_extract_article_payload(
            url,
            wait_ms=wait_ms,
            scroll_times=scroll_times,
            scroll_pause_ms=scroll_pause_ms,
            selector=selector,
        )
    except (OSError, subprocess.CalledProcessError, FileNotFoundError, TimeoutError, ValueError) as exc:
        if not allow_static_fallback:
            raise
        logger.warning("Browser extraction failed for %s, falling back to static extraction: %s", url, exc)
        fetched = _extract_link_text(url, CollectQueueItem(url=url, title=title), allow_browser=False)
        fetched["link_type"] = str(fetched.get("link_type") or "browser_webpage")
        fetched["access_status"] = str(fetched.get("access_status") or "accessible")
        fetched["extraction_strategy"] = f"{fetched.get('extraction_strategy') or 'direct_fetch'}_after_browser_error"
        return fetched
    content = _collapse_space_multiline(str(data.get("content") or ""))
    if len(content) < 80:
        raise ValueError("浏览器提取到的正文为空或过短，请确认页面已加载完成，或尝试增加等待/滚动参数。")
    return {
        "title": _collapse_space(title or str(data.get("title") or url)),
        "text": content,
        "source": _collapse_space(str(data.get("source") or data.get("account_name") or urllib.parse.urlparse(url).netloc)),
        "author": _collapse_space(str(data.get("author") or "")),
        "published_at": _collapse_space(str(data.get("published_at") or "")),
        "link_type": "browser_webpage",
        "access_status": "accessible",
        "extraction_strategy": "browser_automation_wait_scroll",
        "wait_ms": str(_bounded_int(wait_ms, 0, 30000)),
        "scroll_times": str(_bounded_int(scroll_times, 0, 30)),
    }


def _bounded_int(value: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def _browser_extract_article_payload(
    url: str,
    wait_ms: int = 3000,
    scroll_times: int = 5,
    scroll_pause_ms: int = 800,
    selector: str = "",
) -> dict[str, object]:
    try:
        return _browser_harness_extract_article_payload(url, wait_ms, scroll_times, scroll_pause_ms, selector)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _agent_browser_extract_article_payload(url, wait_ms, scroll_times, scroll_pause_ms, selector)


def _browser_harness_extract_article_payload(
    url: str,
    wait_ms: int = 3000,
    scroll_times: int = 5,
    scroll_pause_ms: int = 800,
    selector: str = "",
) -> dict[str, object]:
    wait_seconds = _bounded_int(wait_ms, 0, 30000) / 1000
    scroll_count = _bounded_int(scroll_times, 0, 30)
    pause_seconds = _bounded_int(scroll_pause_ms, 0, 5000) / 1000
    selector_json = json.dumps(selector.strip(), ensure_ascii=False)
    code = f"""
import json
import time
new_tab({json.dumps(url, ensure_ascii=False)})
wait_for_load()
time.sleep({wait_seconds})
for _ in range({scroll_count}):
    js("window.scrollBy(0, Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0) * 0.9)")
    time.sleep({pause_seconds})
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
  const requestedSelector = {selector_json};
  const requested = requestedSelector ? document.querySelector(requestedSelector) : null;
  const ps = Array.from(document.querySelectorAll("article p, main p, .article p, .post p, .content p, p"))
    .map(p => clean(p.innerText)).filter(t => t.length > 20);
  const site = meta("og:site_name") || location.hostname.replace(/^www\\./, "");
  return JSON.stringify({{
    url: location.href,
    title: pickText(["#activity-name", "h1"]) || document.title || meta("og:title"),
    account_name: pickText(["#js_name", ".profile_nickname"]) || site,
    source: site,
    author: pickText(["#js_author_name", "[rel=author]", ".author", ".byline"]) || meta("author") || "",
    published_at: pickText(["#publish_time", "#js_publish_time", "time"]) || meta("article:published_time") || meta("date") || "",
    summary: meta("og:description") || meta("description") || "",
    content: (requested && requested.innerText) || pickText(["#js_content", ".rich_media_content", "article", "main"]) || ps.join("\\n\\n") || document.body.innerText || ""
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


def _agent_browser_extract_article_payload(
    url: str,
    wait_ms: int = 3000,
    scroll_times: int = 5,
    scroll_pause_ms: int = 800,
    selector: str = "",
) -> dict[str, object]:
    command = _agent_browser_command()
    connection_args = _agent_browser_connection_args(command)
    wait_value = str(_bounded_int(wait_ms, 0, 30000))
    scroll_count = _bounded_int(scroll_times, 0, 30)
    pause_value = str(_bounded_int(scroll_pause_ms, 0, 5000))
    subprocess.run(
        [command, *connection_args, "open", url],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=60,
    )
    subprocess.run(
        [command, *connection_args, "wait", wait_value],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        timeout=20,
    )
    for _ in range(scroll_count):
        subprocess.run(
            [command, *connection_args, "eval", "window.scrollBy(0, Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0) * 0.9)"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
            timeout=20,
        )
        if pause_value != "0":
            subprocess.run(
                [command, *connection_args, "wait", pause_value],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
                timeout=20,
            )
    selector_json = json.dumps(selector.strip(), ensure_ascii=False)
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
  const requestedSelector = __REQUESTED_SELECTOR__;
  const requested = requestedSelector ? document.querySelector(requestedSelector) : null;
  return JSON.stringify({
    url: location.href,
    title: pickText(["#activity-name", "h1"]) || document.title || meta("og:title"),
    account_name: pickText(["#js_name", ".profile_nickname"]) || site,
    source: site,
    author: pickText(["#js_author_name", "[rel=author]", ".author", ".byline"]) || meta("author") || "",
    published_at: pickText(["#publish_time", "#js_publish_time", "time"]) || meta("article:published_time") || meta("date") || "",
    summary: meta("og:description") || meta("description") || "",
    content: (requested && requested.innerText) || pickText(["#js_content", ".rich_media_content", "article", "main"]) || ps.join("\n\n") || document.body.innerText || ""
  });
})()
'''.replace("__REQUESTED_SELECTOR__", selector_json)
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
    try:
        return _agent_reach_fetch_webpage_text(url)
    except Exception as exc:
        logger.info("Agent Reach web reader unavailable for %s, falling back to direct fetch: %s", url, exc)

    fetched = _fetch_url_bytes(url, max_bytes=2_000_000)
    content_type = str(fetched["content_type"])
    html_text = _decode_response_text(bytes(fetched["body"]), content_type)
    title = _html_title(html_text)
    text = _html_to_text(html_text)
    if not text.strip():
        raise ValueError("网页正文为空")
    return {"title": title, "text": text}


def _agent_reach_fetch_webpage_text(url: str) -> dict[str, str]:
    if os.environ.get("FIGURELEARNING_AGENT_REACH_WEB", "1").lower() in {"0", "false", "off", "no"}:
        raise ValueError("Agent Reach web reader is disabled")
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise ValueError("Agent Reach web reader is disabled during tests")

    python_path = os.environ.get("FIGURELEARNING_AGENT_REACH_PYTHON", "").strip()
    if not python_path:
        python_path = r"C:\Users\Bo Yang\.agent-reach-venv\Scripts\python.exe"
    command = Path(python_path)
    if not command.exists():
        raise FileNotFoundError(f"Agent Reach Python not found: {python_path}")

    script = (
        "import json, sys\n"
        "from agent_reach.channels.web import WebChannel\n"
        "text = WebChannel().read(sys.argv[1])\n"
        "print(json.dumps({'text': text}, ensure_ascii=False))\n"
    )
    completed = subprocess.run(
        [str(command), "-c", script, url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=True,
    )
    payload = json.loads(completed.stdout.strip())
    reader_text = str(payload.get("text") or "").strip()
    if not reader_text:
        raise ValueError("Agent Reach web reader returned empty text")

    title, text = _parse_agent_reach_reader_markdown(reader_text, url)
    if not text.strip():
        raise ValueError("Agent Reach web reader returned empty article text")
    return {
        "title": title,
        "text": text,
        "source": urllib.parse.urlparse(url).netloc,
        "access_status": "accessible",
        "extraction_strategy": "agent_reach_jina_reader",
    }


def _parse_agent_reach_reader_markdown(reader_text: str, url: str) -> tuple[str, str]:
    title = ""
    body_lines: list[str] = []
    in_body = False
    for raw_line in reader_text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not title and line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            continue
        if line.lower().startswith(("url source:", "markdown content:")):
            in_body = True
            continue
        if in_body or not line.lower().startswith(("warning:", "error:")):
            body_lines.append(raw_line)

    text = "\n".join(body_lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not title:
        for line in text.splitlines():
            candidate = line.strip().lstrip("#").strip()
            if candidate and not _looks_like_url(candidate):
                title = candidate[:120]
                break
    return title or url, text


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
    try:
        best_cleaned = ""
        for parser in ("lxml", "html.parser"):
            soup = BeautifulSoup(html_text, parser)
            text = _extract_best_html_text(soup)
            if text:
                cleaned = _clean_html_article_text(text)
                if len(cleaned) > len(best_cleaned):
                    best_cleaned = cleaned
        if best_cleaned:
            return best_cleaned
    except Exception:
        pass
    html_text = _main_content_hint(html_text)
    cleaned = re.sub(r"<(script|style|noscript|nav|footer|aside)[^>]*>.*?</\1>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"</(p|div|section|article|li|h[1-6]|br|blockquote|figcaption)>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = _strip_tags(cleaned)
    lines = [_collapse_space(line) for line in cleaned.splitlines()]
    return _clean_html_article_text("\n".join(line for line in lines if line))


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


def _extract_best_html_text(soup: BeautifulSoup) -> str:
    for selector in (
        "#UCAP-CONTENT",
        "#zoom",
        "#content",
        ".pages_content",
        ".trs_editor_view",
        ".article-content",
        ".article_content",
        ".article",
        ".content",
        "article",
        "main",
        "[role='main']",
        "[itemprop='articleBody']",
    ):
        node = soup.select_one(selector)
        if node:
            text = _node_text_score(node)
            cleaned = _clean_html_article_text(text)
            if len(cleaned) >= 200:
                return cleaned

    best_text = ""
    best_score = 0
    for node in soup.find_all(["article", "main", "section", "div"]):
        text = _node_text_score(node)
        cleaned = _clean_html_article_text(text)
        if len(cleaned) < 200:
            continue
        score = _html_text_score(node, cleaned)
        if score > best_score:
            best_text = cleaned
            best_score = score
    return best_text


def _node_text_score(node) -> str:
    node = BeautifulSoup(str(node), "lxml")
    for tag in node.find_all(["script", "style", "noscript", "nav", "footer", "aside", "form", "header", "menu"]):
        tag.decompose()
    parts = []
    for element in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption", "td"]):
        text = _collapse_space(element.get_text(" ", strip=True))
        if text:
            parts.append(text)
    if not parts:
        text = _collapse_space(node.get_text(" ", strip=True))
        return text
    return "\n".join(parts)


def _html_text_score(node, text: str) -> int:
    paragraph_count = len([line for line in text.splitlines() if len(line.strip()) >= 20])
    link_text = _collapse_space(" ".join(link.get_text(" ", strip=True) for link in node.find_all("a")))
    link_ratio = len(link_text) / max(len(text), 1)
    penalty = int(link_ratio * 500)
    bonus = paragraph_count * 40
    long_paragraph_bonus = len([line for line in text.splitlines() if len(line.strip()) >= 60]) * 30
    class_hint = " ".join(node.get("class", [])) if isinstance(node.get("class"), list) else str(node.get("class") or "")
    if re.search(r"(article|content|post|entry|body|main)", class_hint, flags=re.IGNORECASE):
        bonus += 120
    if re.search(r"(nav|menu|toolbar|footer|sidebar|aside|breadcrumb|recommend)", class_hint, flags=re.IGNORECASE):
        penalty += 180
    if node.name in {"article", "main"}:
        bonus += 180
    return len(text) + bonus + long_paragraph_bonus - penalty


def _clean_html_article_text(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    filtered = []
    for raw_line in lines:
        line = _collapse_space(raw_line)
        if not line:
            filtered.append("")
            continue
        lower = line.lower()
        if re.fullmatch(r"(home|login|sign in|sign up|next|previous|相关阅读|相关推荐|返回顶部)", lower):
            continue
        if len(line) <= 8 and re.fullmatch(r"[0-9/.-]+", line):
            continue
        filtered.append(line)
    text = "\n".join(filtered)
    return document_parser.clean_extracted_document_text(text)


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
    visible_text = _html_to_text(html_text)
    if len(visible_text) >= 800:
        return False

    lower_html = html_text.lower()
    lower_visible = visible_text.lower()
    lower_url = final_url.lower()
    form_like = bool(
        re.search(r"<input[^>]+type=[\"']?(password|submit)[\"']?", lower_html, flags=re.IGNORECASE)
        or re.search(r"<form[^>]+(?:login|signin|auth|passport)", lower_html, flags=re.IGNORECASE)
    )
    markers = ["login", "sign in", "signin", "登录", "请登录", "权限", "unauthorized", "forbidden"]
    return form_like or any(marker in lower_visible or marker in lower_url for marker in markers)


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
