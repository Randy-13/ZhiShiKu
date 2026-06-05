from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("LOCALAPPDATA", ROOT / "data")) / "FigureLearning"


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _select_storage_root() -> Path:
    configured = os.getenv("FIGURELEARNING_STORAGE_ROOT")
    candidates = [
        Path(configured) if configured else None,
        DATA_DIR,
        ROOT / "data" / "runtime",
    ]
    for candidate in candidates:
        if candidate and _is_writable_dir(candidate):
            return candidate.resolve()
    fallback = ROOT / "data" / "runtime"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()


STORAGE_ROOT = _select_storage_root()
IMAGE_DIR = STORAGE_ROOT / "images"
DOCUMENT_DIR = STORAGE_ROOT / "documents"
KNOWLEDGE_DIR = STORAGE_ROOT / "knowledge"
MEDIA_DIR = STORAGE_ROOT / "media"
MINING_DIR = STORAGE_ROOT / "mining"
DB_PATH = Path(os.getenv("FIGURELEARNING_DB_PATH", ROOT / "knowledge.db"))

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".md", ".markdown", ".txt", ".docx", ".pdf"}
ALLOWED_MEDIA_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".flac",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".srt",
    ".vtt",
    ".ass",
}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass"}


def init_storage() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    MINING_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                image_hash TEXT NOT NULL UNIQUE,
                markdown_path TEXT,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                error_message TEXT,
                topic TEXT,
                tags TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_ids TEXT NOT NULL,
                image_hash TEXT NOT NULL UNIQUE,
                markdown_path TEXT,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing',
                error_message TEXT,
                topic TEXT,
                tags TEXT,
                graph_status TEXT NOT NULL DEFAULT 'not_ingested',
                graph_error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL UNIQUE,
                original_name TEXT,
                content_type TEXT,
                file_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS media_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_kind TEXT NOT NULL,
                platform TEXT NOT NULL,
                source_url TEXT,
                canonical_url TEXT,
                file_path TEXT,
                media_hash TEXT NOT NULL UNIQUE,
                original_name TEXT,
                title TEXT,
                duration_seconds REAL,
                transcript_path TEXT,
                transcript_kind TEXT NOT NULL DEFAULT 'none',
                content_type TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                strategy_type TEXT NOT NULL DEFAULT 'creation_strategy',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                artifact_path TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_project_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                title TEXT,
                text_path TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                error_message TEXT,
                UNIQUE(project_id, source_type, source_id),
                FOREIGN KEY(project_id) REFERENCES mining_projects(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mining_strategy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                artifact_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT,
                UNIQUE(project_id, version),
                FOREIGN KEY(project_id) REFERENCES mining_projects(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS perspective_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'custom',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
            """
        )
        _ensure_column(conn, "knowledge_entries", "graph_status", "TEXT NOT NULL DEFAULT 'not_ingested'")
        _ensure_column(conn, "knowledge_entries", "graph_error_message", "TEXT")
        _ensure_column(conn, "knowledge_entries", "source_type", "TEXT NOT NULL DEFAULT 'screenshots'")
        _ensure_column(conn, "knowledge_entries", "source_ids", "TEXT")
        _ensure_column(conn, "knowledge_entries", "source_hash", "TEXT")
        recover_markdown_entries(conn)
        conn.commit()


def storage_relative(path: Path) -> str:
    resolved = path.resolve()
    for root in (STORAGE_ROOT, ROOT):
        try:
            return str(resolved.relative_to(root.resolve()))
        except ValueError:
            continue
    return str(resolved)


def connect() -> sqlite3.Connection:
    global DB_PATH
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.OperationalError:
        fallback = ROOT / "knowledge.db"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH = fallback
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    if "effective_graph_status" in item:
        item["graph_status"] = item.pop("effective_graph_status")
    return item


def recover_markdown_entries(conn: sqlite3.Connection) -> int:
    recovered = 0
    for path in sorted(KNOWLEDGE_DIR.glob("*/*.md")):
        relative_path = storage_relative(path)
        exists = conn.execute(
            "SELECT id FROM knowledge_entries WHERE markdown_path = ?",
            (relative_path,),
        ).fetchone()
        if exists:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")

        title = parse_markdown_title(text) or path.stem.rsplit("_", 1)[0]
        created_at = parse_markdown_meta(text, "导入时间") or datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        topic = parse_markdown_meta(text, "主题") or ""
        tags = parse_markdown_tags(text)
        item_hash = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
        while conn.execute("SELECT id FROM knowledge_entries WHERE image_hash = ?", (item_hash,)).fetchone():
            item_hash = hashlib.sha256(f"{relative_path}:{item_hash}".encode("utf-8")).hexdigest()

        conn.execute(
            """
            INSERT INTO knowledge_entries (
                image_ids, image_hash, markdown_path, title, created_at, updated_at,
                status, error_message, topic, tags, graph_status, graph_error_message,
                source_type, source_ids, source_hash
            ) VALUES (?, ?, ?, ?, ?, ?, 'ready', NULL, ?, ?, 'not_ingested', NULL, 'recovered_markdown', '[]', ?)
            """,
            (
                "[]",
                item_hash,
                relative_path,
                title,
                created_at,
                datetime.now().isoformat(timespec="seconds"),
                topic,
                json.dumps(tags, ensure_ascii=False),
                item_hash,
            ),
        )
        recovered += 1
    return recovered


def parse_markdown_title(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def parse_markdown_meta(text: str, key: str) -> str | None:
    prefix = f"- {key}："
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def parse_markdown_tags(text: str) -> list[str]:
    raw = parse_markdown_meta(text, "标签") or ""
    if not raw or raw == "未标注":
        return []
    return [item.strip() for item in re.split(r"[、,，]", raw) if item.strip()]


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extension_for_upload(upload: UploadFile) -> str:
    normalized_type = normalize_image_content_type(upload.content_type, upload.filename)
    guessed = mimetypes.guess_extension(normalized_type or "")
    suffix = Path(upload.filename or "").suffix.lower()
    ext = guessed or suffix or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    return ext


def normalize_image_content_type(content_type: str | None, filename: str | None = None) -> str:
    if content_type in ALLOWED_IMAGE_TYPES:
        return content_type
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".bmp":
        return "image/bmp"
    return content_type or "image/png"


def detect_image_content_type(data: bytes, content_type: str | None, filename: str | None = None) -> str:
    normalized = normalize_image_content_type(content_type, filename)
    if normalized in ALLOWED_IMAGE_TYPES:
        return normalized
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"BM"):
        return "image/bmp"
    return normalized


def assert_image_upload(upload: UploadFile) -> None:
    normalized = normalize_image_content_type(upload.content_type, upload.filename)
    if normalized and normalized not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"不支持的图片类型：{upload.content_type}")


def save_upload(upload: UploadFile) -> dict[str, Any]:
    data = upload.file.read()
    if not data:
        raise ValueError("上传文件为空")
    return save_image_bytes(data, upload.filename, upload.content_type)


def save_document_upload(upload: UploadFile) -> dict[str, Any]:
    data = upload.file.read()
    if not data:
        raise ValueError("上传文件为空")
    return save_document_bytes(data, upload.filename, upload.content_type)


def save_media_upload(upload: UploadFile) -> dict[str, Any]:
    data = upload.file.read()
    if not data:
        raise ValueError("上传文件为空")
    return save_media_bytes(data, upload.filename, upload.content_type)


def save_document_bytes(data: bytes, filename: str | None = None, content_type: str | None = None) -> dict[str, Any]:
    if not data:
        raise ValueError("上传文件为空")
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".doc":
        raise ValueError("暂不支持 .doc，请另存为 .docx 后上传")
    if suffix not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError(f"不支持的文件类型：{suffix or content_type or 'unknown'}")

    file_hash = hash_bytes(data)
    now = datetime.now().isoformat(timespec="seconds")
    dated_dir = DOCUMENT_DIR / datetime.now().strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    file_path = dated_dir / f"{file_hash[:16]}{suffix}"

    with connect() as conn:
        existing = conn.execute("SELECT * FROM source_files WHERE file_hash = ?", (file_hash,)).fetchone()
        if existing:
            item = row_to_dict(existing)
            item["duplicate"] = True
            return item
        file_path.write_bytes(data)
        cursor = conn.execute(
            """
            INSERT INTO source_files (
                file_path, file_hash, original_name, content_type, file_type,
                created_at, updated_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded')
            """,
            (
                storage_relative(file_path),
                file_hash,
                filename or file_path.name,
                content_type or mimetypes.guess_type(filename or "")[0] or "",
                suffix.removeprefix("."),
                now,
                now,
            ),
        )
        conn.commit()
        item = get_source_file(cursor.lastrowid)
        item["duplicate"] = False
        return item


def save_media_bytes(data: bytes, filename: str | None = None, content_type: str | None = None) -> dict[str, Any]:
    if not data:
        raise ValueError("上传文件为空")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_MEDIA_EXTENSIONS:
        raise ValueError(f"不支持的音视频/字幕类型：{suffix or content_type or 'unknown'}")

    media_hash = hash_bytes(data)
    now = datetime.now().isoformat(timespec="seconds")
    dated_dir = MEDIA_DIR / datetime.now().strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    file_path = dated_dir / f"{media_hash[:16]}{suffix}"
    source_kind = "subtitle_file" if suffix in SUBTITLE_EXTENSIONS else "local_file"
    transcript_kind = "uploaded_subtitle" if source_kind == "subtitle_file" else "none"

    with connect() as conn:
        existing = conn.execute("SELECT * FROM media_sources WHERE media_hash = ?", (media_hash,)).fetchone()
        if existing:
            item = row_to_dict(existing)
            item["duplicate"] = True
            return item
        file_path.write_bytes(data)
        cursor = conn.execute(
            """
            INSERT INTO media_sources (
                source_kind, platform, file_path, media_hash, original_name, title,
                transcript_path, transcript_kind, content_type, created_at, updated_at, status
            ) VALUES (?, 'local', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded')
            """,
            (
                source_kind,
                storage_relative(file_path),
                media_hash,
                filename or file_path.name,
                Path(filename or file_path.name).stem,
                storage_relative(file_path) if source_kind == "subtitle_file" else None,
                transcript_kind,
                content_type or mimetypes.guess_type(filename or "")[0] or "",
                now,
                now,
            ),
        )
        conn.commit()
        item = get_media_source(cursor.lastrowid)
        item["duplicate"] = False
        return item


def save_image_bytes(data: bytes, filename: str | None = None, content_type: str | None = None) -> dict[str, Any]:
    if not data:
        raise ValueError("上传文件为空")

    content_type = detect_image_content_type(data, content_type, filename)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"不支持的图片类型：{content_type or 'unknown'}")

    image_hash = hash_bytes(data)
    now = datetime.now().isoformat(timespec="seconds")
    ext = mimetypes.guess_extension(content_type) or Path(filename or "").suffix.lower() or ".png"
    if ext == ".jpe":
        ext = ".jpg"
    dated_dir = IMAGE_DIR / datetime.now().strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    image_path = dated_dir / f"{image_hash[:16]}{ext}"

    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM screenshots WHERE image_hash = ?",
            (image_hash,),
        ).fetchone()
        if existing:
            existing_dict = row_to_dict(existing)
            existing_dict["duplicate"] = True
            return existing_dict

        try:
            image_path.write_bytes(data)
            cursor = conn.execute(
                """
                INSERT INTO screenshots (
                    image_path, image_hash, created_at, updated_at, status
                ) VALUES (?, ?, ?, ?, 'uploaded')
                """,
                (storage_relative(image_path), image_hash, now, now),
            )
            conn.commit()
            item = get_screenshot(cursor.lastrowid)
        except sqlite3.IntegrityError:
            conn.rollback()
            existing = conn.execute(
                "SELECT * FROM screenshots WHERE image_hash = ?",
                (image_hash,),
            ).fetchone()
            if existing is None:
                raise
            item = row_to_dict(existing)
            item["duplicate"] = True
            return item
        item["duplicate"] = False
        return item


def get_screenshot(screenshot_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM screenshots WHERE id = ?",
            (screenshot_id,),
        ).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Screenshot {screenshot_id} not found")
    return item


def get_screenshots(ids: list[int]) -> list[dict[str, Any]]:
    return [get_screenshot(screenshot_id) for screenshot_id in ids]


def get_source_file(file_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM source_files WHERE id = ?", (file_id,)).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Source file {file_id} not found")
    return item


def get_source_files(ids: list[int]) -> list[dict[str, Any]]:
    return [get_source_file(file_id) for file_id in ids]


def get_media_source(media_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM media_sources WHERE id = ?", (media_id,)).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Media source {media_id} not found")
    return item


def get_media_sources(ids: list[int]) -> list[dict[str, Any]]:
    return [get_media_source(media_id) for media_id in ids]


def list_media_transcripts() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM media_sources
            WHERE transcript_path IS NOT NULL
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def create_remote_media_source(
    *,
    platform: str,
    source_url: str,
    canonical_url: str,
    title: str | None = None,
    duration_seconds: float | None = None,
    status: str = "resolved",
    error_message: str | None = None,
) -> dict[str, Any]:
    media_hash = hash_bytes(f"{platform}|{canonical_url}".encode("utf-8"))
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        existing = conn.execute("SELECT * FROM media_sources WHERE media_hash = ?", (media_hash,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE media_sources
                SET source_url = ?, canonical_url = ?, title = ?, duration_seconds = ?,
                    updated_at = ?, status = ?, error_message = ?
                WHERE media_hash = ?
                """,
                (source_url, canonical_url, title, duration_seconds, now, status, error_message, media_hash),
            )
            conn.commit()
            item = get_media_by_hash(media_hash)
            if item is None:
                raise KeyError(f"Media source with hash {media_hash} not found")
            item["duplicate"] = True
            return item
        cursor = conn.execute(
            """
            INSERT INTO media_sources (
                source_kind, platform, source_url, canonical_url, media_hash, title,
                duration_seconds, transcript_kind, created_at, updated_at, status, error_message
            ) VALUES ('remote_url', ?, ?, ?, ?, ?, ?, 'none', ?, ?, ?, ?)
            """,
            (platform, source_url, canonical_url, media_hash, title, duration_seconds, now, now, status, error_message),
        )
        conn.commit()
        item = get_media_source(cursor.lastrowid)
        item["duplicate"] = False
        return item


def get_media_by_hash(media_hash: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM media_sources WHERE media_hash = ?", (media_hash,)).fetchone()
    return row_to_dict(row)


def update_media_source(media_id: int, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_media_source(media_id)
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(media_id)
    with connect() as conn:
        conn.execute(f"UPDATE media_sources SET {assignments} WHERE id = ?", values)
        conn.commit()
    return get_media_source(media_id)


def delete_media_transcripts(ids: list[int]) -> dict[str, Any]:
    deleted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    with connect() as conn:
        for media_id in ids:
            row = conn.execute("SELECT * FROM media_sources WHERE id = ?", (media_id,)).fetchone()
            item = row_to_dict(row)
            if item is None:
                skipped.append({"id": media_id, "reason": "not_found"})
                continue
            transcript_path = resolve_root_path(item.get("transcript_path"))
            conn.execute(
                """
                UPDATE media_sources
                SET transcript_path = NULL, transcript_kind = 'none', status = 'resolved',
                    error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(timespec="seconds"), media_id),
            )
            deleted.append({"id": media_id, "title": item.get("title"), "transcript_path": item.get("transcript_path")})
            if transcript_path and transcript_path.exists() and transcript_path.is_file():
                try:
                    transcript_path.unlink()
                except OSError as exc:
                    skipped.append({"id": media_id, "reason": f"file_delete_failed: {exc}"})
        conn.commit()
    return {"deleted": deleted, "skipped": skipped}


def combined_media_hash(items: list[dict[str, Any]]) -> str:
    ordered_hashes = [item["media_hash"] for item in items]
    return hashlib.sha256("|".join(ordered_hashes).encode("utf-8")).hexdigest()


def media_transcript_path_for(media_id: int, title: str | None = None) -> Path:
    dated_dir = MEDIA_DIR / datetime.now().strftime("%Y-%m-%d") / "transcripts"
    dated_dir.mkdir(parents=True, exist_ok=True)
    safe_title = safe_filename(title or f"media-{media_id}", fallback=f"media-{media_id}")
    return dated_dir / f"{safe_title}_{media_id}.txt"


def update_source_file(file_id: int, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_source_file(file_id)
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(file_id)
    with connect() as conn:
        conn.execute(f"UPDATE source_files SET {assignments} WHERE id = ?", values)
        conn.commit()
    return get_source_file(file_id)


def update_screenshot(screenshot_id: int, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_screenshot(screenshot_id)

    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(screenshot_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE screenshots SET {assignments} WHERE id = ?",
            values,
        )
        conn.commit()
    return get_screenshot(screenshot_id)


def list_knowledge() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                k.*,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM knowledge_node_links l WHERE l.knowledge_id = k.id
                    ) THEN 'ingested'
                    ELSE COALESCE(k.graph_status, 'not_ingested')
                END AS effective_graph_status
            FROM knowledge_entries k
            WHERE markdown_path IS NOT NULL
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_knowledge_entry(entry_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                k.*,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM knowledge_node_links l WHERE l.knowledge_id = k.id
                    ) THEN 'ingested'
                    ELSE COALESCE(k.graph_status, 'not_ingested')
                END AS effective_graph_status
            FROM knowledge_entries k
            WHERE k.id = ?
            """,
            (entry_id,),
        ).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Knowledge entry {entry_id} not found")
    return item


def get_knowledge_by_hash(image_hash: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                k.*,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM knowledge_node_links l WHERE l.knowledge_id = k.id
                    ) THEN 'ingested'
                    ELSE COALESCE(k.graph_status, 'not_ingested')
                END AS effective_graph_status
            FROM knowledge_entries k
            WHERE k.image_hash = ?
            """,
            (image_hash,),
        ).fetchone()
    return row_to_dict(row)


def combined_hash(items: list[dict[str, Any]]) -> str:
    ordered_hashes = [item["image_hash"] for item in items]
    return hashlib.sha256("|".join(ordered_hashes).encode("utf-8")).hexdigest()


def combined_file_hash(items: list[dict[str, Any]]) -> str:
    ordered_hashes = [item["file_hash"] for item in items]
    return hashlib.sha256("|".join(ordered_hashes).encode("utf-8")).hexdigest()


def create_or_update_knowledge_entry(
    image_ids: list[int],
    image_hash: str,
    source_type: str = "screenshots",
    source_ids: list[int] | None = None,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    image_ids_json = json.dumps(image_ids, ensure_ascii=False)
    source_ids_json = json.dumps(source_ids if source_ids is not None else image_ids, ensure_ascii=False)
    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM knowledge_entries WHERE image_hash = ?",
            (image_hash,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE knowledge_entries
                SET image_ids = ?, updated_at = ?, status = 'processing', error_message = NULL,
                    graph_status = 'not_ingested', graph_error_message = NULL,
                    source_type = ?, source_ids = ?, source_hash = ?
                WHERE image_hash = ?
                """,
                (image_ids_json, now, source_type, source_ids_json, image_hash, image_hash),
            )
            conn.commit()
            existing_item = get_knowledge_by_hash(image_hash)
            if existing_item is None:
                raise KeyError(f"Knowledge entry with hash {image_hash} not found")
            return existing_item

        cursor = conn.execute(
            """
            INSERT INTO knowledge_entries (
                image_ids, image_hash, created_at, updated_at, status, graph_status,
                source_type, source_ids, source_hash
            ) VALUES (?, ?, ?, ?, 'processing', 'not_ingested', ?, ?, ?)
            """,
            (image_ids_json, image_hash, now, now, source_type, source_ids_json, image_hash),
        )
        conn.commit()
        return get_knowledge_entry(cursor.lastrowid)


def update_knowledge_entry(entry_id: int, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_knowledge_entry(entry_id)

    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(entry_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE knowledge_entries SET {assignments} WHERE id = ?",
            values,
        )
        conn.commit()
    return get_knowledge_entry(entry_id)


def update_knowledge_graph_status(
    entry_id: int,
    graph_status: str,
    graph_error_message: str | None = None,
) -> dict[str, Any]:
    if graph_status not in {"not_ingested", "pending", "ingested", "graph_error"}:
        raise ValueError(f"Unsupported graph status: {graph_status}")
    return update_knowledge_entry(
        entry_id,
        graph_status=graph_status,
        graph_error_message=graph_error_message,
    )


def delete_not_ingested_knowledge(ids: list[int]) -> dict[str, Any]:
    deleted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    allowed_statuses = {"not_ingested", "graph_error"}
    with connect() as conn:
        for entry_id in ids:
            row = conn.execute(
                """
                SELECT
                    k.*,
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM knowledge_node_links l WHERE l.knowledge_id = k.id
                        ) THEN 'ingested'
                        ELSE COALESCE(k.graph_status, 'not_ingested')
                    END AS effective_graph_status
                FROM knowledge_entries k
                WHERE k.id = ?
                """,
                (entry_id,),
            ).fetchone()
            item = row_to_dict(row)
            if item is None:
                skipped.append({"id": entry_id, "reason": "not_found"})
                continue
            graph_status = item.get("effective_graph_status") or item.get("graph_status") or "not_ingested"
            if graph_status not in allowed_statuses:
                skipped.append(
                    {
                        "id": entry_id,
                        "title": item.get("title"),
                        "graph_status": graph_status,
                        "reason": "already_or_pending_ingested",
                    }
                )
                continue
            markdown_path = resolve_root_path(item.get("markdown_path"))
            conn.execute("DELETE FROM knowledge_entries WHERE id = ?", (entry_id,))
            deleted.append({"id": entry_id, "title": item.get("title"), "markdown_path": item.get("markdown_path")})
            if markdown_path and markdown_path.exists() and markdown_path.is_file():
                try:
                    markdown_path.unlink()
                except OSError as exc:
                    skipped.append({"id": entry_id, "reason": f"file_delete_failed: {exc}"})
        conn.commit()
    return {"deleted": deleted, "skipped": skipped}


def resolve_root_path(relative_or_absolute: str | None) -> Path | None:
    if not relative_or_absolute:
        return None
    path = Path(relative_or_absolute)
    if not path.is_absolute():
        storage_candidate = STORAGE_ROOT / path
        if storage_candidate.exists():
            return storage_candidate
        root_candidate = ROOT / path
        if root_candidate.exists():
            return root_candidate
        first_part = path.parts[0] if path.parts else ""
        if first_part in {"images", "documents", "knowledge", "media", "mining"}:
            return storage_candidate
        return root_candidate
    return path


def safe_filename(value: str, fallback: str = "截图知识") -> str:
    text = value.strip() or fallback
    text = re.sub(r"[\\/:*?\"<>|#\r\n\t]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return text[:48] or fallback


def markdown_path_for(title: str, image_hash: str, created_at: str | None = None) -> Path:
    if created_at:
        date_part = created_at[:10]
    else:
        date_part = datetime.now().strftime("%Y-%m-%d")
    dated_dir = KNOWLEDGE_DIR / date_part
    dated_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(title)}_{image_hash[:8]}.md"
    return dated_dir / filename


def mining_project_dir(project: dict[str, Any]) -> Path:
    created_at = str(project.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    dated_dir = MINING_DIR / created_at[:10] / safe_filename(str(project.get("name") or f"project-{project['id']}"), fallback=f"project-{project['id']}")
    dated_dir.mkdir(parents=True, exist_ok=True)
    return dated_dir


def mining_source_text_path(project: dict[str, Any], source_type: str, source_id: int, title: str | None = None) -> Path:
    source_dir = mining_project_dir(project) / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    safe_title = safe_filename(title or f"{source_type}-{source_id}", fallback=f"{source_type}-{source_id}")
    return source_dir / f"{source_type}-{source_id}-{safe_title}.txt"


def mining_strategy_path(project: dict[str, Any], version: int) -> Path:
    return mining_project_dir(project) / f"strategy_v{version}.md"


def list_mining_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   COUNT(s.id) AS source_count,
                   MAX(v.version) AS latest_version
            FROM mining_projects p
            LEFT JOIN mining_project_sources s ON s.project_id = p.id
            LEFT JOIN mining_strategy_versions v ON v.project_id = p.id
            GROUP BY p.id
            ORDER BY p.updated_at DESC, p.id DESC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def create_mining_project(name: str, strategy_type: str = "creation_strategy") -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    clean_name = name.strip() or "创作策略学习"
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO mining_projects (name, strategy_type, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (clean_name, strategy_type, now, now),
        )
        conn.commit()
    return get_mining_project(cursor.lastrowid)


def get_mining_project(project_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM mining_projects WHERE id = ?", (project_id,)).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Mining project {project_id} not found")
    return item


def update_mining_project(project_id: int, **fields: Any) -> dict[str, Any]:
    if not fields:
        return get_mining_project(project_id)
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(project_id)
    with connect() as conn:
        conn.execute(f"UPDATE mining_projects SET {assignments} WHERE id = ?", values)
        conn.commit()
    return get_mining_project(project_id)


def upsert_mining_project_source(
    project_id: int,
    source_type: str,
    source_id: int,
    title: str,
    text_path: Path,
    status: str = "ready",
    error_message: str | None = None,
) -> dict[str, Any]:
    project = get_mining_project(project_id)
    now = datetime.now().isoformat(timespec="seconds")
    relative_text_path = storage_relative(text_path)
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM mining_project_sources
            WHERE project_id = ? AND source_type = ? AND source_id = ?
            """,
            (project_id, source_type, source_id),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE mining_project_sources
                SET title = ?, text_path = ?, status = ?, error_message = ?
                WHERE id = ?
                """,
                (title, relative_text_path, status, error_message, existing["id"]),
            )
            source_id_row = int(existing["id"])
        else:
            cursor = conn.execute(
                """
                INSERT INTO mining_project_sources (
                    project_id, source_type, source_id, title, text_path,
                    created_at, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, source_type, source_id, title, relative_text_path, now, status, error_message),
            )
            source_id_row = int(cursor.lastrowid)
        conn.execute(
            "UPDATE mining_projects SET updated_at = ? WHERE id = ?",
            (now, project["id"]),
        )
        conn.commit()
    return get_mining_project_source(source_id_row)


def get_mining_project_source(source_row_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM mining_project_sources WHERE id = ?", (source_row_id,)).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Mining source {source_row_id} not found")
    return item


def list_mining_project_sources(project_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM mining_project_sources
            WHERE project_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (project_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def list_mining_strategy_versions(project_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM mining_strategy_versions
            WHERE project_id = ?
            ORDER BY version DESC
            """,
            (project_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def next_mining_strategy_version(project_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS latest FROM mining_strategy_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return int(row["latest"] or 0) + 1


def create_mining_strategy_version(
    project_id: int,
    version: int,
    artifact_path: Path,
    summary: str = "",
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    relative_artifact_path = storage_relative(artifact_path)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO mining_strategy_versions (project_id, version, artifact_path, created_at, summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, version, relative_artifact_path, now, summary),
        )
        conn.execute(
            """
            UPDATE mining_projects
            SET artifact_path = ?, updated_at = ?, status = 'ready'
            WHERE id = ?
            """,
            (relative_artifact_path, now, project_id),
        )
        conn.commit()
    with connect() as conn:
        row = conn.execute("SELECT * FROM mining_strategy_versions WHERE id = ?", (cursor.lastrowid,)).fetchone()
    item = row_to_dict(row)
    if item is None:
        raise KeyError(f"Mining strategy version {cursor.lastrowid} not found")
    return item


def read_mining_source_texts(project_id: int) -> list[tuple[dict[str, Any], str]]:
    results: list[tuple[dict[str, Any], str]] = []
    for source in list_mining_project_sources(project_id):
        path = resolve_root_path(source.get("text_path"))
        if not path or not path.exists():
            continue
        results.append((source, path.read_text(encoding="utf-8", errors="ignore")))
    return results


def read_mining_artifact(project: dict[str, Any]) -> str:
    path = resolve_root_path(project.get("artifact_path"))
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def list_perspective_profiles() -> list[dict[str, Any]]:
    init_storage()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM perspective_profiles
            WHERE status = 'active'
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    profiles: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        if item is None:
            continue
        try:
            profile = json.loads(str(item.get("profile_json") or "{}"))
        except json.JSONDecodeError:
            profile = {}
        profile["id"] = item["id"]
        profile["name"] = profile.get("name") or item["name"]
        profile["origin"] = item.get("origin") or "custom"
        profile["created_at"] = item.get("created_at") or ""
        profile["updated_at"] = item.get("updated_at") or ""
        profiles.append(profile)
    return profiles


def upsert_perspective_profile(profile: dict[str, Any]) -> dict[str, Any]:
    init_storage()
    now = datetime.now().isoformat(timespec="seconds")
    profile_id = str(profile.get("id") or "").strip() or f"custom_{uuid.uuid4().hex[:10]}"
    if not profile_id.startswith("custom_"):
        profile_id = f"custom_{profile_id}_{uuid.uuid4().hex[:6]}"
    name = str(profile.get("name") or "").strip() or "自定义视角"
    normalized = dict(profile)
    normalized["id"] = profile_id
    normalized["name"] = name
    normalized["origin"] = "custom"
    profile_json = json.dumps(normalized, ensure_ascii=False)
    with connect() as conn:
        existing = conn.execute("SELECT id FROM perspective_profiles WHERE id = ?", (profile_id,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE perspective_profiles
                SET name = ?, profile_json = ?, origin = 'custom', updated_at = ?, status = 'active'
                WHERE id = ?
                """,
                (name, profile_json, now, profile_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO perspective_profiles (id, name, profile_json, origin, created_at, updated_at, status)
                VALUES (?, ?, ?, 'custom', ?, ?, 'active')
                """,
                (profile_id, name, profile_json, now, now),
            )
        conn.commit()
    return next(item for item in list_perspective_profiles() if item["id"] == profile_id)


def delete_perspective_profile(profile_id: str) -> dict[str, Any]:
    init_storage()
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        row = conn.execute("SELECT * FROM perspective_profiles WHERE id = ?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(f"Perspective profile {profile_id} not found")
        conn.execute(
            """
            UPDATE perspective_profiles
            SET status = 'deleted', updated_at = ?
            WHERE id = ?
            """,
            (now, profile_id),
        )
        conn.commit()
    item = row_to_dict(row) or {}
    item["status"] = "deleted"
    return item


def read_markdown_for_ids(ids: list[int]) -> list[tuple[dict[str, Any], str]]:
    results: list[tuple[dict[str, Any], str]] = []
    for entry_id in ids:
        item = get_knowledge_entry(entry_id)
        path = resolve_root_path(item.get("markdown_path"))
        if not path or not path.exists():
            raise FileNotFoundError(f"知识文件不存在：{entry_id}")
        results.append((item, path.read_text(encoding="utf-8")))
    return results


def remove_empty_file(path: Path) -> None:
    try:
        if path.exists() and path.is_file() and path.stat().st_size == 0:
            path.unlink()
    except OSError:
        pass


def copy_into_workspace(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
