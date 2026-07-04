from __future__ import annotations

import base64
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import api_settings
import asr_settings
import deepseek_client
import document_parser
import image_api_settings
import media_parser
import ocr_client
import storage
import workbench_settings
import writer_tools
from markdown_writer import render_creation_strategy_markdown, render_knowledge_markdown
from media_transcriber import transcribe_audio, transcribe_audio_url
from schemas import DocumentPlanResult, DocumentPlanSegment, KnowledgeResult
from src.auth import current_context, is_cloud_mode
from src import quotas as quota_service
import src.api_v2 as api_v2
from src.api_v2 import auth_router, jobs_router, router as api_v2_router
from src.pages import router as pages_router
from src.settings_helpers import (
    activate_list_setting,
    delete_list_setting,
    resolve_api_test_setting,
    resolve_image_api_test_setting,
    save_list_setting,
    test_asr_setting_payload,
)
from src.shared.frontend_app import current_frontend_path, frontend_file_response, react_app_response
from src.shared.navigation import replace_app_rail


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("figurelearning")
APP_ROOT = Path(__file__).resolve().parent


def _public_knowledge_item(item: dict[str, object]) -> dict[str, object]:
    public_item = dict(item)
    public_item.pop("graph_status", None)
    public_item.pop("graph_error_message", None)
    return public_item


def _public_knowledge_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [_public_knowledge_item(item) for item in items]


@asynccontextmanager
async def lifespan(_: FastAPI):
    workbench_settings.load_settings()
    yield


