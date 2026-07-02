from pathlib import Path

from fastapi.testclient import TestClient

import app
import storage
import src.api_v2 as api_v2


def setup_storage(tmp_path, monkeypatch):
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
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.db")
    storage.init_storage()


def test_html_grab_check_reports_edge_session_without_forcing_wechat(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    monkeypatch.setattr(api_v2, "_fetch_url_bytes", lambda url, max_bytes: {
        "body": b"<html><body><form><input type=\"password\" /></form>please login</body></html>",
        "content_type": "text/html; charset=utf-8",
        "final_url": url,
    })
    monkeypatch.setattr(api_v2, "_agent_reach_fetch_webpage_text", lambda url: {"text": "readable body " * 20})
    monkeypatch.setattr(api_v2, "_agent_browser_command", lambda: "agent-browser")
    monkeypatch.setattr(api_v2, "_agent_browser_connection_args", lambda command: ["--cdp", "9222"])

    response = client.post("/api/v2/settings/html-grab-check", json={})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["authorization_required"] is True
    assert payload["ok"] is True
    assert payload["target_url"] == ""
    keys = {item["key"] for item in payload["checks"]}
    assert "browser_session" in keys
    assert "direct_fetch" not in keys
    assert "agent_reach" not in keys


def test_html_grab_authorize_opens_blank_edge_session_by_default(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    opened = []
    monkeypatch.setattr(api_v2, "_open_edge_remote_debugging_page", lambda url: opened.append(url))

    response = client.post("/api/v2/settings/html-grab-authorize", json={})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True
    assert payload["target_url"] == "about:blank"
    assert opened == ["about:blank"]


def test_agent_browser_extract_prefers_new_tab(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    calls = []

    class Completed:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.returncode = 0

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[-2:] == ["new-tab", "https://example.com/article"]:
            return Completed()
        if "eval" in command:
            return Completed('{"title":"Example","content":"body body body body body body body body body body body body body body body body body body body body"}')
        return Completed()

    monkeypatch.setattr(api_v2, "_agent_browser_command", lambda: "agent-browser")
    monkeypatch.setattr(api_v2, "_agent_browser_connection_args", lambda command: ["--cdp", "9222"])
    monkeypatch.setattr(api_v2.subprocess, "run", fake_run)

    result = api_v2._agent_browser_extract_article_payload("https://example.com/article")

    assert calls[0] == ["agent-browser", "--cdp", "9222", "new-tab", "https://example.com/article"]
    assert result["title"] == "Example"
