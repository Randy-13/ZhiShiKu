from __future__ import annotations

import base64
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import api_settings
import asr_settings
import deepseek_client
import document_parser
import graph_core
import image_api_settings
import media_parser
import ocr_client
import storage
import workbench_settings
import writer_tools
from markdown_writer import render_creation_strategy_markdown, render_knowledge_markdown
from media_transcriber import transcribe_audio_url
from schemas import DocumentPlanResult, DocumentPlanSegment, KnowledgeResult
from src.api_v2 import router as api_v2_router
from src.pages import router as pages_router
from src.shared.frontend_app import FRONTEND_DIST, react_app_response
from src.shared.navigation import replace_app_rail


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("figurelearning")
APP_ROOT = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.init_storage()
    graph_core.init_graph()
    yield


app = FastAPI(title="Screenshot Knowledge Base", version="0.3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=storage.ROOT / "static"), name="static")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIST, check_dir=False), name="frontend")


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


class KnowledgeGraphIngestRequest(BaseModel):
    knowledge_ids: list[int]


class KnowledgeDeleteRequest(BaseModel):
    knowledge_ids: list[int]


class MiningProjectCreateRequest(BaseModel):
    name: str = "鍒涗綔绛栫暐瀛︿範"
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


class GraphNodeRenameRequest(BaseModel):
    label: str


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
    base_url: str
    model: str
    api_key: str | None = None
    size: str | None = None
    quality: str | None = None
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


class WriterImageSuggestionsRequest(BaseModel):
    markdown: str
    topic: dict[str, object] | None = None


class WriterFormatRequest(BaseModel):
    workspace: str
    markdown: str | None = None
    theme: str = "tech"
    design_strategy: str | None = None


class WriterPublishRequest(BaseModel):
    workspace: str
    title: str
    author: str = "Bobo"
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


class WriterProjectKnowledgeRequest(BaseModel):
    knowledge_ids: list[int]
    library_files: list[dict[str, object]] = []


class WriterProjectTopicRequest(BaseModel):
    topic: dict[str, object]


class WriterProjectDraftRequest(BaseModel):
    topic: dict[str, object] | None = None


class WriterProjectReviseRequest(BaseModel):
    instruction: str
    markdown: str | None = None


class WriterProjectImageSuggestionsRequest(BaseModel):
    markdown: str | None = None
    topic: dict[str, object] | None = None


class WriterProjectImagesRequest(BaseModel):
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []


class WriterProjectFormatRequest(BaseModel):
    markdown: str | None = None
    theme: str = "tech"
    design_strategy: str | None = None


class WriterProjectPublishRequest(BaseModel):
    title: str = ""
    author: str = "Bobo"
    digest: str | None = None
    cover_path: str | None = None


class WriterProjectAdvanceRequest(BaseModel):
    step: str | None = None
    knowledge_ids: list[int] = []
    topic: dict[str, object] | None = None
    instruction: str | None = None
    markdown: str | None = None
    cover_prompt: str | None = None
    content_image_prompts: list[str] = []
    title: str | None = None
    author: str = "Bobo"
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


@app.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
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
        item = api_settings.save_setting(request.model_dump())
        return {"item": item, **api_settings.list_payload()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/api-settings/active")
def set_active_api_setting(request: ApiSettingActiveRequest) -> dict[str, object]:
    try:
        item = api_settings.set_active(request.id)
        return {"item": item, **api_settings.list_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/api-settings/{setting_id}")
def delete_api_setting(setting_id: str) -> dict[str, object]:
    try:
        api_settings.delete_setting(setting_id)
        return api_settings.list_payload()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/api-settings/test")
def test_api_setting(request: ApiSettingTestRequest) -> dict[str, str]:
    try:
        setting = None
        if request.setting:
            payload = request.setting.model_dump()
            if payload.get("id") and not payload.get("api_key"):
                existing = api_settings.get_setting(payload["id"])
                if existing:
                    payload["api_key"] = existing.get("api_key")
            setting = {
                "id": payload.get("id") or "temporary",
                "name": payload.get("name") or "涓存椂 API",
                "provider": payload.get("provider") or "compatible",
                "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
                "model": (payload.get("model") or "").strip(),
                "api_key": (payload.get("api_key") or "").strip(),
                "timeout": payload.get("timeout") or 60,
                "max_retries": payload.get("max_retries") or 0,
            }
        elif request.id:
            setting = api_settings.get_setting(request.id)
            if setting is None:
                raise KeyError("API setting not found")
        if setting is None:
            setting = api_settings.active_setting()
        return deepseek_client.diagnose(setting)
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
        item = asr_settings.save_setting(request.model_dump())
        return {"item": item, **asr_settings.list_payload()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/asr-settings/test")
def test_asr_setting(request: AsrSettingSaveRequest) -> dict[str, object]:
    try:
        payload = request.model_dump()
        if not payload.get("api_key"):
            payload["api_key"] = asr_settings.load_setting().get("api_key")
        saved = asr_settings.save_setting(payload)
        setting = asr_settings.active_setting()
        if setting.get("provider") == "dashscope":
            sample_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/paraformer/hello_world_female2.wav"
            transcribe_audio_url(sample_url, setting)
        asr_settings.mark_test_result(True, "ASR API verified with a real transcription request.")
        return {
            "ok": True,
            "item": saved,
            "message": "ASR API verified with a real transcription request.",
        }
    except ValueError as exc:
        asr_settings.mark_test_result(False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        asr_settings.mark_test_result(False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/image-api-settings")
def list_image_api_settings() -> dict[str, object]:
    return image_api_settings.list_payload()


@app.post("/api/image-api-settings")
def save_image_api_setting(request: ImageApiSettingSaveRequest) -> dict[str, object]:
    try:
        item = image_api_settings.save_setting(request.model_dump())
        return {"item": item, **image_api_settings.list_payload()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/image-api-settings/active")
def set_active_image_api_setting(request: ImageApiSettingActiveRequest) -> dict[str, object]:
    try:
        item = image_api_settings.set_active(request.id)
        return {"item": item, **image_api_settings.list_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/image-api-settings/{setting_id}")
def delete_image_api_setting(setting_id: str) -> dict[str, object]:
    try:
        image_api_settings.delete_setting(setting_id)
        return image_api_settings.list_payload()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/image-api-settings/test")
def test_image_api_setting(request: ImageApiSettingTestRequest) -> dict[str, str]:
    try:
        setting = None
        if request.setting:
            payload = request.setting.model_dump()
            if payload.get("id") and not payload.get("api_key"):
                existing = image_api_settings.get_setting(payload["id"])
                if existing:
                    payload["api_key"] = existing.get("api_key")
            setting = {
                "id": payload.get("id") or "temporary",
                "name": payload.get("name") or "涓存椂鍥剧墖 API",
                "provider": payload.get("provider") or "compatible",
                "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
                "model": (payload.get("model") or "").strip(),
                "api_key": (payload.get("api_key") or "").strip(),
                "size": (payload.get("size") or "1024x1024").strip(),
                "quality": (payload.get("quality") or "auto").strip(),
                "response_format": (payload.get("response_format") or "").strip(),
                "timeout": payload.get("timeout") or 120,
            }
        elif request.id:
            setting = image_api_settings.get_setting(request.id)
            if setting is None:
                raise KeyError("Image API setting not found")
        diagnosis = image_api_settings.diagnose(setting)
        if not request.real_test:
            return diagnosis
        if diagnosis.get("ok") != "true":
            return diagnosis
        output_dir = storage.ROOT / "writer" / "_api_tests"
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
            "generated_path": str(output_path.relative_to(storage.ROOT)),
            "message": f"图片 API 字段诊断通过，并已真实生成测试图片：{result.get('path')}",
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/images")
def upload_images(files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading file name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            items.append(storage.save_upload(upload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Upload failed for %s", upload.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.post("/api/files")
def upload_source_files(files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading source file name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            items.append(storage.save_document_upload(upload))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Source file upload failed for %s", upload.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.post("/api/media/upload")
def upload_media_files(files: list[UploadFile] = File(...)) -> dict[str, object]:
    storage.init_storage()
    items = []
    for upload in files:
        try:
            logger.info(
                "Uploading media name=%s content_type=%s size=%s",
                upload.filename,
                upload.content_type,
                getattr(upload, "size", None),
            )
            items.append(storage.save_media_upload(upload))
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
def bilibili_cookie_status() -> dict[str, object]:
    try:
        return media_parser.bilibili_cookie_status()
    except Exception as exc:
        logger.exception("Bilibili cookie status check failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/media/bilibili-cookies/login")
def open_bilibili_cookie_login(request: BilibiliCookieLoginRequest) -> dict[str, object]:
    try:
        return media_parser.launch_bilibili_cookie_login(request.url)
    except Exception as exc:
        logger.exception("Bilibili cookie login launch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/media/transcripts")
def list_media_transcripts() -> dict[str, object]:
    return {"items": storage.list_media_transcripts()}


@app.get("/api/media/{media_id}/transcript")
def read_media_transcript(media_id: int) -> dict[str, object]:
    item = storage.get_media_source(media_id)
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


def _fallback_readable_document(title: str, raw_text: str, note: str = "") -> dict[str, object]:
    cleaned = _strip_extraction_wrappers(raw_text)
    heading = title.strip() or "Readable document"
    if not cleaned.startswith("#"):
        markdown = f"# {heading}\n\n{cleaned}"
    else:
        markdown = cleaned
    return {
        "title": heading,
        "note": note or "Main text was extracted from the source; local parsed text is kept when LLM cleanup is unavailable.",
        "markdown": markdown.strip(),
        "raw_text": raw_text,
        "cleaned_by": "local",
    }


def _readable_document_from_text(title: str, raw_text: str, material_type: str) -> dict[str, object]:
    fallback = _fallback_readable_document(title, raw_text)
    try:
        setting = api_settings.active_setting()
        cleaned = deepseek_client.clean_readable_document(raw_text, material_type=material_type, setting=setting)
        return {
            "title": cleaned.title.strip() or fallback["title"],
            "note": cleaned.note.strip() or "Cleaned into a readable source document with LLM.",
            "markdown": cleaned.markdown.strip() or fallback["markdown"],
            "raw_text": raw_text,
            "cleaned_by": "llm",
        }
    except Exception as exc:
        logger.warning("Readable document cleanup failed, using local extracted text: %s", exc)
        fallback["note"] = f"{fallback['note']} Cleanup failed: {exc}"
        return fallback


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
        storage.ROOT / "raw_materials",
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
def readable_document(request: ReadableDocumentRequest) -> dict[str, object]:
    if not (request.image_ids or request.file_ids or request.media_ids):
        raise HTTPException(status_code=400, detail="Please select at least one source material")
    parser_mode = request.parser_mode or workbench_settings.load_settings().get("text_extraction_mode") or "local_ocr"
    if parser_mode not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported parser mode")

    raw_blocks: list[str] = []
    titles: list[str] = []
    try:
        if request.image_ids:
            screenshots = storage.get_screenshots(request.image_ids)
            image_paths = []
            for screenshot in screenshots:
                image_path = storage.resolve_root_path(screenshot.get("image_path"))
                if not image_path or not image_path.exists():
                    recovered = _recover_screenshot_text_from_history(screenshot)
                    if recovered:
                        title, text = recovered
                        titles.append(title)
                        raw_blocks.append(text)
                        continue
                    raise FileNotFoundError(
                        f"Image file not found and no recoverable OCR/Markdown history is available: {screenshot['id']}"
                    )
                image_paths.append(image_path)
                titles.append(str(screenshot.get("title") or Path(str(screenshot.get("image_path") or "")).name or f"screenshot-{screenshot['id']}"))
            if image_paths:
                if parser_mode == "ai_vision":
                    raw_blocks.append(deepseek_client.recognize_screenshots_with_ai(image_paths, setting=api_settings.active_setting()))
                else:
                    try:
                        raw_blocks.append(ocr_client.recognize_screenshots(image_paths))
                    except Exception as exc:
                        logger.warning("Local OCR failed, trying AI vision extraction: %s", exc)
                        raw_blocks.append(deepseek_client.recognize_screenshots_with_ai(image_paths, setting=api_settings.active_setting()))

        if request.file_ids:
            files = storage.get_source_files(request.file_ids)
            titles.extend(str(item.get("original_name") or item.get("title") or f"file-{item['id']}") for item in files)
            prefer_visual = parser_mode == "ai_vision"
            raw_blocks.append(
                document_parser.recognize_files(
                    files,
                    storage.ROOT,
                    visual_recognizer=lambda image_paths: deepseek_client.recognize_screenshots_with_ai(
                        image_paths,
                        setting=api_settings.active_setting(),
                    ),
                    prefer_visual=prefer_visual,
                    storage_root=storage.STORAGE_ROOT,
                )
            )

        if request.media_ids:
            for media_id in request.media_ids:
                item = storage.get_media_source(media_id)
                transcript, _ = media_parser.ensure_transcript(item)
                refreshed = storage.get_media_source(media_id)
                titles.append(str(refreshed.get("title") or refreshed.get("original_name") or f"media-{media_id}"))
                raw_blocks.append(media_parser.format_media_transcript(refreshed, transcript))

        unique_blocks = []
        seen_blocks = set()
        for block in raw_blocks:
            clean_block = block.strip()
            if not clean_block:
                continue
            fingerprint = re.sub(r"\s+", "", clean_block)[:4000]
            if fingerprint in seen_blocks:
                continue
            seen_blocks.add(fingerprint)
            unique_blocks.append(clean_block)
        raw_text = "\n\n---\n\n".join(unique_blocks).strip()
        if not raw_text:
            raise ValueError("No readable text was extracted")
        title = titles[0] if len(titles) == 1 else f"{titles[0] if titles else 'Combined material'} and {len(titles) - 1} more"
        material_types = []
        if request.image_ids:
            material_types.append("image")
        if request.file_ids:
            material_types.append("file")
        if request.media_ids:
            material_types.append("media")
        return _readable_document_from_text(title, raw_text, "+".join(material_types) or "raw")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Readable document extraction failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/workbench-settings")
def list_workbench_settings() -> dict[str, object]:
    return workbench_settings.load_settings()


@app.post("/api/workbench-settings")
def save_workbench_settings(request: WorkbenchSettingsRequest) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True)
    if "text_extraction_mode" in payload and payload["text_extraction_mode"] not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported text extraction mode")
    return workbench_settings.save_settings(payload)


@app.post("/api/media/plan-ranges")
def plan_media_ranges(request: MediaPlanRequest) -> dict[str, object]:
    if not request.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one media item")
    segments = []
    results = []
    for media_id in request.media_ids:
        try:
            item = storage.get_media_source(media_id)
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
def generate_knowledge_from_media_plan(request: MediaPlanGenerateRequest) -> dict[str, object]:
    segments = [segment for segment in request.segments if segment.selected]
    if not segments:
        raise HTTPException(status_code=400, detail="Please select at least one transcript segment")
    try:
        setting = api_settings.active_setting()
        results = []
        for segment in segments:
            item = storage.get_media_source(segment.media_id)
            transcript, _ = media_parser.ensure_transcript(item)
            item = storage.get_media_source(segment.media_id)
            selected_text = media_segment_text(transcript, segment)
            if not selected_text:
                raise ValueError(f"Segment has no transcript text: {segment.title}")
            segment_hash = storage.hash_bytes(
                f"{item['media_hash']}|{segment.id}|{segment.time_start}|{segment.time_end}|{segment.title}".encode("utf-8")
            )
            existing = storage.get_knowledge_by_hash(segment_hash)
            if existing and existing.get("markdown_path") and existing.get("status") == "ready":
                results.append({"item": existing, "segment": segment.model_dump(), "skipped": True})
                continue

            entry = storage.create_or_update_knowledge_entry(
                [],
                segment_hash,
                source_type="media_plan",
                source_ids=[int(item["id"])],
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
            knowledge, raw_text = deepseek_client.generate_knowledge_from_text(raw_text, setting=setting)
            markdown = render_knowledge_markdown(
                knowledge,
                raw_text=raw_text,
                imported_at=entry.get("created_at"),
                source="media_plan",
            )
            markdown_path = storage.markdown_path_for(
                knowledge.title or segment.title or "media-plan-knowledge",
                segment_hash,
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
                graph_status="not_ingested",
                graph_error_message=None,
            )
            storage.update_media_source(int(item["id"]), status="ready", error_message=None)
            results.append({"item": updated, "segment": segment.model_dump(), "skipped": False})
        return {"items": results, "generated": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/images/paste")
def upload_pasted_images(request: ImageDataBatchRequest) -> dict[str, object]:
    storage.init_storage()
    items = []
    for image in request.images:
        try:
            header, _, payload = image.data_url.partition(",")
            if not payload:
                raise ValueError("Pasted image data is empty")
            content_type = image.content_type
            if header.startswith("data:") and ";" in header:
                content_type = header.removeprefix("data:").split(";", 1)[0]
            data = base64.b64decode(payload)
            items.append(storage.save_image_bytes(data, image.filename, content_type))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Pasted image upload failed for %s", image.filename)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"items": items}


@app.get("/api/images/{image_id}/file")
def image_file(image_id: int) -> FileResponse:
    item = storage.get_screenshot(image_id)
    path = storage.resolve_root_path(item.get("image_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.get("/api/files/{file_id}/raw")
def source_file_raw(file_id: int) -> FileResponse:
    item = storage.get_source_file(file_id)
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
        setting = api_settings.active_setting()
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
                    setting=setting,
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
        setting = api_settings.active_setting()
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
                setting=setting,
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
def generate_knowledge(request: GenerateRequest) -> dict[str, object]:
    if not request.image_ids:
        raise HTTPException(status_code=400, detail="Please select at least one screenshot")
    if request.parser_mode not in {"local_ocr", "ai_vision"}:
        raise HTTPException(status_code=400, detail="Unsupported parser mode")

    try:
        setting = api_settings.active_setting()
        screenshots = storage.get_screenshots(request.image_ids)
        round_hash = storage.combined_hash(screenshots)
        existing = storage.get_knowledge_by_hash(round_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": existing, "images": screenshots, "skipped": True}

        entry = storage.create_or_update_knowledge_entry(request.image_ids, round_hash)
        image_paths = []
        for screenshot in screenshots:
            image_path = storage.resolve_root_path(screenshot.get("image_path"))
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {screenshot['id']}")
            image_paths.append(image_path)

        if request.parser_mode == "ai_vision":
            combined_raw_text = deepseek_client.recognize_screenshots_with_ai(image_paths, setting=setting)
        else:
            combined_raw_text = ocr_client.recognize_screenshots(image_paths)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=setting,
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
            source="screenshot",
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "screenshot-knowledge",
            round_hash,
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
            graph_status="not_ingested",
            graph_error_message=None,
        )
        for screenshot in screenshots:
            storage.update_screenshot(screenshot["id"], status="ready", error_message=None)
        return {
            "item": updated,
            "images": screenshots,
            "skipped": False,
            "parser_mode": request.parser_mode,
            "graph": {"ok": True, "status": "not_ingested", "pending_node_ids": []},
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for image_id in request.image_ids:
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
        setting = api_settings.active_setting()
        meta = deepseek_client.generate_knowledge_draft_meta(
            request.materials,
            request.body,
            language=request.language,
            setting=setting,
        )
        return meta.model_dump()
    except Exception as exc:
        logger.exception("Knowledge draft metadata generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/commit-draft")
def commit_knowledge_draft(request: KnowledgeDraftCommitRequest) -> dict[str, object]:
    title = request.title.strip() or "Untitled knowledge"
    body = request.body
    if not body.strip():
        raise HTTPException(status_code=400, detail="Draft body is required")
    note = request.note.strip()
    markdown = strip_repeated_note_quotes(body, note) if request.backend_id else body
    if note and not request.backend_id:
        markdown = f"> {note}\n\n{body}"

    try:
        if request.backend_id:
            item = storage.get_knowledge_entry(request.backend_id)
            markdown_path = storage.resolve_root_path(item.get("markdown_path"))
            if markdown_path is None:
                markdown_path = storage.markdown_path_for(title, str(item.get("image_hash") or request.backend_id), item.get("created_at"))
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(markdown, encoding="utf-8")
            updated = storage.update_knowledge_entry(
                request.backend_id,
                markdown_path=storage.storage_relative(markdown_path),
                title=title,
                topic=note or item.get("topic") or "",
                status="ready",
                error_message=None,
                graph_status="not_ingested",
                graph_error_message=None,
            )
            return {"item": updated, "content": markdown}

        draft_hash = storage.hash_bytes(json.dumps(
            {
                "title": title,
                "note": note,
                "body": body,
                "source_ids": request.source_ids,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"))
        entry = storage.create_or_update_knowledge_entry(
            [],
            draft_hash,
            source_type="draft",
            source_ids=[],
        )
        markdown_path = storage.markdown_path_for(title, draft_hash, entry.get("created_at"))
        markdown_path.write_text(markdown, encoding="utf-8")
        updated = storage.update_knowledge_entry(
            entry["id"],
            markdown_path=storage.storage_relative(markdown_path),
            title=title,
            topic=note,
            tags=json.dumps([], ensure_ascii=False),
            status="ready",
            error_message=None,
            graph_status="not_ingested",
            graph_error_message=None,
        )
        return {"item": updated, "content": markdown}
    except Exception as exc:
        logger.exception("Knowledge draft commit failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-files")
def generate_knowledge_from_files(request: FileGenerateRequest) -> dict[str, object]:
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="Please select at least one file")

    try:
        setting = api_settings.active_setting()
        source_files = storage.get_source_files(request.file_ids)
        round_hash = storage.combined_file_hash(source_files)
        existing = storage.get_knowledge_by_hash(round_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": existing, "files": source_files, "skipped": True, "graph": {"ok": True, "status": existing.get("graph_status")}}

        entry = storage.create_or_update_knowledge_entry(
            [],
            round_hash,
            source_type="files",
            source_ids=request.file_ids,
        )
        combined_raw_text = document_parser.recognize_files(source_files, storage.ROOT)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=setting,
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "file-knowledge",
            round_hash,
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
            graph_status="not_ingested",
            graph_error_message=None,
        )
        for item in source_files:
            storage.update_source_file(item["id"], status="ready", error_message=None)
        return {
            "item": updated,
            "files": source_files,
            "skipped": False,
            "graph": {"ok": True, "status": "not_ingested", "pending_node_ids": []},
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for file_id in request.file_ids:
            try:
                storage.update_source_file(file_id, status="error", error_message=str(exc))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-media")
def generate_knowledge_from_media(request: MediaGenerateRequest) -> dict[str, object]:
    if not request.media_ids:
        raise HTTPException(status_code=400, detail="Please select at least one media item")

    try:
        setting = api_settings.active_setting()
        media_items = storage.get_media_sources(request.media_ids)
        round_hash = storage.combined_media_hash(media_items)
        existing = storage.get_knowledge_by_hash(round_hash)
        if existing and existing.get("markdown_path") and existing.get("status") == "ready":
            return {"item": existing, "media": media_items, "skipped": True, "graph": {"ok": True, "status": existing.get("graph_status")}}

        entry = storage.create_or_update_knowledge_entry(
            [],
            round_hash,
            source_type="media",
            source_ids=request.media_ids,
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
                "item": storage.get_knowledge_entry(entry["id"]),
                "media": storage.get_media_sources(request.media_ids),
                "skipped": False,
                "generated": False,
                "errors": failed_media,
                "graph": {"ok": False, "status": "error", "pending_node_ids": []},
            }

        combined_raw_text = "\n\n---\n\n".join(transcript_blocks)
        knowledge, combined_raw_text = deepseek_client.generate_knowledge_from_text(
            combined_raw_text,
            setting=setting,
        )
        markdown = render_knowledge_markdown(
            knowledge,
            raw_text=combined_raw_text,
            imported_at=entry.get("created_at"),
            source="media",
        )
        markdown_path = storage.markdown_path_for(
            knowledge.title or "media-knowledge",
            round_hash,
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
            graph_status="not_ingested",
            graph_error_message=None,
        )
        for item in media_items:
            if any(int(failed["item"].get("id")) == int(item["id"]) for failed in failed_media):
                continue
            storage.update_media_source(int(item["id"]), status="ready", error_message=None)
        return {
            "item": updated,
            "media": storage.get_media_sources(request.media_ids),
            "skipped": False,
            "generated": True,
            "errors": failed_media,
            "graph": {"ok": True, "status": "not_ingested", "pending_node_ids": []},
        }
    except Exception as exc:
        if "entry" in locals():
            storage.update_knowledge_entry(entry["id"], status="error", error_message=str(exc))
        for media_id in request.media_ids:
            try:
                storage.update_media_source(media_id, status="error", error_message=str(exc))
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/knowledge/generate-from-file-plan")
def generate_knowledge_from_file_plan(request: FilePlanGenerateRequest) -> dict[str, object]:
    payloads = [
        SegmentGeneratePayload(item=storage.get_source_file(request.file_id), segment=segment)
        for segment in request.segments
        if segment.selected
    ]
    return generate_knowledge_for_segment_payloads(payloads)


@app.post("/api/knowledge/generate-from-plan-segments")
def generate_knowledge_from_plan_segments(request: MultiFilePlanGenerateRequest) -> dict[str, object]:
    payloads = [
        SegmentGeneratePayload(item=storage.get_source_file(segment.file_id), segment=segment)
        for segment in request.segments
        if segment.selected and segment.file_id
    ]
    return generate_knowledge_for_segment_payloads(payloads)


def generate_knowledge_for_segment_payloads(payloads: list[SegmentGeneratePayload]) -> dict[str, object]:
    if not payloads:
        raise HTTPException(status_code=400, detail="Please select at least one planned topic")

    try:
        setting = api_settings.active_setting()
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
            existing = storage.get_knowledge_by_hash(segment_hash)
            if existing and existing.get("markdown_path") and existing.get("status") == "ready":
                results.append({"item": existing, "segment": segment.model_dump(), "skipped": True})
                continue

            entry = storage.create_or_update_knowledge_entry(
                [],
                segment_hash,
                source_type="file_plan",
                source_ids=[int(item["id"])],
            )
            raw_text = (
                f"[File: {item.get('original_name') or path.name}]\n"
                f"[Planned Topic: {segment.title}]\n"
                f"[Theme: {segment.theme}]\n"
                f"[Pages: {segment.page_ranges or f'{segment.page_start or 1}-{segment.page_end or len(pages)}'}]\n\n"
                f"{segment_text}"
            )
            knowledge, raw_text = deepseek_client.generate_knowledge_from_text(raw_text, setting=setting)
            markdown = render_knowledge_markdown(
                knowledge,
                raw_text=raw_text,
                imported_at=entry.get("created_at"),
                source="file_plan",
            )
            markdown_path = storage.markdown_path_for(
                knowledge.title or segment.title or "file-plan-knowledge",
                segment_hash,
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
                graph_status="not_ingested",
                graph_error_message=None,
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
def list_knowledge() -> dict[str, object]:
    return {"items": storage.list_knowledge()}


@app.post("/api/knowledge/delete-not-ingested")
def delete_not_ingested_knowledge(request: KnowledgeDeleteRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨瑕佸垹闄ょ殑鐭ヨ瘑鏂囦欢")
    try:
        result = storage.delete_not_ingested_knowledge(request.knowledge_ids)
        return {**result, "items": storage.list_knowledge()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/knowledge/{knowledge_id:int}")
def read_knowledge(knowledge_id: int) -> dict[str, object]:
    item = storage.get_knowledge_entry(knowledge_id)
    path = storage.resolve_root_path(item.get("markdown_path"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    return {"item": item, "content": path.read_text(encoding="utf-8")}


@app.post("/api/knowledge/{knowledge_id:int}")
def update_knowledge(knowledge_id: int, request: KnowledgeUpdateRequest) -> dict[str, object]:
    title = request.title.strip() or "Untitled knowledge"
    note = request.note.strip()
    body = strip_repeated_note_quotes(request.body, note)
    if not body.strip():
        raise HTTPException(status_code=400, detail="Knowledge body is required")

    try:
        item = storage.get_knowledge_entry(knowledge_id)
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
        return {"item": updated, "content": body}
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


def _mining_project_payload(project_id: int) -> dict[str, object]:
    project = storage.get_mining_project(project_id)
    return {
        "project": project,
        "sources": storage.list_mining_project_sources(project_id),
        "versions": storage.list_mining_strategy_versions(project_id),
        "artifact_content": storage.read_mining_artifact(project),
    }


def _mining_source_text(project: dict[str, object], source: MiningSourceRef) -> tuple[str, str]:
    if source.source_type == "screenshot":
        item = storage.get_screenshot(source.source_id)
        image_path = storage.resolve_root_path(item.get("image_path"))
        if not image_path or not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {source.source_id}")
        if source.parser_mode == "ai_vision":
            text = deepseek_client.recognize_screenshots_with_ai([image_path], setting=api_settings.active_setting())
        else:
            text = ocr_client.recognize_screenshots([image_path])
        title = source.title or str(item.get("title") or item.get("image_path") or f"screenshot-{source.source_id}")
        return title, text

    if source.source_type == "file":
        item = storage.get_source_file(source.source_id)
        title = source.title or str(item.get("original_name") or f"file-{source.source_id}")
        return title, document_parser.recognize_files([item], storage.ROOT)

    if source.source_type == "media":
        item = storage.get_media_source(source.source_id)
        transcript, _ = media_parser.ensure_transcript(item)
        refreshed = storage.get_media_source(source.source_id)
        title = source.title or str(refreshed.get("title") or refreshed.get("original_name") or f"media-{source.source_id}")
        return title, media_parser.format_media_transcript(refreshed, transcript)

    raise ValueError(f"Unsupported mining source type: {source.source_type}")


@app.get("/api/mining/projects")
def list_mining_projects() -> dict[str, object]:
    try:
        return {"items": storage.list_mining_projects()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects")
def create_mining_project(request: MiningProjectCreateRequest) -> dict[str, object]:
    try:
        project = storage.create_mining_project(request.name, request.strategy_type)
        return _mining_project_payload(int(project["id"]))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/mining/projects/{project_id}")
def update_mining_project(project_id: int, request: MiningProjectUpdateRequest) -> dict[str, object]:
    try:
        fields: dict[str, object] = {}
        if request.name is not None:
            fields["name"] = request.name.strip() or "鍒涗綔绛栫暐瀛︿範"
        if request.status is not None:
            fields["status"] = request.status
        storage.update_mining_project(project_id, **fields)
        return _mining_project_payload(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/mining/projects/{project_id}")
def read_mining_project(project_id: int) -> dict[str, object]:
    try:
        return _mining_project_payload(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects/{project_id}/sources")
def add_mining_project_sources(project_id: int, request: MiningSourcesRequest) -> dict[str, object]:
    if not request.sources:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨瑕佸姞鍏ョ瓥鐣ュ涔犵殑绱犳潗")
    try:
        project = storage.get_mining_project(project_id)
        results = []
        for source in request.sources:
            try:
                title, text = _mining_source_text(project, source)
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
        return {**_mining_project_payload(project_id), "results": results}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mining/projects/{project_id}/learn-creation-strategy")
def learn_creation_strategy(project_id: int) -> dict[str, object]:
    try:
        project = storage.get_mining_project(project_id)
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
            setting=api_settings.active_setting(),
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
        payload = _mining_project_payload(project_id)
        payload["version"] = version_item
        return payload
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _section_from_markdown(content: str, header: str) -> str:
    pattern = rf"##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, content, flags=re.S)
    return match.group(1).strip() if match else ""


def _knowledge_from_entry_markdown(item: dict[str, object], content: str) -> KnowledgeResult:
    title_match = re.search(r"^#\s+(.+)$", content, flags=re.M)
    title = title_match.group(1).strip() if title_match else str(item.get("title") or "Untitled knowledge")
    tags: list[str] = []
    try:
        parsed = json.loads(str(item.get("tags") or "[]"))
        if isinstance(parsed, list):
            tags = [str(tag) for tag in parsed if tag]
    except json.JSONDecodeError:
        tags = []
    raw_text = _section_from_markdown(content, "Raw recognized text")
    clusters = _section_from_markdown(content, "Core knowledge")
    focus = _section_from_markdown(content, "Focus question")
    insights = _section_from_markdown(content, "Insights")
    return KnowledgeResult(
        title=title,
        topic=str(item.get("topic") or ""),
        tags=tags,
        focus_question=focus or raw_text[:600] or title,
        clusters=[],
        investment_insights="\n\n".join(part for part in [insights, clusters, raw_text[:3000]] if part),
    )


@app.post("/api/knowledge/ingest-to-graph")
def ingest_knowledge_to_graph(request: KnowledgeGraphIngestRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨瑕佸叆缃戠殑鐭ヨ瘑鏂囦欢")
    try:
        setting = api_settings.active_setting()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = []
    all_pending_ids: list[str] = []
    for knowledge_id in request.knowledge_ids:
        try:
            item = storage.get_knowledge_entry(knowledge_id)
            path = storage.resolve_root_path(item.get("markdown_path"))
            if not path or not path.exists():
                raise FileNotFoundError(f"鐭ヨ瘑鏂囦欢涓嶅瓨鍦細{knowledge_id}")
            content = path.read_text(encoding="utf-8")
            knowledge = _knowledge_from_entry_markdown(item, content)
            try:
                graph_payload = graph_core.graph_payload()
                extraction = deepseek_client.extract_knowledge_network(
                    knowledge,
                    existing_nodes=graph_payload.get("nodes", []),
                    setting=setting,
                )
            except Exception:
                extraction = graph_core.fallback_network_extraction(knowledge)
            ingest_result = graph_core.ingest_knowledge_network(item, knowledge, extraction, as_pending=True)
            pending_ids = ingest_result.get("pending_node_ids", [])
            if isinstance(pending_ids, list):
                all_pending_ids.extend(str(node_id) for node_id in pending_ids)
            storage.update_knowledge_graph_status(knowledge_id, "pending")
            results.append({"knowledge_id": knowledge_id, "ok": True, **ingest_result})
        except Exception as exc:
            logger.exception("Manual graph ingestion failed for knowledge entry %s", knowledge_id)
            try:
                storage.update_knowledge_graph_status(knowledge_id, "graph_error", str(exc))
            except Exception:
                pass
            results.append({"knowledge_id": knowledge_id, "ok": False, "error": str(exc)})

    return {
        "ok": any(item.get("ok") for item in results),
        "results": results,
        "pending_node_ids": all_pending_ids,
        **graph_core.graph_payload(),
    }


@app.get("/api/graph")
def read_graph() -> dict[str, object]:
    return graph_core.graph_payload()


@app.get("/api/graph/node/{node_id:path}")
def read_graph_node(node_id: str) -> dict[str, object]:
    try:
        return graph_core.node_detail(node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/graph/node/{node_id:path}")
def rename_graph_node(node_id: str, request: GraphNodeRenameRequest) -> dict[str, object]:
    try:
        result = graph_core.rename_node(node_id, request.label)
        return {"ok": True, **result, **graph_core.graph_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/graph/node/{node_id:path}")
def delete_graph_node(node_id: str) -> dict[str, object]:
    try:
        result = graph_core.delete_node(node_id)
        return {"ok": True, **result, **graph_core.graph_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/graph/pending/{node_id:path}")
def update_pending_graph_node(node_id: str, request: GraphNodeRenameRequest) -> dict[str, object]:
    try:
        result = graph_core.update_pending_node(node_id, request.label)
        return {"ok": True, **result, **graph_core.graph_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/graph/pending/{node_id:path}/approve")
def approve_pending_graph_node(node_id: str) -> dict[str, object]:
    try:
        result = graph_core.approve_pending_node(node_id)
        return {"ok": True, **result, **graph_core.graph_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/graph/pending/{node_id:path}")
def delete_pending_graph_node(node_id: str) -> dict[str, object]:
    try:
        result = graph_core.delete_pending_node(node_id)
        return {"ok": True, **result, **graph_core.graph_payload()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/graph/refresh")
def refresh_graph() -> dict[str, object]:
    try:
        return {"ok": True, **graph_core.merge_duplicate_nodes(), **graph_core.graph_payload()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/graph/organize")
def organize_graph() -> dict[str, object]:
    try:
        payload = graph_core.graph_payload()
        setting = api_settings.active_setting()
        organization = deepseek_client.organize_graph_nodes(payload.get("nodes", []), setting=setting)
        return {
            "ok": True,
            **graph_core.apply_graph_organization(organization),
            **graph_core.graph_payload(),
        }
    except Exception as exc:
        logger.exception("Graph organization failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/graph/rebuild")
def rebuild_graph() -> dict[str, object]:
    try:
        return {"ok": True, **graph_core.rebuild_from_existing(), **graph_core.graph_payload()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/retrieval/chat")
def retrieval_chat(request: RetrievalChatRequest) -> dict[str, object]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a retrieval question")
    matches = graph_core.search_knowledge(question)
    if not matches:
        return {
            "answer": "No matching knowledge was found. Try another keyword or import related source material first.",
            "matched_categories": [],
            "reference_files": [],
            "follow_up_suggestions": [],
            "matches": [],
        }
    try:
        setting = api_settings.active_setting()
        result = deepseek_client.answer_retrieval_question(
            question,
            graph_core.retrieval_context(matches),
            setting=setting,
        )
        payload = result.model_dump()
    except Exception as exc:
        logger.exception("Retrieval answer generation failed")
        categories = sorted({item["item"].get("topic") or "Uncategorized" for item in matches})
        files = [Path(item["item"].get("markdown_path") or f"knowledge-{item['item']['id']}.md").name for item in matches]
        payload = {
            "answer": "Related knowledge was found, but API summarization failed. Local matches are listed first.",
            "matched_categories": categories,
            "reference_files": files,
            "follow_up_suggestions": ["Narrow the keyword and ask again", "Open the matched knowledge file to inspect source text"],
            "error": str(exc),
        }
    payload["matches"] = [
        {
            "id": item["item"]["id"],
            "title": item["item"].get("title"),
            "topic": item["item"].get("topic"),
            "markdown_path": item["item"].get("markdown_path"),
            "score": item["score"],
        }
        for item in matches
    ]
    return payload


@app.post("/api/topics/generate")
def generate_topics(request: TopicRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="Please select at least one knowledge file")

    try:
        api_settings.active_setting()
        selected = storage.read_markdown_for_ids(request.knowledge_ids)
        payload = []
        for item, content in selected:
            markdown_path = storage.resolve_root_path(item.get("markdown_path"))
            name = Path(markdown_path).name if markdown_path else f"knowledge-{item['id']}.md"
            payload.append((name, content))
        result = deepseek_client.generate_topics(payload)
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


def _writer_materials(knowledge_ids: list[int]) -> list[tuple[str, str]]:
    selected = storage.read_markdown_for_ids(knowledge_ids)
    payload = []
    for item, content in selected:
        markdown_path = storage.resolve_root_path(item.get("markdown_path"))
        name = Path(markdown_path).name if markdown_path else f"knowledge-{item['id']}.md"
        payload.append((name, content))
    return payload


def _writer_library_files(knowledge_ids: list[int]) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for item, _content in storage.read_markdown_for_ids(knowledge_ids):
        markdown_path = storage.resolve_root_path(item.get("markdown_path"))
        if not markdown_path:
            continue
        files.append(
            {
                "library": "knowledge",
                "knowledge_id": int(item["id"]),
                "markdown_path": str(markdown_path.relative_to(storage.ROOT)),
                "title": item.get("title") or markdown_path.stem,
            }
        )
    return files


def _writer_library_files_from_refs(refs: list[dict[str, object]]) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    seen: set[str] = set()
    for ref in refs:
        markdown_path = str(ref.get("markdown_path") or ref.get("markdownPath") or "").strip()
        if not markdown_path:
            continue
        path = storage.resolve_root_path(markdown_path)
        if not path or not path.exists():
            continue
        relative_path = storage.storage_relative(path)
        if relative_path in seen:
            continue
        seen.add(relative_path)
        files.append(
            {
                "library": str(ref.get("library") or "original"),
                "knowledge_id": ref.get("knowledge_id") or ref.get("knowledgeId"),
                "markdown_path": relative_path,
                "title": str(ref.get("title") or path.stem),
            }
        )
    return files


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


def _writer_project_next_action_for_project(project: dict[str, object], step: str) -> str:
    if step == "draft" and project.get("image_suggestion_rationale"):
        return "generate_images"
    if step == "publish_check" and not (project.get("preflight") or {}).get("ok"):
        return "run_preflight"
    return _writer_project_next_action(step)


def _writer_project_payload(project_id: str) -> dict[str, object]:
    project = writer_tools.load_project(project_id)
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


def _writer_project_workspace(project_id: str) -> Path:
    return writer_tools.resolve_project_workspace(project_id)


def _require_project_materials(project: dict[str, object]) -> list[tuple[str, str]]:
    materials = _writer_project_materials(project)
    if not materials:
        raise HTTPException(status_code=400, detail="Please confirm at least one knowledge file")
    return materials


@app.get("/api/writer/session")
def writer_session(ids: str | None = None) -> dict[str, object]:
    knowledge_ids = _parse_ids(ids)
    if not knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鐭ヨ瘑鏂囦欢")
    try:
        items = writer_tools.selected_markdowns(knowledge_ids)
        return {"items": items, "knowledge_ids": knowledge_ids}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/workspaces")
def writer_workspaces() -> dict[str, object]:
    try:
        return {"items": writer_tools.list_workspaces()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/workspace")
def writer_workspace(path: str) -> dict[str, object]:
    try:
        workspace = writer_tools.resolve_workspace(path)
        return writer_tools.load_workspace(workspace)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/writer/projects")
def writer_projects() -> dict[str, object]:
    try:
        return {"items": writer_tools.list_projects()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects")
def writer_project_create(request: WriterProjectCreateRequest) -> dict[str, object]:
    try:
        default_name = ""
        files = _writer_library_files_from_refs(request.library_files) if request.library_files else _writer_library_files(request.knowledge_ids)
        if files:
            default_name = str(files[0]["title"]) if files else ""
        project = writer_tools.create_project(
            request.name or default_name or "Untitled writing project",
            project_type=request.project_type,
            description=request.description,
            writing_strategy=request.writing_strategy,
            design_strategy=request.design_strategy,
        )
        if files:
            writer_tools.set_project_library_files(str(project["id"]), files)
        return _writer_project_payload(str(project["id"]))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/projects/{project_id}")
def writer_project_read(project_id: str) -> dict[str, object]:
    try:
        return _writer_project_payload(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/knowledge")
def writer_project_confirm_knowledge(project_id: str, request: WriterProjectKnowledgeRequest) -> dict[str, object]:
    if not request.knowledge_ids and not request.library_files:
        raise HTTPException(status_code=400, detail="Please select at least one knowledge file")
    try:
        files = _writer_library_files_from_refs(request.library_files) if request.library_files else _writer_library_files(request.knowledge_ids)
        if not files:
            raise HTTPException(status_code=400, detail="Selected knowledge files have no readable Markdown path")
        writer_tools.set_project_library_files(project_id, files)
        return _writer_project_payload(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/topics")
def writer_project_generate_topics(project_id: str) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        materials = _require_project_materials(project)
        setting = api_settings.active_setting()
        result = deepseek_client.generate_topics(materials, setting=setting)
        suggestions = result.model_dump().get("suggestions", [])
        updated = writer_tools.update_project(project_id, topics=suggestions)
        return {**_writer_project_payload(project_id), "topics": updated.get("topics", [])}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/topic")
def writer_project_select_topic(project_id: str, request: WriterProjectTopicRequest) -> dict[str, object]:
    if not request.topic:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨涓€涓€夐")
    try:
        writer_tools.update_project(project_id, topic=request.topic)
        return _writer_project_payload(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/draft")
def writer_project_generate_draft(project_id: str, request: WriterProjectDraftRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        materials = _require_project_materials(project)
        topic = request.topic or project.get("topic")
        if not isinstance(topic, dict) or not topic:
            raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨涓€涓€夐")
        setting = api_settings.active_setting()
        result = deepseek_client.generate_wechat_article(
            topic,
            materials,
            writing_strategy=str(project.get("writing_strategy") or ""),
            setting=setting,
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
            article_path=str(article_path.relative_to(storage.ROOT)),
        )
        return {**_writer_project_payload(project_id), "article": result.model_dump()}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/revise")
def writer_project_revise(project_id: str, request: WriterProjectReviseRequest) -> dict[str, object]:
    if not request.instruction.strip():
        raise HTTPException(status_code=400, detail="Please enter revision instructions")
    try:
        project = writer_tools.load_project(project_id)
        materials = _require_project_materials(project)
        markdown = request.markdown if request.markdown is not None else str(project.get("article_markdown") or "")
        if not markdown.strip():
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鍒濈")
        setting = api_settings.active_setting()
        result = deepseek_client.revise_wechat_article(markdown, request.instruction, materials, setting=setting)
        workspace = _writer_project_workspace(project_id)
        article_path = writer_tools.write_article(workspace, result.markdown)
        version_path = writer_tools.write_article(workspace, result.markdown, f"article_revised_{datetime.now().strftime('%H%M%S')}.md")
        writer_tools.update_project(
            project_id,
            article_path=str(article_path.relative_to(storage.ROOT)),
            latest_revision_path=str(version_path.relative_to(storage.ROOT)),
            change_summary=getattr(result, "change_summary", ""),
            cover_prompt=getattr(result, "cover_prompt", "") or project.get("cover_prompt"),
            content_image_prompts=getattr(result, "content_image_prompts", []) or project.get("content_image_prompts"),
        )
        return {**_writer_project_payload(project_id), "revision": result.model_dump(), "version_path": str(version_path.relative_to(storage.ROOT))}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/image-suggestions")
def writer_project_image_suggestions(project_id: str, request: WriterProjectImageSuggestionsRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        markdown = request.markdown if request.markdown is not None else str(project.get("article_markdown") or "")
        if not markdown.strip():
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鏂囩珷鍒濈")
        topic = request.topic if request.topic is not None else project.get("topic")
        setting = api_settings.active_setting()
        result = deepseek_client.suggest_writer_images(markdown, topic=topic if isinstance(topic, dict) else None, setting=setting)
        writer_tools.update_project(
            project_id,
            cover_prompt=result.cover_prompt,
            content_image_prompts=result.content_image_prompts,
            image_suggestion_rationale=result.rationale,
        )
        return {**_writer_project_payload(project_id), "suggestions": result.model_dump()}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/images")
def writer_project_generate_images(project_id: str, request: WriterProjectImagesRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        cover_prompt = request.cover_prompt or project.get("cover_prompt")
        content_prompts = request.content_image_prompts or project.get("content_image_prompts") or []
        if not cover_prompt and not content_prompts:
            raise HTTPException(status_code=400, detail="璇峰厛鐢熸垚鎴栧～鍐欓厤鍥炬彁绀鸿瘝")
        workspace = _writer_project_workspace(project_id)
        result = writer_tools.generate_writer_images(
            workspace,
            cover_prompt=str(cover_prompt) if cover_prompt else None,
            content_prompts=[str(item) for item in content_prompts],
        )
        writer_tools.update_project(project_id, images=result)
        return {**_writer_project_payload(project_id), "images": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/format")
def writer_project_format(project_id: str, request: WriterProjectFormatRequest) -> dict[str, object]:
    try:
        workspace = _writer_project_workspace(project_id)
        project = writer_tools.load_project(project_id)
        design_strategy = request.design_strategy if request.design_strategy is not None else str(project.get("design_strategy") or "")
        result = writer_tools.format_article(
            workspace,
            markdown=request.markdown,
            theme=request.theme,
            design_strategy=design_strategy,
        )
        writer_tools.update_project(project_id, html_path=result.get("path"), html_theme=request.theme, design_strategy=design_strategy)
        return {**_writer_project_payload(project_id), "format": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/publish/preflight")
def writer_project_publish_preflight(project_id: str, request: WriterProjectPublishRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        workspace = _writer_project_workspace(project_id)
        title = request.title or str(project.get("title") or project.get("name") or "")
        digest = request.digest if request.digest is not None else project.get("digest")
        result = writer_tools.publish_preflight(workspace, title, author=request.author or "Bobo", digest=str(digest or ""), cover_path=request.cover_path)
        safe_digest = result.get("digest", str(digest or ""))
        writer_tools.update_project(
            project_id,
            preflight=result,
            publish_title=title,
            publish_author=request.author or "Bobo",
            publish_digest=safe_digest,
            publish_cover_path=request.cover_path,
        )
        return {**_writer_project_payload(project_id), "preflight": result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/publish")
def writer_project_publish(project_id: str, request: WriterProjectPublishRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        workspace = _writer_project_workspace(project_id)
        title = request.title or str(project.get("publish_title") or project.get("title") or project.get("name") or "")
        author = request.author or str(project.get("publish_author") or "Bobo")
        digest = request.digest if request.digest is not None else project.get("publish_digest") or project.get("digest")
        cover_path = request.cover_path or project.get("publish_cover_path")
        preflight = writer_tools.publish_preflight(
            workspace,
            title,
            author=author,
            digest=str(digest or ""),
            cover_path=str(cover_path) if cover_path else None,
        )
        digest = preflight.get("digest", str(digest or ""))
        if not preflight["ok"]:
            writer_tools.update_project(project_id, preflight=preflight)
            raise HTTPException(status_code=400, detail={"message": "Publish preflight failed", **preflight})
        result = writer_tools.publish_draft(
            workspace,
            title,
            author=author,
            digest=str(digest or ""),
            cover_path=str(cover_path) if cover_path else None,
        )
        writer_tools.update_project(project_id, preflight=preflight, publish_result=result, status="published" if result.get("returncode") == 0 else "active")
        return {**_writer_project_payload(project_id), "preflight": preflight, "publish": result}
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/projects/{project_id}/advance")
def writer_project_advance(project_id: str, request: WriterProjectAdvanceRequest) -> dict[str, object]:
    try:
        project = writer_tools.load_project(project_id)
        current_step = _writer_project_step(project)
        step = request.step or _writer_project_next_action_for_project(project, current_step)
        if step == "confirm_knowledge":
            return writer_project_confirm_knowledge(
                project_id,
                WriterProjectKnowledgeRequest(knowledge_ids=request.knowledge_ids),
            )
        if step == "generate_topics":
            return writer_project_generate_topics(project_id)
        if step == "select_topic":
            return writer_project_select_topic(
                project_id,
                WriterProjectTopicRequest(topic=request.topic or {}),
            )
        if step == "generate_draft":
            return writer_project_generate_draft(
                project_id,
                WriterProjectDraftRequest(topic=request.topic),
            )
        if step == "revise":
            return writer_project_revise(
                project_id,
                WriterProjectReviseRequest(
                    instruction=request.instruction or "",
                    markdown=request.markdown,
                ),
            )
        if step == "suggest_images":
            return writer_project_image_suggestions(
                project_id,
                WriterProjectImageSuggestionsRequest(
                    markdown=request.markdown,
                    topic=request.topic,
                ),
            )
        if step == "generate_images":
            return writer_project_generate_images(
                project_id,
                WriterProjectImagesRequest(
                    cover_prompt=request.cover_prompt,
                    content_image_prompts=request.content_image_prompts,
                ),
            )
        if step == "format_article":
            return writer_project_format(
                project_id,
                WriterProjectFormatRequest(markdown=request.markdown),
            )
        if step == "run_preflight":
            return writer_project_publish_preflight(
                project_id,
                WriterProjectPublishRequest(
                    title=request.title or "",
                    author=request.author,
                    digest=request.digest,
                    cover_path=request.cover_path,
                ),
            )
        if step == "publish":
            return writer_project_publish(
                project_id,
                WriterProjectPublishRequest(
                    title=request.title or "",
                    author=request.author,
                    digest=request.digest,
                    cover_path=request.cover_path,
                ),
            )
        if step == "done":
            return _writer_project_payload(project_id)
        raise HTTPException(status_code=400, detail=f"Unknown writer step: {step}")
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/topics")
def writer_topics(request: WriterTopicRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鐭ヨ瘑鏂囦欢")
    try:
        setting = api_settings.active_setting()
        result = deepseek_client.generate_topics(_writer_materials(request.knowledge_ids), setting=setting)
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/article")
def writer_article(request: WriterArticleRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鐭ヨ瘑鏂囦欢")
    try:
        setting = api_settings.active_setting()
        result = deepseek_client.generate_wechat_article(
            request.topic,
            _writer_materials(request.knowledge_ids),
            setting=setting,
        )
        workspace = writer_tools.dated_workspace(result.title)
        article_path = writer_tools.write_article(workspace, result.markdown)
        return {
            **result.model_dump(),
            "workspace": str(workspace.relative_to(storage.ROOT)),
            "article_path": str(article_path.relative_to(storage.ROOT)),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/revise")
def writer_revise(request: WriterReviseRequest) -> dict[str, object]:
    if not request.knowledge_ids:
        raise HTTPException(status_code=400, detail="璇峰厛閫夋嫨鐭ヨ瘑鏂囦欢")
    if not request.instruction.strip():
        raise HTTPException(status_code=400, detail="Please enter revision instructions")
    try:
        setting = api_settings.active_setting()
        result = deepseek_client.revise_wechat_article(
            request.markdown,
            request.instruction,
            _writer_materials(request.knowledge_ids),
            setting=setting,
        )
        workspace = writer_tools.resolve_workspace(request.workspace) if request.workspace else writer_tools.dated_workspace("article")
        article_path = writer_tools.write_article(workspace, result.markdown)
        version_path = writer_tools.write_article(
            workspace,
            result.markdown,
            f"article_revised_{datetime.now().strftime('%H%M%S')}.md",
        )
        return {
            **result.model_dump(),
            "workspace": str(workspace.relative_to(storage.ROOT)),
            "article_path": str(article_path.relative_to(storage.ROOT)),
            "version_path": str(version_path.relative_to(storage.ROOT)),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/images")
def writer_images(request: WriterImagesRequest) -> dict[str, object]:
    try:
        workspace = writer_tools.resolve_workspace(request.workspace)
        result = writer_tools.generate_writer_images(
            workspace,
            cover_prompt=request.cover_prompt,
            content_prompts=request.content_image_prompts,
        )
        return {"workspace": str(workspace.relative_to(storage.ROOT)), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/image-suggestions")
def writer_image_suggestions(request: WriterImageSuggestionsRequest) -> dict[str, object]:
    try:
        setting = api_settings.active_setting()
        result = deepseek_client.suggest_writer_images(
            request.markdown,
            topic=request.topic,
            setting=setting,
        )
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/file")
def writer_file(path: str) -> FileResponse:
    try:
        return FileResponse(writer_tools.resolve_writer_file(path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/writer/format")
def writer_format(request: WriterFormatRequest) -> dict[str, object]:
    try:
        workspace = writer_tools.resolve_workspace(request.workspace)
        result = writer_tools.format_article(
            workspace,
            markdown=request.markdown,
            theme=request.theme,
            design_strategy=request.design_strategy or "",
        )
        return {"workspace": str(workspace.relative_to(storage.ROOT)), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish")
def writer_publish(request: WriterPublishRequest) -> dict[str, object]:
    try:
        workspace = writer_tools.resolve_workspace(request.workspace)
        preflight = writer_tools.publish_preflight(
            workspace,
            request.title,
            author=request.author or "Bobo",
            digest=request.digest,
            cover_path=request.cover_path,
        )
        digest = preflight.get("digest", request.digest or "")
        if not preflight["ok"]:
            raise HTTPException(status_code=400, detail={"message": "Publish preflight failed", **preflight})
        result = writer_tools.publish_draft(
            workspace,
            request.title,
            author=request.author or "Bobo",
            digest=str(digest or ""),
            cover_path=request.cover_path,
        )
        return {"workspace": str(workspace.relative_to(storage.ROOT)), "preflight": preflight, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish/preflight")
def writer_publish_preflight(request: WriterPublishRequest) -> dict[str, object]:
    try:
        workspace = writer_tools.resolve_workspace(request.workspace)
        result = writer_tools.publish_preflight(
            workspace,
            request.title,
            author=request.author or "Bobo",
            digest=request.digest,
            cover_path=request.cover_path,
        )
        return {"workspace": str(workspace.relative_to(storage.ROOT)), **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/writer/publish/ip-check")
def writer_publish_ip_check() -> dict[str, object]:
    try:
        return writer_tools.check_wechat_publish_ip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/writer/publish/token/refresh")
def writer_publish_token_refresh() -> dict[str, object]:
    try:
        return writer_tools.refresh_wechat_access_token()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if not getattr(app.state, "api_v2_contracts_mounted", False):
    app.include_router(api_v2_router)
    app.include_router(pages_router)
    app.state.api_v2_contracts_mounted = True

