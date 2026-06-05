from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import storage


SETTINGS_PATH = storage.DATA_DIR / "image_api_settings.json"


@dataclass
class ImageApiSetting:
    id: str
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str
    size: str
    quality: str
    timeout: float
    created_at: str
    updated_at: str


TEMPLATES = [
    {
        "id": "openai",
        "name": "OpenAI 图片 API",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-image-1",
        "size": "1024x1024",
        "quality": "auto",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "compatible",
        "name": "OpenAI 兼容图片中转站",
        "provider": "compatible",
        "base_url": "https://your-relay.example.com/v1",
        "model": "填入中转站图片模型名",
        "size": "1024x1024",
        "quality": "auto",
        "api_key_placeholder": "填入中转站 Key",
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
    return {"active_id": None, "settings": []}


def load_data() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return _default_data()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = _default_data()
    data.setdefault("active_id", None)
    data.setdefault("settings", [])
    return data


def save_data(data: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SETTINGS_PATH)


def sanitize(setting: dict[str, Any]) -> dict[str, Any]:
    result = dict(setting)
    result.pop("api_key", None)
    result["api_key_masked"] = mask_key(setting.get("api_key", ""))
    return result


def list_payload() -> dict[str, Any]:
    data = load_data()
    return {
        "active_id": data.get("active_id"),
        "items": [sanitize(item) for item in data.get("settings", [])],
        "templates": TEMPLATES,
    }


def get_setting(setting_id: str) -> dict[str, Any] | None:
    data = load_data()
    for item in data.get("settings", []):
        if item.get("id") == setting_id:
            return item
    return None


def active_setting() -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    for item in data.get("settings", []):
        if item.get("id") == active_id and item.get("api_key"):
            return item
    for item in data.get("settings", []):
        if item.get("api_key"):
            data["active_id"] = item["id"]
            save_data(data)
            return item
    raise RuntimeError("尚未设置可用的图片 API。请在写文工具中打开“图片 API 设置”，添加并启用一个配置。")


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    data = load_data()
    settings = data.get("settings", [])
    setting_id = payload.get("id") or str(uuid.uuid4())
    existing = next((item for item in settings if item.get("id") == setting_id), None)
    now = now_iso()
    api_key = (payload.get("api_key") or "").strip()
    if existing and not api_key:
        api_key = existing.get("api_key", "")

    item = asdict(
        ImageApiSetting(
            id=setting_id,
            name=(payload.get("name") or "未命名图片 API").strip(),
            provider=(payload.get("provider") or "compatible").strip(),
            base_url=(payload.get("base_url") or "").strip().rstrip("/"),
            model=(payload.get("model") or "").strip(),
            api_key=api_key,
            size=(payload.get("size") or "1024x1024").strip(),
            quality=(payload.get("quality") or "auto").strip(),
            timeout=float(payload.get("timeout") or 120),
            created_at=existing.get("created_at") if existing else now,
            updated_at=now,
        )
    )

    if not item["name"]:
        raise ValueError("请填写图片 API 配置名称")
    if not item["base_url"]:
        raise ValueError("请填写图片 API Base URL")
    if not item["model"]:
        raise ValueError("请填写图片模型名称")
    if not item["api_key"]:
        raise ValueError("请填写图片 API Key")

    if existing:
        settings = [item if old.get("id") == setting_id else old for old in settings]
    else:
        settings.append(item)
    data["settings"] = settings
    if payload.get("make_active", True) or not data.get("active_id"):
        data["active_id"] = setting_id
    save_data(data)
    return sanitize(item)


def set_active(setting_id: str) -> dict[str, Any]:
    data = load_data()
    item = next((setting for setting in data.get("settings", []) if setting.get("id") == setting_id), None)
    if item is None:
        raise KeyError("图片 API 配置不存在")
    if not item.get("api_key"):
        raise ValueError("该图片 API 配置缺少 API Key")
    data["active_id"] = setting_id
    save_data(data)
    return sanitize(item)


def delete_setting(setting_id: str) -> None:
    data = load_data()
    settings = [item for item in data.get("settings", []) if item.get("id") != setting_id]
    if len(settings) == len(data.get("settings", [])):
        raise KeyError("图片 API 配置不存在")
    data["settings"] = settings
    if data.get("active_id") == setting_id:
        data["active_id"] = settings[0]["id"] if settings else None
    save_data(data)


def diagnose(setting: dict[str, Any] | None = None) -> dict[str, str]:
    try:
        resolved = setting or active_setting()
        missing = [
            key
            for key in ("base_url", "model", "api_key")
            if not (resolved.get(key) or "").strip()
        ]
        if missing:
            return {"ok": "false", "error": "缺少字段：" + ", ".join(missing)}
        base_url = resolved.get("base_url", "").rstrip("/")
        endpoint = base_url + ("/images/generations" if base_url.endswith("/v1") else "/images/generations")
        return {
            "ok": "true",
            "provider": resolved.get("provider", "compatible"),
            "name": resolved.get("name", ""),
            "model": resolved.get("model", ""),
            "base_url": base_url,
            "endpoint": endpoint,
            "size": resolved.get("size", ""),
            "quality": resolved.get("quality", ""),
            "message": "配置字段完整。实际生成时会调用 OpenAI 兼容的 /images/generations 接口。",
        }
    except Exception as exc:
        return {"ok": "false", "error": str(exc)}
