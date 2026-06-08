from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import storage


VALID_TEXT_EXTRACTION_MODES = {"local_ocr", "ai_vision"}
DEFAULT_SETTINGS: dict[str, Any] = {
    "text_extraction_mode": "local_ocr",
    "storage_locations": {},
}


def _select_settings_path() -> Path:
    candidates = [
        storage.DATA_DIR / "workbench_settings.json",
        storage.STORAGE_ROOT / "workbench_settings.json",
        storage.ROOT / "data" / "runtime" / "workbench_settings.json",
    ]
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.open("a", encoding="utf-8").close()
            else:
                probe = path.with_suffix(path.suffix + ".probe")
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    return storage.ROOT / "data" / "runtime" / "workbench_settings.json"


SETTINGS_PATH = _select_settings_path()


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    data = {**DEFAULT_SETTINGS, **payload}
    mode = data.get("text_extraction_mode")
    if mode not in VALID_TEXT_EXTRACTION_MODES:
        data["text_extraction_mode"] = DEFAULT_SETTINGS["text_extraction_mode"]
    locations = data.get("storage_locations")
    if not isinstance(locations, dict):
        locations = {}
    data["storage_locations"] = storage.apply_storage_locations(
        {key: str(value) for key, value in locations.items() if value is not None}
    )
    return data


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    if not isinstance(payload, dict):
        return dict(DEFAULT_SETTINGS)
    return _normalize(payload)


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize({**load_settings(), **payload})
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SETTINGS_PATH)
    return data
