from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import storage


SETTINGS_PATH = storage.DATA_DIR / "web_settings.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_setting() -> dict[str, Any]:
    now = now_iso()
    return {
        "app_name": "知识酷",
        "workspace_name": "Research OS",
        "default_route": "/collect",
        "global_library_refresh_seconds": 8,
        "right_library_visible": True,
        "language": "zh-CN",
        "created_at": now,
        "updated_at": now,
    }


def load_setting() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return default_setting()
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    setting = default_setting()
    setting.update({key: value for key, value in data.items() if value is not None})
    return normalize(setting)


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    item = dict(payload)
    item["app_name"] = str(item.get("app_name") or "知识酷").strip() or "知识酷"
    item["workspace_name"] = str(item.get("workspace_name") or "Research OS").strip() or "Research OS"
    route = str(item.get("default_route") or "/collect").strip()
    item["default_route"] = route if route in {"/collect", "/learn", "/mine", "/create", "/settings"} else "/collect"
    try:
        refresh = int(item.get("global_library_refresh_seconds") or 8)
    except (TypeError, ValueError):
        refresh = 8
    item["global_library_refresh_seconds"] = max(3, min(refresh, 60))
    item["right_library_visible"] = bool(item.get("right_library_visible", True))
    item["language"] = str(item.get("language") or "zh-CN").strip() or "zh-CN"
    item.setdefault("created_at", now_iso())
    item["updated_at"] = str(item.get("updated_at") or now_iso())
    return item


def save_setting(payload: dict[str, Any]) -> dict[str, Any]:
    existing = load_setting()
    item = normalize({**existing, **payload})
    item["created_at"] = existing.get("created_at") or now_iso()
    item["updated_at"] = now_iso()
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SETTINGS_PATH)
    return item


def payload() -> dict[str, Any]:
    return {"item": load_setting()}
