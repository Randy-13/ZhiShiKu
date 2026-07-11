from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
from openai import OpenAI

import asr_settings


def transcribe_audio(path: Path, provider: str = "local") -> str:
    setting = asr_settings.active_setting()
    provider = (provider if provider != "local" else setting.get("provider") or "").lower()
    if provider == "local":
        text = transcribe_with_local_whisper(path, setting)
        asr_settings.mark_test_result(True, "最近一次本地语音转写成功。")
        return text
    if provider in {"openai", "compatible", "minimax"}:
        text = transcribe_with_openai_compatible(path, setting)
        asr_settings.mark_test_result(True, "最近一次语音转写成功。")
        return text
    if provider == "dashscope":
        raise RuntimeError(
            "当前激活的 DashScope Fun-ASR 只能转写公网可访问的 HTTP/HTTPS 音频 URL，不能直接读取本地上传文件。"
            "请在设置中心切换到本地 Whisper、OpenAI-compatible 或 MiniMax ASR 后重试，或上传字幕文件。"
        )
    raise RuntimeError(
        "ASR is not configured yet. Configure ASR API settings on the media page or upload a subtitle file."
    )


def transcribe_with_local_whisper(path: Path, setting: dict) -> str:
    if importlib.util.find_spec("whisper") is None:
        raise RuntimeError(
            "本地 ASR 需要安装 openai-whisper。当前环境已找到 ffmpeg，但未找到 whisper 包；"
            "请在项目虚拟环境安装 openai-whisper，或切换到 OpenAI-compatible / MiniMax ASR。"
        )
    command = [
        sys.executable,
        "-c",
        (
            "import json, sys, whisper; "
            "model = whisper.load_model(sys.argv[2]); "
            "result = model.transcribe(sys.argv[1], language=sys.argv[3] or None, fp16=False); "
            "print(json.dumps({'text': result.get('text', '')}, ensure_ascii=False))"
        ),
        str(path),
        str(setting.get("model") or "base"),
        str(setting.get("language") or "zh"),
    ]
    env = None
    ffmpeg_dir = local_ffmpeg_dir()
    if ffmpeg_dir:
        env = dict(os.environ)
        env["PATH"] = str(ffmpeg_dir) + os.pathsep + env.get("PATH", "")
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=float(setting.get("timeout") or 1800),
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"本地 Whisper 转写失败：{message[-1000:]}")
    try:
        data = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"本地 Whisper 没有返回可读结果：{completed.stdout[-1000:]}") from exc
    text = str(data.get("text") or "").strip()
    if not text:
        raise RuntimeError("本地 Whisper 转写完成，但没有识别到文字。")
    return text


def local_ffmpeg_dir() -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return Path(ffmpeg).resolve().parent
    candidate = Path.home() / ".agent-reach" / "tools" / "ffmpeg" / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
    if candidate.exists():
        return candidate.parent
    return None


def transcribe_with_openai_compatible(path: Path, setting: dict) -> str:
    client = OpenAI(
        api_key=setting["api_key"],
        base_url=setting["base_url"],
        timeout=float(setting.get("timeout") or 300),
    )
    with path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=setting["model"],
            file=audio_file,
            response_format="text",
        )
    return str(result).strip()


def transcribe_audio_url(audio_url: str, setting: dict | None = None) -> str:
    setting = setting or asr_settings.active_setting()
    provider = (setting.get("provider") or "").lower()
    if provider not in {"dashscope", "openai", "compatible", "minimax"}:
        raise RuntimeError("ASR provider is not configured.")
    if provider in {"openai", "compatible", "minimax"}:
        raise RuntimeError(
            "OpenAI-compatible and MiniMax ASR only accept local audio files in this app. "
            "Download the audio first or switch to DashScope for remote file URLs."
        )
    task_id = submit_dashscope_task(audio_url, setting)
    result = poll_dashscope_task(task_id, setting)
    text = extract_dashscope_text(result)
    asr_settings.mark_test_result(True, "最近一次语音转写成功。")
    return text


