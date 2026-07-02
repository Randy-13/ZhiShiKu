from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import config
import storage


SETTINGS_PATH = storage.DATA_DIR / "asr_settings.json"

TEMPLATES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini-transcribe",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "dashscope",
        "name": "DashScope Fun-ASR",
        "provider": "dashscope",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "model": "paraformer-v2",
        "api_key_placeholder": "DASHSCOPE API key",
    },
    {
        "id": "compatible",
        "name": "OpenAI compatible",
        "provider": "compatible",
        "base_url": "https://your-relay.example.com/v1",
        "model": "whisper-1",
        "api_key_placeholder": "ASR API key",
    },
    {
        "id": "minimax",
        "name": "MiniMax ASR",
        "provider": "minimax",
        "base_url": "https://api.minimaxi.com/v1",
        "model": "Speech-2.8-HD",
        "api_key_placeholder": "MiniMax API key",
    },
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _env_setting() -> dict[str, Any]:
    return {
        "provider": (config.ASR_PROVIDER or "").strip(),
        "base_url": (config.ASR_BASE_URL or "").strip().rstrip("/"),
        "model": (config.ASR_MODEL or "").strip(),
        "api_key": (config.ASR_API_KEY or "").strip(),
        "timeout": float(config.ASR_TIMEOUT or 300),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "source": "env",
    }


def _default_setting() -> dict[str, Any]:
    setting = _env_setting()
    if not setting["provider"] and setting["api_key"]:
        setting["provider"] = "dashscope"
    if not setting["provider"]:
        setting["provider"] = "dashscope"
    if not setting["base_url"]:
        setting["base_url"] = "https://dashscope.aliyuncs.com/api/v1"
    if not setting["model"]:
        setting["model"] = "paraformer-v2"
    return setting


def load_setting() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return _default_setting()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_setting()
    setting = _default_setting()
    setting.update({key: value for key, value in data.items() if value is not None})
    return normalize_setting(setting)


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    existing = load_setting()
    api_key = (payload.get("api_key") or "").strip() or existing.get("api_key", "")
    now = now_iso()
    provider = (payload.get("provider") or "compatible").strip().lower()
    base_url = (payload.get("base_url") or "").strip().rstrip("/")
    model = (payload.get("model") or "").strip()
    if "dashscope.aliyuncs.com" in base_url or "fun-asr" in model.lower():
        provider = "dashscope"
    if "minimaxi.com" in base_url:
        provider = "minimax"
    if provider == "dashscope" and model.lower() == "fun-asr":
        model = "paraformer-v2"
    config_changed = any(
        [
            provider != existing.get("provider"),
            base_url != existing.get("base_url"),
            model != existing.get("model"),
            bool(api_key) and api_key != existing.get("api_key"),
        ]
    )
    item = normalize_setting(
        {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "timeout": float(payload.get("timeout") or 300),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "source": "file",
            "last_test_ok": bool(existing.get("last_test_ok", False)) and not config_changed,
            "last_test_at": existing.get("last_test_at"),
            "last_test_message": existing.get("last_test_message", "") if not config_changed else "",
        }
    )
    validate(item)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SETTINGS_PATH)
    return sanitize(item)


def normalize_setting(setting: dict[str, Any]) -> dict[str, Any]:
    item = dict(setting)
    provider = (item.get("provider") or "").strip().lower()
    base_url = (item.get("base_url") or "").strip().rstrip("/")
    model = (item.get("model") or "").strip()
    if "dashscope.aliyuncs.com" in base_url or "fun-asr" in model.lower():
        provider = "dashscope"
    if "minimaxi.com" in base_url:
        provider = "minimax"
    if provider == "dashscope":
        base_url = "https://dashscope.aliyuncs.com/api/v1"
        if model.lower() == "fun-asr":
            model = "paraformer-v2"
    if provider == "minimax":
        if not base_url:
            base_url = "https://api.minimaxi.com/v1"
        if not model:
            model = "Speech-2.8-HD"
    item["provider"] = provider
    item["base_url"] = base_url
    item["model"] = model
    return item


def validate(setting: dict[str, Any]) -> None:
    if setting.get("provider") not in {"openai", "compatible", "dashscope", "minimax"}:
        raise ValueError("ASR provider must be openai, compatible, dashscope, or minimax.")
    if not setting.get("base_url"):
        raise ValueError("Please fill in ASR Base URL.")
    if not setting.get("model"):
        raise ValueError("Please fill in ASR model.")
    if not setting.get("api_key"):
        raise ValueError("Please fill in ASR API Key.")
    if float(setting.get("timeout") or 0) <= 0:
        raise ValueError("ASR timeout must be greater than 0.")


def active_setting() -> dict[str, Any]:
    setting = load_setting()
    validate(setting)
    return setting


def sanitize(setting: dict[str, Any]) -> dict[str, Any]:
    result = dict(setting)
    result.pop("api_key", None)
    result["api_key_masked"] = mask_key(setting.get("api_key", ""))
    result["configured"] = is_configured(setting)
    return result


def is_configured(setting: dict[str, Any] | None = None) -> bool:
    setting = setting or load_setting()
    return bool(
        setting.get("provider")
        and setting.get("base_url")
        and setting.get("model")
        and setting.get("api_key")
    )


def mark_test_result(ok: bool, message: str) -> dict[str, Any]:
    setting = load_setting()
    setting["last_test_ok"] = bool(ok)
    setting["last_test_at"] = now_iso()
    setting["last_test_message"] = message
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(setting, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SETTINGS_PATH)
    return sanitize(setting)


def list_payload() -> dict[str, Any]:
    setting = load_setting()
    return {
        "item": sanitize(setting),
        "templates": TEMPLATES,
    }


def status_payload() -> dict[str, Any]:
    setting = load_setting()
    configured = is_configured(setting)
    verified = bool(setting.get("last_test_ok"))
    message = (
        setting.get("last_test_message") or f"{setting.get('provider')} / {setting.get('model')}"
        if configured
        else "Configure ASR API settings to enable audio transcription."
    )
    if configured and not verified:
        message = "已填写语音转写配置，但尚未完成真实转写检测。"
    return {
        "available": configured and verified,
        "purpose": "用于抖音、本地音视频等没有字幕时，把语音识别成文字。",
        "message": message,
        "provider": setting.get("provider") or "",
        "base_url": setting.get("base_url") or "",
        "model": setting.get("model") or "",
        "configured": configured,
        "verified": verified,
    }
