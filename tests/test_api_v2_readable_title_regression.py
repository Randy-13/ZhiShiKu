import base64

from fastapi.testclient import TestClient

import storage
import src.api_v2 as api_v2
from schemas import RawMaterialPolishResult
from src.main import create_app


def test_screenshot_readable_draft_uses_body_title_when_upload_name_is_generic(monkeypatch, tmp_path):
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
    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_PATH", tmp_path / "data" / "api_settings.json")
    monkeypatch.setattr(api_v2.asr_settings, "SETTINGS_PATH", tmp_path / "data" / "asr_settings.json")
    monkeypatch.setattr(api_v2.image_api_settings, "SETTINGS_PATH", tmp_path / "data" / "image_api_settings.json")
    monkeypatch.setattr(api_v2.web_settings, "SETTINGS_PATH", tmp_path / "data" / "web_settings.json")
    storage.init_storage()

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    screenshot = storage.save_image_bytes(png, filename="image.png", content_type="image/png")

    monkeypatch.setattr(
        api_v2.ocr_client,
        "recognize_screenshots",
        lambda paths: "[Screenshot 1]\n???????\n5???????????",
    )
    monkeypatch.setattr(
        api_v2.deepseek_client,
        "polish_raw_material",
        lambda raw_text, material_type="raw", setting=None: RawMaterialPolishResult(
            title="",
            markdown="???????\n\n5???????????",
        ),
    )
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "screenshot",
            "items": [{"id": screenshot["id"], "title": "image.png"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True, payload
    assert payload["title"] == "???????"
    assert payload["markdown"].startswith("???????")
