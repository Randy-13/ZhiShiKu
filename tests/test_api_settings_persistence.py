from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import graph_core
import storage
import src.api_v2 as api_v2
from src.main import create_app


@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    runtime_root = tmp_path
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(storage, "STORAGE_ROOT", runtime_root)
    monkeypatch.setattr(storage, "IMAGE_DIR", runtime_root / "images")
    monkeypatch.setattr(storage, "DOCUMENT_DIR", runtime_root / "documents")
    monkeypatch.setattr(storage, "KNOWLEDGE_DIR", runtime_root / "knowledge")
    monkeypatch.setattr(storage, "MEDIA_DIR", runtime_root / "media")
    monkeypatch.setattr(storage, "MINING_DIR", runtime_root / "mining")
    monkeypatch.setattr(storage, "RAW_MATERIAL_DIR", runtime_root / "raw_materials")
    monkeypatch.setattr(storage, "WRITER_DIR", runtime_root / "writer")
    monkeypatch.setattr(storage, "TRASH_DIR", runtime_root / "trash")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "SYSTEM_DATA_DIR", tmp_path / "system-data")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.test.db")
    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_PATH", tmp_path / "data" / "api_settings.json")
    monkeypatch.setattr(api_v2.image_api_settings, "SETTINGS_PATH", tmp_path / "data" / "image_api_settings.json")
    storage.init_storage()
    graph_core.init_graph()


def test_v2_text_api_create_persists_and_appears_in_list():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/settings/api",
        json={
            "name": "LLM Fixture",
            "provider": "compatible",
            "base_url": "https://example.test/v1",
            "model": "fixture-model",
            "api_key": "sk-test-secret",
            "timeout": 30,
            "max_retries": 0,
            "make_active": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True, payload
    assert payload["item"]["api_key_masked"] == "sk-t...cret"
    assert "sk-test-secret" not in str(payload)

    list_payload = client.get("/api/v2/settings/api").json()["data"]
    assert list_payload["active_id"] == payload["item"]["id"]
    assert any(item["id"] == payload["item"]["id"] for item in list_payload["items"])


def test_v2_text_api_save_survives_windows_replace_permission_error(monkeypatch):
    target = api_v2.api_settings.SETTINGS_PATH
    original_replace = Path.replace
    calls = {"count": 0}

    def flaky_replace(self, destination):
        if Path(destination) == target and calls["count"] == 0:
            calls["count"] += 1
            raise PermissionError("simulated locked settings file")
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    api_v2.api_settings.save_data({"active_id": "fixture", "settings": [{"id": "fixture", "api_key": "sk-test"}]})

    assert calls["count"] == 1
    assert api_v2.api_settings.load_data()["active_id"] == "fixture"


def test_v2_text_api_save_falls_back_when_primary_file_is_not_writable(monkeypatch, tmp_path):
    primary = tmp_path / "readonly" / "api_settings.json"
    fallback = tmp_path / "fallback" / "api_settings.json"
    primary.parent.mkdir(parents=True)
    primary.write_text('{"active_id": null, "settings": []}', encoding="utf-8")

    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_FILENAME", "api_settings.json")
    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_PATH", primary)
    monkeypatch.setattr(api_v2.api_settings, "_settings_path_candidates", lambda filename: [primary, fallback])

    original_save = api_v2.api_settings._save_data_to_path

    def fail_primary(path, serialized):
        if path == primary:
            raise PermissionError("primary locked")
        return original_save(path, serialized)

    monkeypatch.setattr(api_v2.api_settings, "_save_data_to_path", fail_primary)

    api_v2.api_settings.save_data({"active_id": "fallback", "settings": [{"id": "fallback", "api_key": "sk-test"}]})

    assert api_v2.api_settings.SETTINGS_PATH == fallback
    assert api_v2.api_settings.load_data()["active_id"] == "fallback"


def test_v2_text_api_storage_error_returns_ok_false(monkeypatch):
    client = TestClient(create_app())

    def fail_save(payload):
        raise PermissionError("simulated storage lock")

    monkeypatch.setattr(api_v2.api_settings, "save_setting", fail_save)

    response = client.post(
        "/api/v2/settings/api",
        json={
            "name": "Locked API",
            "provider": "compatible",
            "base_url": "https://example.test/v1",
            "model": "locked-model",
            "api_key": "sk-test-secret",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is False
    assert "simulated storage lock" in payload["error"]
