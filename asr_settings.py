from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import config
import storage


SETTINGS_PATH = storage.DATA_DIR / "asr_settings.json"


@dataclass
class AsrSetting:
    id: str
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float
    created_at: str
    updated_at: str
    source: str
    last_test_ok: bool
    last_test_at: str
    last_test_message: str


TEMPLATES = [
    {
        "id": "local-whisper",
        "name": "本地 Whisper",
        "provider": "local",
        "base_url": "local",
        "model": "base",
        "api_key_placeholder": "无需 API Key",
    },
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


def _default_data() -> dict[str, Any]:
    setting = _default_setting()
    if not is_configured(setting):
        return {"active_id": None, "settings": []}
    setting.setdefault("id", str(uuid.uuid4()))
    setting.setdefault("name", _default_name(setting))
    return {"active_id": setting["id"], "settings": [setting]}


def _env_setting() -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": "ASR from env",
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


def _default_name(setting: dict[str, Any]) -> str:
    provider = (setting.get("provider") or "ASR").strip()
    model = (setting.get("model") or "").strip()
    return f"{provider} {model}".strip() or "Untitled ASR API"


def _looks_like_single_setting(data: dict[str, Any]) -> bool:
    return "settings" not in data and any(key in data for key in ("provider", "base_url", "model", "api_key"))


def _normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    if _looks_like_single_setting(data):
        item = normalize_setting(data)
        item.setdefault("id", str(uuid.uuid4()))
        item.setdefault("name", _default_name(item))
        return {"active_id": item["id"], "settings": [item]}
    data.setdefault("active_id", None)
    data.setdefault("settings", [])
    normalized_settings = []
    for raw in data.get("settings", []):
        if not isinstance(raw, dict):
            continue
        item = normalize_setting(raw)
        item.setdefault("id", str(uuid.uuid4()))
        item.setdefault("name", _default_name(item))
        normalized_settings.append(item)
    data["settings"] = normalized_settings
    if data.get("active_id") and not any(item.get("id") == data.get("active_id") for item in normalized_settings):
        data["active_id"] = None
    if not data.get("active_id") and normalized_settings:
        data["active_id"] = normalized_settings[0].get("id")
    return data


def load_data() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return _default_data()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_data()
    if not isinstance(data, dict):
        return _default_data()
    return _normalize_data(data)


def load_setting() -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    for item in data.get("settings", []):
        if item.get("id") == active_id:
            return normalize_setting(item)
    if data.get("settings"):
        return normalize_setting(data["settings"][0])
    return _default_setting()


def save_data(data: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(_normalize_data(data), ensure_ascii=False, indent=2)
    last_error: OSError | None = None
    for attempt in range(6):
        tmp_path = SETTINGS_PATH.with_name(f".{SETTINGS_PATH.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp_path.write_text(serialized, encoding="utf-8")
            tmp_path.replace(SETTINGS_PATH)
            return
        except PermissionError as exc:
            last_error = exc
            try:
                SETTINGS_PATH.write_text(serialized, encoding="utf-8")
                return
            except PermissionError as direct_exc:
                last_error = direct_exc
        finally:
            tmp_path.unlink(missing_ok=True)
        time.sleep(0.05 * (attempt + 1))
    if last_error is not None:
        raise last_error


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    data = load_data()
    settings = data.get("settings", [])
    setting_id = payload.get("id") or str(uuid.uuid4())
    existing = next((item for item in settings if item.get("id") == setting_id), None)
    fallback = existing or load_setting()
    api_key = (payload.get("api_key") or "").strip() or (existing or {}).get("api_key", "")
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
            provider != (existing or {}).get("provider"),
            base_url != (existing or {}).get("base_url"),
            model != (existing or {}).get("model"),
            bool(api_key) and api_key != (existing or {}).get("api_key"),
        ]
    )
    item = normalize_setting(
        asdict(
            AsrSetting(
                id=setting_id,
                name=(payload.get("name") or (existing or {}).get("name") or _default_name({"provider": provider, "model": model})).strip(),
                provider=provider,
                base_url=base_url,
                model=model,
                api_key=api_key,
                timeout=float(payload.get("timeout") or fallback.get("timeout") or 300),
                created_at=(existing or {}).get("created_at") or now,
                updated_at=now,
                source="file",
                last_test_ok=bool((existing or {}).get("last_test_ok", False)) and not config_changed,
                last_test_at=(existing or {}).get("last_test_at") or "",
                last_test_message=((existing or {}).get("last_test_message", "") if not config_changed else ""),
            )
        )
    )
    validate(item)
    if existing:
        settings = [item if old.get("id") == setting_id else old for old in settings]
    else:
        settings.append(item)
    data["settings"] = settings
    if payload.get("make_active", True) or not data.get("active_id"):
        data["active_id"] = setting_id
    save_data(data)
    return sanitize(item)


def normalize_setting(setting: dict[str, Any]) -> dict[str, Any]:
    item = dict(setting)
    provider = (item.get("provider") or "").strip().lower()
    base_url = (item.get("base_url") or "").strip().rstrip("/")
    model = (item.get("model") or "").strip()
    if provider in {"whisper", "local-whisper", "local_whisper"}:
        provider = "local"
    if "dashscope.aliyuncs.com" in base_url or "fun-asr" in model.lower():
        provider = "dashscope"
    if "minimaxi.com" in base_url:
        provider = "minimax"
    if provider == "local":
        base_url = base_url or "local"
        model = model or "base"
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
    if setting.get("provider") not in {"openai", "compatible", "dashscope", "minimax", "local"}:
        raise ValueError("ASR provider must be openai, compatible, dashscope, minimax, or local.")
    if setting.get("provider") == "local":
        if not setting.get("model"):
            raise ValueError("Please fill in local ASR model, for example base or small.")
        if float(setting.get("timeout") or 0) <= 0:
            raise ValueError("ASR timeout must be greater than 0.")
        return
    if not setting.get("base_url"):
        raise ValueError("Please fill in ASR Base URL.")
    if not setting.get("model"):
        raise ValueError("Please fill in ASR model.")
    if not setting.get("api_key"):
        raise ValueError("Please fill in ASR API Key.")
    if float(setting.get("timeout") or 0) <= 0:
        raise ValueError("ASR timeout must be greater than 0.")


def active_setting() -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    for item in data.get("settings", []):
        if item.get("id") == active_id and (item.get("api_key") or normalize_setting(item).get("provider") == "local"):
            setting = normalize_setting(item)
            validate(setting)
            return setting
    for item in data.get("settings", []):
        if item.get("api_key") or normalize_setting(item).get("provider") == "local":
            data["active_id"] = item["id"]
            save_data(data)
            setting = normalize_setting(item)
            validate(setting)
            return setting
    setting = load_setting()
    validate(setting)
    return setting


def sanitize(setting: dict[str, Any]) -> dict[str, Any]:
    result = dict(setting)
    result.setdefault("id", str(uuid.uuid4()))
    result.setdefault("name", _default_name(result))
    result.pop("api_key", None)
    result["api_key_masked"] = mask_key(setting.get("api_key", ""))
    result["configured"] = is_configured(setting)
    return result


def is_configured(setting: dict[str, Any] | None = None) -> bool:
    setting = setting or load_setting()
    if setting.get("provider") == "local":
        return bool(setting.get("model"))
    return bool(
        setting.get("provider")
        and setting.get("base_url")
        and setting.get("model")
        and setting.get("api_key")
    )


def mark_test_result(ok: bool, message: str) -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    for item in data.get("settings", []):
        if item.get("id") == active_id:
            item["last_test_ok"] = bool(ok)
            item["last_test_at"] = now_iso()
            item["last_test_message"] = message
            save_data(data)
            return sanitize(item)
    setting = load_setting()
    setting["last_test_ok"] = bool(ok)
    setting["last_test_at"] = now_iso()
    setting["last_test_message"] = message
    setting.setdefault("id", str(uuid.uuid4()))
    setting.setdefault("name", _default_name(setting))
    save_data({"active_id": setting["id"], "settings": [setting]})
    return sanitize(setting)


def list_payload() -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    items = [sanitize(item) for item in data.get("settings", [])]
    item = next((entry for entry in items if entry.get("id") == active_id), items[0] if items else sanitize(load_setting()))
    return {
        "active_id": active_id,
        "items": items,
        "item": item,
        "templates": TEMPLATES,
    }


def get_setting(setting_id: str) -> dict[str, Any] | None:
    data = load_data()
    for item in data.get("settings", []):
        if item.get("id") == setting_id:
            return normalize_setting(item)
    return None


def set_active(setting_id: str) -> dict[str, Any]:
    data = load_data()
    item = next((setting for setting in data.get("settings", []) if setting.get("id") == setting_id), None)
    if item is None:
        raise KeyError("ASR setting not found")
    if not item.get("api_key"):
        raise ValueError("ASR setting is missing API Key")
    data["active_id"] = setting_id
    save_data(data)
    return sanitize(item)


def delete_setting(setting_id: str) -> None:
    data = load_data()
    settings = [item for item in data.get("settings", []) if item.get("id") != setting_id]
    if len(settings) == len(data.get("settings", [])):
        raise KeyError("ASR setting not found")
    data["settings"] = settings
    if data.get("active_id") == setting_id:
        data["active_id"] = settings[0]["id"] if settings else None
    save_data(data)


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
