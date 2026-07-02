import base64

from fastapi.testclient import TestClient
import pytest

import app as legacy_app
import storage
import src.api_v2 as api_v2
from schemas import RawMaterialPolishResult
from src.main import create_app


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


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


def test_readable_draft_text_uses_v2_backend_main_path():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "text",
            "title": "manual note",
            "items": [{"title": "manual note", "content": "first paragraph\n\nsecond paragraph"}],
        },
    )

    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["ok"] is True, payload
    assert payload["title"] == "manual note"
    assert "first paragraph" in payload["markdown"]


def test_readable_draft_screenshot_respects_ai_vision_and_polishes(monkeypatch):
    seen = {}

    def fake_ai(paths, setting=None):
        seen["paths"] = paths
        return "[Screenshot 1]\nRecognized text:\nAI vision screenshot body"

    def fake_polish(raw_text, material_type="raw", setting=None):
        seen["raw_text"] = raw_text
        return RawMaterialPolishResult(title="AI vision title", markdown="# AI vision title\n\nAI vision screenshot body")

    monkeypatch.setattr(api_v2.deepseek_client, "recognize_screenshots_with_ai", fake_ai)
    monkeypatch.setattr(api_v2.deepseek_client, "polish_raw_material", fake_polish)
    monkeypatch.setattr(api_v2.deepseek_client, "current_setting", lambda setting=None: {"api_key": "test-key", "timeout": 10})
    screenshot = storage.save_image_bytes(PNG_1X1, filename="image.png", content_type="image/png")
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={"material_type": "screenshot", "parser_mode": "ai_vision", "items": [{"id": screenshot["id"], "title": "image.png"}]},
    )

    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["ok"] is True, payload
    assert payload["title"] == "AI vision title"
    assert seen["paths"]
    assert "[Screenshot" not in seen["raw_text"]


def test_readable_draft_document_media_and_link_share_v2_endpoint(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr(api_v2.document_parser, "extract_text", lambda path, visual_recognizer=None, prefer_visual=False: "document extracted body")
    upload = client.post("/api/files", files={"files": ("note.txt", b"document bytes", "text/plain")})
    file_id = upload.json()["items"][0]["id"]

    media_item = storage.save_media_bytes(b"media-bytes", "talk.mp3", "audio/mpeg")
    monkeypatch.setattr(api_v2.media_parser, "ensure_transcript", lambda item: ("media transcript body", "asr"))
    monkeypatch.setattr(
        api_v2,
        "_extract_link_text",
        lambda url, item, allow_browser=True: {
            "title": "Linked article",
            "text": "linked article body",
            "source": "example.com",
            "link_type": "public_webpage",
            "access_status": "accessible",
            "extraction_strategy": "direct_fetch",
        },
    )

    cases = [
        ("document", [{"id": file_id, "title": "note.txt"}], "document extracted body"),
        ("media", [{"id": media_item["id"], "title": "talk.mp3"}], "media transcript body"),
        ("web_link", [{"url": "https://example.com/a", "title": "Linked article"}], "linked article body"),
    ]
    for material_type, items, expected in cases:
        response = client.post("/api/v2/collect/readable-draft", json={"material_type": material_type, "items": items})
        payload = response.json()["data"]
        assert response.status_code == 200
        assert payload["ok"] is True, payload
        assert expected in payload["markdown"]


def test_web_link_rejects_media_platform_in_readable_draft():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={"material_type": "web_link", "items": [{"url": "https://www.bilibili.com/video/BV123", "title": "video"}]},
    )

    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["ok"] is False
    assert "video" in payload["error"] or "???" in payload["error"]


def test_legacy_readable_document_delegates_to_v2_builder(monkeypatch):
    screenshot = storage.save_image_bytes(PNG_1X1, filename="legacy.png", content_type="image/png")
    seen = {}

    def fake_build(request, context):
        seen["material_type"] = request.material_type
        seen["items"] = request.items
        return {
            "ok": True,
            "title": "delegated title",
            "note": "delegated note",
            "markdown": "# delegated title\n\ndelegated body",
            "errors": [],
            "polish": {"status": "delegated"},
        }

    monkeypatch.setattr(legacy_app.api_v2, "_build_readable_draft", fake_build)
    client = TestClient(legacy_app.app)

    response = client.post("/api/materials/readable-document", json={"image_ids": [screenshot["id"]], "parser_mode": "local_ocr"})

    assert response.status_code == 200
    payload = response.json()
    assert seen["material_type"] == "screenshot"
    assert seen["items"][0].id == screenshot["id"]
    assert payload["title"] == "delegated title"
    assert payload["markdown"].startswith("# delegated title")
    assert payload["raw_text"] == payload["markdown"]
