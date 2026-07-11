from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import Any, Callable

import api_settings
import asr_settings
import image_api_settings


def save_list_setting(manager, payload: dict[str, object]) -> dict[str, object]:
    item = manager.save_setting(payload)
    return {"item": item, **manager.list_payload()}


def activate_list_setting(manager, setting_id: str) -> dict[str, object]:
    item = manager.set_active(setting_id)
    return {"item": item, **manager.list_payload()}


def delete_list_setting(manager, setting_id: str) -> dict[str, object]:
    manager.delete_setting(setting_id)
    return manager.list_payload()


def resolve_api_test_setting(
    request,
    *,
    not_found_message: str = "API setting not found",
) -> dict[str, object]:
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
            "protocol": payload.get("protocol") or "",
            "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
            "model": (payload.get("model") or "").strip(),
            "api_key": (payload.get("api_key") or "").strip(),
            "timeout": payload.get("timeout") or 60,
            "max_retries": payload.get("max_retries") or 0,
        }
    if request.id:
        setting = api_settings.get_setting(request.id)
        if setting is None:
            raise KeyError(not_found_message)
        return setting
    return api_settings.active_setting()


def resolve_image_api_test_setting(
    request,
    *,
    not_found_message: str = "Image API setting not found",
) -> dict[str, object]:
    if request.setting:
        payload = request.setting.model_dump()
        if payload.get("id") and not payload.get("api_key"):
            existing = image_api_settings.get_setting(payload["id"])
            if existing:
                payload["api_key"] = existing.get("api_key")
        return {
            "id": payload.get("id") or "temporary",
            "name": payload.get("name") or "临时图片 API",
            "provider": payload.get("provider") or "compatible",
            "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
            "model": (payload.get("model") or "").strip(),
            "api_key": (payload.get("api_key") or "").strip(),
            "size": (payload.get("size") or "1024x1024").strip(),
            "quality": (payload.get("quality") or "auto").strip(),
            "aspect_ratio": (payload.get("aspect_ratio") or "").strip(),
            "response_format": (payload.get("response_format") or "").strip(),
            "timeout": payload.get("timeout") or 120,
        }
    if request.id:
        setting = image_api_settings.get_setting(request.id)
        if setting is None:
            raise KeyError(not_found_message)
        return setting
    return image_api_settings.active_setting()


def resolve_asr_test_setting(payload: dict[str, object]) -> dict[str, object]:
    nested = payload.get("setting")
    if isinstance(nested, dict):
        resolved = dict(nested)
        if resolved.get("id") and not resolved.get("api_key"):
            existing = asr_settings.get_setting(str(resolved["id"]))
            if existing:
                resolved["api_key"] = existing.get("api_key")
        return resolved
    setting_id = payload.get("id")
    has_inline_fields = any(payload.get(key) for key in ("base_url", "model", "api_key", "name"))
    if setting_id and not has_inline_fields:
        setting = asr_settings.get_setting(str(setting_id))
        if setting is None:
            raise ValueError("ASR setting not found")
        return setting
    resolved = dict(payload)
    if resolved.get("id") and not resolved.get("api_key"):
        existing = asr_settings.get_setting(str(resolved["id"]))
        if existing:
            resolved["api_key"] = existing.get("api_key")
    return resolved


def test_asr_setting_payload(
    payload: dict[str, object],
    *,
    transcribe_audio_url_fn: Callable[[str, dict[str, Any]], object],
    transcribe_audio_fn: Callable[[Path], object] | None = None,
) -> dict[str, object]:
    payload = resolve_asr_test_setting(payload)
    if payload.get("provider") != "local" and not payload.get("api_key"):
        payload["api_key"] = asr_settings.load_setting().get("api_key")
    saved = asr_settings.save_setting(payload)
    setting = asr_settings.active_setting()
    if setting.get("provider") == "dashscope":
        sample_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/paraformer/hello_world_female2.wav"
        transcribe_audio_url_fn(sample_url, setting)
    elif setting.get("provider") in {"minimax", "local"}:
        if transcribe_audio_fn is None:
            raise RuntimeError("This ASR provider requires a local audio transcription probe.")
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_path = Path(temp_dir) / "asr_probe.wav"
            _write_silent_wav(sample_path)
            try:
                transcribe_audio_fn(sample_path)
            except RuntimeError as exc:
                if setting.get("provider") != "local" or "没有识别到文字" not in str(exc):
                    raise
    asr_settings.mark_test_result(True, "ASR API verified with a real transcription request.")
    return {
        "ok": True,
        "item": saved,
        "message": "ASR API verified with a real transcription request.",
    }


def _write_silent_wav(path: Path) -> None:
    sample_rate = 16_000
    duration_seconds = 1
    frame_count = sample_rate * duration_seconds
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
