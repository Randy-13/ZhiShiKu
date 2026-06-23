from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import storage


SETTINGS_PATH = storage.DATA_DIR / "image_api_settings.json"

OPENAI_COMPATIBLE_PROTOCOL = "openai_compatible"
MINIMAX_PROTOCOL = "minimax"
CUSTOM_ENDPOINT_PROTOCOL = "custom_endpoint"
SUPPORTED_PROTOCOLS = {OPENAI_COMPATIBLE_PROTOCOL, MINIMAX_PROTOCOL, CUSTOM_ENDPOINT_PROTOCOL}


@dataclass
class ImageApiSetting:
    id: str
    name: str
    provider: str
    protocol: str
    base_url: str
    model: str
    api_key: str
    size: str
    quality: str
    aspect_ratio: str
    response_format: str
    timeout: float
    created_at: str
    updated_at: str


TEMPLATES = [
    {
        "id": "openai",
        "name": "OpenAI 图片 API",
        "provider": "openai",
        "protocol": OPENAI_COMPATIBLE_PROTOCOL,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-image-1",
        "size": "1024x1024",
        "quality": "auto",
        "aspect_ratio": "1:1",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "compatible",
        "name": "OpenAI 兼容图片中转",
        "provider": "compatible",
        "protocol": OPENAI_COMPATIBLE_PROTOCOL,
        "base_url": "https://your-relay.example.com/v1",
        "model": "填写中转站图片模型名",
        "size": "1024x1024",
        "quality": "auto",
        "aspect_ratio": "1:1",
        "api_key_placeholder": "填写中转站 Key",
    },
    {
        "id": "minimax",
        "name": "MiniMax 原生图片 API",
        "provider": "minimax",
        "protocol": MINIMAX_PROTOCOL,
        "base_url": "https://api.minimaxi.com/v1/image_generation",
        "model": "image-01",
        "size": "1024x1024",
        "quality": "",
        "aspect_ratio": "1:1",
        "response_format": "base64",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "custom_endpoint",
        "name": "完整 Endpoint",
        "provider": "custom",
        "protocol": CUSTOM_ENDPOINT_PROTOCOL,
        "base_url": "https://api.example.com/v1/images/generations",
        "model": "填写图片模型名",
        "size": "1024x1024",
        "quality": "auto",
        "aspect_ratio": "1:1",
        "api_key_placeholder": "填写 API Key",
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


def normalize_size(value: Any) -> str:
    size = str(value or "").strip()
    size = (
        size.replace("\u00d7", "x")
        .replace("\uff58", "x")
        .replace("\uff38", "x")
        .replace("*", "x")
        .replace(" ", "")
    )
    if not size or size.lower() in {"auto", "default", "none"}:
        return "1024x1024"
    return size


def normalize_quality(value: Any) -> str:
    quality = str(value or "").strip()
    return quality or "auto"


def normalize_aspect_ratio(value: Any, size: Any = "") -> str:
    ratio = str(value or "").strip()
    if ratio:
        return ratio
    normalized_size = normalize_size(size)
    width_text, sep, height_text = normalized_size.partition("x")
    if sep:
        try:
            width = int(width_text)
            height = int(height_text)
            if width == height:
                return "1:1"
            if width > height:
                return "16:9"
            return "9:16"
        except ValueError:
            pass
    return "1:1"


def normalize_protocol(value: Any, provider: Any = "", base_url: Any = "") -> str:
    protocol = str(value or "").strip().lower()
    if protocol in SUPPORTED_PROTOCOLS:
        return protocol
    provider_text = str(provider or "").strip().lower()
    base_text = str(base_url or "").strip().lower()
    if provider_text == "minimax" or "minimaxi.com" in base_text:
        return MINIMAX_PROTOCOL
    return OPENAI_COMPATIBLE_PROTOCOL


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


def _with_defaults(setting: dict[str, Any]) -> dict[str, Any]:
    result = dict(setting)
    result["protocol"] = normalize_protocol(result.get("protocol"), result.get("provider"), result.get("base_url"))
    result["size"] = normalize_size(result.get("size"))
    result["quality"] = normalize_quality(result.get("quality"))
    result["aspect_ratio"] = normalize_aspect_ratio(result.get("aspect_ratio"), result.get("size"))
    result.setdefault("response_format", "")
    return result


def sanitize(setting: dict[str, Any]) -> dict[str, Any]:
    result = _with_defaults(setting)
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
            return _with_defaults(item)
    return None


def active_setting() -> dict[str, Any]:
    data = load_data()
    active_id = data.get("active_id")
    for item in data.get("settings", []):
        if item.get("id") == active_id and item.get("api_key"):
            return _with_defaults(item)
    for item in data.get("settings", []):
        if item.get("api_key"):
            data["active_id"] = item["id"]
            save_data(data)
            return _with_defaults(item)
    raise RuntimeError("尚未设置可用的图片 API。请在写作工具中打开“图片 API 设置”，添加并启用一个配置。")


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    data = load_data()
    settings = data.get("settings", [])
    setting_id = payload.get("id") or str(uuid.uuid4())
    existing = next((item for item in settings if item.get("id") == setting_id), None)
    now = now_iso()
    api_key = (payload.get("api_key") or "").strip()
    if existing and not api_key:
        api_key = existing.get("api_key", "")

    base_url = (payload.get("base_url") or "").strip().rstrip("/")
    provider = (payload.get("provider") or "compatible").strip()
    item = asdict(
        ImageApiSetting(
            id=setting_id,
            name=(payload.get("name") or "未命名图片 API").strip(),
            provider=provider,
            protocol=normalize_protocol(payload.get("protocol"), provider, base_url),
            base_url=base_url,
            model=(payload.get("model") or "").strip(),
            api_key=api_key,
            size=normalize_size(payload.get("size")),
            quality=normalize_quality(payload.get("quality")),
            aspect_ratio=normalize_aspect_ratio(payload.get("aspect_ratio"), payload.get("size")),
            response_format=(payload.get("response_format") or "").strip(),
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


def image_endpoint(setting: dict[str, Any]) -> str:
    base_url = str(setting.get("base_url") or "").rstrip("/")
    protocol = normalize_protocol(setting.get("protocol"), setting.get("provider"), base_url)
    if protocol in {MINIMAX_PROTOCOL, CUSTOM_ENDPOINT_PROTOCOL}:
        return base_url
    if base_url.endswith("/images/generations"):
        return base_url
    return base_url + "/images/generations"


def diagnose(setting: dict[str, Any] | None = None) -> dict[str, str]:
    try:
        resolved = _with_defaults(setting or active_setting())
        missing = [
            key
            for key in ("base_url", "model", "api_key")
            if not (resolved.get(key) or "").strip()
        ]
        if missing:
            return {"ok": "false", "error": "缺少字段：" + ", ".join(missing)}
        base_url = resolved.get("base_url", "").rstrip("/")
        endpoint = image_endpoint(resolved)
        protocol = normalize_protocol(resolved.get("protocol"), resolved.get("provider"), base_url)
        payload_shape = (
            "model, prompt, aspect_ratio, response_format"
            if protocol == MINIMAX_PROTOCOL
            else "model, prompt, n, size, quality, response_format"
        )
        return {
            "ok": "true",
            "provider": resolved.get("provider", "compatible"),
            "protocol": protocol,
            "name": resolved.get("name", ""),
            "model": resolved.get("model", ""),
            "base_url": base_url,
            "endpoint": endpoint,
            "size": normalize_size(resolved.get("size")),
            "quality": normalize_quality(resolved.get("quality")),
            "aspect_ratio": normalize_aspect_ratio(resolved.get("aspect_ratio"), resolved.get("size")),
            "response_format": resolved.get("response_format", ""),
            "payload_shape": payload_shape,
            "message": f"配置字段完整。实际生成将调用 {endpoint}，请求字段：{payload_shape}。",
        }
    except Exception as exc:
        return {"ok": "false", "error": str(exc)}
