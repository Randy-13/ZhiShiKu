from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import config
import storage


def _settings_path_candidates(filename: str) -> list[Path]:
    candidates = [
        storage.DATA_DIR / filename,
        storage.STORAGE_ROOT / filename,
        storage.ROOT / "data" / "runtime" / filename,
        storage.SYSTEM_DATA_DIR / filename,
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def _path_allows_direct_write(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with path.open("r+", encoding="utf-8"):
                pass
        else:
            probe = path.with_name(f".{path.name}.{uuid.uuid4().hex}.probe")
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _select_settings_path(filename: str) -> Path:
    candidates = _settings_path_candidates(filename)
    for path in candidates:
        if _path_allows_direct_write(path):
            return path
    fallback = storage.SYSTEM_DATA_DIR / filename
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


SETTINGS_FILENAME = "api_settings.json"
SETTINGS_PATH = _select_settings_path(SETTINGS_FILENAME)


@dataclass
class ApiSetting:
    id: str
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float
    max_retries: int
    created_at: str
    updated_at: str


TEMPLATES = [
    {
        "id": "deepseek",
        "name": "DeepSeek 官方",
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "openai",
        "name": "OpenAI 官方",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "api_key_placeholder": "sk-...",
    },
    {
        "id": "compatible",
        "name": "OpenAI 兼容中转站",
        "provider": "compatible",
        "base_url": "https://your-relay.example.com/v1",
        "model": "填入中转站支持的模型名",
        "api_key_placeholder": "填入中转站 Key",
    },
    {
        "id": "minimax-m3",
        "name": "MiniMax-M3",
        "provider": "minimax",
        "base_url": "https://api.minimaxi.com/anthropic",
        "model": "MiniMax-M3",
        "api_key_placeholder": "MiniMax API Key",
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


def _env_setting() -> ApiSetting | None:
    if not config.DEEPSEEK_API_KEY:
        return None
    now = now_iso()
    return ApiSetting(
        id=str(uuid.uuid4()),
        name="DeepSeek（从 .env 导入）",
        provider="deepseek",
        base_url=config.DEEPSEEK_BASE_URL,
        model=config.DEEPSEEK_MODEL,
        api_key=config.DEEPSEEK_API_KEY,
        timeout=config.LLM_TIMEOUT,
        max_retries=config.LLM_MAX_RETRIES,
        created_at=now,
        updated_at=now,
    )


def _default_data() -> dict[str, Any]:
    setting = _env_setting()
    if setting is None:
        return {"active_id": None, "settings": []}
    return {"active_id": setting.id, "settings": [asdict(setting)]}


def _normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("active_id", None)
    data.setdefault("settings", [])
    return data


def _read_settings_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return {"active_id": None, "settings": []}
    return _normalize_data(data)


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


def load_data() -> dict[str, Any]:
    candidates = _settings_path_candidates(SETTINGS_FILENAME)
    if SETTINGS_PATH not in candidates:
        selected_data = _read_settings_file(SETTINGS_PATH)
        if selected_data is None:
            selected_data = _default_data()
            if selected_data["settings"]:
                save_data(selected_data)
        return _normalize_data(selected_data)

    selected_data = _read_settings_file(SETTINGS_PATH)
    selected_mtime = _path_mtime(SETTINGS_PATH) if selected_data is not None else -1.0
    for path in candidates:
        if path == SETTINGS_PATH:
            continue
        data = _read_settings_file(path)
        if data is None:
            continue
        mtime = _path_mtime(path)
        if selected_data is None or mtime > selected_mtime:
            selected_data = data
            selected_mtime = mtime
    if selected_data is None:
        selected_data = _default_data()
        if selected_data["settings"]:
            save_data(selected_data)
    return _normalize_data(selected_data)


def _save_data_to_path(path: Path, serialized: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: OSError | None = None
    for attempt in range(6):
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp_path.write_text(serialized, encoding="utf-8")
            tmp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            try:
                path.write_text(serialized, encoding="utf-8")
                return
            except PermissionError as direct_exc:
                last_error = direct_exc
        finally:
            tmp_path.unlink(missing_ok=True)
        time.sleep(0.05 * (attempt + 1))
    if last_error is not None:
        raise last_error


def save_data(data: dict[str, Any]) -> None:
    global SETTINGS_PATH
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    errors: list[OSError] = []
    candidates = [SETTINGS_PATH, *[path for path in _settings_path_candidates(SETTINGS_FILENAME) if path != SETTINGS_PATH]]
    for path in candidates:
        try:
            _save_data_to_path(path, serialized)
            SETTINGS_PATH = path
            return
        except OSError as exc:
            errors.append(exc)
    if errors:
        raise errors[-1]


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
    settings = data.get("settings", [])
    if active_id:
        for item in settings:
            if item.get("id") == active_id:
                if item.get("api_key"):
                    return item
                break
    if settings:
        for item in settings:
            if item.get("api_key"):
                data["active_id"] = item["id"]
                save_data(data)
                return item
    raise RuntimeError("尚未设置可用 API。请点击页面右上角“API 设置”，添加并启用一个 API 配置。")


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    data = load_data()
    settings = data.get("settings", [])
    setting_id = payload.get("id") or str(uuid.uuid4())
    existing = next((item for item in settings if item.get("id") == setting_id), None)
    now = now_iso()
    api_key = (payload.get("api_key") or "").strip()
    if existing and not api_key:
        api_key = existing.get("api_key", "")

    item = {
        "id": setting_id,
        "name": (payload.get("name") or "未命名 API").strip(),
        "provider": (payload.get("provider") or "compatible").strip(),
        "base_url": (payload.get("base_url") or "").strip().rstrip("/"),
        "model": (payload.get("model") or "").strip(),
        "api_key": api_key,
        "timeout": float(payload.get("timeout") or config.LLM_TIMEOUT),
        "max_retries": int(payload.get("max_retries") or config.LLM_MAX_RETRIES),
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
    }

    if not item["name"]:
        raise ValueError("请填写 API 配置名称")
    if not item["base_url"]:
        raise ValueError("请填写 API Base URL")
    if not item["model"]:
        raise ValueError("请填写模型名称")
    if not item["api_key"]:
        raise ValueError("请填写 API Key")

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
        raise KeyError("API 配置不存在")
    if not item.get("api_key"):
        raise ValueError("该 API 配置缺少 API Key")
    data["active_id"] = setting_id
    save_data(data)
    return sanitize(item)


def delete_setting(setting_id: str) -> None:
    data = load_data()
    settings = [item for item in data.get("settings", []) if item.get("id") != setting_id]
    if len(settings) == len(data.get("settings", [])):
        raise KeyError("API 配置不存在")
    data["settings"] = settings
    if data.get("active_id") == setting_id:
        data["active_id"] = settings[0]["id"] if settings else None
    save_data(data)