def submit_dashscope_task(audio_url: str, setting: dict) -> str:
    url = f"{setting['base_url'].rstrip('/')}/services/audio/asr/transcription"
    payload = {
        "model": setting["model"],
        "input": {
            "file_urls": [audio_url],
        },
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {setting['api_key']}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        json=payload,
        timeout=float(setting.get("timeout") or 300),
    )
    if not response.ok:
        raise RuntimeError(extract_http_error(response))
    data = response.json()
    task_id = data.get("output", {}).get("task_id") or data.get("task_id")
    if not task_id:
        raise RuntimeError(f"DashScope did not return a task_id: {json.dumps(data, ensure_ascii=False)}")
    return str(task_id)


def poll_dashscope_task(task_id: str, setting: dict) -> dict:
    url = f"{setting['base_url'].rstrip('/')}/tasks/{task_id}"
    deadline = time.time() + float(setting.get("timeout") or 300)
    while time.time() < deadline:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {setting['api_key']}"},
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(extract_http_error(response))
        data = response.json()
        status = str(data.get("output", {}).get("task_status") or data.get("task_status") or "").lower()
        if status in {"succeeded", "success", "done", "completed"}:
            return data
        if status in {"failed", "canceled", "cancelled"}:
            raise RuntimeError(extract_dashscope_error(data))
        time.sleep(3)
    raise RuntimeError("DashScope ASR timed out while waiting for the transcription result.")


def extract_dashscope_text(data: dict) -> str:
    output = data.get("output", {})
    texts: list[str] = []
    for result in output.get("results", []) or []:
        url = result.get("transcription_url")
        if not url:
            continue
        response = requests.get(url, timeout=60)
        if not response.ok:
            raise RuntimeError(extract_http_error(response))
        transcript_json = response.json()
        texts.extend(extract_transcription_texts(transcript_json))
    if texts:
        return "\n".join(texts).strip()
    if isinstance(output.get("transcription"), dict):
        transcription = output["transcription"]
        if transcription.get("text"):
            return str(transcription["text"]).strip()
        if transcription.get("result"):
            return str(transcription["result"]).strip()
    if output.get("text"):
        return str(output["text"]).strip()
    if output.get("result"):
        return str(output["result"]).strip()
    if data.get("text"):
        return str(data["text"]).strip()
    raise RuntimeError("DashScope ASR succeeded, but the transcription result did not contain readable text.")


def extract_transcription_texts(payload: dict) -> list[str]:
    texts: list[str] = []
    collect_text_fields(payload, texts)
    if texts:
        return normalize_texts(texts)
    for transcript in payload.get("transcripts", []) or []:
        collect_text_fields(transcript, texts)
        for sentence in transcript.get("sentences", []) or []:
            collect_text_fields(sentence, texts)
        for word in transcript.get("words", []) or []:
            collect_text_fields(word, texts)
    for sentence in payload.get("sentences", []) or []:
        collect_text_fields(sentence, texts)
    for sentence in payload.get("sentence_info", []) or []:
        collect_text_fields(sentence, texts)
    for word in payload.get("words", []) or []:
        collect_text_fields(word, texts)
    if texts:
        return normalize_texts(texts)
    for key in ("transcript", "transcription", "result"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested: list[str] = []
            collect_text_fields(value, nested)
            if nested:
                return normalize_texts(nested)
    return []


def collect_text_fields(value: dict, texts: list[str]) -> None:
    for key in ("content", "text", "sentence", "transcript", "transcription", "result"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())


def normalize_texts(texts: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for text in texts:
        text = " ".join(str(text).split())
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    if len(cleaned) > 1:
        whole = max(cleaned, key=len)
        fragments = [item for item in cleaned if item != whole and item in whole]
        if fragments:
            cleaned = [item for item in cleaned if item not in fragments]
    return cleaned


def extract_dashscope_error(data: dict) -> str:
    output = data.get("output", {})
    for key in ("message", "error_message", "error"):
        value = output.get(key) or data.get(key)
        if value:
            return str(value)
    return json.dumps(data, ensure_ascii=False)


def extract_http_error(response: requests.Response) -> str:
    try:
        data = response.json()
        message = data.get("message") or data.get("error") or data
    except Exception:
        message = response.text
    return f"ASR request failed: {response.status_code} {message}"


def asr_status() -> dict:
    return asr_settings.status_payload()
