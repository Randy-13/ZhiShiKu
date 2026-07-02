import base64

from fastapi.testclient import TestClient
import pytest

import graph_core
import storage
import src.api_v2 as api_v2
from src.main import create_app
from schemas import RawMaterialPolishResult


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
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.test.db")
    monkeypatch.setattr(api_v2.writer_tools, "WRITER_DIR", runtime_root / "writer")
    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_PATH", tmp_path / "data" / "api_settings.json")
    monkeypatch.setattr(api_v2.asr_settings, "SETTINGS_PATH", tmp_path / "data" / "asr_settings.json")
    monkeypatch.setattr(api_v2.image_api_settings, "SETTINGS_PATH", tmp_path / "data" / "image_api_settings.json")
    monkeypatch.setattr(api_v2.web_settings, "SETTINGS_PATH", tmp_path / "data" / "web_settings.json")
    storage.init_storage()
    graph_core.init_graph()


def test_v2_collect_readable_draft_caps_screenshot_polish_timeout(monkeypatch):
    seen: dict[str, object] = {}

    def fake_ocr(image_paths):
        return "[Screenshot 1]\nRecognized text:\nThis screenshot body is long enough to trigger polish."

    def fake_polish(raw_text, material_type="raw", setting=None):
        seen["material_type"] = material_type
        seen["setting"] = setting
        return RawMaterialPolishResult(title="timeout-guard", markdown="# timeout-guard\n\nThis screenshot body is long enough to trigger polish.")

    monkeypatch.setattr(api_v2.ocr_client, "recognize_screenshots", fake_ocr)
    monkeypatch.setattr(api_v2.deepseek_client, "polish_raw_material", fake_polish)
    monkeypatch.setattr(
        api_v2.deepseek_client,
        "current_setting",
        lambda setting=None: {"api_key": "test-key", "timeout": 180, "max_retries": 3},
    )

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    screenshot = storage.save_image_bytes(png, filename="timeout-cap.png", content_type="image/png")
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={"material_type": "screenshot", "items": [{"id": screenshot["id"], "title": "??????"}]},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True, payload
    assert seen["material_type"] == "screenshot"
    assert seen["setting"]["timeout"] == 45.0
    assert seen["setting"]["max_retries"] == 0
