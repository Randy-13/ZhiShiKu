from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import asr_settings
import storage
from media_transcriber import asr_status, transcribe_audio, transcribe_audio_url


SUPPORTED_PLATFORMS = {"bilibili", "douyin", "wechat_channels", "local"}
SUBTITLE_SUFFIXES = {".srt", ".vtt", ".ass"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".flac"}
YTDLP_COOKIES_FILE_ENV = "FIGURELEARNING_YTDLP_COOKIES_FILE"
YTDLP_COOKIES_FROM_BROWSER_ENV = "FIGURELEARNING_YTDLP_COOKIES_FROM_BROWSER"
REQUIRED_BILIBILI_COOKIE_NAMES = ("SESSDATA", "DedeUserID", "bili_jct")


@dataclass(frozen=True)
class YtDlpAuthState:
    mode: str
    value: str = ""
    exists: bool = False
    source: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.value)


def ytdlp_command() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    script_path = Path(sys.executable).resolve().parent / ("yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp")
    if script_path.exists():
        return [str(script_path)]
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode == 0:
            return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        return None
    return None


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def ytdlp_cookie_file_candidates() -> list[Path]:
    candidates = [
        storage.ROOT / "auth" / "bilibili.cookies.txt",
        storage.STORAGE_ROOT / "auth" / "bilibili.cookies.txt",
        Path.cwd() / "auth" / "bilibili.cookies.txt",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve() if _path_exists(candidate.parent) else candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def ytdlp_cookie_source() -> str:
    cookies_file = os.getenv(YTDLP_COOKIES_FILE_ENV, "").strip()
    if cookies_file:
        return cookies_file
    for candidate in ytdlp_cookie_file_candidates():
        if _path_exists(candidate):
            return str(candidate)
    return ""


def ytdlp_auth_state() -> YtDlpAuthState:
    explicit_file = os.getenv(YTDLP_COOKIES_FILE_ENV, "").strip()
    if explicit_file:
        return YtDlpAuthState("file", explicit_file, _path_exists(Path(explicit_file)), YTDLP_COOKIES_FILE_ENV)
    cookies_browser = os.getenv(YTDLP_COOKIES_FROM_BROWSER_ENV, "").strip()
    if cookies_browser:
        return YtDlpAuthState("browser", cookies_browser, True, YTDLP_COOKIES_FROM_BROWSER_ENV)
    default_file = ytdlp_cookie_source()
    if default_file:
        return YtDlpAuthState("file", default_file, _path_exists(Path(default_file)), "auth/bilibili.cookies.txt")
    return YtDlpAuthState("none")


def ytdlp_auth_args(cookies_file: str | None = None) -> list[str]:
    if cookies_file:
        return ["--cookies", cookies_file]
    explicit_file = os.getenv(YTDLP_COOKIES_FILE_ENV, "").strip()
    if explicit_file:
        return ["--cookies", explicit_file]
    cookies_browser = os.getenv(YTDLP_COOKIES_FROM_BROWSER_ENV, "").strip()
    if cookies_browser:
        return ["--cookies-from-browser", cookies_browser]
    cookies_file = ytdlp_cookie_source()
    if cookies_file:
        return ["--cookies", cookies_file]
    return []


def parse_netscape_cookies(path: Path) -> list[dict[str, object]]:
    cookies: list[dict[str, object]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        expiry = 0
        try:
            expiry = int(float(parts[4] or 0))
        except ValueError:
            expiry = 0
        cookies.append(
            {
                "domain": parts[0],
                "path": parts[2],
                "secure": parts[3].upper() == "TRUE",
                "expires": expiry,
                "name": parts[5],
            }
        )
    return cookies


def bilibili_cookie_status() -> dict[str, object]:
    auth_state = ytdlp_auth_state()
    path = Path(auth_state.value) if auth_state.mode == "file" and auth_state.value else None
    result: dict[str, object] = {
        "mode": auth_state.mode,
        "source": auth_state.source,
        "path": str(path) if path else "",
        "exists": bool(path and _path_exists(path)),
        "ok": False,
        "message": "",
        "missing": list(REQUIRED_BILIBILI_COOKIE_NAMES),
        "cookie_count": 0,
        "last_modified": "",
    }
    if auth_state.mode == "browser":
        result.update(
            {
                "message": f"Configured to read cookies from browser source: {auth_state.value}. Export to a file for stable Bilibili subtitle extraction.",
                "missing": [],
            }
        )
        return result
    if not path:
        result["message"] = "Bilibili cookies are not configured."
        return result
    if not _path_exists(path):
        result["message"] = f"Bilibili cookie file was not found: {path}"
        return result

    stat = path.stat()
    cookies = parse_netscape_cookies(path)
    now = int(time.time())
    active_names = {
        str(cookie["name"])
        for cookie in cookies
        if "bilibili.com" in str(cookie.get("domain") or "")
        and (int(cookie.get("expires") or 0) == 0 or int(cookie.get("expires") or 0) > now)
    }
    missing = [name for name in REQUIRED_BILIBILI_COOKIE_NAMES if name not in active_names]
    result.update(
        {
            "cookie_count": len(cookies),
            "missing": missing,
            "last_modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            "ok": not missing,
        }
    )
    if missing:
        result["message"] = f"Bilibili cookie file is missing required login keys: {', '.join(missing)}."
    else:
        result["message"] = "Bilibili cookie file looks valid. Subtitle extraction can use this file."
    return result


def launch_bilibili_cookie_login(url: str | None = None) -> dict[str, object]:
    script = storage.ROOT / "export_bilibili_cookies_with_edge.bat"
    if not script.exists():
        raise FileNotFoundError(f"Cookie export script was not found: {script}")
    env = os.environ.copy()
    if url:
        env["BILIBILI_COOKIE_EXPORT_URL"] = url
    creationflags = subprocess.CREATE_NEW_CONSOLE if sys.platform.startswith("win") else 0
    command = ["cmd.exe", "/c", str(script)] if sys.platform.startswith("win") else [str(script)]
    subprocess.Popen(command, cwd=str(storage.ROOT), env=env, creationflags=creationflags)
    return {"ok": True, "message": "Opened Edge login window for Bilibili cookie export.", "script": str(script)}


def ytdlp_auth_attempts(cookies_file: str | None = None) -> list[tuple[YtDlpAuthState, list[str]]]:
    attempts: list[tuple[YtDlpAuthState, list[str]]] = []
    explicit_file = os.getenv(YTDLP_COOKIES_FILE_ENV, "").strip()
    cookies_browser = os.getenv(YTDLP_COOKIES_FROM_BROWSER_ENV, "").strip()
    if cookies_file:
        attempts.append((YtDlpAuthState("file", cookies_file, _path_exists(Path(cookies_file)), "temporary cookies"), ["--cookies", cookies_file]))
    elif explicit_file:
        attempts.append((YtDlpAuthState("file", explicit_file, _path_exists(Path(explicit_file)), YTDLP_COOKIES_FILE_ENV), ["--cookies", explicit_file]))
    if cookies_browser:
        attempts.append((YtDlpAuthState("browser", cookies_browser, True, YTDLP_COOKIES_FROM_BROWSER_ENV), ["--cookies-from-browser", cookies_browser]))
    default_file = ytdlp_cookie_source()
    if default_file and default_file not in {cookies_file, explicit_file}:
        attempts.append((YtDlpAuthState("file", default_file, _path_exists(Path(default_file)), "auth/bilibili.cookies.txt"), ["--cookies", default_file]))
    if not attempts:
        attempts.append((YtDlpAuthState("none"), []))
    return attempts




def ffmpeg_command() -> str | None:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return str(bundled)
    except Exception:
        return None
    return None


def dependency_status() -> dict[str, object]:
    ytdlp = ytdlp_command()
    ffmpeg = ffmpeg_command()
    auth_state = ytdlp_auth_state()
    if auth_state.mode == "file" and auth_state.exists:
        auth_detail = f"已配置登录 Cookie：{auth_state.value}"
    elif auth_state.mode == "file":
        auth_detail = f"已配置登录 Cookie，但文件不存在：{auth_state.value}"
    elif auth_state.mode == "browser":
        auth_detail = f"已配置从浏览器读取 Cookie：{auth_state.value}"
    else:
        auth_detail = "未配置登录 Cookie"
    return {
        "bilibili_subtitle": {
            "label": "B\u7ad9\u5b57\u5e55\u83b7\u53d6",
            "available": ytdlp is not None,
            "purpose": "\u7528\u4e8e\u89e3\u6790 Bilibili \u94fe\u63a5\uff0c\u8bfb\u53d6\u5b98\u65b9\u5b57\u5e55\u6216\u81ea\u52a8\u5b57\u5e55\u3002",
            "detail": "\u5df2\u627e\u5230\u89c6\u9891\u4e0b\u8f7d\u5de5\u5177\u3002" if ytdlp else "\u672a\u627e\u5230\u89c6\u9891\u4e0b\u8f7d\u5de5\u5177\uff0c\u8bf7\u5b89\u88c5 yt-dlp\u3002",
            "auth": auth_detail,
        },
        "local_audio_extract": {
            "label": "\u672c\u5730\u89c6\u9891\u8f6c\u97f3\u9891",
            "available": ffmpeg is not None,
            "purpose": "\u7528\u4e8e\u628a\u672c\u5730 mp4/webm/mov \u7b49\u89c6\u9891\u8f6c\u6210\u97f3\u9891\u540e\u518d\u8bc6\u522b\u3002",
            "detail": f"\u5df2\u627e\u5230\u8f6c\u97f3\u9891\u5de5\u5177\uff1a{ffmpeg}" if ffmpeg else "\u672a\u627e\u5230 ffmpeg\uff0c\u672c\u5730\u89c6\u9891\u62bd\u97f3\u9891\u4e0d\u53ef\u7528\u3002",
        },
        "speech_to_text": {
            "label": "AI \u8bed\u97f3\u8f6c\u6587\u5b57",
            **asr_status(),
        },
    }


@dataclass
class ResolvedMedia:
    platform: str
    source_url: str
    canonical_url: str
    title: str | None = None
    duration_seconds: float | None = None
    status: str = "resolved"
    error_message: str | None = None
    metadata: dict | None = None


def identify_platform(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    if "channels.weixin.qq.com" in host or "weixin.qq.com" in host or "wechat" in host:
        return "wechat_channels"
    raise ValueError("Only Bilibili, Douyin, and WeChat Channels links are supported in this version.")


def resolve_url(url: str) -> ResolvedMedia:
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")
    platform = identify_platform(url)
    if platform == "bilibili":
        return resolve_bilibili_url(url)
    if platform == "douyin":
        return resolve_douyin_url(url)
    return ResolvedMedia(
        platform="wechat_channels",
        source_url=url,
        canonical_url=url,
        title="WeChat Channels link",
        status="needs_local_file",
        error_message="WeChat Channels direct link capture is not available in v1. Please upload a saved video or audio file.",
    )


def resolve_bilibili_url(url: str) -> ResolvedMedia:
    parsed = urlparse(url)
    match = re.search(r"/video/([^/?#]+)", parsed.path)
    video_id = match.group(1) if match else parsed.path.strip("/")
    query = parse_qs(parsed.query)
    start = query.get("t", [None])[0]
    canonical_url = f"https://www.bilibili.com/video/{video_id}" if video_id else url
    if start:
        canonical_url = f"{canonical_url}?t={start}"
    title = f"Bilibili {video_id}" if video_id else "Bilibili video"
    metadata = {"video_id": video_id, "start_seconds": start}
    info = ytdlp_dump_json(url)
    if info:
        title = info.get("title") or title
        duration = info.get("duration")
        canonical_url = info.get("webpage_url") or canonical_url
        return ResolvedMedia("bilibili", url, canonical_url, title, duration, metadata={"video_id": video_id, "start_seconds": start})
    return ResolvedMedia("bilibili", url, canonical_url, title, metadata=metadata)


def resolve_douyin_url(url: str) -> ResolvedMedia:
    canonical_url = follow_redirect(url)
    video_id = extract_douyin_video_id(canonical_url) or extract_douyin_video_id(url)
    title = f"Douyin {video_id}" if video_id else "Douyin video"
    duration = None
    if video_id:
        cached = douyin_detail_from_video_id(video_id)
        if cached:
            title = cached.get("desc") or cached.get("item_title") or title
            duration_value = cached.get("duration")
            if duration_value:
                try:
                    duration = float(duration_value) / 1000 if float(duration_value) > 1000 else float(duration_value)
                except (TypeError, ValueError):
                    duration = None
    status = "resolved" if video_id else "needs_local_file"
    error = None if video_id else "Could not identify a Douyin video id. Please upload the local video or audio file."
    return ResolvedMedia(
        "douyin",
        url,
        canonical_url,
        title,
        duration,
        status=status,
        error_message=error,
        metadata={"video_id": video_id},
    )


def follow_redirect(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=12) as response:
            return response.geturl()
    except Exception:
        return url


def extract_douyin_video_id(url: str) -> str | None:
    patterns = [
        r"/share/video/(\d+)",
        r"/video/(\d+)",
        r"modal_id=(\d+)",
        r"aweme_id=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def ytdlp_dump_json(url: str) -> dict | None:
    command = ytdlp_command()
    if not command:
        return None
    with temporary_ytdlp_cookies() as cookie_file:
        completed = subprocess.run(
            [*command, *ytdlp_auth_args(cookie_file), "--dump-json", "--skip-download", "--no-warnings", url],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=45,
            check=False,
        )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return None


def ensure_transcript(item: dict) -> tuple[str, str]:
    existing_path = storage.resolve_root_path(item.get("transcript_path"))
    if existing_path and existing_path.exists():
        return existing_path.read_text(encoding="utf-8", errors="ignore"), str(item.get("transcript_kind") or "none")

    file_path = storage.resolve_root_path(item.get("file_path"))
    suffix = file_path.suffix.lower() if file_path else ""
    if suffix in SUBTITLE_SUFFIXES and file_path:
        text = transcript_from_subtitle_file(item, file_path)
        return text, "uploaded_subtitle"

    if item.get("source_kind") == "local_file" and file_path:
        return transcript_from_local_media(file_path)

    if item.get("platform") == "bilibili" and item.get("source_url"):
        text = transcript_from_bilibili(item)
        if text:
            return text, "platform_subtitle"
    if item.get("platform") == "douyin" and item.get("source_url"):
        text = transcript_from_douyin(item)
        if text:
            return text, "asr"

    if file_path:
        return transcript_from_local_media(file_path)

    raise RuntimeError(
        "No transcript is available. For WeChat Channels v1, upload a local media file or subtitle file."
    )


def transcript_from_local_media(file_path: Path) -> tuple[str, str]:
    suffix = file_path.suffix.lower()
    if suffix in AUDIO_SUFFIXES:
        return transcribe_audio(file_path), "asr"
    if suffix in VIDEO_SUFFIXES:
        audio_path = extract_audio(file_path)
        return transcribe_audio(audio_path), "asr"
    raise RuntimeError("Unsupported local media type. Upload audio, video, or subtitle files.")


def transcript_from_subtitle_file(item: dict, path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    transcript = parse_subtitle(raw, path.suffix.lower())
    write_transcript(item, transcript, "uploaded_subtitle")
    return transcript


def transcript_from_bilibili(item: dict) -> str:
    command = ytdlp_command()
    if not command:
        raise RuntimeError("yt-dlp is not installed. Install yt-dlp or upload a subtitle/local media file.")
    url = str(item.get("source_url") or item.get("canonical_url") or "")
    stderr = ""
    auth_state = ytdlp_auth_state()
    with tempfile.TemporaryDirectory() as temp_dir, temporary_ytdlp_cookies() as cookie_file:
        output = str(Path(temp_dir) / "subtitle.%(ext)s")
        completed = subprocess.run(
            [
                *command,
                *ytdlp_auth_args(cookie_file),
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                "ai-zh,zh-Hans,zh-CN,zh",
                "--sub-format",
                "vtt/srt/ass/best",
                "-o",
                output,
                url,
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=90,
            check=False,
        )
        stderr = completed.stderr
        subtitle_files = sorted(Path(temp_dir).glob("subtitle*"))
        for subtitle in candidate_subtitle_files(subtitle_files):
            raw = subtitle.read_text(encoding="utf-8", errors="ignore")
            if looks_like_failed_subtitle(raw):
                continue
            transcript = parse_subtitle(raw, subtitle.suffix.lower())
            if transcript:
                write_transcript(item, transcript, "platform_subtitle")
                return transcript
    raise RuntimeError(explain_bilibili_subtitle_error(stderr, auth_state))


def transcript_from_douyin(item: dict) -> str:
    detail = douyin_detail_from_cache(item)
    if not detail:
        raise RuntimeError(
            "Douyin full subtitles are not exposed by this page. Open the Douyin video in the browser first, "
            "then import the captured aweme/detail JSON, or configure ASR and provide a downloadable audio URL."
        )
    subtitle = extract_douyin_platform_subtitle(detail)
    if subtitle:
        write_transcript(item, subtitle, "platform_subtitle")
        return subtitle
    audio_url = extract_douyin_audio_url(detail)
    if not audio_url:
        raise RuntimeError("Douyin detail JSON did not contain a downloadable audio URL.")
    provider = (asr_settings.load_setting().get("provider") or "").lower()
    if provider == "dashscope":
        transcript = transcribe_audio_url(audio_url)
    else:
        audio_path = download_douyin_audio(item, audio_url)
        transcript = transcribe_audio(audio_path)
    write_transcript(item, transcript, "asr")
    return transcript


def douyin_detail_from_cache(item: dict) -> dict | None:
    video_id = extract_douyin_video_id(str(item.get("canonical_url") or item.get("source_url") or ""))
    if not video_id:
        return None
    return douyin_detail_from_video_id(video_id)


def douyin_detail_from_video_id(video_id: str) -> dict | None:
    cache_dir = storage.MEDIA_DIR / "douyin_detail"
    candidates = [
        cache_dir / f"{video_id}.json",
        storage.ROOT / "auth" / f"douyin-{video_id}.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("aweme_detail") if isinstance(payload.get("aweme_detail"), dict) else payload
    return None


def extract_douyin_platform_subtitle(detail: dict) -> str:
    # Real subtitle fields vary by rollout. Chapter recommendations are intentionally excluded.
    candidates = []
    for key in ("video_text", "caption_list", "subtitle_list", "subtitles"):
        value = detail.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    rows: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or item.get("sentence") or "").strip()
        if not text:
            continue
        start = format_milliseconds(item.get("start") or item.get("start_time") or item.get("from"))
        end = format_milliseconds(item.get("end") or item.get("end_time") or item.get("to"))
        rows.append(f"[{start} - {end}] {text}")
    return "\n".join(rows).strip()


def extract_douyin_audio_url(detail: dict) -> str | None:
    urls = []
    video = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    for path in (
        ("play_addr", "url_list"),
        ("play_addr_h264", "url_list"),
        ("download_addr", "url_list"),
    ):
        node = video
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, list):
            urls.extend(str(url) for url in node if url)
    music = detail.get("music") if isinstance(detail.get("music"), dict) else {}
    play_url = music.get("play_url") if isinstance(music.get("play_url"), dict) else {}
    if isinstance(play_url.get("url_list"), list):
        urls.extend(str(url) for url in play_url["url_list"] if url)
    audio_like = [url for url in urls if "media-audio" in url or ".mp3" in url or "music" in url]
    return (audio_like or urls or [None])[0]


def download_douyin_audio(item: dict, audio_url: str) -> Path:
    media_id = int(item["id"])
    target_dir = storage.MEDIA_DIR / "douyin_audio"
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".mp3" if ".mp3" in audio_url.lower() else ".mp4"
    target = target_dir / f"douyin_{media_id}{suffix}"
    request = Request(audio_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.douyin.com/"})
    with urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())
    storage.update_media_source(media_id, file_path=storage.storage_relative(target), content_type="audio/mp4")
    return target


def format_milliseconds(value: object) -> str:
    try:
        total = int(float(value or 0))
    except (TypeError, ValueError):
        total = 0
    if total > 1000:
        total = total // 1000
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def candidate_subtitle_files(paths: list[Path]) -> list[Path]:
    priority = {".srt": 0, ".vtt": 1, ".ass": 2}
    files = [
        path
        for path in paths
        if path.suffix.lower() in SUBTITLE_SUFFIXES and path.exists() and path.stat().st_size > 0
    ]
    return sorted(files, key=lambda path: (priority.get(path.suffix.lower(), 9), path.name))


def looks_like_failed_subtitle(raw: str) -> bool:
    stripped = raw.strip().lower()
    if not stripped:
        return True
    failure_markers = ("not found", "404", "<html", "<!doctype html")
    return any(marker in stripped[:500] for marker in failure_markers)


def explain_bilibili_subtitle_error(stderr: str | None = None, auth_state: YtDlpAuthState | None = None) -> str:
    stderr = (stderr or "").strip()
    auth_state = auth_state or ytdlp_auth_state()
    if "Subtitles are only available when logged in" in stderr:
        if auth_state.mode == "file" and auth_state.exists:
            return (
                "Bilibili says subtitles require valid login cookies, but the configured cookies were not accepted: "
                f"{auth_state.value}. Refresh this file with tools/browser_state_to_netscape_cookies.py, "
                "or upload a subtitle/local media file."
            )
        if auth_state.mode == "file":
            return (
                "Bilibili says subtitles require login cookies, but the configured cookie file was not found: "
                f"{auth_state.value}. Recreate it with tools/browser_state_to_netscape_cookies.py, "
                f"or set {YTDLP_COOKIES_FILE_ENV} to an existing Netscape cookies file."
            )
        if auth_state.mode == "browser":
            return (
                "Bilibili says subtitles require valid login cookies, but yt-dlp could not use the configured browser "
                f"cookie source: {auth_state.value}. Export fresh cookies with tools/browser_state_to_netscape_cookies.py, "
                "or upload a subtitle/local media file."
            )
        return (
            "Bilibili says subtitles require login cookies. Export browser login cookies with "
            "tools/browser_state_to_netscape_cookies.py to auth/bilibili.cookies.txt, set "
            f"{YTDLP_COOKIES_FILE_ENV} or {YTDLP_COOKIES_FROM_BROWSER_ENV}, or upload a subtitle/local media file."
        )
    if stderr:
        return f"No Bilibili subtitle was found. yt-dlp said: {stderr[-800:]}"
    return (
        "No downloadable Bilibili subtitle track was found. The visible text may be hard-burned into the video. "
        "Use Bilibili login cookies, upload a subtitle file, or configure ASR/OCR fallback."
    )


class temporary_ytdlp_cookies:
    def __init__(self) -> None:
        self.source = ytdlp_cookie_source()
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.path: str | None = None

    def __enter__(self) -> str | None:
        if not self.source:
            return None
        source_path = Path(self.source)
        if not source_path.exists():
            return self.source
        self.temp_dir = tempfile.TemporaryDirectory()
        target = Path(self.temp_dir.name) / "cookies.txt"
        shutil.copyfile(source_path, target)
        self.path = str(target)
        return self.path

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.temp_dir:
            self.temp_dir.cleanup()


def write_transcript(item: dict, transcript: str, kind: str) -> Path:
    path = storage.media_transcript_path_for(int(item["id"]), str(item.get("title") or item.get("original_name") or "media"))
    path.write_text(to_readable_transcript(transcript), encoding="utf-8")
    storage.update_media_source(
        int(item["id"]),
        transcript_path=storage.storage_relative(path),
        transcript_kind=kind,
        status="transcribed",
        error_message=None,
    )
    return path


def to_readable_transcript(transcript: str) -> str:
    sentences: list[str] = []
    for line in transcript.splitlines():
        text = re.sub(r"^\[\d{2}:\d{2}:\d{2}\s+-\s+\d{2}:\d{2}:\d{2}\]\s*", "", line).strip()
        if text:
            sentences.append(text)
    article = " ".join(sentences)
    article = re.sub(r"\s+", " ", article).strip()
    article = re.sub(r"([。！？!?])\s+", r"\1\n\n", article)
    return article or transcript.strip()


def parse_subtitle(raw: str, suffix: str = ".srt") -> str:
    if suffix == ".ass":
        return parse_ass(raw)
    if suffix == ".vtt":
        raw = re.sub(r"^\ufeff?WEBVTT.*?(?:\n\n|\r\n\r\n)", "", raw, flags=re.S)
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    rows: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_line = next((line for line in lines if "-->" in line), "")
        if not time_line:
            continue
        start, end = normalize_time_range(time_line)
        text = " ".join(clean_subtitle_text(line) for line in lines if line != time_line and not line.isdigit())
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            rows.append(f"[{start} - {end}] {text}")
    return "\n".join(rows).strip()


def parse_ass(raw: str) -> str:
    rows: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        start = format_ass_time(parts[1])
        end = format_ass_time(parts[2])
        text = clean_subtitle_text(parts[9])
        if text:
            rows.append(f"[{start} - {end}] {text}")
    return "\n".join(rows).strip()


def normalize_time_range(line: str) -> tuple[str, str]:
    start, _, rest = line.partition("-->")
    end = rest.split()[0] if rest.split() else rest.strip()
    return format_subtitle_time(start.strip()), format_subtitle_time(end.strip())


def format_subtitle_time(value: str) -> str:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        parts = ["00", *parts]
    seconds = parts[-1].split(".")[0].zfill(2)
    return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{seconds}"


def format_ass_time(value: str) -> str:
    return format_subtitle_time(value.strip())


def clean_subtitle_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\{\\.*?\}", "", value)
    value = value.replace("\\N", " ")
    return value.strip()


def format_media_transcript(item: dict, transcript: str) -> str:
    duration = format_seconds(item.get("duration_seconds"))
    return "\n".join(
        [
            f"[Media: {item.get('title') or item.get('original_name') or 'Untitled media'}]",
            f"[Platform: {item.get('platform') or 'local'}]",
            f"[Source: {item.get('canonical_url') or item.get('source_url') or item.get('original_name') or ''}]",
            f"[Duration: {duration}]",
            f"[Transcript Source: {item.get('transcript_kind') or 'none'}]",
            "",
            transcript.strip(),
        ]
    ).strip()


def format_seconds(value: object) -> str:
    try:
        total = int(float(value or 0))
    except (TypeError, ValueError):
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def extract_audio(video_path: Path) -> Path:
    ffmpeg = ffmpeg_command()
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed. Install ffmpeg or upload an audio/subtitle file.")
    audio_path = video_path.with_suffix(".wav")
    completed = subprocess.run(
        [ffmpeg, "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed to extract audio.")
    return audio_path


def plan_segments(transcript: str, media_id: int, title: str, target_chars: int = 8000) -> list[dict]:
    lines = [line for line in transcript.splitlines() if line.strip()]
    if not lines:
        return []
    if not any(re.match(r"\[\d{2}:\d{2}:\d{2}\s+-\s+\d{2}:\d{2}:\d{2}\]", line) for line in lines):
        return plan_text_segments(transcript, media_id, title, target_chars)
    segments: list[dict] = []
    current: list[str] = []
    current_start = "00:00:00"
    index = 1
    for line in lines:
        time_match = re.match(r"\[(\d{2}:\d{2}:\d{2})\s+-\s+(\d{2}:\d{2}:\d{2})\]", line)
        if not current and time_match:
            current_start = time_match.group(1)
        current.append(line)
        current_chars = sum(len(item) for item in current)
        is_last = line == lines[-1]
        if current_chars >= target_chars or is_last:
            end = time_match.group(2) if time_match else current_start
            segments.append(
                {
                    "id": f"media-{media_id}-segment-{index}",
                    "media_id": media_id,
                    "title": f"{title[:30]} Part {index}",
                    "theme": f"{current_start}-{end} 的音视频核心内容",
                    "time_start": current_start,
                    "time_end": end,
                    "time_ranges": f"{current_start}-{end}",
                    "reason": "按时间轴和文本长度自动切分，避免长音视频一次性生成被截断。",
                    "estimated_chars": current_chars,
                    "selected": True,
                }
            )
            index += 1
            current = []
    return segments


def plan_text_segments(transcript: str, media_id: int, title: str, target_chars: int = 8000) -> list[dict]:
    text = re.sub(r"\s+", " ", transcript).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target_chars, len(text))
        if end < len(text):
            split_at = max(text.rfind(mark, start, end) for mark in ("。", "！", "？", ".", "!", "?"))
            if split_at > start + target_chars // 2:
                end = split_at + 1
        chunks.append(text[start:end].strip())
        start = end
    return [
        {
            "id": f"media-{media_id}-segment-{index}",
            "media_id": media_id,
            "title": f"{title[:30]} Part {index}",
            "theme": f"{title[:30]} 第 {index} 段核心内容",
            "time_start": None,
            "time_end": None,
            "time_ranges": f"文本段 {index}",
            "reason": "按整理后的字幕文章长度自动切分，避免长文本一次性生成被截断。",
            "estimated_chars": len(chunk),
            "text": chunk,
            "selected": True,
        }
        for index, chunk in enumerate(chunks, start=1)
    ]
