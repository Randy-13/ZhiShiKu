from __future__ import annotations

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
            "response_format": (payload.get("response_format") or "").strip(),
            "timeout": payload.get("timeout") or 120,
        }
    if request.id:
        setting = image_api_settings.get_setting(request.id)
        if setting is None:
            raise KeyError(not_found_message)
        return setting
    return image_api_settings.active_setting()


def test_asr_setting_payload(
    payload: dict[str, object],
    *,
    transcribe_audio_url_fn: Callable[[str, dict[str, Any]], object],
) -> dict[str, object]:
    if not payload.get("api_key"):
        payload["api_key"] = asr_settings.load_setting().get("api_key")
    saved = asr_settings.save_setting(payload)
    setting = asr_settings.active_setting()
    if setting.get("provider") == "dashscope":
        sample_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/paraformer/hello_world_female2.wav"
        transcribe_audio_url_fn(sample_url, setting)
    asr_settings.mark_test_result(True, "ASR API verified with a real transcription request.")
    return {
        "ok": True,
        "item": saved,
        "message": "ASR API verified with a real transcription request.",
    }