app = FastAPI(
    title="Screenshot Knowledge Base",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
app.mount("/static", StaticFiles(directory=storage.ROOT / "static"), name="static")


@app.get("/frontend/{asset_path:path}", include_in_schema=False)
def frontend_asset(asset_path: str) -> FileResponse:
    return frontend_file_response(asset_path)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    icon_path = current_frontend_path("favicon.ico")
    if not icon_path.exists():
        raise HTTPException(status_code=404, detail="favicon has not been built")
    return FileResponse(icon_path)


@app.middleware("http")
async def require_cloud_auth_for_api_writes(request: Request, call_next):
    if (
        is_cloud_mode()
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api")
        and not request.url.path.startswith("/api/auth")
    ):
        try:
            storage.init_storage()
            with storage.connect() as conn:
                current_context(request, conn)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


class GenerateRequest(BaseModel):
    image_ids: list[int]
    parser_mode: str = "local_ocr"


class FileGenerateRequest(BaseModel):
    file_ids: list[int]


class MediaUrlResolveRequest(BaseModel):
    url: str


class BilibiliCookieLoginRequest(BaseModel):
    url: str | None = None


class MediaTranscriptRequest(BaseModel):
    media_ids: list[int]


class MediaPlanRequest(BaseModel):
    media_ids: list[int]


class MediaDeleteRequest(BaseModel):
    media_ids: list[int]


class MediaGenerateRequest(BaseModel):
    media_ids: list[int]


class ReadableDocumentRequest(BaseModel):
    image_ids: list[int] = []
    file_ids: list[int] = []
    media_ids: list[int] = []
    parser_mode: str | None = None


class WorkbenchSettingsRequest(BaseModel):
    text_extraction_mode: str | None = None
    storage_locations: dict[str, str] | None = None


class MediaPlanSegmentRequest(BaseModel):
    id: str
    media_id: int
    title: str
    theme: str | None = None
    text: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    time_ranges: str | None = None
    reason: str | None = None
    estimated_chars: int | None = None
    selected: bool = True


class MediaPlanGenerateRequest(BaseModel):
    segments: list[MediaPlanSegmentRequest]


class FilePlanRequest(BaseModel):
    file_id: int


class FilePlanGenerateRequest(BaseModel):
    file_id: int
    segments: list[DocumentPlanSegment]


class FilePageInfoRequest(BaseModel):
    file_ids: list[int]


class FilePlanItemRequest(BaseModel):
    file_id: int
    page_ranges: str | None = None


class MultiFilePlanRequest(BaseModel):
    files: list[FilePlanItemRequest]


class MultiFilePlanGenerateRequest(BaseModel):
    segments: list[DocumentPlanSegment]


class SegmentGeneratePayload(BaseModel):
    item: dict[str, object]
    segment: DocumentPlanSegment


class TopicRequest(BaseModel):
    knowledge_ids: list[int]


class KnowledgeDeleteRequest(BaseModel):
    knowledge_ids: list[int]


class MiningProjectCreateRequest(BaseModel):
    name: str = "创作策略学习"
    strategy_type: str = "creation_strategy"


class MiningProjectUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class MiningSourceRef(BaseModel):
    source_type: str
    source_id: int
    title: str | None = None
    parser_mode: str = "local_ocr"


class MiningSourcesRequest(BaseModel):
    sources: list[MiningSourceRef]


class RetrievalChatRequest(BaseModel):
    question: str


class ImageDataRequest(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    data_url: str


class ImageDataBatchRequest(BaseModel):
    images: list[ImageDataRequest]


class KnowledgeDraftMetaRequest(BaseModel):
    materials: list[dict[str, str]]
    body: str
    language: str = "zh"


class KnowledgeDraftCommitRequest(BaseModel):
    backend_id: int | None = None
    title: str
    note: str = ""
    body: str
    source_ids: list[str] = []


class KnowledgeUpdateRequest(BaseModel):
    title: str
    note: str = ""
    body: str


class ApiSettingSaveRequest(BaseModel):
    id: str | None = None
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float | None = None
    max_retries: int | None = None
    make_active: bool = True


class ApiSettingActiveRequest(BaseModel):
    id: str


class ApiSettingTestRequest(BaseModel):
    id: str | None = None
    setting: ApiSettingSaveRequest | None = None


class ImageApiSettingSaveRequest(BaseModel):
    id: str | None = None
    name: str
    provider: str
    protocol: str | None = None
    base_url: str
    model: str
    api_key: str | None = None
    size: str | None = None
    quality: str | None = None
    aspect_ratio: str | None = None
    response_format: str | None = None
    timeout: float | None = None
    make_active: bool = True


class ImageApiSettingActiveRequest(BaseModel):
    id: str


class ImageApiSettingTestRequest(BaseModel):
    id: str | None = None
    setting: ImageApiSettingSaveRequest | None = None
    real_test: bool = False
    prompt: str | None = None


class AsrSettingSaveRequest(BaseModel):
    provider: str = "compatible"
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float | None = None


class WriterTopicRequest(BaseModel):
    knowledge_ids: list[int]


class WriterArticleRequest(BaseModel):
    knowledge_ids: list[int]
    topic: dict[str, object]


class WriterReviseRequest(BaseModel):
    knowledge_ids: list[int]
    markdown: str
    instruction: str
    workspace: str | None = None


class WriterImagesRequest(BaseModel):
    workspace: str
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []
    cover_aspect_ratio: str | None = None
    content_aspect_ratio: str | None = None


class WriterImageSuggestionsRequest(BaseModel):
    markdown: str
    topic: dict[str, object] | None = None


class WriterFormatRequest(BaseModel):
    workspace: str
    markdown: str | None = None
    theme: str = "tech"
    design_strategy: str | None = None


def _test_asr_setting_payload_or_400(payload: dict[str, object]) -> dict[str, object]:
    try:
        return test_asr_setting_payload(
            payload,
            transcribe_audio_url_fn=transcribe_audio_url,
            transcribe_audio_fn=transcribe_audio,
        )
    except ValueError as exc:
        asr_settings.mark_test_result(False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        asr_settings.mark_test_result(False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class WriterPublishRequest(BaseModel):
    workspace: str
    title: str
    author: str = ""
    digest: str | None = None
    cover_path: str | None = None


class WriterProjectCreateRequest(BaseModel):
    name: str = ""
    project_type: str = "article"
    description: str = ""
    knowledge_ids: list[int] = []
    library_files: list[dict[str, object]] = []
    writing_strategy: str = ""
    design_strategy: str = ""


class WriterWritingStrategySaveRequest(BaseModel):
    id: str | None = None
    name: str
    body: str


class WriterProjectKnowledgeRequest(BaseModel):
    knowledge_ids: list[int]
    library_files: list[dict[str, object]] = []


class WriterProjectTopicRequest(BaseModel):
    topic: dict[str, object]


class WriterProjectDraftRequest(BaseModel):
    topic: dict[str, object] | None = None


class WriterProjectStrategiesRequest(BaseModel):
    writing_strategy: str | None = None
    design_strategy: str | None = None


class WriterProjectReviseRequest(BaseModel):
    instruction: str
    markdown: str | None = None


class WriterProjectImageSuggestionsRequest(BaseModel):
    markdown: str | None = None
    topic: dict[str, object] | None = None
    content_image_count: int = 1
    image_style_preset: str | None = None


class WriterProjectImagesRequest(BaseModel):
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []
    cover_aspect_ratio: str | None = None
    content_aspect_ratio: str | None = None


class WriterProjectImageItemRequest(BaseModel):
    kind: str
    prompt: str
    index: int | None = None
    aspect_ratio: str | None = None


class WriterProjectFormatRequest(BaseModel):
    markdown: str | None = None
    theme: str = "tech"
    design_strategy: str | None = None


class WriterProjectDesignConfirmRequest(BaseModel):
    confirmed: bool = True


class WriterProjectPublishRequest(BaseModel):
    title: str = ""
    author: str = ""
    digest: str | None = None
    cover_path: str | None = None


class WechatPublisherBindingRequest(BaseModel):
    appid: str
    appsecret: str | None = None
    account_name: str = ""
    author: str = "Bobo"


class WriterProjectAdvanceRequest(BaseModel):
    step: str | None = None
    knowledge_ids: list[int] = []
    topic: dict[str, object] | None = None
    instruction: str | None = None
    markdown: str | None = None
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []
    cover_aspect_ratio: str | None = None
    content_aspect_ratio: str | None = None
    title: str | None = None
    author: str = ""
    digest: str | None = None
    cover_path: str | None = None


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled error for %s %s", request.method, request.url.path)
    raise exc


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return react_app_response()


@app.get("/collect", response_class=HTMLResponse)
def collect_page() -> HTMLResponse:
    return react_app_response()


@app.get("/learn", response_class=HTMLResponse)
def learn_page() -> HTMLResponse:
    return react_app_response()


@app.get("/mine", response_class=HTMLResponse)
def mine_page() -> HTMLResponse:
    return react_app_response()


@app.get("/create", response_class=HTMLResponse)
def create_page() -> HTMLResponse:
    return react_app_response()


@app.get("/library", response_class=HTMLResponse)
def library_page() -> HTMLResponse:
    return react_app_response()


@app.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
    return react_app_response()


@app.get("/docs", response_class=HTMLResponse)
def docs_page() -> HTMLResponse:
    return react_app_response()


@app.get("/writer", response_class=HTMLResponse)
def writer_page() -> HTMLResponse:
    return _static_page("writer.html", active_section="create")


@app.get("/media", response_class=HTMLResponse)
def media_page() -> HTMLResponse:
    return _static_page("media.html", active_section="collect")


def _static_page(filename: str, active_section: str) -> HTMLResponse:
    page_html = (APP_ROOT / "static" / filename).read_text(encoding="utf-8")
    return HTMLResponse(replace_app_rail(page_html, active_section))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/llm/status")
def llm_status() -> dict[str, str]:
    return deepseek_client.diagnose()


@app.get("/api/openai/status")
def openai_status() -> dict[str, str]:
    return deepseek_client.diagnose()


@app.get("/api/api-settings")
def list_api_settings() -> dict[str, object]:
    return api_settings.list_payload()


@app.post("/api/api-settings")
def save_api_setting(request: ApiSettingSaveRequest) -> dict[str, object]:
    try:
        return save_list_setting(api_settings, request.model_dump())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/api-settings/active")
def set_active_api_setting(request: ApiSettingActiveRequest) -> dict[str, object]:
    try:
        return activate_list_setting(api_settings, request.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/api-settings/{setting_id}")
def delete_api_setting(setting_id: str) -> dict[str, object]:
    try:
        return delete_list_setting(api_settings, setting_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/api-settings/test")
def test_api_setting(request: ApiSettingTestRequest) -> dict[str, str]:
    try:
        return deepseek_client.diagnose(resolve_api_test_setting(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/asr-settings")
def list_asr_settings() -> dict[str, object]:
    return asr_settings.list_payload()


@app.post("/api/asr-settings")
def save_asr_setting(request: AsrSettingSaveRequest) -> dict[str, object]:
    try:
        return save_list_setting(asr_settings, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/asr-settings/test")
def test_asr_setting(request: AsrSettingSaveRequest) -> dict[str, object]:
    return _test_asr_setting_payload_or_400(request.model_dump())


@app.get("/api/image-api-settings")
def list_image_api_settings() -> dict[str, object]:
    return image_api_settings.list_payload()


@app.post("/api/image-api-settings")
def save_image_api_setting(request: ImageApiSettingSaveRequest) -> dict[str, object]:
    try:
        return save_list_setting(image_api_settings, request.model_dump())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/image-api-settings/active")
def set_active_image_api_setting(request: ImageApiSettingActiveRequest) -> dict[str, object]:
    try:
        return activate_list_setting(image_api_settings, request.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/image-api-settings/{setting_id}")
def delete_image_api_setting(setting_id: str) -> dict[str, object]:
    try:
        return delete_list_setting(image_api_settings, setting_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/image-api-settings/test")
def test_image_api_setting(request: ImageApiSettingTestRequest) -> dict[str, str]:
    try:
        setting = resolve_image_api_test_setting(request)
        diagnosis = image_api_settings.diagnose(setting)
        if not request.real_test:
            return diagnosis
        if diagnosis.get("ok") != "true":
            return diagnosis
        output_dir = storage.WRITER_DIR / "_api_tests"
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = output_dir / f"image_api_test_{stamp}.png"
        result = writer_tools.generate_image(
            request.prompt or "一张简洁的测试图，白色背景，中心写有少量简体中文文字：测试",
            output_path,
            setting=setting,
        )
        return {
            **diagnosis,
            "real_test": "true",
            "generated_path": storage.storage_relative(output_path),
            "message": f"图片 API 字段诊断通过，并已真实生成测试图片：{result.get('path')}",
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/images")
def upload_images(request: Request, files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    context = _enforce_upload_quotas(request, files)
    owner_user_id, workspace_id = _context_owner_ids(context)
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading file name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            item = storage.save_upload(upload, owner_user_id=owner_user_id, workspace_id=workspace_id)
            _mark_uploaded_item_owner("screenshots", item, context)
            items.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Upload failed for %s", upload.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.post("/api/files")
def upload_source_files(request: Request, files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    context = _enforce_upload_quotas(request, files)
    owner_user_id, workspace_id = _context_owner_ids(context)
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading source file name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            item = storage.save_document_upload(upload, owner_user_id=owner_user_id, workspace_id=workspace_id)
            _mark_uploaded_item_owner("source_files", item, context)
            items.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Source file upload failed for %s", upload.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.post("/api/media/upload")
def upload_media_files(request: Request, files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    context = _enforce_upload_quotas(request, files)
    owner_user_id, workspace_id = _context_owner_ids(context)
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading media name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            item = storage.save_media_upload(upload, owner_user_id=owner_user_id, workspace_id=workspace_id)
            _mark_uploaded_item_owner("media_sources", item, context)
            items.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Media upload failed for %s", upload.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.get("/api/media/dependencies")
def media_dependencies() -> dict[str, object]:
    return media_parser.dependency_status()


@app.get("/api/media/bilibili-cookies")
def bilibili_cookie_status(request: Request) -> dict[str, object]:
    try:
        status_payload = media_parser.bilibili_cookie_status()
        if _should_redact_local_settings(request):
            return _redact_bilibili_cookie_status(status_payload)
        return status_payload
    except Exception as exc:
        logger.exception("Bilibili cookie status check failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/media/bilibili-cookies/login")
def open_bilibili_cookie_login(payload: BilibiliCookieLoginRequest, request: Request) -> dict[str, object]:
    try:
        if _should_redact_local_settings(request):
            raise HTTPException(status_code=403, detail="公网内测普通用户不能操作服务器 Cookie 登录")
        return media_parser.launch_bilibili_cookie_login(payload.url)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Bilibili cookie login launch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/media/transcripts")
def list_media_transcripts(request: Request) -> dict[str, object]:
    with storage.connect() as conn:
        context = current_context(request, conn)
    owner_user_id, _workspace_id = _context_owner_ids(context)
    user = context.get("user") or {}
    scoped_owner = None if context.get("deploymentMode") != "cloud" or (isinstance(user, dict) and user.get("role") == "admin") else owner_user_id
    return {"items": storage.list_media_transcripts(owner_user_id=scoped_owner)}


@app.get("/api/media/{media_id}/transcript")
def read_media_transcript(media_id: int, request: Request) -> dict[str, object]:
    item = storage.get_media_source(media_id)
    _ensure_cloud_record_access(request, item, "Transcript")
    path = storage.resolve_root_path(item.get("transcript_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Transcript file not found")
    return {"item": item, "content": path.read_text(encoding="utf-8", errors="ignore")}


@app.post("/api/media/delete-transcripts")
def delete_media_transcripts(request: MediaDeleteRequest) -> dict[str, object]:
    if not request.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one transcript file")
    try:
        result = storage.delete_media_transcripts(request.media_ids)
        return {**result, "items": storage.list_media_transcripts()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/media/resolve-url")
def resolve_media_url(request: MediaUrlResolveRequest) -> dict[str, object]:
    storage.init_storage()
    try:
        resolved = media_parser.resolve_url(request.url)
        item = storage.create_remote_media_source(
            platform=resolved.platform,
            source_url=resolved.source_url,
            canonical_url=resolved.canonical_url,
            title=resolved.title,
            duration_seconds=resolved.duration_seconds,
            status=resolved.status,
            error_message=resolved.error_message,
        )
        item["metadata"] = resolved.metadata or {}
        return {"item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/media/transcript")
def transcribe_media(request: MediaTranscriptRequest) -> dict[str, object]:
    if not request.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one media item")
    results = []
    for media_id in request.media_ids:
        try:
            item = storage.get_media_source(media_id)
            storage.update_media_source(media_id, status="transcribing", error_message=None)
            transcript, kind = media_parser.ensure_transcript(item)
            updated = storage.get_media_source(media_id)
            formatted = media_parser.format_media_transcript(updated, transcript)
            results.append({"item": updated, "transcript": formatted, "transcript_kind": kind, "ok": True})
        except Exception as exc:
            logger.exception("Media transcript failed for %s", media_id)
            try:
                updated = storage.update_media_source(media_id, status="error", error_message=str(exc))
            except Exception:
                updated = {"id": media_id}
            results.append({"item": updated, "ok": False, "error": str(exc)})
    return {"items": results}


def _strip_extraction_wrappers(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if re.fullmatch(r"\[(Screenshot|File|Media|PDF Page|Page)\b[^\]]*\]", line, flags=re.I):
            continue
        if re.match(r"^(Title hint|Topic hint|Recognized text|Platform|Source|Duration|Transcript Source):", line, flags=re.I):
            continue
        if line == "---":
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or text.strip()


def _is_markdown_block_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.startswith(("#", ">", "|", "```"))


def _is_markdown_list_line(line: str) -> bool:
    return bool(re.match(r"^([-*+]\s+|\d+[.)]\s+)", line.strip()))


def _join_wrapped_text(lines: list[str]) -> str:
    merged = lines[0].strip()
    for raw_line in lines[1:]:
        current = raw_line.strip()
        if not current:
            continue
        if re.search(r"[\u4e00-\u9fff]$", merged) or re.match(r"^[\u4e00-\u9fff?????????????????]", current):
            merged += current
        else:
            merged += f" {current}"
    return merged


def _rewrap_extracted_prose(text: str) -> str:
    paragraphs: list[str] = []
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer:
                paragraphs.append(_join_wrapped_text(buffer))
                buffer = []
            if not paragraphs or paragraphs[-1] != "":
                paragraphs.append("")
            continue
        if _is_markdown_block_line(line):
            if buffer:
                paragraphs.append(_join_wrapped_text(buffer))
                buffer = []
            paragraphs.append(line)
            continue
        if _is_markdown_list_line(line) and buffer:
            paragraphs.append(_join_wrapped_text(buffer))
            buffer = [line]
            continue
        buffer.append(line)
    if buffer:
        paragraphs.append(_join_wrapped_text(buffer))
    return "\n".join(paragraphs).strip()


def _normalize_readable_markdown(markdown: str, material_type: str) -> str:
    cleaned = markdown.strip()
    if "image" not in material_type:
        return cleaned
    lines = cleaned.splitlines()
    normalized: list[str] = []
    prose_buffer: list[str] = []

    def flush_prose() -> None:
        nonlocal prose_buffer
        if not prose_buffer:
            return
        normalized.append(_rewrap_extracted_prose("\n".join(prose_buffer)))
        prose_buffer = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("```"):
            flush_prose()
            normalized.append(stripped)
            continue
        prose_buffer.append(line)
    flush_prose()
    return "\n".join(part for part in normalized if part is not None).strip()


def _fallback_readable_document(title: str, raw_text: str, note: str = "") -> dict[str, object]:
    cleaned = _rewrap_extracted_prose(_strip_extraction_wrappers(raw_text))
    heading = title.strip() or "Readable document"
    if not cleaned.startswith("#"):
        markdown = f"# {heading}\n\n{cleaned}"
    else:
        markdown = _normalize_readable_markdown(cleaned, "image")
    return {
        "title": heading,
        "note": note or "Main text was extracted from the source; local parsed text is kept when LLM cleanup is unavailable.",
        "markdown": markdown.strip(),
        "raw_text": raw_text,
        "cleaned_by": "local",
    }


def _readable_document_keeps_source_content(markdown: str, raw_text: str) -> bool:
    cleaned_markdown = _strip_extraction_wrappers(markdown)
    cleaned_source = _strip_extraction_wrappers(raw_text)
    source_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned_source) if part.strip()]
    if not source_paragraphs:
        return True
    matched = 0
    for paragraph in source_paragraphs:
        normalized = re.sub(r"\s+", "", paragraph)
        if len(normalized) < 6:
            continue
        if normalized[:80] in re.sub(r"\s+", "", cleaned_markdown):
            matched += 1
    return matched > 0


def _readable_document_from_text(title: str, raw_text: str, material_type: str) -> dict[str, object]:
    fallback = _fallback_readable_document(title, raw_text)
    try:
        llm_source_text = _rewrap_extracted_prose(raw_text) if "image" in material_type else raw_text
        cleaned = deepseek_client.clean_readable_document(llm_source_text, material_type=material_type)
        cleaned_markdown = _normalize_readable_markdown(cleaned.markdown.strip() or fallback["markdown"], material_type)
        if not _readable_document_keeps_source_content(cleaned_markdown, raw_text):
            fallback["note"] = (
                "LLM cleanup omitted source content, so the locally extracted readable text was kept instead."
            )
            return fallback
        return {
            "title": cleaned.title.strip() or fallback["title"],
            "note": cleaned.note.strip() or "Cleaned into a readable source document with LLM.",
            "markdown": cleaned_markdown,
            "raw_text": raw_text,
            "cleaned_by": "llm",
        }
    except Exception as exc:
        logger.warning("Readable document cleanup failed, using local extracted text: %s", exc)
        fallback["note"] = f"{fallback['note']} Cleanup failed: {exc}"
        return fallback


def _should_redact_local_settings(request: Request) -> bool:
    if not is_cloud_mode():
        return False
    try:
        storage.init_storage()
        with storage.connect() as conn:
            context = current_context(request, conn)
        return context["user"]["role"] != "admin"
    except HTTPException:
        return True


def _require_local_or_cloud_admin(request: Request, detail: str) -> None:
    if _should_redact_local_settings(request):
        raise HTTPException(status_code=403, detail=detail)


def _upload_size(upload: UploadFile) -> int:
    size = getattr(upload, "size", None)
    if size is not None:
        return int(size)
    try:
        current = upload.file.tell()
        upload.file.seek(0, 2)
        measured = upload.file.tell()
        upload.file.seek(current)
        return int(measured)
    except (OSError, AttributeError):
        return 0


def _quota_bytes_detail(label: str, quota: dict[str, object]) -> str:
    used = int(quota.get("used", 0) or 0)
    limit = int(quota.get("limit", 0) or 0)
    return f"{label}超出限制（{used}/{limit} bytes）"


def _enforce_upload_quotas(request: Request, files: list[UploadFile]) -> dict[str, object]:
    with storage.connect() as conn:
        context = current_context(request, conn)
        if not quota_service.is_enforced(context):
            return context
        user_id, _workspace_id = quota_service.user_ids(context)
        incoming = 0
        for upload in files:
            size = _upload_size(upload)
            incoming += size
            size_quota = quota_service.check_upload_size(size)
            if not size_quota["allowed"]:
                raise HTTPException(status_code=413, detail=_quota_bytes_detail("单文件上传", size_quota))
        storage_quota = quota_service.check_storage(conn, user_id=user_id, incoming_bytes=incoming)
        if not storage_quota["allowed"]:
            raise HTTPException(status_code=429, detail=_quota_bytes_detail("存储空间", storage_quota))
        return context


def _enforce_upload_byte_quotas(request: Request, sizes: list[int]) -> dict[str, object]:
    with storage.connect() as conn:
        context = current_context(request, conn)
        if not quota_service.is_enforced(context):
            return context
        user_id, _workspace_id = quota_service.user_ids(context)
        incoming = 0
        for size in sizes:
            incoming += max(0, int(size))
            size_quota = quota_service.check_upload_size(size)
            if not size_quota["allowed"]:
                raise HTTPException(status_code=413, detail=_quota_bytes_detail("单文件上传", size_quota))
        storage_quota = quota_service.check_storage(conn, user_id=user_id, incoming_bytes=incoming)
        if not storage_quota["allowed"]:
            raise HTTPException(status_code=429, detail=_quota_bytes_detail("存储空间", storage_quota))
        return context


def _mark_uploaded_item_owner(table: str, item: dict[str, object], context: dict[str, object]) -> None:
    user = context.get("user") or {}
    workspace = context.get("workspace") or {}
    item_id = item.get("id")
    if not item_id or not isinstance(user, dict) or not isinstance(workspace, dict):
        return
    with storage.connect() as conn:
        conn.execute(
            f"""
            UPDATE {table}
            SET owner_user_id = COALESCE(owner_user_id, ?),
                workspace_id = COALESCE(workspace_id, ?)
            WHERE id = ?
            """,
            (user.get("id"), workspace.get("id"), item_id),
        )
        conn.commit()
    if not item.get("owner_user_id"):
        item["owner_user_id"] = user.get("id")
    if not item.get("workspace_id"):
        item["workspace_id"] = workspace.get("id")


def _context_owner_ids(context: dict[str, object]) -> tuple[str | None, str | None]:
    user = context.get("user") or {}
    workspace = context.get("workspace") or {}
    owner_user_id = user.get("id") if isinstance(user, dict) else None
    workspace_id = workspace.get("id") if isinstance(workspace, dict) else None
    return (
        str(owner_user_id) if owner_user_id else None,
        str(workspace_id) if workspace_id else None,
    )


def _cloud_scoped_owner_id(context: dict[str, object]) -> str | None:
    if context.get("deploymentMode") != "cloud":
        return None
    user = context.get("user") or {}
    if isinstance(user, dict) and user.get("role") == "admin":
        return None
    owner_user_id, _workspace_id = _context_owner_ids(context)
    return owner_user_id


def _ensure_cloud_record_access(request: Request, item: dict[str, object], label: str) -> None:
    with storage.connect() as conn:
        context = current_context(request, conn)
    if context.get("deploymentMode") != "cloud":
        return
    user = context.get("user") or {}
    if isinstance(user, dict) and user.get("role") == "admin":
        return
    owner_user_id = str(item.get("owner_user_id") or "")
    user_id = str(user.get("id") or "") if isinstance(user, dict) else ""
    if not owner_user_id or owner_user_id != user_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")


def _redact_workbench_settings_for_request(payload: dict[str, object], request: Request) -> dict[str, object]:
    if not _should_redact_local_settings(request):
        return payload
    redacted = dict(payload)
    redacted["storage_locations"] = {}
    redacted["local_diagnostics_visible"] = False
    return redacted


def _redact_bilibili_cookie_status(payload: dict[str, object]) -> dict[str, object]:
    return {
        "ok": bool(payload.get("ok")),
        "mode": "cloud_redacted",
        "source": "server",
        "exists": bool(payload.get("exists")),
        "has_sessdata": bool(payload.get("has_sessdata")),
        "has_dedeuserid": bool(payload.get("has_dedeuserid")),
        "has_bili_jct": bool(payload.get("has_bili_jct")),
        "message": "B 站 Cookie 状态由管理员配置，普通用户只显示可用性。",
    }


def _wechat_user_binding_context(request: Request) -> tuple[dict[str, object], str, str]:
    storage.init_storage()
    with storage.connect() as conn:
        context = current_context(request, conn)
    user = context.get("user") or {}
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="请先登录后再配置公众号")
    return context, str(user.get("id") or ""), str(user.get("username") or "")


def _writer_wechat_account_key(request: Request) -> str | None:
    context, user_id, _username = _wechat_user_binding_context(request)
    account_key = writer_tools.wechat_account_key_for_context(context)
    if context.get("deploymentMode") == "cloud" and not writer_tools.wechat_user_config_exists(user_id):
        raise HTTPException(status_code=403, detail="请先在设置中心绑定自己的微信公众号")
    return account_key


def _knowledge_entries_for_screenshot(screenshot_id: int) -> list[dict[str, object]]:
    needle = str(int(screenshot_id))
    with storage.connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM knowledge_entries
            WHERE source_type = 'screenshots'
              AND (image_ids LIKE ? OR source_ids LIKE ?)
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """,
            (f"%{needle}%", f"%{needle}%"),
        ).fetchall()
    matches: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        for key in ("image_ids", "source_ids"):
            try:
                ids = json.loads(str(item.get(key) or "[]"))
            except json.JSONDecodeError:
                ids = []
            if any(str(value) == needle for value in ids):
                matches.append(item)
                break
    return matches


def _legacy_markdown_paths_from_error(message: object) -> list[Path]:
    if not message:
        return []
    text = str(message)
    candidates = re.findall(r"'([^']+?\.md)'", text)
    paths: list[Path] = []
    for candidate in candidates:
        try:
            path = Path(candidate)
        except OSError:
            continue
        normalized = str(path).lower()
        in_current_storage = False
        try:
            path.resolve().relative_to(storage.ROOT.resolve())
            in_current_storage = True
        except (OSError, ValueError):
            in_current_storage = False
        if not in_current_storage and ("figurelearning" not in normalized or "knowledge" not in normalized):
            continue
        paths.append(path)
    return paths


def _markdown_title_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    stopwords = {"ai", "api", "gpt", "ces"}
    for chunk in re.split(r"[：:，,。．\.、；;\s/\\|()（）【】\[\]{}<>]+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        subchunks = [chunk]
        subchunks.extend(part for part in re.split(r"[与和及]", chunk) if part.strip())
        for subchunk in subchunks:
            subchunk = subchunk.strip()
            lowered = subchunk.lower()
            if not subchunk or lowered in stopwords:
                continue
            ascii_terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]*", subchunk)
            for term in ascii_terms:
                if term.lower() not in stopwords and term not in fragments:
                    fragments.append(term)
            if len(subchunk) >= 3 or lowered in {"fsd"}:
                if subchunk not in fragments:
                    fragments.append(subchunk)
            for keyword in ("算力", "能源", "电力", "中美", "竞赛", "试驾", "无人驾驶", "自动驾驶", "落地", "预期"):
                if keyword in subchunk and keyword not in fragments:
                    fragments.append(keyword)
    if "无人驾驶" in fragments and "自动驾驶" not in fragments:
        fragments.append("自动驾驶")
    if "自动驾驶" in fragments and "无人驾驶" not in fragments:
        fragments.append("无人驾驶")
    return fragments


def _search_local_markdown_by_title(title_hint: str) -> Path | None:
    fragments = _markdown_title_fragments(title_hint)
    if not fragments:
        return None
    normalized_title = _normalize_match_text(title_hint)
    search_roots = [
        storage.ROOT / "knowledge",
        storage.RAW_MATERIAL_DIR,
        storage.KNOWLEDGE_DIR,
    ]
    best: tuple[int, Path] | None = None
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            score = _score_markdown_match(path.name, normalized_title, fragments)
            try:
                prefix = path.read_text(encoding="utf-8", errors="ignore")[:20000]
            except OSError:
                prefix = ""
            score += _score_markdown_match(prefix, normalized_title, fragments)
            if score > 0 and (best is None or score > best[0]):
                best = (score, path)
    if best and best[0] >= 4:
        return best[1]
    return None


def _normalize_match_text(text: str) -> str:
    normalized = re.sub(r"[\s，,。．\.、：:；;！!？?（）()\[\]【】{}<>《》\"'“”‘’_\-—|/\\]+", "", text.lower())
    return normalized.replace("的", "")


def _score_markdown_match(text: str, normalized_title: str, fragments: list[str]) -> int:
    score = 0
    normalized_text = _normalize_match_text(text)
    if normalized_title and normalized_title in normalized_text:
        score += 12
    for fragment in fragments:
        normalized_fragment = _normalize_match_text(fragment)
        if not normalized_fragment:
            continue
        if normalized_fragment in normalized_text:
            score += 6 if len(normalized_fragment) >= 4 else 3
    return score


def _recover_screenshot_text_from_history(screenshot: dict[str, object]) -> tuple[str, str] | None:
    screenshot_id = int(screenshot["id"])
    candidates: list[tuple[Path, str]] = []

    for entry in _knowledge_entries_for_screenshot(screenshot_id):
        markdown_path = storage.resolve_root_path(entry.get("markdown_path"))
        if markdown_path:
            candidates.append((markdown_path, str(entry.get("title") or "")))
        for legacy_path in _legacy_markdown_paths_from_error(entry.get("error_message")):
            candidates.append((legacy_path, str(entry.get("title") or legacy_path.stem.rsplit("_", 1)[0])))

    for legacy_path in _legacy_markdown_paths_from_error(screenshot.get("error_message")):
        candidates.append((legacy_path, str(screenshot.get("title") or legacy_path.stem.rsplit("_", 1)[0])))

    seen: set[str] = set()
    for path, title_hint in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except PermissionError as exc:
            logger.warning("Historical readable document exists but is not readable: %s (%s)", path, exc)
            continue
        except OSError:
            continue
        if text:
            title = title_hint or path.stem.rsplit("_", 1)[0]
            raw_text = _extract_raw_text_from_historical_markdown(text)
            return title, _slice_historical_text_by_hint(raw_text, title)

    for _, title_hint in candidates:
        matched = _search_local_markdown_by_title(title_hint)
        if not matched:
            continue
        try:
            text = matched.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if text:
            title = title_hint or matched.stem.rsplit("_", 1)[0]
            raw_text = _extract_raw_text_from_historical_markdown(text)
            return title, _slice_historical_text_by_hint(raw_text, title)
    return None


def _extract_raw_text_from_historical_markdown(markdown: str) -> str:
    headings = [
        "## 原始识别文本",
        "## 原始文本",
        "## OCR",
        "## Raw text",
    ]
    for heading in headings:
        marker = markdown.find(heading)
        if marker >= 0:
            tail = markdown[marker + len(heading) :].strip()
            fenced = re.search(r"```(?:text|markdown)?\s*\n(.*?)\n```", tail, flags=re.S | re.I)
            if fenced:
                return _strip_extraction_wrappers(fenced.group(1).strip())
            return _strip_extraction_wrappers(tail)
    matches = re.findall(r"```(?:text|markdown)?\s*\n(.*?)\n```", markdown, flags=re.S | re.I)
    if matches:
        return _strip_extraction_wrappers(matches[-1].strip())
    return markdown.strip()


def _slice_historical_text_by_hint(text: str, title_hint: str) -> str:
    hint = _normalize_match_text(title_hint)
    if not text.strip() or not hint:
        return text.strip()

    if "fsd" in hint or "无人驾驶" in hint or "自动驾驶" in hint:
        sliced = _slice_between_markers(text, [r"2[、.．]\s*亲驾\s*FSD", r"2[、.．].*FSD"], [r"\n\s*3[、.．]\s*算力"])
        return sliced or text.strip()

    if "算力" in hint or "能源" in hint or "中美" in hint:
        sliced = _slice_between_markers(
            text,
            [r"3[、.．]\s*算力", r"3[、.．].*能源"],
            [r"\n\s*如今[，,]\s*AI", r"\n\s*[•\-]\s*满大街", r"\n\s*4[、.．]"],
        )
        return sliced or text.strip()

    if "任泽平" in hint or "不是风口" in hint or "是海啸" in hint:
        sliced = _slice_between_markers(
            text,
            [r"从美国.*?AI不是风口", r"刚从美国回来", r"今年1月初.*?美国"],
            [r"\n\s*2[、.．]\s*亲驾\s*FSD", r"\n\s*2[、.．].*FSD"],
        )
        return sliced or text.strip()

    return text.strip()


def _slice_between_markers(text: str, start_patterns: list[str], end_patterns: list[str]) -> str:
    start = None
    for pattern in start_patterns:
        match = re.search(pattern, text, flags=re.S | re.I)
        if match:
            start = match.start()
            break
    if start is None:
        return ""
    end = len(text)
    tail = text[start:]
    for pattern in end_patterns:
        match = re.search(pattern, tail, flags=re.S | re.I)
        if match and match.start() > 0:
            end = min(end, start + match.start())
    return text[start:end].strip()


@app.post("/api/materials/readable-document")
def readable_document(request: ReadableDocumentRequest, http_request: Request) -> dict[str, object]:
    if not (request.image_ids or request.file_ids or request.media_ids):
        raise HTTPException(status_code=400, detail="Please select at least one source material")
    parser_mode = request.parser_mode or workbench_settings.load_settings().get("text_extraction_mode") or "ai_vision"
    if parser_mode not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported parser mode")

    try:
        with storage.connect() as conn:
            context = current_context(http_request, conn)

        drafts: list[dict[str, object]] = []

        def append_draft(material_type: str, items: list[api_v2.CollectQueueItem]) -> None:
            if not items:
                return
            draft_request = api_v2.CollectReadableDraftRequest(
                material_type=material_type,
                items=items,
                parser_mode=parser_mode,
            )
            result = api_v2._build_readable_draft(draft_request, context=context)
            if result.get("ok") is False:
                raise ValueError(str(result.get("error") or "Readable draft extraction failed"))
            drafts.append(result)

        recovered_text_items: list[api_v2.CollectQueueItem] = []
        screenshot_items: list[api_v2.CollectQueueItem] = []
        if request.image_ids:
            for screenshot in storage.get_screenshots(request.image_ids):
                image_path = storage.resolve_root_path(screenshot.get("image_path"))
                title = str(screenshot.get("title") or Path(str(screenshot.get("image_path") or "")).name or f"screenshot-{screenshot['id']}")
                if image_path and image_path.exists():
                    screenshot_items.append(api_v2.CollectQueueItem(id=int(screenshot["id"]), title=title))
                    continue
                recovered = _recover_screenshot_text_from_history(screenshot)
                if recovered:
                    recovered_title, recovered_text = recovered
                    recovered_text_items.append(api_v2.CollectQueueItem(title=recovered_title, content=recovered_text))
                    continue
                raise FileNotFoundError(
                    f"Image file not found and no recoverable OCR/Markdown history is available: {screenshot['id']}"
                )
            append_draft("text", recovered_text_items)
            append_draft("screenshot", screenshot_items)

        if request.file_ids:
            file_items = []
            for item in storage.get_source_files(request.file_ids):
                file_items.append(
                    api_v2.CollectQueueItem(
                        id=int(item["id"]),
                        title=str(item.get("original_name") or item.get("title") or f"file-{item['id']}"),
                    )
                )
            append_draft("document", file_items)

        if request.media_ids:
            media_items = []
            for media_id in request.media_ids:
                item = storage.get_media_source(media_id)
                media_items.append(
                    api_v2.CollectQueueItem(
                        id=int(item["id"]),
                        title=str(item.get("title") or item.get("original_name") or f"media-{media_id}"),
                    )
                )
            append_draft("media", media_items)

        if not drafts:
            raise ValueError("No readable text was extracted")

        if len(drafts) == 1:
            draft = drafts[0]
            markdown = str(draft.get("markdown") or "")
            return {
                "title": str(draft.get("title") or "Readable document"),
                "note": str(draft.get("note") or ""),
                "markdown": markdown,
                "raw_text": markdown,
                "cleaned_by": "v2_readable_draft",
                "errors": draft.get("errors") or [],
                "polish": draft.get("polish") or {},
            }

        title = str(drafts[0].get("title") or "Combined material")
        markdown_parts = []
        for index, draft in enumerate(drafts, start=1):
            part_title = str(draft.get("title") or f"Material {index}")
            draft_markdown = str(draft.get("markdown") or "").strip()
            markdown_parts.append(f"## {index}. {part_title}\n\n{draft_markdown}")
        markdown = "\n\n---\n\n".join(markdown_parts).strip()
        errors = [error for draft in drafts for error in (draft.get("errors") or [])]
        notes = [str(draft.get("note") or "").strip() for draft in drafts if str(draft.get("note") or "").strip()]
        return {
            "title": f"{title} and {len(drafts) - 1} more",
            "note": " ".join(notes),
            "markdown": markdown,
            "raw_text": markdown,
            "cleaned_by": "v2_readable_draft",
            "errors": errors,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Readable document extraction failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/workbench-settings")
def list_workbench_settings(request: Request) -> dict[str, object]:
    return _redact_workbench_settings_for_request(workbench_settings.load_settings(), request)


@app.post("/api/workbench-settings")
def save_workbench_settings(request: WorkbenchSettingsRequest, http_request: Request) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True)
    if "text_extraction_mode" in payload and payload["text_extraction_mode"] not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported text extraction mode")
    if _should_redact_local_settings(http_request):
        payload.pop("storage_locations", None)
    return _redact_workbench_settings_for_request(workbench_settings.save_settings(payload), http_request)


@app.get("/api/settings/wechat-publisher")
def get_wechat_publisher_binding(request: Request) -> dict[str, object]:
    _context, user_id, username = _wechat_user_binding_context(request)
    return {"ok": True, **writer_tools.wechat_binding_status(user_id, username)}


@app.post("/api/settings/wechat-publisher")
def save_wechat_publisher_binding(payload: WechatPublisherBindingRequest, request: Request) -> dict[str, object]:
    _context, user_id, username = _wechat_user_binding_context(request)
    try:
        return {"ok": True, **writer_tools.save_wechat_binding(
            user_id,
            username,
            appid=payload.appid,
            appsecret=payload.appsecret,
            account_name=payload.account_name,
            author=payload.author,
        )}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/settings/wechat-publisher/token/refresh")
def refresh_wechat_publisher_binding_token(request: Request) -> dict[str, object]:
    _context, user_id, _username = _wechat_user_binding_context(request)
    return writer_tools.refresh_wechat_access_token(account_key=user_id)


@app.post("/api/media/plan-ranges")
def plan_media_ranges(payload: MediaPlanRequest, request: Request) -> dict[str, object]:
    if not payload.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one media item")
    segments = []
    results = []
    for media_id in payload.media_ids:
        try:
            item = storage.get_media_source(media_id)
            _ensure_cloud_record_access(request, item, "Media")
            transcript, _ = media_parser.ensure_transcript(item)
            item = storage.get_media_source(media_id)
            media_segments = media_parser.plan_segments(
                transcript,
                media_id=media_id,
                title=str(item.get("title") or item.get("original_name") or "media"),
            )
            segments.extend(media_segments)
            results.append({"media_id": media_id, "segments": media_segments, "ok": True})
        except Exception as exc:
            results.append({"media_id": media_id, "segments": [], "ok": False, "error": str(exc)})
    return {"plan": {"segments": segments}, "items": results}


def media_segment_text(transcript: str, segment: MediaPlanSegmentRequest) -> str:
    if segment.text:
        return segment.text.strip()
    if not segment.time_start or not segment.time_end:
        return transcript
    selected: list[str] = []
    for line in transcript.splitlines():
        match = re.match(r"\[(\d{2}:\d{2}:\d{2})\s+-\s+(\d{2}:\d{2}:\d{2})\]", line)
        if not match:
            continue
        start = match.group(1)
        if segment.time_start <= start <= segment.time_end:
            selected.append(line)
    return "\n".join(selected).strip() or transcript


@app.post("/api/knowledge/generate-from-media-plan")
def generate_knowledge_from_media_plan(payload: MediaPlanGenerateRequest, request: Request) -> dict[str, object]:
    segments = [segment for segment in payload.segments if segment.selected]
    if not segments:
        raise HTTPException(status_code=400, detail="Please select at least one transcript segment")
    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        results = []
        for segment in segments:
            item = storage.get_media_source(segment.media_id)
            _ensure_cloud_record_access(request, item, "Media")
            transcript, _ = media_parser.ensure_transcript(item)
            item = storage.get_media_source(segment.media_id)
            selected_text = media_segment_text(transcript, segment)
            if not selected_text:
                raise ValueError(f"Segment has no transcript text: {segment.title}")
            segment_hash = storage.hash_bytes(
                f"{item['media_hash']}|{segment.id}|{segment.time_start}|{segment.time_end}|{segment.title}".encode("utf-8")
            )
            scoped_hash = storage.scoped_content_hash(segment_hash, owner_user_id)
            existing = storage.get_knowledge_by_hash(scoped_hash)
            if existing and existing.get("markdown_path") and existing.get("status") == "ready":
                results.append({"item": existing, "segment": segment.model_dump(), "skipped": True})
                continue

            entry = storage.create_or_update_knowledge_entry(
                [],
                segment_hash,
                source_type="media_plan",
                source_ids=[int(item["id"])],
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
            )
            raw_text = "\n".join(
                [
                    f"[Media: {item.get('title') or item.get('original_name') or 'Untitled media'}]",
                    f"[Platform: {item.get('platform') or 'local'}]",
                    f"[Source: {item.get('canonical_url') or item.get('source_url') or item.get('original_name') or ''}]",
                    f"[Planned Topic: {segment.title}]",
                    f"[Theme: {segment.theme or ''}]",
                    f"[Time Range: {segment.time_ranges or ''}]",
                    f"[Transcript Source: {item.get('transcript_kind') or 'none'}]",
                    "",
                    selected_text,
                ]
            ).strip()
            knowledge, raw_text = deepseek_client.generate_knowledge_from_text(raw_text)
            markdown = render_knowledge_markdown(
                knowledge,
                raw_text=raw_text,
                imported_at=entry.get("created_at"),
                source="media_plan",
            )
            markdown_path = storage.markdown_path_for(
                knowledge.title or segment.title or "media-plan-knowledge",
                entry.get("image_hash") or segment_hash,
                entry.get("created_at"),
            )
            markdown_path.write_text(markdown, encoding="utf-8")
            updated = storage.update_knowledge_entry(
                entry["id"],
                markdown_path=storage.storage_relative(markdown_path),
                title=knowledge.title,
                topic=knowledge.topic,
                tags=json.dumps(knowledge.tags, ensure_ascii=False),
                status="ready",
                error_message=None,
            )
            storage.update_media_source(int(item["id"]), status="ready", error_message=None)
            results.append({"item": updated, "segment": segment.model_dump(), "skipped": False})
        return {"items": results, "generated": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/images/paste")
def upload_pasted_images(payload: ImageDataBatchRequest, request: Request) -> dict[str, object]:
    storage.init_storage()
    decoded_images: list[tuple[ImageDataRequest, bytes, str]] = []
    for image in payload.images:
        header, _, data_payload = image.data_url.partition(",")
        if not data_payload:
            raise HTTPException(status_code=400, detail="Pasted image data is empty")
        content_type = image.content_type
        if header.startswith("data:") and ";" in header:
            content_type = header.removeprefix("data:").split(";", 1)[0]
        try:
            decoded_images.append((image, base64.b64decode(data_payload), content_type))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Pasted image data is not valid base64") from exc

    context = _enforce_upload_byte_quotas(request, [len(data) for _, data, _ in decoded_images])
    owner_user_id, workspace_id = _context_owner_ids(context)
    items = []
    for image, data, content_type in decoded_images:
        try:
            item = storage.save_image_bytes(
                data,
                image.filename,
                content_type,
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
            )
            _mark_uploaded_item_owner("screenshots", item, context)
            items.append(item)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Pasted image upload failed for %s", image.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.get("/api/images/{image_id}/file")
def image_file(image_id: int, request: Request) -> FileResponse:
    item = storage.get_screenshot(image_id)
    _ensure_cloud_record_access(request, item, "Image")
    path = storage.resolve_root_path(item.get("image_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.get("/api/files/{file_id}/raw")
def source_file_raw(file_id: int, request: Request) -> FileResponse:
    item = storage.get_source_file(file_id)
    _ensure_cloud_record_access(request, item, "Source file")
    path = storage.resolve_root_path(item.get("file_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    return FileResponse(path, filename=item.get("original_name") or path.name)


def fallback_document_plan(item: dict[str, object], pages: list[dict]) -> DocumentPlanResult:
    page_count = len(pages)
    total_chars = sum(int(page.get("char_count") or 0) for page in pages)
    long_document = page_count > document_parser.LONG_DOCUMENT_PAGE_THRESHOLD or total_chars > document_parser.LONG_DOCUMENT_CHAR_THRESHOLD
    if not pages:
        segments = []
    elif not long_document:
        segments = [
            DocumentPlanSegment(
                id="segment-1",
                title=Path(str(item.get("original_name") or "鏂囦欢鐭ヨ瘑")).stem[:48],
                theme="Whole document",
                page_start=1,
                page_end=page_count,
                reason="Short document; use as one segment.",
                estimated_chars=total_chars,
            )
        ]
    else:
        target_chars = 9000
        segments = []
        start_page = 1
        current_chars = 0
        segment_index = 1
        for page in pages:
            current_chars += int(page.get("char_count") or 0)
            page_number = int(page.get("page") or start_page)
            if current_chars >= target_chars or page_number == page_count:
                segments.append(
                    DocumentPlanSegment(
                        id=f"segment-{segment_index}",
                        title=f"{Path(str(item.get('original_name') or 'document')).stem[:30]} part {segment_index}",
                        theme=f"Pages {start_page}-{page_number}",
                        page_start=start_page,
                        page_end=page_number,
                        reason="Split by page and length to avoid truncation.",
                        estimated_chars=current_chars,
                    )
                )
                segment_index += 1
                start_page = page_number + 1
                current_chars = 0
    return DocumentPlanResult(
        file_id=int(item["id"]),
        file_name=str(item.get("original_name") or ""),
        file_type=str(item.get("file_type") or ""),
        page_count=page_count,
        total_chars=total_chars,
        long_document=long_document,
        summary="Rule-based fallback plan to avoid truncation.",
        segments=segments,
    )


def fallback_document_plan(item: dict[str, object], pages: list[dict]) -> DocumentPlanResult:
    page_numbers = [int(page.get("page") or 0) for page in pages]
    page_count = max(page_numbers) if page_numbers else 0
    total_chars = sum(int(page.get("char_count") or 0) for page in pages)
    long_document = page_count > document_parser.LONG_DOCUMENT_PAGE_THRESHOLD or total_chars > document_parser.LONG_DOCUMENT_CHAR_THRESHOLD
    file_id = int(item["id"])
    file_name = str(item.get("original_name") or "")
    if not pages:
        segments: list[DocumentPlanSegment] = []
    elif not long_document:
        segments = [
            DocumentPlanSegment(
                id=f"file-{file_id}-segment-1",
                title=Path(file_name or "document").stem[:48],
                theme="Selected page range",
                file_id=file_id,
                file_name=file_name,
                page_start=min(page_numbers),
                page_end=max(page_numbers),
                reason="Short selected content; use as one segment.",
                estimated_chars=total_chars,
            )
        ]
    else:
        target_chars = 9000
        segments = []
        start_page = page_numbers[0]
        current_chars = 0
        segment_index = 1
        last_page = start_page
        for index, page in enumerate(pages):
            current_chars += int(page.get("char_count") or 0)
            last_page = int(page.get("page") or last_page)
            if current_chars >= target_chars or index == len(pages) - 1:
                segments.append(
                    DocumentPlanSegment(
                        id=f"file-{file_id}-segment-{segment_index}",
                        title=f"{Path(file_name or 'document').stem[:30]} part {segment_index}",
                        theme=f"Pages {start_page}-{last_page}",
                        file_id=file_id,
                        file_name=file_name,
                        page_start=start_page,
                        page_end=last_page,
                        reason="Split by page and length to avoid truncation.",
                        estimated_chars=current_chars,
                    )
                )
                segment_index += 1
                current_chars = 0
                start_page = last_page + 1
    return DocumentPlanResult(
        file_id=file_id,
        file_name=file_name,
        file_type=str(item.get("file_type") or ""),
        page_count=page_count,
        total_chars=total_chars,
        long_document=long_document,
        summary="Rule-based fallback plan to avoid truncation.",
        segments=segments,
    )


def source_file_pages(item: dict[str, object]) -> tuple[Path, list[dict]]:
    path = storage.resolve_root_path(item.get("file_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
    return path, document_parser.document_pages(path)


def normalize_plan_segment_pages(
    segment: DocumentPlanSegment,
    allowed_ranges: list[tuple[int, int]],
) -> DocumentPlanSegment | None:
    if not allowed_ranges:
        return None
    allowed_pages = {
        page_number
        for start_page, end_page in allowed_ranges
        for page_number in range(start_page, end_page + 1)
    }
    if segment.page_start is None or segment.page_end is None:
        selected_pages = sorted(allowed_pages)
    else:
        start_page = min(segment.page_start, segment.page_end)
        end_page = max(segment.page_start, segment.page_end)
        selected_pages = sorted(
            page_number
            for page_number in allowed_pages
            if start_page <= page_number <= end_page
        )
    if not selected_pages:
        return None
    segment.page_start = selected_pages[0]
    segment.page_end = selected_pages[-1]
    segment.page_ranges = document_parser.format_page_ranges(
        document_parser.merge_page_ranges([(page_number, page_number) for page_number in selected_pages])
    )
    return segment


@app.post("/api/files/page-info")
def source_file_page_info(request: FilePageInfoRequest) -> dict[str, object]:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鏂囦欢")
    items = []
    try:
        for file_id in request.file_ids:
            item = storage.get_source_file(file_id)
            _, pages = source_file_pages(item)
            page_count = len(pages)
            total_chars = sum(int(page.get("char_count") or 0) for page in pages)
            items.append(
                {
                    "id": item["id"],
                    "file_name": item.get("original_name") or "",
                    "file_type": item.get("file_type") or "",
                    "page_count": page_count,
                    "total_chars": total_chars,
                    "default_range": f"1-{page_count}" if page_count else "",
                }
            )
        return {"items": items}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/plan-ranges")
def plan_source_file_ranges(request: MultiFilePlanRequest) -> dict[str, object]:
    if not request.files:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鏂囦欢")
    try:
        plans = []
        combined_segments = []
        for file_request in request.files:
            item = storage.get_source_file(file_request.file_id)
            path, pages = source_file_pages(item)
            page_count = len(pages)
            ranges = document_parser.parse_page_ranges(file_request.page_ranges, page_count)
            selected_pages = document_parser.filter_pages_by_ranges(pages, ranges)
            if not selected_pages:
                raise ValueError(f"No content selected in page range: {item.get('original_name') or path.name}")
            total_chars = sum(int(page.get("char_count") or 0) for page in selected_pages)
            overview = document_parser.compact_pages_for_prompt(selected_pages)
            range_text = document_parser.format_page_ranges(ranges)
            try:
                plan = deepseek_client.plan_document_knowledge(
                    file_name=item.get("original_name") or path.name,
                    file_type=item.get("file_type") or path.suffix.lstrip("."),
                    page_count=page_count,
                    total_chars=total_chars,
                    page_overview=overview,
                    setting=deepseek_client.current_setting(),
                )
                plan.file_id = item["id"]
                plan.file_name = item.get("original_name") or path.name
                plan.file_type = item.get("file_type") or path.suffix.lstrip(".")
                plan.page_count = page_count
                plan.total_chars = total_chars
                plan.long_document = page_count > document_parser.LONG_DOCUMENT_PAGE_THRESHOLD or total_chars > document_parser.LONG_DOCUMENT_CHAR_THRESHOLD
                if not plan.segments:
                    plan = fallback_document_plan(item, selected_pages)
            except Exception as exc:
                logger.warning("AI range document planning failed, using fallback: %s", exc)
                plan = fallback_document_plan(item, selected_pages)

            normalized_segments = []
            for segment in plan.segments:
                normalized = normalize_plan_segment_pages(segment, ranges)
                if normalized is not None:
                    normalized_segments.append(normalized)
            if not normalized_segments:
                plan = fallback_document_plan(item, selected_pages)
                normalized_segments = [
                    segment
                    for segment in (normalize_plan_segment_pages(segment, ranges) for segment in plan.segments)
                    if segment is not None
                ]
            plan.segments = normalized_segments

            for index, segment in enumerate(plan.segments, start=1):
                segment.file_id = int(item["id"])
                segment.file_name = str(item.get("original_name") or path.name)
                if not segment.id or segment.id.startswith("segment-"):
                    segment.id = f"file-{item['id']}-segment-{index}"
                if segment.page_start is None:
                    segment.page_start = min(start_page for start_page, _ in ranges)
                if segment.page_end is None:
                    segment.page_end = max(end_page for _, end_page in ranges)
                if not segment.page_ranges:
                    segment.page_ranges = range_text
                combined_segments.append(segment)
            plans.append(plan.model_dump())
        return {"plans": plans, "plan": {"segments": [segment.model_dump() for segment in combined_segments]}}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/plan")
def plan_source_file(request: FilePlanRequest) -> dict[str, object]:
    try:
        item = storage.get_source_file(request.file_id)
        path = storage.resolve_root_path(item.get("file_path"))
        if not path or not path.exists():
            raise HTTPException(status_code=404, detail="Source file not found")
        pages = document_parser.document_pages(path)
        total_chars = sum(int(page.get("char_count") or 0) for page in pages)
        long_document = len(pages) > document_parser.LONG_DOCUMENT_PAGE_THRESHOLD or total_chars > document_parser.LONG_DOCUMENT_CHAR_THRESHOLD
        overview = document_parser.compact_pages_for_prompt(pages)
        try:
            plan = deepseek_client.plan_document_knowledge(
                file_name=item.get("original_name") or path.name,
                file_type=item.get("file_type") or path.suffix.lstrip("."),
                page_count=len(pages),
                total_chars=total_chars,
                page_overview=overview,
                setting=deepseek_client.current_setting(),
            )
            plan.file_id = item["id"]
            plan.file_name = item.get("original_name") or path.name
            plan.file_type = item.get("file_type") or path.suffix.lstrip(".")
            plan.page_count = len(pages)
            plan.total_chars = total_chars
            plan.long_document = long_document
            if not plan.segments:
                plan = fallback_document_plan(item, pages)
        except Exception as exc:
            logger.warning("AI document planning failed, using fallback: %s", exc)
            plan = fallback_document_plan(item, pages)
        return {"plan": plan.model_dump(), "pages": [{"page": p["page"], "char_count": p["char_count"], "used_ocr": p["used_ocr"]} for p in pages]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate")
def generate_knowledge(payload: GenerateRequest, request: Request) -> dict[str, object]:
    if not payload.image_ids:
        raise HTTPException(status_code=400, detail="Please select at least one screenshot")
    if payload.parser_mode not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported parser mode")

    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        screenshots = storage.get_screenshots(payload.image_ids)
        for screenshot in screenshots:
            _ensure_cloud_record_access(request, screenshot, "Image")
        round_hash = storage.combined_hash(screenshots)
        scoped_hash = storage.scoped_content_hash(round_hash, owner_user_id)
        existing = storage.get_knowledge_by_hash(scoped_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": _public_knowledge_item(existing), "images": screenshots, "skipped": True}

        entry = storage.create_or_update_knowledge_entry(payload.image_ids, round_hash, owner_user_id=owner_user_id, workspace_id=workspace_id)
        image_paths = []
        for screenshot in screenshots:
            image_path = storage.resolve_root_path(screenshot.get("image_path"))
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {screenshot['id']}")
            image_paths.append(image_path)
        if payload.parser_mode == "ai_vision":
            combined_raw_text = deepseek_client.recognize_screenshots_with_ai(
                image_paths,
                setting=deepseek_client.current_setting(),
            )
        else:
            combined_raw_text = ocr_client.recognize_screenshots(image_paths)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=deepseek_client.current_setting(),
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
            source="screenshot",
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "screenshot-knowledge",
            entry.get("image_hash") or round_hash,
            entry.get("created_at"),
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=knowledge.title,
            topic=knowledge.topic,
            tags=json.dumps(knowledge.tags, ensure_ascii=False),
            status="ready",
            error_message=None,
        )
        for screenshot in screenshots:
            storage.update_screenshot(screenshot["id"], status="ready", error_message=None)
        return {
            "item": _public_knowledge_item(updated),
            "images": screenshots,
            "skipped": False,
            "parser_mode": payload.parser_mode,
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for image_id in payload.image_ids:
            try:
                storage.update_screenshot(image_id, status="error", error_message=str(exc))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/draft-meta")
def generate_knowledge_draft_meta(request: KnowledgeDraftMetaRequest) -> dict[str, object]:
    if not request.body.strip():
        raise HTTPException(status_code=400, detail="Draft body is required")
    try:
        meta = deepseek_client.generate_knowledge_draft_meta(
            request.materials,
            request.body,
            language=request.language,
        )
        return meta.model_dump()
    except Exception as exc:
        logger.exception("Knowledge draft metadata generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/commit-draft")
def commit_knowledge_draft(payload: KnowledgeDraftCommitRequest, request: Request) -> dict[str, object]:
    title = payload.title.strip() or "Untitled knowledge"
    body = payload.body
    if not body.strip():
        raise HTTPException(status_code=400, detail="Draft body is required")
    note = payload.note.strip()
    markdown = strip_repeated_note_quotes(body, note) if payload.backend_id else body
    if note and not payload.backend_id:
        markdown = f"> {note}\n\n{body}"

    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        if payload.backend_id:
            item = storage.get_knowledge_entry(payload.backend_id)
            _ensure_cloud_record_access(request, item, "Knowledge")
            markdown_path = storage.resolve_root_path(item.get("markdown_path"))
            if markdown_path is None:
                markdown_path = storage.markdown_path_for(title, str(item.get("image_hash") or payload.backend_id), item.get("created_at"))
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(markdown, encoding="utf-8")
            updated = storage.update_knowledge_entry(
                payload.backend_id,
                markdown_path=storage.storage_relative(markdown_path),
                title=title,
                topic=note or item.get("topic") or "",
                status="ready",
                error_message=None,
            )
            return {"item": _public_knowledge_item(updated), "content": markdown}

        draft_hash = storage.hash_bytes(json.dumps(
            {
                "title": title,
                "note": note,
                "body": body,
                "source_ids": payload.source_ids,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"))
        entry = storage.create_or_update_knowledge_entry(
            [],
            draft_hash,
            source_type="draft",
            source_ids=[],
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
        )
        markdown_path = storage.markdown_path_for(title, entry.get("image_hash") or draft_hash, entry.get("created_at"))
        markdown_path.write_text(markdown, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=title,
            topic=note,
            tags=json.dumps([], ensure_ascii=False),
            status="ready",
            error_message=None,
        )
        return {"item": _public_knowledge_item(updated), "content": markdown}
    except Exception as exc:
        logger.exception("Knowledge draft commit failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-files")
def generate_knowledge_from_files(payload: FileGenerateRequest, request: Request) -> dict[str, object]:
    if not payload.file_ids:
        raise HTTPException(status_code=400, detail="Please select at least one file")

    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        source_files = storage.get_source_files(payload.file_ids)
        for item in source_files:
            _ensure_cloud_record_access(request, item, "Source file")
        round_hash = storage.combined_file_hash(source_files)
        scoped_hash = storage.scoped_content_hash(round_hash, owner_user_id)
        existing = storage.get_knowledge_by_hash(scoped_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": _public_knowledge_item(existing), "files": source_files, "skipped": True}

        entry = storage.create_or_update_knowledge_entry(
            [],
            round_hash,
            source_type="files",
            source_ids=payload.file_ids,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
        )
        combined_raw_text = document_parser.recognize_files(source_files, storage.ROOT)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=deepseek_client.current_setting(),
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "file-knowledge",
            entry.get("image_hash") or round_hash,
            entry.get("created_at"),
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=knowledge.title,
            topic=knowledge.topic,
            tags=json.dumps(knowledge.tags, ensure_ascii=False),
            status="ready",
            error_message=None,
        )
        for item in source_files:
            storage.update_source_file(item["id"], status="ready", error_message=None)
        return {
            "item": _public_knowledge_item(updated),
            "files": source_files,
            "skipped": False,
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for file_id in payload.file_ids:
            try:
                storage.update_source_file(file_id, status="error", error_message=str(exc))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-media")
def generate_knowledge_from_media(payload: MediaGenerateRequest, request: Request) -> dict[str, object]:
    if not payload.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one media item")

    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        media_items = storage.get_media_sources(payload.media_ids)
        for item in media_items:
            _ensure_cloud_record_access(request, item, "Media")
        round_hash = storage.combined_media_hash(media_items)
        scoped_hash = storage.scoped_content_hash(round_hash, owner_user_id)
        existing = storage.get_knowledge_by_hash(scoped_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": _public_knowledge_item(existing), "media": media_items, "skipped": True}

        entry = storage.create_or_update_knowledge_entry(
            [],
            round_hash,
            source_type="media",
            source_ids=payload.media_ids,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
        )
        transcript_blocks = []
        failed_media = []
        for item in media_items:
            media_id = int(item["id"])
            try:
                storage.update_media_source(media_id, status="processing", error_message=None)
                transcript, _ = media_parser.ensure_transcript(item)
                refreshed = storage.get_media_source(media_id)
                transcript_blocks.append(media_parser.format_media_transcript(refreshed, transcript))
            except Exception as exc:
                logger.exception("Media transcript failed during knowledge generation for %s", media_id)
                failed = storage.update_media_source(media_id, status="error", error_message=str(exc))
                failed_media.append({"item": failed, "error": str(exc)})

        if not transcript_blocks:
            storage.update_knowledge_entry(entry["id"], status="error", error_message="No media transcript is available")
            return {
                "item": _public_knowledge_item(storage.get_knowledge_entry(entry["id"])),
                "media": storage.get_media_sources(payload.media_ids),
                "skipped": False,
                "generated": False,
                "errors": failed_media,
            }

        combined_raw_text = "\n\n---\n\n".join(transcript_blocks)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=deepseek_client.current_setting(),
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
            source="media",
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "media-knowledge",
            entry.get("image_hash") or round_hash,
            entry.get("created_at"),
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=knowledge.title,
            topic=knowledge.topic,
            tags=json.dumps(knowledge.tags, ensure_ascii=False),
            status="ready",
            error_message=None,
        )
        for item in media_items:
            if any(int(failed["item"].get("id")) == int(item["id"]) for failed in failed_media):
                continue
            storage.update_media_source(int(item["id"]), status="ready", error_message=None)
        return {
            "item": _public_knowledge_item(updated),
            "media": storage.get_media_sources(payload.media_ids),
            "skipped": False,
            "generated": True,
            "errors": failed_media,
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for media_id in payload.media_ids:
            try:
                storage.update_media_source(media_id, status="error", error_message=str(exc))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-file-plan")
def generate_knowledge_from_file_plan(payload: FilePlanGenerateRequest, request: Request) -> dict[str, object]:
    item = storage.get_source_file(payload.file_id)
    _ensure_cloud_record_access(request, item, "Source file")
    payloads = [
        SegmentGeneratePayload(item=item, segment=segment)
        for segment in payload.segments
        if segment.selected
    ]
    return generate_knowledge_for_segment_payloads(payloads, request)


@app.post("/api/knowledge/generate-from-plan-segments")
def generate_knowledge_from_plan_segments(payload: MultiFilePlanGenerateRequest, request: Request) -> dict[str, object]:
    payloads = []
    for segment in payload.segments:
        if not segment.selected or not segment.file_id:
            continue
        item = storage.get_source_file(segment.file_id)
        _ensure_cloud_record_access(request, item, "Source file")
        payloads.append(SegmentGeneratePayload(item=item, segment=segment))
    return generate_knowledge_for_segment_payloads(payloads, request)


def generate_knowledge_for_segment_payloads(payloads: list[SegmentGeneratePayload], request: Request | None = None) -> dict[str, object]:
    if not payloads:
        raise HTTPException(status_code=400, detail="Please select at least one planned topic")

    try:
        context: dict[str, object] | None = None
        owner_user_id: str | None = None
        workspace_id: str | None = None
        if request is not None:
            with storage.connect() as conn:
                context = current_context(request, conn)
            owner_user_id, workspace_id = _context_owner_ids(context)
        pages_cache: dict[int, tuple[dict[str, object], Path, list[dict]]] = {}
        results = []
        for payload in payloads:
            item = payload.item
            segment = payload.segment
            path = storage.resolve_root_path(item.get("file_path"))
            if not path or not path.exists():
                raise HTTPException(status_code=404, detail="Source file not found")
            if int(item["id"]) not in pages_cache:
                pages_cache[int(item["id"])] = (item, path, document_parser.document_pages(path))
            _, path, pages = pages_cache[int(item["id"])]
            if segment.page_ranges:
                page_ranges = document_parser.parse_page_ranges(segment.page_ranges, len(pages))
                segment_pages = document_parser.filter_pages_by_ranges(pages, page_ranges)
                segment_text = document_parser.pages_text(segment_pages)
            else:
                segment_text = document_parser.pages_text(pages, segment.page_start, segment.page_end)
            if not segment_text:
                raise ValueError(f"Planned topic has no usable text: {segment.title}")
            segment_hash = storage.hash_bytes(
                f"{item['file_hash']}|{segment.id}|{segment.page_start}|{segment.page_end}|{segment.title}".encode("utf-8")
            )
            scoped_hash = storage.scoped_content_hash(segment_hash, owner_user_id)
            existing = storage.get_knowledge_by_hash(scoped_hash)
            if existing and existing.get("markdown_path") and existing.get("status") == "ready":
                results.append({"item": existing, "segment": segment.model_dump(), "skipped": True})
                continue

            entry = storage.create_or_update_knowledge_entry(
                [],
                segment_hash,
                source_type="file_plan",
                source_ids=[int(item["id"])],
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
            )
            raw_text = (
                f"[File: {item.get('original_name') or path.name}]\n"
                f"[Planned Topic: {segment.title}]\n"
                f"[Theme: {segment.theme}]\n"
                f"[Pages: {segment.page_ranges or f'{segment.page_start or 1}-{segment.page_end or len(pages)}'}]\n\n"
                f"{segment_text}"
            )
            knowledge, raw_text = deepseek_client.generate_knowledge_from_text(raw_text)
            markdown = render_knowledge_markdown(
                knowledge,
                raw_text=raw_text,
                imported_at=entry.get("created_at"),
                source="file_plan",
            )
            markdown_path = storage.markdown_path_for(
                knowledge.title or segment.title or "file-plan-knowledge",
                entry.get("image_hash") or segment_hash,
                entry.get("created_at"),
            )
            markdown_path.write_text(markdown, encoding="utf-8")
            updated = storage.update_knowledge_entry(
                entry["id"],
                markdown_path=storage.storage_relative(markdown_path),
                title=knowledge.title,
                topic=knowledge.topic,
                tags=json.dumps(knowledge.tags, ensure_ascii=False),
                status="ready",
                error_message=None,
            )
            results.append({"item": updated, "segment": segment.model_dump(), "skipped": False})
        ready_files = []
        for cached_item, _, _ in pages_cache.values():
            ready_files.append(cached_item)
            storage.update_source_file(cached_item["id"], status="ready", error_message=None)
        return {"items": results, "files": ready_files, "generated": len(results)}
    except HTTPException:
        raise
    except Exception as exc:
        try:
            for payload in payloads:
                storage.update_source_file(payload.item["id"], status="error", error_message=str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/knowledge")
def list_knowledge(request: Request) -> dict[str, object]:
    with storage.connect() as conn:
        context = current_context(request, conn)
    return {"items": _public_knowledge_items(storage.list_knowledge(owner_user_id=_cloud_scoped_owner_id(context)))}


@app.get("/api/knowledge/{knowledge_id:int}")
def read_knowledge(knowledge_id: int, request: Request) -> dict[str, object]:
    item = storage.get_knowledge_entry(knowledge_id)
    _ensure_cloud_record_access(request, item, "Knowledge")
    path = storage.resolve_root_path(item.get("markdown_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    return {"item": _public_knowledge_item(item), "content": path.read_text(encoding="utf-8")}


@app.post("/api/knowledge/{knowledge_id:int}")
def update_knowledge(knowledge_id: int, payload: KnowledgeUpdateRequest, request: Request) -> dict[str, object]:
    title = payload.title.strip() or "Untitled knowledge"
    note = payload.note.strip()
    body = strip_repeated_note_quotes(payload.body, note)
    if not body.strip():
        raise HTTPException(status_code=400, detail="Knowledge body is required")

    try:
        item = storage.get_knowledge_entry(knowledge_id)
        _ensure_cloud_record_access(request, item, "Knowledge")
        markdown_path = storage.resolve_root_path(item.get("markdown_path"))
        if markdown_path is None:
            markdown_path = storage.markdown_path_for(
                title,
                str(item.get("image_hash") or knowledge_id),
                item.get("created_at"),
            )
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(body, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            knowledge_id,
            markdown_path=storage.storage_relative(markdown_path),
            title=title,
            topic=note,
            status="ready",
            error_message=None,
        )
        return {"item": _public_knowledge_item(updated), "content": body}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Knowledge entry not found") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Knowledge update failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def strip_repeated_note_quotes(body: str, note: str) -> str:
    clean_note = normalize_note_text(note)
    if not clean_note:
        return body
    lines = body.splitlines()
    index = 0
    removed = False
    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break
        line = lines[index].strip()
        if not line.startswith(">"):
            break
        if normalize_note_text(line[1:]) != clean_note:
            break
        removed = True
        index += 1
    if not removed:
        return body
    return "\n".join(lines[index:]).lstrip("\n")


def normalize_note_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _mining_owner_scope(request: Request) -> str | None:
    with storage.connect() as conn:
        context = current_context(request, conn)
    return _cloud_scoped_owner_id(context)


def _mining_project_payload(project_id: int, owner_user_id: str | None = None) -> dict[str, object]:
    project = storage.get_mining_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)
    return {
        "project": project,
        "sources": storage.list_mining_project_sources(project_id),
        "versions": storage.list_mining_strategy_versions(project_id),
        "artifact_content": storage.read_mining_artifact(project),
    }


def _mining_source_text(project: dict[str, object], source: MiningSourceRef, request: Request | None = None) -> tuple[str, str]:
    if source.source_type == "screenshot":
        item = storage.get_screenshot(source.source_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Image")
        image_path = storage.resolve_root_path(item.get("image_path"))
        if not image_path or not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {source.source_id}")
        if source.parser_mode == "ai_vision":
            text = deepseek_client.recognize_screenshots_with_ai(
                [image_path],
                setting=deepseek_client.current_setting(),
            )
        else:
            text = ocr_client.recognize_screenshots([image_path])
        title = source.title or str(item.get("title") or item.get("image_path") or f"screenshot-{source.source_id}")
        return title, text

    if source.source_type == "file":
        item = storage.get_source_file(source.source_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Source file")
        title = source.title or str(item.get("original_name") or f"file-{source.source_id}")
        return title, document_parser.recognize_files([item], storage.ROOT)

    if source.source_type == "media":
        item = storage.get_media_source(source.source_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Media")
        transcript, _ = media_parser.ensure_transcript(item)
        refreshed = storage.get_media_source(source.source_id)
        title = source.title or str(refreshed.get("title") or refreshed.get("original_name") or f"media-{source.source_id}")
        return title, media_parser.format_media_transcript(refreshed, transcript)

    raise ValueError(f"Unsupported mining source type: {source.source_type}")


@app.get("/api/mining/projects")
def list_mining_projects(request: Request) -> dict[str, object]:
    try:
        owner_user_id = _mining_owner_scope(request)
        return {"items": storage.list_mining_projects(owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects")
def create_mining_project(payload: MiningProjectCreateRequest, request: Request) -> dict[str, object]:
    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        project = storage.create_mining_project(
            payload.name,
            payload.strategy_type,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
        )
        scoped_owner_id = _cloud_scoped_owner_id(context)
        return _mining_project_payload(int(project["id"]), owner_user_id=scoped_owner_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/mining/projects/{project_id}")
def update_mining_project(project_id: int, payload: MiningProjectUpdateRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _mining_owner_scope(request)
        fields: dict[str, object] = {}
        if payload.name is not None:
            fields["name"] = payload.name.strip() or "创作策略学习"
        if payload.status is not None:
            fields["status"] = payload.status
        storage.update_mining_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None, **fields)
        return _mining_project_payload(project_id, owner_user_id=owner_user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/mining/projects/{project_id}")
def read_mining_project(project_id: int, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _mining_owner_scope(request)
        return _mining_project_payload(project_id, owner_user_id=owner_user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects/{project_id}/sources")
def add_mining_project_sources(project_id: int, payload: MiningSourcesRequest, request: Request) -> dict[str, object]:
    if not payload.sources:
        raise HTTPException(status_code=400, detail="请先选择要加入策略学习的素材")
    try:
        owner_user_id = _mining_owner_scope(request)
        project = storage.get_mining_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)
        results = []
        for source in payload.sources:
            try:
                title, text = _mining_source_text(project, source, request=request)
                text_path = storage.mining_source_text_path(project, source.source_type, source.source_id, title)
                text_path.write_text(text, encoding="utf-8")
                saved = storage.upsert_mining_project_source(
                    project_id,
                    source.source_type,
                    source.source_id,
                    title,
                    text_path,
                )
                results.append({"item": saved, "ok": True})
            except Exception as exc:
                logger.exception("Mining source attach failed")
                results.append({"source": source.model_dump(), "ok": False, "error": str(exc)})
        return {**_mining_project_payload(project_id, owner_user_id=owner_user_id), "results": results}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects/{project_id}/learn-creation-strategy")
def learn_creation_strategy(project_id: int, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _mining_owner_scope(request)
        project = storage.get_mining_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)
        materials = storage.read_mining_source_texts(project_id)
        if not materials:
            raise HTTPException(status_code=400, detail="Please add at least one author sample")
        named_materials = [
            (str(source.get("title") or f"{source.get('source_type')}-{source.get('source_id')}"), text)
            for source, text in materials
        ]
        result = deepseek_client.learn_creation_strategy(
            named_materials,
            previous_strategy=storage.read_mining_artifact(project),
            setting=deepseek_client.current_setting(),
        )
        version = storage.next_mining_strategy_version(project_id)
        previous_strategy = storage.read_mining_artifact(project)
        markdown = render_creation_strategy_markdown(result, named_materials, previous_strategy=previous_strategy)
        artifact_path = storage.mining_strategy_path(project, version)
        artifact_path.write_text(markdown, encoding="utf-8")
        version_item = storage.create_mining_strategy_version(
            project_id,
            version,
            artifact_path,
            summary=result.summary,
        )
        response_payload = _mining_project_payload(project_id, owner_user_id=owner_user_id)
        response_payload["version"] = version_item
        return response_payload
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




@app.post("/api/topics/generate")
def generate_topics(request: TopicRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="Please select at least one knowledge file")

    try:
        selected = storage.read_markdown_for_ids(request.knowledge_ids)
        payload = []
        for item, content in selected:
            markdown_path = storage.resolve_root_path(item.get("markdown_path"))
            name = Path(markdown_path).name if markdown_path else f"knowledge-{item['id']}.md"
            payload.append((name, content))
        result = deepseek_client.generate_topics(payload, setting=deepseek_client.current_setting())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result.model_dump()


def _parse_ids(ids: str | None) -> list[int]:
    if not ids:
        return []
    result: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part:
            result.append(int(part))
    return result


def _writer_materials(knowledge_ids: list[int], request: Request | None = None) -> list[tuple[str, str]]:
    selected: list[tuple[dict[str, object], str]] = []
    for knowledge_id in knowledge_ids:
        item = storage.get_knowledge_entry(knowledge_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Knowledge")
        path = storage.resolve_root_path(item.get("markdown_path"))
        if not path or not path.exists():
            raise FileNotFoundError(f"知识文件不存在：{knowledge_id}")
        selected.append((item, path.read_text(encoding="utf-8")))
    payload = []
    for item, content in selected:
        markdown_path = storage.resolve_root_path(item.get("markdown_path"))
        name = Path(markdown_path).name if markdown_path else f"knowledge-{item['id']}.md"
        payload.append((name, content))
    return payload


def _writer_selected_markdowns(knowledge_ids: list[int], request: Request | None = None) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for knowledge_id in knowledge_ids:
        item = storage.get_knowledge_entry(knowledge_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Knowledge")
        path = storage.resolve_root_path(item.get("markdown_path"))
        if not path or not path.exists():
            raise FileNotFoundError(f"知识文件不存在：{knowledge_id}")
        results.append(
            {
                "item": item,
                "filename": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return results


def _writer_owner_scope(request: Request) -> str | None:
    with storage.connect() as conn:
        context = current_context(request, conn)
    return _cloud_scoped_owner_id(context)


def _ensure_legacy_writer_workspace_access(request: Request, workspace: Path) -> None:
    owner_user_id = _writer_owner_scope(request)
    if owner_user_id is None:
        return
    projects_root = writer_tools.projects_dir().resolve()
    resolved = workspace.resolve()
    try:
        relative = resolved.relative_to(projects_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Writer workspace not found") from exc
    project_id = relative.parts[0] if relative.parts else ""
    try:
        writer_tools.load_project(project_id, owner_user_id=owner_user_id, include_ownerless=False)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Writer workspace not found") from exc


def _resolve_legacy_writer_workspace(path: str, request: Request) -> Path:
    workspace = writer_tools.resolve_workspace(path)
    _ensure_legacy_writer_workspace_access(request, workspace)
    return workspace


def _resolve_legacy_writer_file(path: str, request: Request) -> Path:
    file_path = writer_tools.resolve_writer_file(path)
    owner_user_id = _writer_owner_scope(request)
    if owner_user_id is None:
        return file_path
    projects_root = writer_tools.projects_dir().resolve()
    try:
        relative = file_path.resolve().relative_to(projects_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Writer file not found") from exc
    project_id = relative.parts[0] if relative.parts else ""
    try:
        writer_tools.load_project(project_id, owner_user_id=owner_user_id, include_ownerless=False)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Writer file not found") from exc
    return file_path


def _writer_project_payload(project_id: str, owner_user_id: str | None = None) -> dict[str, object]:
    project = writer_tools.load_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)
    workspace = writer_tools.resolve_project_workspace(project_id)
    status = writer_tools.workspace_status(workspace)
    publish_result = None
    publish_path = workspace / "publish_result.json"
    if publish_path.exists():
        try:
            publish_result = json.loads(publish_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            publish_result = {"raw": publish_path.read_text(encoding="utf-8", errors="replace")}
    if publish_result:
        project["publish_result"] = publish_result
    step = _writer_project_step(project)
    return {
        "project": project,
        "status": status,
        "step": step,
        "next_action": _writer_project_next_action_for_project(project, step),
    }


def _writer_load_project(project_id: str, owner_user_id: str | None = None) -> dict[str, object]:
    return writer_tools.load_project(project_id, owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)


def _writer_library_files(knowledge_ids: list[int], request: Request | None = None) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for knowledge_id in knowledge_ids:
        item = storage.get_knowledge_entry(knowledge_id)
        if request is not None:
            _ensure_cloud_record_access(request, item, "Knowledge")
        markdown_path = storage.resolve_root_path(item.get("markdown_path"))
        if not markdown_path:
            continue
        files.append(
            {
                "library": "knowledge",
                "knowledge_id": int(item["id"]),
                "markdown_path": storage.storage_relative(markdown_path),
                "title": item.get("title") or markdown_path.stem,
            }
        )
    return files


def _writer_library_files_from_refs(refs: list[dict[str, object]], request: Request | None = None) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    seen: set[str] = set()
    scoped_owner = _writer_owner_scope(request) if request is not None else None
    for ref in refs:
        library = _normalize_writer_library_id(str(ref.get("library") or "original"))
        knowledge_id = ref.get("knowledge_id") or ref.get("knowledgeId")
        markdown_path = str(ref.get("markdown_path") or ref.get("markdownPath") or "").strip()

        if scoped_owner is not None and knowledge_id is not None:
            item = storage.get_knowledge_entry(int(knowledge_id))
            _ensure_cloud_record_access(request, item, "Knowledge")
            markdown_path = str(item.get("markdown_path") or markdown_path).strip()

        if not markdown_path:
            continue
        path = _resolve_writer_library_ref_path(library, markdown_path)
        if not path or not path.exists():
            continue
        if scoped_owner is not None and request is not None:
            _ensure_cloud_library_file_access(request, path)
        relative_path = storage.storage_relative(path)
        if relative_path in seen:
            continue
        seen.add(relative_path)
        files.append(
            {
                "library": library,
                "knowledge_id": knowledge_id,
                "markdown_path": relative_path,
                "title": str(ref.get("title") or _markdown_title_for_file(path) or path.stem),
            }
        )
    return files


def _normalize_writer_library_id(library: str) -> str:
    normalized = library.strip().lower()
    if normalized == "raw":
        return "original"
    if normalized in {"original", "focus", "perspective", "knowledge"}:
        return normalized
    return "original"


def _resolve_writer_library_ref_path(library: str, markdown_path: str) -> Path | None:
    path = storage.resolve_root_path(markdown_path)
    if path and path.exists():
        return path
    root = {
        "original": storage.RAW_MATERIAL_DIR,
        "raw": storage.RAW_MATERIAL_DIR,
        "focus": storage.KNOWLEDGE_DIR,
        "knowledge": storage.KNOWLEDGE_DIR,
        "perspective": storage.MINING_DIR,
    }.get(library)
    if not root:
        return None
    candidate = root / markdown_path
    return candidate if candidate.exists() else None


def _ensure_cloud_library_file_access(request: Request, path: Path) -> None:
    with storage.connect() as conn:
        context = current_context(request, conn)
    if context.get("deploymentMode") != "cloud":
        return
    user = context.get("user") or {}
    if isinstance(user, dict) and user.get("role") == "admin":
        return
    user_id = str(user.get("id") or "") if isinstance(user, dict) else ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    owner = _markdown_owner_user_id(text)
    if owner and owner == user_id:
        return
    relative_path = storage.storage_relative(path)
    if relative_path:
        with storage.connect() as conn:
            row = conn.execute(
                "SELECT owner_user_id FROM knowledge_entries WHERE markdown_path = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                (relative_path,),
            ).fetchone()
        if row and row["owner_user_id"] and row["owner_user_id"] == user_id:
            return
    raise HTTPException(status_code=404, detail="Library file not found")


def _markdown_owner_user_id(text: str) -> str:
    for line in text.splitlines()[:40]:
        stripped = line.strip().lstrip("- ").strip()
        if not stripped:
            continue
        if "\uff1a" in stripped:
            key, value = stripped.split("\uff1a", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
        else:
            continue
        normalized = key.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized == "owner_user_id":
            return value.strip()
    return ""


def _markdown_title_for_file(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
    except OSError:
        return ""
    return ""



def _writer_project_knowledge_ids(project: dict[str, object]) -> list[int]:
    ids: list[int] = []
    for item in project.get("library_files") or []:
        if not isinstance(item, dict):
            continue
        knowledge_id = item.get("knowledge_id")
        if knowledge_id is not None:
            try:
                ids.append(int(knowledge_id))
            except (TypeError, ValueError):
                continue
    return ids


def _writer_project_materials(project: dict[str, object]) -> list[tuple[str, str]]:
    knowledge_ids = _writer_project_knowledge_ids(project)
    if knowledge_ids:
        return _writer_materials(knowledge_ids)
    materials: list[tuple[str, str]] = []
    for item in project.get("library_files") or []:
        if not isinstance(item, dict):
            continue
        path = storage.resolve_root_path(item.get("markdown_path"))
        if path and path.exists():
            materials.append((path.name, path.read_text(encoding="utf-8")))
    return materials


def _writer_project_step(project: dict[str, object]) -> str:
    if project.get("publish_result"):
        return "published"
    if project.get("preflight"):
        return "publish_check"
    if project.get("html_path"):
        return "designed"
    if project.get("images"):
        return "images"
    if project.get("article_markdown"):
        return "draft"
    if project.get("topic"):
        return "topic"
    if project.get("topics"):
        return "topics"
    if project.get("library_files"):
        return "knowledge_confirmed"
    return "created"


def _writer_project_next_action(step: str) -> str:
    return {
        "created": "confirm_knowledge",
        "knowledge_confirmed": "generate_topics",
        "topics": "select_topic",
        "topic": "generate_draft",
        "draft": "suggest_images",
        "images": "format_article",
        "designed": "run_preflight",
        "publish_check": "publish",
        "published": "done",
    }.get(step, "confirm_knowledge")


def _writer_project_images_need_retry(project: dict[str, object]) -> bool:
    images = project.get("images")
    if not isinstance(images, dict):
        return False
    if images.get("partial") or images.get("ok") is False or images.get("errors"):
        return True
    cover_prompt = str(project.get("cover_prompt") or "").strip()
    if cover_prompt and not isinstance(images.get("cover"), dict):
        return True
    expected_content_count = len(
        [
            str(item).strip()
            for item in (project.get("content_image_prompts") or [])
            if str(item).strip()
        ]
    )
    content_images = images.get("content_images") if isinstance(images.get("content_images"), list) else []
    existing_indexes = {
        int(item.get("index") or 0)
        for item in content_images
        if isinstance(item, dict) and item.get("path")
    }
    return any(index not in existing_indexes for index in range(1, expected_content_count + 1))


def _writer_project_next_action_for_project(project: dict[str, object], step: str) -> str:
    if step == "draft" and project.get("image_suggestion_rationale"):
        return "generate_images"
    if step == "images" and _writer_project_images_need_retry(project):
        return "retry_failed_images"
    if step == "designed" and not project.get("design_confirmed"):
        return "confirm_design"
    if step == "publish_check" and not (project.get("preflight") or {}).get("ok"):
        return "run_preflight"
    return _writer_project_next_action(step)


def _writer_project_workspace(project_id: str) -> Path:
    return writer_tools.resolve_project_workspace(project_id)


def _require_project_materials(project: dict[str, object]) -> list[tuple[str, str]]:
    materials = _writer_project_materials(project)
    if not materials:
        raise HTTPException(status_code=400, detail="Please confirm at least one knowledge file")
    return materials


@app.get("/api/writer/session")
def writer_session(http_request: Request, ids: str | None = None) -> dict[str, object]:
    knowledge_ids = _parse_ids(ids)
    if not knowledge_ids:
        raise HTTPException(status_code=400, detail="请先选择知识文件")
    try:
        items = _writer_selected_markdowns(knowledge_ids, http_request)
        return {"items": items, "knowledge_ids": knowledge_ids}
    except HTTPException:
        raise
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/workspaces")
def writer_workspaces(request: Request) -> dict[str, object]:
    try:
        if _writer_owner_scope(request) is not None:
            return {"items": []}
        return {"items": writer_tools.list_workspaces()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/workspace")
def writer_workspace(path: str, request: Request) -> dict[str, object]:
    try:
        workspace = _resolve_legacy_writer_workspace(path, request)
        return writer_tools.load_workspace(workspace)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/writer/projects")
def writer_projects(request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        return {"items": writer_tools.list_projects(owner_user_id=owner_user_id, include_ownerless=owner_user_id is None)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/writing-strategies")
def writer_writing_strategies() -> dict[str, object]:
    try:
        return writer_tools.list_writing_strategies()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/writing-strategies")
def writer_writing_strategy_save(payload: WriterWritingStrategySaveRequest) -> dict[str, object]:
    try:
        item = writer_tools.save_writing_strategy(payload.name, payload.body, payload.id)
        return {**writer_tools.list_writing_strategies(), "item": item}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/writer/writing-strategies/{strategy_id}")
def writer_writing_strategy_delete(strategy_id: str) -> dict[str, object]:
    try:
        writer_tools.delete_writing_strategy(strategy_id)
        return writer_tools.list_writing_strategies()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects")
def writer_project_create(payload: WriterProjectCreateRequest, request: Request) -> dict[str, object]:
    try:
        with storage.connect() as conn:
            context = current_context(request, conn)
        owner_user_id, workspace_id = _context_owner_ids(context)
        default_name = ""
        files = _writer_library_files_from_refs(payload.library_files, request) if payload.library_files else _writer_library_files(payload.knowledge_ids, request)
        if files:
            default_name = str(files[0]["title"]) if files else ""
        project = writer_tools.create_project(
            payload.name or default_name or "Untitled writing project",
            project_type=payload.project_type,
            description=payload.description,
            writing_strategy=payload.writing_strategy,
            design_strategy=payload.design_strategy,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
        )
        if files:
            writer_tools.set_project_library_files(str(project["id"]), files)
        return _writer_project_payload(str(project["id"]), owner_user_id=_cloud_scoped_owner_id(context))
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/projects/{project_id}")
def writer_project_read(project_id: str, request: Request) -> dict[str, object]:
    try:
        return _writer_project_payload(project_id, owner_user_id=_writer_owner_scope(request))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/knowledge")
def writer_project_confirm_knowledge(project_id: str, payload: WriterProjectKnowledgeRequest, request: Request) -> dict[str, object]:
    if not payload.knowledge_ids and not payload.library_files:
        raise HTTPException(status_code=400, detail="Please select at least one knowledge file")
    try:
        owner_user_id = _writer_owner_scope(request)
        _writer_load_project(project_id, owner_user_id=owner_user_id)
        files = _writer_library_files_from_refs(payload.library_files, request) if payload.library_files else _writer_library_files(payload.knowledge_ids, request)
        if not files:
            raise HTTPException(status_code=400, detail="Selected knowledge files have no readable Markdown path")
        writer_tools.set_project_library_files(project_id, files)
        writer_tools.clear_writer_image_metadata(_writer_project_workspace(project_id))
        writer_tools.update_project(
            project_id,
            topics=[],
            topic={},
            title="",
            digest="",
            article_path="",
            cover_prompt="",
            content_image_prompts=[],
            image_suggestion_rationale="",
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return _writer_project_payload(project_id, owner_user_id=owner_user_id)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/topics")
def writer_project_generate_topics(project_id: str, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        materials = _require_project_materials(project)
        result = deepseek_client.generate_topics(materials, setting=deepseek_client.current_setting())
        suggestions = result.model_dump().get("suggestions", [])
        writer_tools.clear_writer_image_metadata(_writer_project_workspace(project_id))
        updated = writer_tools.update_project(
            project_id,
            topics=suggestions,
            topic={},
            title="",
            digest="",
            article_path="",
            cover_prompt="",
            content_image_prompts=[],
            image_suggestion_rationale="",
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "topics": updated.get("topics", [])}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/topic")
def writer_project_select_topic(project_id: str, payload: WriterProjectTopicRequest, request: Request) -> dict[str, object]:
    if not payload.topic:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨涓€涓€夐")
    try:
        owner_user_id = _writer_owner_scope(request)
        _writer_load_project(project_id, owner_user_id=owner_user_id)
        writer_tools.clear_writer_image_metadata(_writer_project_workspace(project_id))
        writer_tools.update_project(
            project_id,
            topic=payload.topic,
            title="",
            digest="",
            article_path="",
            cover_prompt="",
            content_image_prompts=[],
            image_suggestion_rationale="",
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return _writer_project_payload(project_id, owner_user_id=owner_user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/strategies")
def writer_project_update_strategies(project_id: str, payload: WriterProjectStrategiesRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        writer_tools.update_project(
            project_id,
            writing_strategy=(payload.writing_strategy if payload.writing_strategy is not None else str(project.get("writing_strategy") or "")).strip(),
            design_strategy=(payload.design_strategy if payload.design_strategy is not None else str(project.get("design_strategy") or "")).strip(),
        )
        return _writer_project_payload(project_id, owner_user_id=owner_user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/draft")
def writer_project_generate_draft(project_id: str, payload: WriterProjectDraftRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        materials = _require_project_materials(project)
        topic = payload.topic or project.get("topic")
        if not isinstance(topic, dict) or not topic:
            raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨涓€涓€夐")
        result = deepseek_client.generate_wechat_article(
            topic,
            materials,
            writing_strategy=str(project.get("writing_strategy") or ""),
            setting=deepseek_client.current_setting(),
        )
        workspace = _writer_project_workspace(project_id)
        article_path = writer_tools.write_article(workspace, result.markdown)
        writer_tools.update_project(
            project_id,
            name=result.title or project.get("name"),
            topic=topic,
            title=result.title,
            digest=result.digest,
            cover_prompt=getattr(result, "cover_prompt", "") or project.get("cover_prompt"),
            content_image_prompts=getattr(result, "content_image_prompts", []) or project.get("content_image_prompts"),
            article_path=storage.storage_relative(article_path),
            image_suggestion_rationale="",
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "article": result.model_dump()}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/revise")
def writer_project_revise(project_id: str, payload: WriterProjectReviseRequest, request: Request) -> dict[str, object]:
    if not payload.instruction.strip():
        raise HTTPException(status_code=400, detail="Please enter revision instructions")
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        materials = _require_project_materials(project)
        markdown = payload.markdown if payload.markdown is not None else str(project.get("article_markdown") or "")
        if not markdown.strip():
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鍒濈")
        result = deepseek_client.revise_wechat_article(
            markdown,
            payload.instruction,
            materials,
            setting=deepseek_client.current_setting(),
        )
        workspace = _writer_project_workspace(project_id)
        article_path = writer_tools.write_article(workspace, result.markdown)
        version_path = writer_tools.write_article(workspace, result.markdown, f"article_revised_{datetime.now().strftime('%H%M%S')}.md")
        writer_tools.update_project(
            project_id,
            article_path=storage.storage_relative(article_path),
            latest_revision_path=storage.storage_relative(version_path),
            change_summary=getattr(result, "change_summary", ""),
            cover_prompt=getattr(result, "cover_prompt", "") or project.get("cover_prompt"),
            content_image_prompts=getattr(result, "content_image_prompts", []) or project.get("content_image_prompts"),
            image_suggestion_rationale="",
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "revision": result.model_dump(), "version_path": storage.storage_relative(version_path)}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/image-suggestions")
def writer_project_image_suggestions(project_id: str, payload: WriterProjectImageSuggestionsRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        markdown = payload.markdown if payload.markdown is not None else str(project.get("article_markdown") or "")
        if not markdown.strip():
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鏂囩珷鍒濈")
        topic = payload.topic if payload.topic is not None else project.get("topic")
        content_image_count = max(1, min(3, int(payload.content_image_count or 1)))
        image_style_preset = (payload.image_style_preset or project.get("image_style_preset") or "").strip()
        result = deepseek_client.suggest_writer_images(
            markdown,
            topic=topic if isinstance(topic, dict) else None,
            content_image_count=content_image_count,
            image_style_preset=image_style_preset,
            setting=deepseek_client.current_setting(),
        )
        result.content_image_prompts = (result.content_image_prompts or [])[:content_image_count]
        writer_tools.clear_writer_image_metadata(_writer_project_workspace(project_id))
        writer_tools.update_project(
            project_id,
            cover_prompt=result.cover_prompt,
            content_image_prompts=result.content_image_prompts,
            image_style_preset=image_style_preset,
            image_suggestion_rationale=result.rationale,
            images={},
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "suggestions": result.model_dump()}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/images")
def writer_project_generate_images(project_id: str, payload: WriterProjectImagesRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        cover_prompt = payload.cover_prompt or project.get("cover_prompt")
        content_prompts = payload.content_image_prompts or project.get("content_image_prompts") or []
        if not cover_prompt and not content_prompts:
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鎴栧～鍐欓厤鍥炬彁绀鸿瘝")
        workspace = _writer_project_workspace(project_id)
        result = writer_tools.generate_writer_images(
            workspace,
            cover_prompt=str(cover_prompt) if cover_prompt else None,
            content_prompts=[str(item) for item in content_prompts],
            cover_aspect_ratio=payload.cover_aspect_ratio,
            content_aspect_ratio=payload.content_aspect_ratio,
        )
        writer_tools.update_project(
            project_id,
            images=result,
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "images": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/images/item")
def writer_project_generate_image_item(project_id: str, payload: WriterProjectImageItemRequest, request: Request) -> dict[str, object]:
    if payload.kind not in {"cover", "content"}:
        raise HTTPException(status_code=400, detail="Image kind must be cover or content")
    try:
        owner_user_id = _writer_owner_scope(request)
        _writer_load_project(project_id, owner_user_id=owner_user_id)
        workspace = _writer_project_workspace(project_id)
        result = writer_tools.generate_writer_image_item(
            workspace,
            payload.kind,
            payload.prompt,
            index=payload.index,
            aspect_ratio=payload.aspect_ratio,
        )
        writer_tools.update_project(
            project_id,
            images=result,
            html_path="",
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "images": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/format")
def writer_project_format(project_id: str, payload: WriterProjectFormatRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        workspace = _writer_project_workspace(project_id)
        design_strategy = payload.design_strategy if payload.design_strategy is not None else str(project.get("design_strategy") or "")
        result = writer_tools.format_article(
            workspace,
            markdown=payload.markdown,
            theme=payload.theme,
            design_strategy=design_strategy,
        )
        writer_tools.update_project(
            project_id,
            html_path=result.get("path"),
            html_theme=payload.theme,
            design_strategy=design_strategy,
            design_intent=result.get("design_intent"),
            format_sanitize_report=result.get("sanitize_report"),
            design_confirmed=False,
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "format": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/publish/sanitize")
def writer_project_publish_sanitize(project_id: str, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        if not project.get("html_path"):
            raise HTTPException(status_code=400, detail="请先生成美编 HTML")
        workspace = _writer_project_workspace(project_id)
        result = writer_tools.sanitize_publish_html_preview(workspace)
        writer_tools.update_project(
            project_id,
            publish_sanitize=result,
            publish_inspection=result.get("publish_inspection"),
            preflight={},
            publish_result={},
            status="active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "publish_sanitize": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/confirm-design")
def writer_project_confirm_design(project_id: str, payload: WriterProjectDesignConfirmRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        if not project.get("html_path"):
            raise HTTPException(status_code=400, detail="请先生成美编 HTML")
        writer_tools.update_project(project_id, design_confirmed=bool(payload.confirmed))
        return _writer_project_payload(project_id, owner_user_id=owner_user_id)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/publish/preflight")
def writer_project_publish_preflight(project_id: str, payload: WriterProjectPublishRequest, request: Request) -> dict[str, object]:
    try:
        account_key = _writer_wechat_account_key(request)
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        if not project.get("html_path"):
            raise HTTPException(status_code=400, detail="请先生成美编 HTML")
        if not project.get("design_confirmed"):
            raise HTTPException(status_code=400, detail="请先确认美编预览，再进入发布预检")
        workspace = _writer_project_workspace(project_id)
        title = payload.title or str(project.get("title") or project.get("name") or "")
        digest = payload.digest if payload.digest is not None else project.get("digest")
        author = writer_tools.resolve_publish_author(payload.author, account_key)
        result = writer_tools.publish_preflight(workspace, title, author=author, digest=str(digest or ""), cover_path=payload.cover_path, account_key=account_key)
        safe_digest = result.get("digest", str(digest or ""))
        writer_tools.update_project(
            project_id,
            preflight=result,
            publish_sanitize=result.get("publish_sanitize"),
            publish_inspection=result.get("publish_inspection"),
            publish_title=title,
            publish_author=author,
            publish_digest=safe_digest,
            publish_cover_path=payload.cover_path,
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "preflight": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/publish")
def writer_project_publish(project_id: str, payload: WriterProjectPublishRequest, request: Request) -> dict[str, object]:
    try:
        account_key = _writer_wechat_account_key(request)
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        if not project.get("html_path"):
            raise HTTPException(status_code=400, detail="请先生成美编 HTML")
        if not project.get("design_confirmed"):
            raise HTTPException(status_code=400, detail="请先确认美编预览，再进入发布流程")
        workspace = _writer_project_workspace(project_id)
        title = payload.title or str(project.get("publish_title") or project.get("title") or project.get("name") or "")
        author = writer_tools.resolve_publish_author(payload.author or str(project.get("publish_author") or ""), account_key)
        digest = payload.digest if payload.digest is not None else project.get("publish_digest") or project.get("digest")
        cover_path = payload.cover_path or project.get("publish_cover_path")
        preflight = writer_tools.publish_preflight(
            workspace,
            title,
            author=author,
            digest=str(digest or ""),
            cover_path=str(cover_path) if cover_path else None,
            account_key=account_key,
        )
        digest = preflight.get("digest", str(digest or ""))
        if not preflight["ok"]:
            writer_tools.update_project(
                project_id,
                preflight=preflight,
                publish_sanitize=preflight.get("publish_sanitize"),
                publish_inspection=preflight.get("publish_inspection"),
            )
            raise HTTPException(status_code=400, detail={"message": "Publish preflight failed", **preflight})
        result = writer_tools.publish_draft(
            workspace,
            title,
            author=author,
            digest=str(digest or ""),
            cover_path=str(cover_path) if cover_path else None,
            account_key=account_key,
        )
        writer_tools.update_project(
            project_id,
            preflight=preflight,
            publish_sanitize=preflight.get("publish_sanitize"),
            publish_inspection=preflight.get("publish_inspection"),
            publish_result=result,
            status="published" if result.get("returncode") == 0 else "active",
        )
        return {**_writer_project_payload(project_id, owner_user_id=owner_user_id), "preflight": preflight, "publish": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/advance")
def writer_project_advance(project_id: str, payload: WriterProjectAdvanceRequest, request: Request) -> dict[str, object]:
    try:
        owner_user_id = _writer_owner_scope(request)
        project = _writer_load_project(project_id, owner_user_id=owner_user_id)
        current_step = _writer_project_step(project)
        step = payload.step or _writer_project_next_action_for_project(project, current_step)
        if step == "confirm_knowledge":
            return writer_project_confirm_knowledge(
                project_id,
                WriterProjectKnowledgeRequest(knowledge_ids=payload.knowledge_ids),
                request,
            )
        if step == "generate_topics":
            return writer_project_generate_topics(project_id, request)
        if step == "select_topic":
            return writer_project_select_topic(
                project_id,
                WriterProjectTopicRequest(topic=payload.topic or {}),
                request,
            )
        if step == "generate_draft":
            return writer_project_generate_draft(
                project_id,
                WriterProjectDraftRequest(topic=payload.topic),
                request,
            )
        if step == "revise":
            return writer_project_revise(
                project_id,
                WriterProjectReviseRequest(
                    instruction=payload.instruction or "",
                    markdown=payload.markdown,
                ),
                request,
            )
        if step == "suggest_images":
            return writer_project_image_suggestions(
                project_id,
                WriterProjectImageSuggestionsRequest(
                    markdown=payload.markdown,
                    topic=payload.topic,
                ),
                request,
            )
        if step == "generate_images":
            return writer_project_generate_images(
                project_id,
                WriterProjectImagesRequest(
                    cover_prompt=payload.cover_prompt,
                    content_image_prompts=payload.content_image_prompts,
                    cover_aspect_ratio=payload.cover_aspect_ratio,
                    content_aspect_ratio=payload.content_aspect_ratio,
                ),
                request,
            )
        if step == "format_article":
            return writer_project_format(
                project_id,
                WriterProjectFormatRequest(markdown=payload.markdown),
                request,
            )
        if step == "run_preflight":
            return writer_project_publish_preflight(
                project_id,
                WriterProjectPublishRequest(
                    title=payload.title or "",
                    author=payload.author,
                    digest=payload.digest,
                    cover_path=payload.cover_path,
                ),
                request,
            )
        if step == "publish":
            return writer_project_publish(
                project_id,
                WriterProjectPublishRequest(
                    title=payload.title or "",
                    author=payload.author,
                    digest=payload.digest,
                    cover_path=payload.cover_path,
                ),
                request,
            )
        if step == "done":
            return _writer_project_payload(project_id, owner_user_id=owner_user_id)
        raise HTTPException(status_code=400, detail=f"Unknown writer step: {step}")
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/topics")
def writer_topics(payload: WriterTopicRequest, request: Request) -> dict[str, object]:
    if not payload.knowledge_ids:
        raise HTTPException(status_code=400, detail="请先选择知识文件")
    try:
        result = deepseek_client.generate_topics(
            _writer_materials(payload.knowledge_ids, request),
            setting=deepseek_client.current_setting(),
        )
        return result.model_dump()
    except HTTPException:
        raise
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/article")
def writer_article(payload: WriterArticleRequest, request: Request) -> dict[str, object]:
    if not payload.knowledge_ids:
        raise HTTPException(status_code=400, detail="请先选择知识文件")
    try:
        result = deepseek_client.generate_wechat_article(
            payload.topic,
            _writer_materials(payload.knowledge_ids, request),
            setting=deepseek_client.current_setting(),
        )
        workspace = writer_tools.dated_workspace(result.title)
        article_path = writer_tools.write_article(workspace, result.markdown)
        return {
            **result.model_dump(),
            "workspace": storage.storage_relative(workspace),
            "article_path": storage.storage_relative(article_path),
        }
    except HTTPException:
        raise
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/revise")
def writer_revise(payload: WriterReviseRequest, request: Request) -> dict[str, object]:
    if not payload.knowledge_ids:
        raise HTTPException(status_code=400, detail="请先选择知识文件")
    if not payload.instruction.strip():
        raise HTTPException(status_code=400, detail="Please enter revision instructions")
    try:
        result = deepseek_client.revise_wechat_article(
            payload.markdown,
            payload.instruction,
            _writer_materials(payload.knowledge_ids, request),
            setting=deepseek_client.current_setting(),
        )
        workspace = _resolve_legacy_writer_workspace(payload.workspace, request) if payload.workspace else writer_tools.dated_workspace("article")
        article_path = writer_tools.write_article(workspace, result.markdown)
        version_path = writer_tools.write_article(
            workspace,
            result.markdown,
            f"article_revised_{datetime.now().strftime('%H%M%S')}.md",
        )
        return {
            **result.model_dump(),
            "workspace": storage.storage_relative(workspace),
            "article_path": storage.storage_relative(article_path),
            "version_path": storage.storage_relative(version_path),
        }
    except HTTPException:
        raise
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/images")
def writer_images(payload: WriterImagesRequest, request: Request) -> dict[str, object]:
    try:
        workspace = _resolve_legacy_writer_workspace(payload.workspace, request)
        result = writer_tools.generate_writer_images(
            workspace,
            cover_prompt=payload.cover_prompt,
            content_prompts=payload.content_image_prompts,
            cover_aspect_ratio=payload.cover_aspect_ratio,
            content_aspect_ratio=payload.content_aspect_ratio,
        )
        return {"workspace": storage.storage_relative(workspace), **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/image-suggestions")
def writer_image_suggestions(request: WriterImageSuggestionsRequest) -> dict[str, object]:
    try:
        result = deepseek_client.suggest_writer_images(
            request.markdown,
            topic=request.topic,
            setting=deepseek_client.current_setting(),
        )
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/file")
def writer_file(path: str, request: Request) -> FileResponse:
    try:
        return FileResponse(_resolve_legacy_writer_file(path, request))
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/writer/format")
def writer_format(payload: WriterFormatRequest, request: Request) -> dict[str, object]:
    try:
        workspace = _resolve_legacy_writer_workspace(payload.workspace, request)
        result = writer_tools.format_article(
            workspace,
            markdown=payload.markdown,
            theme=payload.theme,
            design_strategy=payload.design_strategy or "",
        )
        return {"workspace": storage.storage_relative(workspace), **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish")
def writer_publish(payload: WriterPublishRequest, request: Request) -> dict[str, object]:
    try:
        account_key = _writer_wechat_account_key(request)
        workspace = _resolve_legacy_writer_workspace(payload.workspace, request)
        author = writer_tools.resolve_publish_author(payload.author, account_key)
        preflight = writer_tools.publish_preflight(
            workspace,
            payload.title,
            author=author,
            digest=payload.digest,
            cover_path=payload.cover_path,
            account_key=account_key,
        )
        digest = preflight.get("digest", payload.digest or "")
        if not preflight["ok"]:
            raise HTTPException(status_code=400, detail={"message": "Publish preflight failed", **preflight})
        publish_kwargs = {
            "author": author,
            "digest": str(digest or ""),
            "cover_path": payload.cover_path,
        }
        if account_key:
            publish_kwargs["account_key"] = account_key
        result = writer_tools.publish_draft(workspace, payload.title, **publish_kwargs)
        return {"workspace": storage.storage_relative(workspace), "preflight": preflight, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish/preflight")
def writer_publish_preflight(payload: WriterPublishRequest, request: Request) -> dict[str, object]:
    try:
        account_key = _writer_wechat_account_key(request)
        workspace = _resolve_legacy_writer_workspace(payload.workspace, request)
        author = writer_tools.resolve_publish_author(payload.author, account_key)
        result = writer_tools.publish_preflight(
            workspace,
            payload.title,
            author=author,
            digest=payload.digest,
            cover_path=payload.cover_path,
            account_key=account_key,
        )
        return {"workspace": storage.storage_relative(workspace), **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/publish/ip-check")
def writer_publish_ip_check(request: Request) -> dict[str, object]:
    try:
        return writer_tools.check_wechat_publish_ip(account_key=_writer_wechat_account_key(request))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish/token/refresh")
def writer_publish_token_refresh(request: Request) -> dict[str, object]:
    try:
        return writer_tools.refresh_wechat_access_token(account_key=_writer_wechat_account_key(request))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if not getattr(app.state, "api_v2_contracts_mounted", False):
    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(api_v2_router)
    app.include_router(pages_router)
    app.state.api_v2_contracts_mounted = True

