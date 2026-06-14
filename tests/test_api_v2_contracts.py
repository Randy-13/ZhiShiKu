import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import graph_core
import app as legacy_app
import storage
import src.api_v2 as api_v2
from src.auth import bootstrap_admin
from src.main import create_app
from schemas import (
    KnowledgeCluster,
    KnowledgeResult,
    PerspectiveFinding,
    PerspectiveInterpretationResult,
    RawMaterialPolishResult,
    TopicSuggestion,
    TopicSuggestionsResult,
    WriterArticleResult,
    WriterRevisionResult,
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
    graph_core.init_graph()


def test_v2_material_types_contract():
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.get("/api/v2/material-types")

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {"id": "text", "label": "Text"},
            {"id": "screenshot", "label": "Screenshot"},
            {"id": "document", "label": "Document"},
            {"id": "media", "label": "Media"},
            {"id": "link", "label": "Link"},
        ],
        "meta": {},
    }


def test_v2_app_shell_contract():
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.get("/api/v2/app-shell")

    assert response.status_code == 200
    payload = response.json()
    sections = payload["data"]["primarySections"]
    entries = payload["data"]["workspaceEntries"]
    libraries = payload["data"]["globalLibraries"]
    assert [item["id"] for item in sections] == ["collect", "learn", "mine", "create", "library", "settings"]
    assert [item["navLabel"] for item in sections] == ["收集", "学习", "挖掘", "创作", "知识库", "设置中心"]
    assert [item["id"] for item in libraries] == ["raw", "focus", "perspective"]
    assert [item["label"] for item in libraries] == ["原料库", "重点库", "视角库"]
    assert all(item["navDescription"] for item in sections)
    assert any(
        item["id"] == "collect-media"
        and item["route"] == "/collect/media"
        and item["shellSection"] == "collect"
        and item["capabilityId"] == "capture_materials"
        for item in entries
    )
    assert any(
        item["id"] == "create-content"
        and item["route"] == "/create"
        and item["shellSection"] == "create"
        and item["capabilityId"] == "create_content"
        for item in entries
    )
    assert any(
        item["id"] == "library-files"
        and item["route"] == "/library"
        and item["shellSection"] == "library"
        and item["capabilityId"] == "manage_libraries"
        for item in entries
    )
    assert payload["meta"] == {}


def test_v2_settings_overview_contract_does_not_expose_secret_keys():
    client = TestClient(create_app())

    response = client.get("/api/v2/settings/overview")

    assert response.status_code == 200
    payload = response.json()
    sections = payload["data"]["sections"]
    assert [item["id"] for item in sections] == ["web", "llm", "asr", "image"]
    assert all({"id", "label", "configured", "activeId", "activeName", "itemCount"} <= set(item) for item in sections)
    assert "api_key" not in str(payload).lower()
    assert payload["meta"] == {}


def test_auth_me_defaults_to_local_admin_user(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["deploymentMode"] == "local"
    assert payload["authenticated"] is True
    assert payload["user"]["id"] == "local-user"
    assert payload["user"]["role"] == "admin"
    assert payload["workspace"]["id"] == "local-workspace"


def test_cloud_auth_requires_session_and_supports_invite_registration(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    storage.init_storage()
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO invitations (
                id, code, role, max_uses, used_count, expires_at, created_at, status
            ) VALUES ('invite-test', 'INVITE-CODE', 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
            """
        )
        conn.commit()

    client = TestClient(create_app(), base_url="https://testserver")

    assert client.get("/api/auth/me").status_code == 401
    register_response = client.post(
        "/api/auth/register-with-invite",
        json={
            "invite_code": "INVITE-CODE",
            "email": "beta@example.test",
            "username": "beta_user",
            "password": "password-123",
        },
    )

    assert register_response.status_code == 200
    assert "figurelearning_session" in register_response.headers["set-cookie"]
    assert "HttpOnly" in register_response.headers["set-cookie"]
    payload = register_response.json()["data"]
    assert payload["deploymentMode"] == "cloud"
    assert payload["authenticated"] is True
    assert payload["user"]["email"] == "beta@example.test"
    assert payload["user"]["role"] == "member"
    assert client.get("/api/auth/me").json()["data"]["user"]["username"] == "beta_user"


def test_cloud_preview_can_disable_secure_cookie_for_local_http(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    storage.init_storage()
    with storage.connect() as conn:
        result = bootstrap_admin(
            conn,
            email="admin@example.test",
            username="admin",
            password="password-123",
            invite_max_uses=1,
        )

    client = TestClient(create_app(), base_url="http://testserver")
    login_response = client.post(
        "/api/auth/login",
        json={"identifier": result["admin"]["email"], "password": "password-123"},
    )

    assert login_response.status_code == 200
    cookie = login_response.headers["set-cookie"]
    assert "figurelearning_session" in cookie
    assert "Secure" not in cookie
    assert client.get("/api/auth/me").json()["data"]["user"]["role"] == "admin"


def test_bootstrap_admin_creates_invite_and_is_idempotent(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    storage.init_storage()
    with storage.connect() as conn:
        first = bootstrap_admin(
            conn,
            email="owner@example.test",
            username="owner",
            password="password-123",
            invite_max_uses=3,
        )
        second = bootstrap_admin(
            conn,
            email="owner@example.test",
            username="owner",
            password="password-456",
            invite_max_uses=2,
        )
        admin_count = conn.execute("SELECT COUNT(*) AS count FROM users WHERE email = ?", ("owner@example.test",)).fetchone()["count"]
        invite_count = conn.execute("SELECT COUNT(*) AS count FROM invitations").fetchone()["count"]

    assert first["admin"]["created"] is True
    assert second["admin"]["created"] is False
    assert first["admin"]["id"] == second["admin"]["id"]
    assert admin_count == 1
    assert invite_count == 2


def test_cloud_mode_blocks_api_writes_without_session(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.post(
        "/api/v2/settings/web",
        json={
            "app_name": "知识酷测试",
            "workspace_name": "Research OS Test",
            "default_route": "/mine",
            "global_library_refresh_seconds": 12,
            "right_library_visible": True,
            "language": "zh-CN",
        },
    )

    assert response.status_code == 401
    assert "登录" in response.json()["detail"]


def test_jobs_contract_creates_lists_reads_and_cancels_local_job(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())

    create_response = client.post(
        "/api/jobs",
        json={"kind": "readable_draft", "payload": {"title": "Job Source"}, "auto_start": False},
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]["item"]
    assert created["kind"] == "readable_draft"
    assert created["status"] == "queued"
    assert created["payload"]["title"] == "Job Source"
    assert created["ownerUserId"] == "local-user"
    assert created["workspaceId"] == "local-workspace"
    assert created["events"][0]["status"] == "queued"

    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    assert list_response.json()["data"]["items"][0]["id"] == created["id"]

    detail_response = client.get(f"/api/jobs/{created['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["item"]["events"][0]["message"] == "任务已进入队列"

    cancel_response = client.post(f"/api/jobs/{created['id']}/cancel")
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()["data"]["item"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["events"][-1]["status"] == "cancelled"


def test_jobs_auto_runs_readable_draft_and_persists_result(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())

    create_response = client.post(
        "/api/jobs",
        json={
            "kind": "readable_draft",
            "payload": {
                "material_type": "text",
                "title": "Job Draft",
                "items": [{"content": "job source body", "title": "source"}],
            },
        },
    )

    assert create_response.status_code == 200
    job_id = create_response.json()["data"]["item"]["id"]
    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    item = detail_response.json()["data"]["item"]
    assert item["status"] == "success"
    assert item["result"]["ok"] is True
    assert item["result"]["title"] == "Job Draft"
    statuses = [event["status"] for event in item["events"]]
    assert statuses == ["queued", "running", "success"]


def test_jobs_auto_run_writer_generation_tasks(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())
    monkeypatch.setattr(
        api_v2.api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "key",
        },
    )
    monkeypatch.setattr(
        api_v2.deepseek_client,
        "generate_topics",
        lambda markdown_files, setting=None: TopicSuggestionsResult(
            suggestions=[
                TopicSuggestion(
                    title="Job Topic",
                    angle="job angle",
                    reason="job reason",
                    reader_pain_point="reader pain",
                    material_basis="source basis",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        api_v2.deepseek_client,
        "generate_wechat_article",
        lambda topic, markdown_files, setting=None: WriterArticleResult(
            title="Job Article",
            markdown="# Job Article\n\nBody",
            cover_prompt="cover",
            content_image_prompts=[],
            digest="digest",
        ),
    )
    monkeypatch.setattr(
        api_v2.deepseek_client,
        "revise_wechat_article",
        lambda markdown, instruction, markdown_files, setting=None: WriterRevisionResult(
            markdown="# Job Article Revised\n\nBody",
            change_summary="revised",
        ),
    )

    raw_item = client.post(
        "/api/v2/collect/raw-file",
        json={"material_type": "text", "title": "Job Source", "note": "", "markdown": "# Job Source\n\nBody", "source": "manual"},
    ).json()["data"]["item"]
    project = client.post(
        "/api/v2/create/projects",
        json={"name": "Job Writer Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]
    attach = client.post(
        f"/api/v2/create/projects/{project['id']}/library-files",
        json={"files": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}]},
    )
    assert attach.status_code == 200

    topics_job = client.post("/api/jobs", json={"kind": "writer_topics", "payload": {"project_id": project["id"]}})
    assert topics_job.status_code == 200
    topics_detail = client.get(f"/api/jobs/{topics_job.json()['data']['item']['id']}").json()["data"]["item"]
    assert topics_detail["status"] == "success"
    assert topics_detail["result"]["suggestions"][0]["title"] == "Job Topic"

    article_job = client.post(
        "/api/jobs",
        json={"kind": "writer_article", "payload": {"project_id": project["id"], "topic": {"title": "Job Topic"}}},
    )
    assert article_job.status_code == 200
    article_detail = client.get(f"/api/jobs/{article_job.json()['data']['item']['id']}").json()["data"]["item"]
    assert article_detail["status"] == "success"
    assert article_detail["result"]["title"] == "Job Article"
    assert (storage.ROOT / article_detail["result"]["article_path"]).exists()

    revise_job = client.post(
        "/api/jobs",
        json={
            "kind": "writer_revise",
            "payload": {
                "project_id": project["id"],
                "markdown": "# Job Article\n\nBody",
                "instruction": "make it sharper",
            },
        },
    )
    assert revise_job.status_code == 200
    revise_detail = client.get(f"/api/jobs/{revise_job.json()['data']['item']['id']}").json()["data"]["item"]
    assert revise_detail["status"] == "success"
    assert revise_detail["result"]["change_summary"] == "revised"
    assert (storage.ROOT / revise_detail["result"]["version_path"]).exists()


def test_jobs_auto_run_learn_refine_from_raw_library(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())

    def fake_generate_knowledge_from_text(raw_text: str, setting=None):
        assert "job raw source body for learning" in raw_text
        return (
            KnowledgeResult(
                title="Job Focus Cluster",
                topic="job raw learning topic",
                tags=["学习", "任务"],
                focus_question="这份原文的核心知识是什么？",
                clusters=[
                    KnowledgeCluster(
                        name="任务化重点提炼",
                        domain="知识处理",
                        occurrence_count=1,
                        meaning="把学习区重点提炼迁入任务中心。",
                        key_information=["读取原文库", "生成重点草稿"],
                    )
                ],
                investment_insights="暂无",
            ),
            raw_text,
        )

    monkeypatch.setattr(api_v2.deepseek_client, "generate_knowledge_from_text", fake_generate_knowledge_from_text)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    raw_item = client.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Job Learn Source",
            "note": "",
            "markdown": "# Job Learn Source\n\njob raw source body for learning",
            "source": "manual",
        },
    ).json()["data"]["item"]

    create_response = client.post(
        "/api/jobs",
        json={"kind": "learn_refine", "payload": {"raw_paths": [raw_item["markdown_path"]], "title": "Job Focus Title"}},
    )

    assert create_response.status_code == 200
    detail = client.get(f"/api/jobs/{create_response.json()['data']['item']['id']}").json()["data"]["item"]
    assert detail["status"] == "success"
    assert detail["result"]["ok"] is True
    assert detail["result"]["cluster_count"] == 1
    assert "Job Focus Title" in detail["result"]["markdown"]
    assert raw_item["markdown_path"] in detail["result"]["markdown"]


def test_jobs_auto_run_mine_interpret_from_library(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())

    def fake_interpret(material_blocks, perspective, setting=None):
        assert material_blocks[0]["library"] == "raw"
        assert "job raw material for mining" in material_blocks[0]["text"]
        assert perspective["name"] == "作家视角"
        return PerspectiveInterpretationResult(
            title="Job 作家视角：材料结构",
            perspective_name="作家视角",
            tags=["作家视角", "任务"],
            summary="材料用事实推进观点。",
            findings=[
                PerspectiveFinding(
                    dimension="文字组织逻辑",
                    interpretation="材料先交代事实，再转向判断。",
                    evidence_refs=["S1"],
                )
            ],
            writing_implications=["复用先事实后判断的段落结构。"],
            risks_and_limits=["只有单一来源。"],
        )

    monkeypatch.setattr(api_v2.deepseek_client, "interpret_from_perspective", fake_interpret)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    raw_item = client.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Job Mine Source",
            "note": "",
            "markdown": "# Job Mine Source\n\njob raw material for mining",
            "source": "manual",
        },
    ).json()["data"]["item"]
    perspective = client.get("/api/v2/mine/perspectives").json()["data"]["items"][0]

    create_response = client.post(
        "/api/jobs",
        json={
            "kind": "mine_interpret",
            "payload": {
                "sources": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}],
                "perspective": perspective,
            },
        },
    )

    assert create_response.status_code == 200
    detail = client.get(f"/api/jobs/{create_response.json()['data']['item']['id']}").json()["data"]["item"]
    assert detail["status"] == "success"
    assert detail["result"]["ok"] is True
    markdown = detail["result"]["markdown"]
    assert "Job 作家视角：材料结构" in markdown
    assert "文字组织逻辑" in markdown
    assert raw_item["markdown_path"] in markdown
    assert "job raw material for mining" not in markdown


def test_jobs_auto_run_publish_preflight_for_local_project(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())
    project = client.post(
        "/api/v2/create/projects",
        json={"name": "Publish Job Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]
    workspace = api_v2.writer_tools.resolve_project_workspace(project["id"])
    (workspace / "formatted.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (workspace / "article.md").write_text("# Publish Job\n\nBody", encoding="utf-8")

    def fake_preflight(workspace_arg, title, author="Bobo", digest=None, cover_path=None):
        assert workspace_arg == workspace
        assert title == "Publish Title"
        return {
            "ok": True,
            "checks": [{"key": "html", "label": "HTML", "ok": True, "detail": "formatted.html"}],
            "blocking": [],
            "digest": digest,
        }

    monkeypatch.setattr(api_v2.writer_tools, "publish_preflight", fake_preflight)

    create_response = client.post(
        "/api/jobs",
        json={
            "kind": "publish_preflight",
            "payload": {
                "project_id": project["id"],
                "title": "Publish Title",
                "author": "Bobo",
                "digest": "摘要",
            },
        },
    )

    assert create_response.status_code == 200
    detail = client.get(f"/api/jobs/{create_response.json()['data']['item']['id']}").json()["data"]["item"]
    assert detail["status"] == "success"
    assert detail["result"]["ok"] is True
    assert detail["result"]["preflight"]["ok"] is True
    assert detail["result"]["preflight"]["checks"][0]["key"] == "html"


def test_jobs_auto_run_media_transcript_and_preserve_partial_success(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())
    first = storage.save_media_bytes(b"first media", "first.mp3", "audio/mpeg")
    second = storage.save_media_bytes(b"second media", "second.mp3", "audio/mpeg")

    def fake_ensure_transcript(item: dict) -> tuple[str, str]:
        if int(item["id"]) == int(second["id"]):
            raise RuntimeError("ASR failed")
        return "第一段转写", "asr"

    monkeypatch.setattr(api_v2.media_parser, "ensure_transcript", fake_ensure_transcript)

    create_response = client.post(
        "/api/jobs",
        json={"kind": "media_transcript", "payload": {"media_ids": [first["id"], second["id"]]}},
    )

    assert create_response.status_code == 200
    job_id = create_response.json()["data"]["item"]["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()["data"]["item"]
    assert detail["status"] == "success"
    result_items = detail["result"]["items"]
    assert result_items[0]["ok"] is True
    assert "第一段转写" in result_items[0]["transcript"]
    assert result_items[1]["ok"] is False
    assert "ASR failed" in result_items[1]["error"]
    assert storage.get_media_source(first["id"])["status"] == "ready"
    assert storage.get_media_source(second["id"])["status"] == "error"


def test_jobs_auto_run_writer_images_and_preserve_partial_success(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DEPLOYMENT_MODE", raising=False)
    client = TestClient(create_app())
    project = client.post(
        "/api/v2/create/projects",
        json={"name": "Image Job Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]

    def fake_generate_image(prompt: str, output_path: Path, api_key: str | None = None, **kwargs) -> dict[str, str]:
        if output_path.name == "content-2.png":
            raise RuntimeError("image upstream failed")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return {"path": storage.storage_relative(output_path), "prompt": prompt}

    monkeypatch.setattr(api_v2.writer_tools, "generate_image", fake_generate_image)

    create_response = client.post(
        "/api/jobs",
        json={
            "kind": "image_generate",
            "payload": {
                "project_id": project["id"],
                "cover_prompt": "cover prompt",
                "content_image_prompts": ["first image", "second image"],
            },
        },
    )

    assert create_response.status_code == 200
    job_id = create_response.json()["data"]["item"]["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()["data"]["item"]
    assert detail["status"] == "success"
    images = detail["result"]["images"]
    assert images["ok"] is False
    assert images["partial"] is True
    assert images["cover"]["path"].endswith("cover.png")
    assert images["content_images"][0]["index"] == 1
    assert images["errors"][0]["index"] == 2
    assert "image upstream failed" in images["errors"][0]["message"]
    assert (storage.ROOT / images["cover"]["path"]).exists()
    assert (storage.ROOT / images["content_images"][0]["path"]).exists()

    loaded = client.get(f"/api/v2/create/projects/{project['id']}").json()["data"]["item"]
    assert loaded["images"]["partial"] is True

    item_response = client.post(
        "/api/jobs",
        json={
            "kind": "writer_image_item",
            "payload": {"project_id": project["id"], "kind": "content", "prompt": "third image", "index": 3},
        },
    )
    assert item_response.status_code == 200
    item_detail = client.get(f"/api/jobs/{item_response.json()['data']['item']['id']}").json()["data"]["item"]
    assert item_detail["status"] == "success"
    assert any(item["index"] == 3 for item in item_detail["result"]["images"]["content_images"])


def test_cloud_jobs_create_requires_login(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.post("/api/jobs", json={"kind": "readable_draft", "payload": {}})

    assert response.status_code == 401


def _register_cloud_member(invite_code: str, email: str, username: str) -> tuple[TestClient, dict[str, object]]:
    storage.init_storage()
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO invitations (
                id, code, role, max_uses, used_count, expires_at, created_at, status
            ) VALUES (?, ?, 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
            """,
            (f"invite-{invite_code}", invite_code),
        )
        conn.commit()

    client = TestClient(create_app(), base_url="http://testserver")
    response = client.post(
        "/api/auth/register-with-invite",
        json={
            "invite_code": invite_code,
            "email": email,
            "username": username,
            "password": "password-123",
        },
    )
    assert response.status_code == 200
    return client, response.json()["data"]


def test_cloud_jobs_concurrent_quota_blocks_third_active_job(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client, _payload = _register_cloud_member("JOB-QUOTA", "job-quota@example.test", "job_quota")

    assert client.post("/api/jobs", json={"kind": "readable_draft", "payload": {"index": 1}, "auto_start": False}).status_code == 200
    assert client.post("/api/jobs", json={"kind": "readable_draft", "payload": {"index": 2}, "auto_start": False}).status_code == 200

    response = client.post("/api/jobs", json={"kind": "readable_draft", "payload": {"index": 3}, "auto_start": False})

    assert response.status_code == 429
    assert "2/2" in response.json()["detail"]


def test_cloud_writer_jobs_check_project_owner_and_llm_quota(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client_a, payload_a = _register_cloud_member("WRITER-JOB-A", "writer-job-a@example.test", "writer_job_a")
    client_b, _payload_b = _register_cloud_member("WRITER-JOB-B", "writer-job-b@example.test", "writer_job_b")

    raw_item = client_a.post(
        "/api/v2/collect/raw-file",
        json={"material_type": "text", "title": "A Job Source", "note": "", "markdown": "# A Job Source\n\nBody", "source": "manual"},
    ).json()["data"]["item"]
    project = client_a.post(
        "/api/v2/create/projects",
        json={"name": "A Job Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]
    attach = client_a.post(
        f"/api/v2/create/projects/{project['id']}/library-files",
        json={"files": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}]},
    )
    assert attach.status_code == 200

    other_owner_job = client_b.post("/api/jobs", json={"kind": "writer_topics", "payload": {"project_id": project["id"]}})
    assert other_owner_job.status_code == 404

    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'llm_generate_daily', ?, 50)
            """,
            (payload_a["user"]["id"], payload_a["workspace"]["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    quota_blocked = client_a.post("/api/jobs", json={"kind": "writer_topics", "payload": {"project_id": project["id"]}})
    assert quota_blocked.status_code == 429
    assert "50/50" in quota_blocked.json()["detail"]


def test_cloud_learn_refine_job_checks_raw_owner_and_llm_quota(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client_a, payload_a = _register_cloud_member("LEARN-JOB-A", "learn-job-a@example.test", "learn_job_a")
    client_b, _payload_b = _register_cloud_member("LEARN-JOB-B", "learn-job-b@example.test", "learn_job_b")

    raw_item = client_a.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Private Learn Source",
            "note": "",
            "markdown": "# Private Learn Source\n\nprivate body",
            "source": "manual",
        },
    ).json()["data"]["item"]

    blocked = client_b.post("/api/jobs", json={"kind": "learn_refine", "payload": {"raw_paths": [raw_item["markdown_path"]]}})
    assert blocked.status_code == 404

    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'llm_generate_daily', ?, 50)
            """,
            (payload_a["user"]["id"], payload_a["workspace"]["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("model call should be blocked by job quota")

    monkeypatch.setattr(api_v2.deepseek_client, "generate_knowledge_from_text", fail_if_called)
    quota_blocked = client_a.post("/api/jobs", json={"kind": "learn_refine", "payload": {"raw_paths": [raw_item["markdown_path"]]}})
    assert quota_blocked.status_code == 429
    assert "50/50" in quota_blocked.json()["detail"]


def test_cloud_mine_interpret_job_checks_source_owner_and_llm_quota(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client_a, payload_a = _register_cloud_member("MINE-JOB-A", "mine-job-a@example.test", "mine_job_a")
    client_b, _payload_b = _register_cloud_member("MINE-JOB-B", "mine-job-b@example.test", "mine_job_b")

    raw_item = client_a.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Private Mine Source",
            "note": "",
            "markdown": "# Private Mine Source\n\nprivate mining body",
            "source": "manual",
        },
    ).json()["data"]["item"]
    perspective = client_a.get("/api/v2/mine/perspectives").json()["data"]["items"][0]
    payload = {
        "sources": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}],
        "perspective": perspective,
    }

    blocked = client_b.post("/api/jobs", json={"kind": "mine_interpret", "payload": payload})
    assert blocked.status_code == 404

    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'llm_generate_daily', ?, 50)
            """,
            (payload_a["user"]["id"], payload_a["workspace"]["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("model call should be blocked by job quota")

    monkeypatch.setattr(api_v2.deepseek_client, "interpret_from_perspective", fail_if_called)
    quota_blocked = client_a.post("/api/jobs", json={"kind": "mine_interpret", "payload": payload})
    assert quota_blocked.status_code == 429
    assert "50/50" in quota_blocked.json()["detail"]


def test_cloud_media_transcript_job_checks_owner(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client_a, _payload_a = _register_cloud_member("MEDIA-JOB-A", "media-job-a@example.test", "media_job_a")
    client_b, _payload_b = _register_cloud_member("MEDIA-JOB-B", "media-job-b@example.test", "media_job_b")

    uploaded = client_a.post(
        "/api/media/upload",
        files={"files": ("private.srt", b"1\n00:00:00,000 --> 00:00:01,000\nprivate transcript\n", "application/x-subrip")},
    )
    assert uploaded.status_code == 200
    media_id = uploaded.json()["items"][0]["id"]

    blocked = client_b.post("/api/jobs", json={"kind": "media_transcript", "payload": {"media_ids": [media_id]}})
    assert blocked.status_code == 404


def test_cloud_writer_image_job_checks_project_owner(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client_a, _payload_a = _register_cloud_member("IMAGE-JOB-A", "image-job-a@example.test", "image_job_a")
    client_b, _payload_b = _register_cloud_member("IMAGE-JOB-B", "image-job-b@example.test", "image_job_b")

    project = client_a.post(
        "/api/v2/create/projects",
        json={"name": "Private Image Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]

    blocked_batch = client_b.post(
        "/api/jobs",
        json={
            "kind": "image_generate",
            "payload": {"project_id": project["id"], "cover_prompt": "cover"},
        },
    )
    blocked_item = client_b.post(
        "/api/jobs",
        json={
            "kind": "writer_image_item",
            "payload": {"project_id": project["id"], "kind": "cover", "prompt": "cover"},
        },
    )

    assert blocked_batch.status_code == 404
    assert blocked_item.status_code == 404


def test_cloud_link_parse_daily_quota_blocks_after_limit(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client, payload = _register_cloud_member("LINK-QUOTA", "link-quota@example.test", "link_quota")
    user = payload["user"]
    workspace = payload["workspace"]
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'link_parse_daily', ?, 30)
            """,
            (user["id"], workspace["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    response = client.post("/api/v2/collect/inspect-link", json={"url": "https://example.com/article"})

    assert response.status_code == 429
    assert "30/30" in response.json()["detail"]


def test_cloud_llm_daily_quota_blocks_generation_before_model_call(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client, payload = _register_cloud_member("LLM-QUOTA", "llm-quota@example.test", "llm_quota")
    raw_item = client.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Quota Source",
            "note": "",
            "markdown": "# Quota Source\n\nThis source should not reach the model.",
            "source": "manual",
        },
    ).json()["data"]["item"]
    user = payload["user"]
    workspace = payload["workspace"]
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'llm_generate_daily', ?, 50)
            """,
            (user["id"], workspace["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("model call should be blocked by quota")

    monkeypatch.setattr(api_v2.deepseek_client, "generate_knowledge_from_text", fail_if_called)

    response = client.post(
        "/api/v2/learn/refine-knowledge-cluster",
        json={"raw_paths": [raw_item["markdown_path"]], "title": "Quota Focus"},
    )

    assert response.status_code == 429
    assert "50/50" in response.json()["detail"]


def test_cloud_quota_status_reports_member_usage_without_paths(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client, payload = _register_cloud_member("QUOTA-STATUS", "quota-status@example.test", "quota_status")
    user = payload["user"]
    workspace = payload["workspace"]
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, 'link_parse_daily', ?, 7)
            """,
            (user["id"], workspace["id"], api_v2.quota_service.today_key()),
        )
        conn.commit()

    response = client.get("/api/v2/quotas/me")

    assert response.status_code == 200
    quota = response.json()["data"]
    assert quota["deploymentMode"] == "cloud"
    assert quota["enforced"] is True
    assert quota["daily"]["link_parse_daily"]["used"] == 7
    assert quota["daily"]["link_parse_daily"]["limit"] == 30
    assert quota["uploads"]["single_upload_bytes"]["limit"] == 100 * 1024 * 1024
    assert "path" not in str(quota).lower()


def test_cloud_member_settings_are_redacted(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setattr(
        legacy_app.media_parser,
        "bilibili_cookie_status",
        lambda: {
            "ok": True,
            "exists": True,
            "path": "E:/Invest/FigureLearning/auth/bilibili.cookies.txt",
            "cookie_count": 3,
            "has_sessdata": True,
            "has_dedeuserid": True,
            "has_bili_jct": True,
            "message": "Cookie file is ready",
        },
    )
    storage.init_storage()
    with storage.connect() as conn:
        conn.execute(
            """
            INSERT INTO invitations (
                id, code, role, max_uses, used_count, expires_at, created_at, status
            ) VALUES ('invite-member-redact', 'MEMBER-REDACT', 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
            """
        )
        conn.commit()

    client = TestClient(create_app(), base_url="http://testserver")
    register_response = client.post(
        "/api/auth/register-with-invite",
        json={
            "invite_code": "MEMBER-REDACT",
            "email": "member@example.test",
            "username": "member_user",
            "password": "password-123",
        },
    )
    assert register_response.status_code == 200

    settings_response = client.get("/api/workbench-settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["storage_locations"] == {}
    assert settings_response.json()["local_diagnostics_visible"] is False

    cookie_response = client.get("/api/media/bilibili-cookies")
    assert cookie_response.status_code == 200
    cookie_payload = cookie_response.json()
    assert cookie_payload["ok"] is True
    assert cookie_payload["mode"] == "cloud_redacted"
    assert "path" not in cookie_payload
    assert "bilibili.cookies.txt" not in str(cookie_payload)

    trash_response = client.get("/api/v2/settings/trash")
    assert trash_response.status_code == 200
    trash_payload = trash_response.json()["data"]
    assert trash_payload["path"] == ""
    assert trash_payload["items"] == []
    assert trash_payload["redacted"] is True
    assert client.delete("/api/v2/settings/trash").status_code == 403


def test_cloud_library_files_are_isolated_by_owner(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    storage.init_storage()
    with storage.connect() as conn:
        for code in ("OWNER-A", "OWNER-B"):
            conn.execute(
                """
                INSERT INTO invitations (
                    id, code, role, max_uses, used_count, expires_at, created_at, status
                ) VALUES (?, ?, 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
                """,
                (f"invite-{code}", code),
            )
        conn.commit()

    client_a = TestClient(create_app(), base_url="http://testserver")
    client_b = TestClient(create_app(), base_url="http://testserver")
    assert client_a.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "OWNER-A", "email": "a@example.test", "username": "owner_a", "password": "password-123"},
    ).status_code == 200
    assert client_b.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "OWNER-B", "email": "b@example.test", "username": "owner_b", "password": "password-123"},
    ).status_code == 200

    create_response = client_a.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "A Private Raw",
            "note": "",
            "markdown": "# A Private Raw\n\nOnly owner A can read this.",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200
    raw_item = create_response.json()["data"]["item"]
    markdown_path = raw_item["markdown_path"]

    a_list = client_a.get("/api/v2/libraries/raw/files").json()["data"]["items"]
    b_list = client_b.get("/api/v2/libraries/raw/files").json()["data"]["items"]
    assert any(item["markdown_path"] == markdown_path for item in a_list)
    assert all(item["markdown_path"] != markdown_path for item in b_list)

    assert client_a.get("/api/v2/libraries/raw/file", params={"markdown_path": markdown_path}).status_code == 200
    assert client_b.get("/api/v2/libraries/raw/file", params={"markdown_path": markdown_path}).status_code == 404


def test_cloud_focus_file_is_written_with_owner_and_filtered(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    storage.init_storage()
    with storage.connect() as conn:
        for code in ("FOCUS-A", "FOCUS-B"):
            conn.execute(
                """
                INSERT INTO invitations (
                    id, code, role, max_uses, used_count, expires_at, created_at, status
                ) VALUES (?, ?, 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
                """,
                (f"invite-{code}", code),
            )
        conn.commit()

    client_a = TestClient(create_app(), base_url="http://testserver")
    client_b = TestClient(create_app(), base_url="http://testserver")
    user_a = client_a.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "FOCUS-A", "email": "focus-a@example.test", "username": "focus_a", "password": "password-123"},
    ).json()["data"]["user"]
    assert client_b.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "FOCUS-B", "email": "focus-b@example.test", "username": "focus_b", "password": "password-123"},
    ).status_code == 200

    raw_item = client_a.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Focus Source",
            "note": "",
            "markdown": "# Focus Source\n\nsource body",
            "source": "manual",
        },
    ).json()["data"]["item"]
    focus_response = client_a.post(
        "/api/v2/learn/focus-file",
        json={
            "raw_paths": [raw_item["markdown_path"]],
            "markdown": "# Focus Private\n\n- 主题：隔离\n\nbody",
            "title": "Focus Private",
        },
    )
    assert focus_response.status_code == 200
    focus_item = focus_response.json()["data"]["item"]
    assert focus_item["owner_user_id"] == user_a["id"]
    focus_path = focus_item["markdown_path"]

    a_focus = client_a.get("/api/v2/libraries/focus/files").json()["data"]["items"]
    b_focus = client_b.get("/api/v2/libraries/focus/files").json()["data"]["items"]
    assert any(item["markdown_path"] == focus_path for item in a_focus)
    assert all(item["markdown_path"] != focus_path for item in b_focus)
    assert client_b.get("/api/v2/libraries/focus/file", params={"markdown_path": focus_path}).status_code == 404


def test_cloud_perspective_profiles_are_isolated_by_owner(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    storage.init_storage()
    with storage.connect() as conn:
        for code in ("PROFILE-A", "PROFILE-B"):
            conn.execute(
                """
                INSERT INTO invitations (
                    id, code, role, max_uses, used_count, expires_at, created_at, status
                ) VALUES (?, ?, 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
                """,
                (f"invite-{code}", code),
            )
        conn.commit()

    client_a = TestClient(create_app(), base_url="http://testserver")
    client_b = TestClient(create_app(), base_url="http://testserver")
    assert client_a.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "PROFILE-A", "email": "profile-a@example.test", "username": "profile_a", "password": "password-123"},
    ).status_code == 200
    assert client_b.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "PROFILE-B", "email": "profile-b@example.test", "username": "profile_b", "password": "password-123"},
    ).status_code == 200

    saved = client_a.post(
        "/api/v2/mine/perspectives",
        json={
            "name": "A Private Perspective",
            "positioning": "owner A",
            "core_goal": "private analysis",
            "stance": "private",
        },
    ).json()["data"]["item"]

    a_profiles = client_a.get("/api/v2/mine/perspectives").json()["data"]["items"]
    b_profiles = client_b.get("/api/v2/mine/perspectives").json()["data"]["items"]
    assert any(item["id"] == saved["id"] for item in a_profiles)
    assert all(item["id"] != saved["id"] for item in b_profiles)


def test_cloud_writer_projects_are_isolated_and_library_files_checked(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    storage.init_storage()
    with storage.connect() as conn:
        for code in ("WRITER-A", "WRITER-B"):
            conn.execute(
                """
                INSERT INTO invitations (
                    id, code, role, max_uses, used_count, expires_at, created_at, status
                ) VALUES (?, ?, 'member', 1, 0, NULL, '2026-01-01T00:00:00', 'active')
                """,
                (f"invite-{code}", code),
            )
        conn.commit()

    client_a = TestClient(create_app(), base_url="http://testserver")
    client_b = TestClient(create_app(), base_url="http://testserver")
    assert client_a.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "WRITER-A", "email": "writer-a@example.test", "username": "writer_a", "password": "password-123"},
    ).status_code == 200
    assert client_b.post(
        "/api/auth/register-with-invite",
        json={"invite_code": "WRITER-B", "email": "writer-b@example.test", "username": "writer_b", "password": "password-123"},
    ).status_code == 200

    raw_item = client_a.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Writer Private Raw",
            "note": "",
            "markdown": "# Writer Private Raw\n\nOnly writer A.",
            "source": "manual",
        },
    ).json()["data"]["item"]
    project_a = client_a.post(
        "/api/v2/create/projects",
        json={"name": "A Private Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]
    project_b = client_b.post(
        "/api/v2/create/projects",
        json={"name": "B Project", "project_type": "article", "description": ""},
    ).json()["data"]["item"]

    a_projects = client_a.get("/api/v2/create/projects").json()["data"]["items"]
    b_projects = client_b.get("/api/v2/create/projects").json()["data"]["items"]
    assert any(item["id"] == project_a["id"] for item in a_projects)
    assert all(item["id"] != project_a["id"] for item in b_projects)
    assert client_b.get(f"/api/v2/create/projects/{project_a['id']}").status_code == 404

    attach_response = client_b.post(
        f"/api/v2/create/projects/{project_b['id']}/library-files",
        json={"files": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}]},
    )
    assert attach_response.status_code == 404


def test_v2_cloud_member_cannot_operate_wechat_publish_tools(monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    client, _payload = _register_cloud_member("V2-PUBLISH-TOOLS", "v2-publish@example.test", "v2_publish")

    def forbidden_call(*args, **kwargs):
        raise AssertionError("publish tool should not be called for cloud members")

    monkeypatch.setattr(api_v2.writer_tools, "publish_preflight", forbidden_call)
    monkeypatch.setattr(api_v2.writer_tools, "publish_draft", forbidden_call)

    project = client.post(
        "/api/v2/create/projects",
        json={"name": "V2 发布权限项目", "project_type": "article", "description": ""},
    ).json()["data"]["item"]

    preflight = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/publish/preflight",
        json={"title": "标题", "author": "Bobo"},
    )
    publish = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/publish",
        json={"title": "标题", "author": "Bobo"},
    )
    preflight_job = client.post(
        "/api/jobs",
        json={"kind": "publish_preflight", "payload": {"project_id": project["id"], "title": "标题"}},
    )

    assert preflight.status_code == 403
    assert publish.status_code == 403
    assert preflight_job.status_code == 403


def test_v2_settings_center_reads_and_saves_web_api_and_asr_settings():
    client = TestClient(create_app())

    web_response = client.post(
        "/api/v2/settings/web",
        json={
            "app_name": "知识酷测试",
            "workspace_name": "Research OS Test",
            "default_route": "/mine",
            "global_library_refresh_seconds": 12,
            "right_library_visible": True,
            "language": "zh-CN",
        },
    )
    assert web_response.status_code == 200
    assert web_response.json()["data"]["item"]["default_route"] == "/mine"
    assert client.get("/api/v2/settings/web").json()["data"]["item"]["app_name"] == "知识酷测试"

    api_response = client.post(
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
    assert api_response.status_code == 200
    api_payload = api_response.json()["data"]
    assert api_payload["ok"] is True, api_payload
    assert api_payload["item"]["api_key_masked"] == "sk-t...cret"
    assert "sk-test-secret" not in str(api_payload)
    assert api_payload["active_id"] == api_payload["item"]["id"]

    asr_response = client.post(
        "/api/v2/settings/asr",
        json={
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "whisper-1",
            "api_key": "asr-secret-key",
            "timeout": 120,
        },
    )
    assert asr_response.status_code == 200
    asr_payload = asr_response.json()["data"]
    assert asr_payload["ok"] is True, asr_payload
    assert asr_payload["item"]["configured"] is True
    assert "asr-secret-key" not in str(asr_payload)


def test_v2_create_article_project_uses_library_files_and_writer_flow(monkeypatch):
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key", "model": "test-model"})

    def fake_topics(markdown_files, setting=None):
        assert markdown_files[0][0].endswith(".md")
        assert "project source body" in markdown_files[0][1]
        return TopicSuggestionsResult(
            suggestions=[
                TopicSuggestion(
                    title="Project Topic",
                    angle="project angle",
                    reason="project reason",
                    reader_pain_point="reader pain",
                    material_basis="source basis",
                )
            ]
        )

    def fake_article(topic, markdown_files, setting=None):
        assert topic["title"] == "Project Topic"
        assert setting["model"] == "test-model"
        return WriterArticleResult(
            title="Project Article",
            markdown="# Project Article\n\nBody",
            cover_prompt="cover prompt",
            content_image_prompts=[],
            digest="digest",
        )

    def fake_revise(markdown, instruction, markdown_files, setting=None):
        assert instruction == "make it sharper"
        return WriterRevisionResult(markdown="# Project Article Revised\n\nBody", change_summary="revised")

    monkeypatch.setattr(api_v2.deepseek_client, "generate_topics", fake_topics)
    monkeypatch.setattr(api_v2.deepseek_client, "generate_wechat_article", fake_article)
    monkeypatch.setattr(api_v2.deepseek_client, "revise_wechat_article", fake_revise)

    def fake_format(workspace, markdown=None, theme="tech"):
        path = workspace / "formatted.html"
        path.write_text("<html><body>formatted project</body></html>", encoding="utf-8")
        if markdown is not None:
            api_v2.writer_tools.write_article(workspace, markdown)
        return {"path": str(path.relative_to(storage.ROOT)), "html": path.read_text(encoding="utf-8")}

    monkeypatch.setattr(api_v2.writer_tools, "format_article", fake_format)
    monkeypatch.setattr(
        api_v2.writer_tools,
        "publish_preflight",
        lambda *args, **kwargs: {
            "ok": True,
            "checks": [{"key": "html", "label": "HTML", "ok": True, "detail": "formatted.html"}],
            "blocking": [],
        },
    )
    monkeypatch.setattr(
        api_v2.writer_tools,
        "publish_draft",
        lambda *args, **kwargs: {"media_id": "project-draft-media-id", "path": "writer/projects/publish_result.json"},
    )
    client = TestClient(create_app())

    raw_response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "text",
            "title": "Project Raw",
            "items": [{"content": "project source body", "title": "Project Raw"}],
        },
    )
    raw_item = raw_response.json()["data"]["item"]

    project_response = client.post(
        "/api/v2/create/projects",
        json={"name": "Article Project", "project_type": "article", "description": "draft workspace"},
    )
    assert project_response.status_code == 200
    project = project_response.json()["data"]["item"]
    assert project["type"] == "article"
    assert project["workspace"].startswith("writer")

    settings_response = client.patch(
        f"/api/v2/create/projects/{project['id']}",
        json={"name": "Article Project Renamed", "project_type": "article", "description": "saved settings"},
    )
    assert settings_response.status_code == 200
    project = settings_response.json()["data"]["item"]
    assert project["name"] == "Article Project Renamed"
    assert project["description"] == "saved settings"

    files_response = client.post(
        f"/api/v2/create/projects/{project['id']}/library-files",
        json={"files": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}]},
    )
    assert files_response.status_code == 200
    assert files_response.json()["data"]["item"]["library_files"][0]["markdown_path"] == raw_item["markdown_path"]

    topics_response = client.post(f"/api/v2/create/projects/{project['id']}/writer/topics", json={})
    assert topics_response.status_code == 200
    topic = topics_response.json()["data"]["suggestions"][0]
    assert topic["title"] == "Project Topic"

    article_response = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/article",
        json={"topic": topic},
    )
    assert article_response.status_code == 200
    article_payload = article_response.json()["data"]
    assert article_payload["markdown"].startswith("# Project Article")
    assert (storage.ROOT / article_payload["article_path"]).exists()

    revise_response = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/revise",
        json={"markdown": article_payload["markdown"], "instruction": "make it sharper"},
    )
    assert revise_response.status_code == 200
    assert revise_response.json()["data"]["markdown"].startswith("# Project Article Revised")

    format_response = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/format",
        json={"markdown": revise_response.json()["data"]["markdown"], "theme": "tech"},
    )
    assert format_response.status_code == 200
    assert format_response.json()["data"]["html"].startswith("<html>")

    preflight_response = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/publish/preflight",
        json={"title": "Project Article", "author": "Bobo"},
    )
    assert preflight_response.status_code == 200
    assert preflight_response.json()["data"]["ok"] is True

    publish_response = client.post(
        f"/api/v2/create/projects/{project['id']}/writer/publish",
        json={"title": "Project Article", "author": "Bobo"},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["data"]["media_id"] == "project-draft-media-id"

    loaded = client.get(f"/api/v2/create/projects/{project['id']}")
    assert loaded.json()["data"]["item"]["article_markdown"].startswith("# Project Article Revised")
    assert loaded.json()["data"]["item"]["html"].startswith("<html>")


def test_v2_raw_library_lists_saved_raw_markdown_files():
    client = TestClient(create_app())
    title = "Library Refresh Raw Fixture"
    create_response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "text",
            "title": title,
            "items": [{"content": "library refresh raw body", "title": title}],
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]["item"]

    response = client.get("/api/v2/libraries/raw/files")

    assert response.status_code == 200
    payload = response.json()
    items = payload["data"]["items"]
    match = next(item for item in items if item["markdown_path"] == created["markdown_path"])
    assert match["title"] == title
    assert match["library"] == "raw"
    assert match["markdown_path"] == created["markdown_path"]
    assert match["source"]


def test_v2_library_file_reads_and_updates_raw_markdown():
    client = TestClient(create_app())
    create_response = client.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Editable Raw Fixture",
            "note": "initial note",
            "markdown": "# Editable Raw Fixture\n\nEditable raw body.",
            "source": "editable-raw-source",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]["item"]
    windows_path = created["markdown_path"].replace("/", "\\")

    read_response = client.get("/api/v2/libraries/raw/file", params={"markdown_path": windows_path})

    assert read_response.status_code == 200
    read_payload = read_response.json()["data"]
    assert read_payload["item"]["markdown_path"] == created["markdown_path"]
    assert "Editable raw body." in read_payload["markdown"]

    update_response = client.post(
        "/api/v2/libraries/raw/file",
        params={"markdown_path": windows_path},
        json={"title": "Edited Raw Fixture", "note": "edited note", "markdown": "# Old Title\n\nEdited raw body."},
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()["data"]
    assert update_payload["ok"] is True
    assert update_payload["item"]["title"] == "Edited Raw Fixture"
    assert update_payload["item"]["note"] == "edited note"
    text = (storage.ROOT / created["markdown_path"]).read_text(encoding="utf-8")
    assert "# Edited Raw Fixture" in text
    assert "- 人工备注：edited note" in text
    assert "Edited raw body." in text


def test_v2_library_file_delete_moves_all_libraries_to_trash():
    client = TestClient(create_app())
    client.delete("/api/v2/settings/trash")
    fixtures = [
        ("raw", storage.RAW_MATERIAL_DIR, "raw-delete.md"),
        ("focus", storage.KNOWLEDGE_DIR, "focus-delete.md"),
        ("perspective", storage.MINING_DIR, "perspective-delete.md"),
    ]
    markdown_paths: list[tuple[str, str, Path]] = []
    for library_id, root, filename in fixtures:
        path = root / "2026-06-07" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {filename}\n\nDelete body.", encoding="utf-8")
        markdown_paths.append((library_id, storage.storage_relative(path), path))

    for library_id, markdown_path, path in markdown_paths:
        response = client.delete(f"/api/v2/libraries/{library_id}/file", params={"markdown_path": markdown_path})

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["ok"] is True
        assert not path.exists()
        trash_path = Path(payload["item"]["trash_path"])
        assert (storage.STORAGE_ROOT / trash_path).exists()
        list_response = client.get(f"/api/v2/libraries/{library_id}/files")
        listed_paths = {item["markdown_path"] for item in list_response.json()["data"]["items"]}
        assert markdown_path not in listed_paths

    status = client.get("/api/v2/settings/trash").json()["data"]
    assert status["file_count"] == 3
    assert len(status["items"]) == 3

    raw_trash_item = next(item for item in status["items"] if item["library"] == "raw")
    restored_path = markdown_paths[0][1]
    restore_response = client.post(
        "/api/v2/settings/trash/restore",
        json={"trash_paths": [raw_trash_item["trash_path"]]},
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["data"]["restored"]
    assert (storage.STORAGE_ROOT / restored_path).exists()

    status = client.get("/api/v2/settings/trash").json()["data"]
    delete_response = client.post(
        "/api/v2/settings/trash/delete",
        json={"trash_paths": [status["items"][0]["trash_path"]]},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["deleted"]

    status = client.get("/api/v2/settings/trash").json()["data"]
    assert status["file_count"] == 1
    clear_response = client.delete("/api/v2/settings/trash")
    assert clear_response.status_code == 200
    cleared = clear_response.json()["data"]
    assert cleared["deleted_files"] == 1
    assert cleared["file_count"] == 0
    assert not any(storage.TRASH_DIR.rglob("*.*"))


def test_v2_collect_raw_file_saves_markdown_and_manual_note():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-file",
        json={
            "material_type": "text",
            "title": "Readable Raw Fixture",
            "note": "manual note for original file",
            "markdown": "# Readable Raw Fixture\n\nCollected readable body.",
            "source": "collect-readable-fixture",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is True, payload
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "# Readable Raw Fixture" in text
    assert "Collected readable body." in text
    assert "manual note for original file" in text
    assert item["source"] == "collect-readable-fixture"


def test_v2_collect_readable_draft_extracts_web_link_before_save(monkeypatch):
    monkeypatch.setattr(
        api_v2,
        "_extract_link_text",
        lambda url, item: {
            "title": "Readable Link Fixture",
            "text": "Readable link body",
            "source": "Example Source",
            "author": "Fixture Author",
            "published_at": "2026-06-05",
            "link_type": "public_webpage",
            "access_status": "accessible",
            "extraction_strategy": "direct_fetch",
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "web_link",
            "title": "",
            "items": [
                {
                    "url": "https://example.com/article",
                    "title": "Example Article",
                    "link_type": "public_webpage",
                    "extraction_strategy": "direct_fetch",
                    "access_status": "accessible",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True
    assert payload["title"] == "Example Article"
    assert "Readable link body" in payload["markdown"]
    assert "Example Source" in payload["markdown"]
    assert payload["source"] == "https://example.com/article"


def test_v2_focus_library_lists_files_outside_repo_root(monkeypatch, tmp_path):
    external_root = tmp_path / "external-runtime"
    monkeypatch.setattr(storage, "STORAGE_ROOT", external_root)
    monkeypatch.setattr(storage, "IMAGE_DIR", external_root / "images")
    monkeypatch.setattr(storage, "DOCUMENT_DIR", external_root / "documents")
    monkeypatch.setattr(storage, "KNOWLEDGE_DIR", external_root / "knowledge")
    monkeypatch.setattr(storage, "MEDIA_DIR", external_root / "media")
    monkeypatch.setattr(storage, "MINING_DIR", external_root / "mining")
    storage.init_storage()

    dated_dir = storage.KNOWLEDGE_DIR / "2026-06-05"
    dated_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = dated_dir / "external_focus_fixture.md"
    markdown_path.write_text(
        "# External Focus Fixture\n\n- 状态: 已提炼\n\nFocus body.",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/v2/libraries/focus/files")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    match = next(item for item in items if item["title"] == "External Focus Fixture")
    assert match["library"] == "focus"
    assert match["markdown_path"].endswith("knowledge\\2026-06-05\\external_focus_fixture.md")

    read_response = client.get(
        "/api/v2/libraries/focus/file",
        params={"markdown_path": match["markdown_path"]},
    )

    assert read_response.status_code == 200
    payload = read_response.json()["data"]
    assert payload["item"]["title"] == "External Focus Fixture"
    assert "Focus body." in payload["markdown"]

    save_response = client.post(
        "/api/v2/libraries/focus/file",
        params={"markdown_path": match["markdown_path"]},
        json={
            "title": "External Focus Fixture Edited",
            "note": "edited note",
            "markdown": "# External Focus Fixture\n\nEdited focus body.",
        },
    )

    assert save_response.status_code == 200
    save_payload = save_response.json()["data"]
    assert save_payload["ok"] is True
    assert save_payload["item"]["title"] == "External Focus Fixture Edited"
    assert "Edited focus body." in markdown_path.read_text(encoding="utf-8")


def test_v2_learn_refines_then_saves_focus_markdown_from_raw_library(monkeypatch):
    def fake_generate_knowledge_from_text(raw_text: str, setting=None):
        assert "raw source body for learning" in raw_text
        return (
            KnowledgeResult(
                title="Focus Cluster Fixture",
                topic="raw learning topic",
                tags=["学习", "原料"],
                focus_question="这份原料的核心知识是什么？",
                clusters=[
                    KnowledgeCluster(
                        name="原料到重点库",
                        domain="知识处理",
                        occurrence_count=1,
                        meaning="从原料文件提取结构化知识簇。",
                        key_information=["保留原文引用入口", "保存到重点库"],
                    )
                ],
                investment_insights="暂无",
            ),
            raw_text,
        )

    monkeypatch.setattr(api_v2.deepseek_client, "generate_knowledge_from_text", fake_generate_knowledge_from_text)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    client = TestClient(create_app())
    raw_response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "text",
            "title": "Raw Learn Fixture",
            "items": [{"content": "raw source body for learning", "title": "Raw Learn Fixture"}],
        },
    )
    raw_item = raw_response.json()["data"]["item"]

    response = client.post(
        "/api/v2/learn/refine-knowledge-cluster",
        json={"raw_paths": [raw_item["markdown_path"]]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is True, payload
    markdown = payload["data"]["markdown"]
    assert "Focus Cluster Fixture" in markdown
    assert "原文引用" in markdown
    assert raw_item["markdown_path"] in markdown
    assert "raw source body for learning" not in markdown

    pending_before_save = client.get("/api/v2/libraries/raw/files?pending_focus=true").json()["data"]["items"]
    assert any(file["markdown_path"] == raw_item["markdown_path"] for file in pending_before_save)

    save_response = client.post(
        "/api/v2/learn/focus-file",
        json={"raw_paths": [raw_item["markdown_path"]], "markdown": markdown},
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["data"]["ok"] is True, saved
    item = saved["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    text = path.read_text(encoding="utf-8")
    assert item["title"] == "Focus Cluster Fixture"
    assert item["status"] == "ready"
    assert item["source_type"] == "raw_materials"
    assert raw_item["markdown_path"] in json.loads(item["source_ids"])
    assert "Focus Cluster Fixture" in text
    assert "原文引用" in text
    assert "raw source body for learning" not in text
    assert "原料到重点库" in text

    focus_response = client.get("/api/v2/libraries/focus/files")
    focus_items = focus_response.json()["data"]["items"]
    assert any(file["markdown_path"] == item["markdown_path"] for file in focus_items)

    pending_after_save = client.get("/api/v2/libraries/raw/files?pending_focus=true").json()["data"]["items"]
    assert all(file["markdown_path"] != raw_item["markdown_path"] for file in pending_after_save)


def test_v2_mine_perspectives_expose_structured_profiles():
    client = TestClient(create_app())

    response = client.get("/api/v2/mine/perspectives")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    writer = next(item for item in items if item["id"] == "writer")
    assert writer["name"] == "作家视角"
    assert writer["target_subject"]
    assert writer["purpose"]
    assert writer["focus_dimensions"]
    assert writer["analysis_questions"]
    assert writer["evidence_rule"]


def test_v2_mine_perspectives_can_save_and_delete_custom_profile():
    client = TestClient(create_app())
    profile = {
        "id": "custom_test_writer",
        "name": "自定义作家视角",
        "role": "观察材料的叙事推进",
        "target_subject": "原文结构和表达节奏",
        "purpose": "沉淀可复用写法",
        "focus_dimensions": ["叙事结构", "表达节奏"],
        "analysis_questions": ["材料如何推进观点？"],
        "output_style": "写作备忘录",
        "evidence_rule": "每条判断引用 S1/S2",
    }

    save_response = client.post("/api/v2/mine/perspectives", json=profile)

    assert save_response.status_code == 200
    saved = save_response.json()["data"]
    assert saved["ok"] is True, saved
    assert saved["item"]["id"] == "custom_test_writer"
    assert saved["item"]["origin"] == "custom"

    items = client.get("/api/v2/mine/perspectives").json()["data"]["items"]
    custom = next(item for item in items if item["id"] == "custom_test_writer")
    assert custom["focus_dimensions"] == ["叙事结构", "表达节奏"]
    assert any(item["id"] == "writer" and item["origin"] == "preset" for item in items)

    delete_response = client.delete("/api/v2/mine/perspectives/custom_test_writer")

    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["ok"] is True
    after_delete = client.get("/api/v2/mine/perspectives").json()["data"]["items"]
    assert all(item["id"] != "custom_test_writer" for item in after_delete)


def test_v2_mine_interprets_raw_library_queue_and_saves_perspective_file(monkeypatch):
    def fake_interpret(material_blocks, perspective, setting=None):
        assert material_blocks[0]["library"] == "raw"
        assert "raw material for mining" in material_blocks[0]["text"]
        assert perspective["name"] == "作家视角"
        assert "文字组织逻辑" in perspective["focus_dimensions"]
        return PerspectiveInterpretationResult(
            title="作家视角：材料叙事节奏",
            perspective_name="作家视角",
            tags=["作家视角", "创作逻辑"],
            summary="材料用事实推进观点。",
            findings=[
                PerspectiveFinding(
                    dimension="文字组织逻辑",
                    interpretation="材料先交代事实，再转向判断，适合后续创作引用。",
                    evidence_refs=["S1"],
                )
            ],
            writing_implications=["可以复用先事实后判断的段落结构。"],
            risks_and_limits=["只有单一来源，不能扩大判断。"],
        )

    monkeypatch.setattr(api_v2.deepseek_client, "interpret_from_perspective", fake_interpret)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    client = TestClient(create_app())
    raw_response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "text",
            "title": "Mine Raw Fixture",
            "items": [{"content": "raw material for mining", "title": "Mine Raw Fixture"}],
        },
    )
    raw_item = raw_response.json()["data"]["item"]
    perspective = client.get("/api/v2/mine/perspectives").json()["data"]["items"][0]

    interpret_response = client.post(
        "/api/v2/mine/interpret",
        json={
            "sources": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}],
            "perspective": perspective,
        },
    )

    assert interpret_response.status_code == 200
    interpreted = interpret_response.json()["data"]
    assert interpreted["ok"] is True, interpreted
    markdown = interpreted["markdown"]
    assert "作家视角：材料叙事节奏" in markdown
    assert "文字组织逻辑" in markdown
    assert raw_item["markdown_path"] in markdown
    assert "raw material for mining" not in markdown
    assert "## 视角设定" not in markdown
    assert "## RTFC 解读规范" not in markdown
    assert "## 固定五段式结构" not in markdown
    assert "## 旧版兼容字段" not in markdown

    save_response = client.post(
        "/api/v2/mine/perspective-file",
        json={
            "sources": [{"library": "raw", "markdown_path": raw_item["markdown_path"], "title": raw_item["title"]}],
            "perspective": perspective,
            "markdown": markdown,
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()["data"]
    assert saved["ok"] is True, saved
    item = saved["item"]
    assert item["library"] == "perspective"
    assert item["status"] == "已解读"
    path = storage.ROOT / item["markdown_path"]
    assert path.exists()
    assert "作家视角" in path.read_text(encoding="utf-8")

    perspective_items = client.get("/api/v2/libraries/perspective/files").json()["data"]["items"]
    assert any(file["markdown_path"] == item["markdown_path"] for file in perspective_items)


def test_v2_collect_text_saves_raw_markdown():
    client = TestClient(create_app())

    response = client.post("/api/v2/collect/text", json={"content": "raw observation\nwithout summary"})

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert payload["data"]["ok"] is True
    assert item["material_type"] == "text"
    assert path.exists()
    assert "raw observation" in path.read_text(encoding="utf-8")


def test_v2_collect_web_link_persists_url_even_when_fetch_fails():
    client = TestClient(create_app())

    response = client.post("/api/v2/collect/web-link", json={"url": "https://127.0.0.1:1/unavailable"})

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert payload["data"]["ok"] is True
    assert item["material_type"] == "web_link"
    assert path.exists()
    assert "https://127.0.0.1:1/unavailable" in path.read_text(encoding="utf-8")


def test_v2_collect_inspect_link_classifies_special_platforms():
    client = TestClient(create_app())

    response = client.post("/api/v2/collect/inspect-link", json={"url": "https://mp.weixin.qq.com/s/example"})

    assert response.status_code == 200
    item = response.json()["data"]["item"]
    assert item["link_type"] == "platform_wechat"
    assert item["access_status"] == "needs_specialized_extractor"
    assert item["extraction_strategy"] == "specialized_tool_or_browser"


def test_v2_collect_browser_extract_link_returns_readable_markdown(monkeypatch):
    def fake_inspect(url: str) -> dict[str, object]:
        return {
            "url": url,
            "final_url": url,
            "title": "Browser Article",
            "link_type": "public_webpage",
            "access_status": "accessible",
            "extraction_strategy": "direct_fetch",
            "source": "example.test",
        }

    def fake_browser_extract(**kwargs) -> dict[str, str]:
        assert kwargs["wait_ms"] == 3000
        assert kwargs["scroll_times"] == 5
        return {
            "title": "Browser Article",
            "text": "browser extracted paragraph " * 8,
            "source": "example.test",
            "author": "Author",
            "published_at": "2026-06-09",
            "link_type": "browser_webpage",
            "access_status": "accessible",
            "extraction_strategy": "browser_automation_wait_scroll",
        }

    monkeypatch.setattr(api_v2, "_inspect_link", fake_inspect)
    monkeypatch.setattr(api_v2, "_browser_extract_webpage_text", fake_browser_extract)
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/browser-extract-link",
        json={"url": "https://example.test/article", "title": "Manual Title"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True
    assert payload["title"] == "Manual Title"
    assert "Extraction Strategy: browser_automation_wait_scroll" in payload["markdown"]
    assert "browser extracted paragraph" in payload["markdown"]


def test_v2_collect_inspect_link_keeps_public_article_with_login_nav_accessible(monkeypatch):
    article = "\n".join(f"公共政策正文段落 {index}，这里是可以直接读取的公开网页内容。" for index in range(60))
    html = f"""
    <html>
      <head>
        <title>公开政策文章_中国政府网</title>
        <script>window.loginUrl = "/login";</script>
      </head>
      <body>
        <nav><a href="/login">登录</a></nav>
        <main>
          <h1>公开政策文章</h1>
          <p>{article}</p>
        </main>
      </body>
    </html>
    """

    def fake_fetch_url_bytes(url: str, max_bytes: int) -> dict[str, object]:
        return {
            "body": html.encode("utf-8"),
            "content_type": "text/html; charset=utf-8",
            "final_url": url,
        }

    monkeypatch.setattr(api_v2, "_fetch_url_bytes", fake_fetch_url_bytes)
    monkeypatch.setattr(
        api_v2,
        "_polish_raw_material",
        lambda material_type, body, title: {"markdown": body, "title": title, "response": {"status": "skipped"}},
    )
    client = TestClient(create_app())

    response = client.post("/api/v2/collect/inspect-link", json={"url": "https://www.gov.cn/example.htm"})

    assert response.status_code == 200
    item = response.json()["data"]["item"]
    assert item["link_type"] == "public_webpage"
    assert item["access_status"] == "accessible"
    assert item["extraction_strategy"] == "direct_fetch"

    fetched = api_v2._extract_link_text(
        "https://www.gov.cn/example.htm",
        api_v2.CollectQueueItem(url="https://www.gov.cn/example.htm", title=""),
    )
    assert fetched["access_status"] == "accessible"
    assert "公共政策正文段落 59" in fetched["text"]

    draft = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "web_link",
            "items": [{"url": "https://www.gov.cn/example.htm", "title": "公开政策文章"}],
        },
    )
    draft_payload = draft.json()["data"]
    assert draft.status_code == 200
    assert draft_payload["ok"] is True
    assert "Access Status: accessible" in draft_payload["markdown"]
    assert "公共政策正文段落 59" in draft_payload["markdown"]
    assert "登录墙" not in draft_payload["markdown"]


def test_v2_collect_raw_markdown_extracts_wechat_with_browser_payload(monkeypatch):
    def fake_browser_payload(url: str) -> dict[str, object]:
        return {
            "url": url,
            "title": "Wechat Article Title",
            "account_name": "Test Account",
            "author": "Author A",
            "published_at": "2026-06-02",
            "summary": "short summary",
            "content": "wechat paragraph one\nwechat paragraph two with enough content for extraction validation",
        }

    monkeypatch.setattr(api_v2, "_browser_extract_article_payload", fake_browser_payload)
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "web_link",
            "title": "wechat-correct-link-test",
            "items": [{"url": "https://mp.weixin.qq.com/s/example", "title": "temporary queue label"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    text = path.read_text(encoding="utf-8")
    assert payload["data"]["ok"] is True
    assert item["title"] == "Wechat Article Title"
    assert item["material_type"] == "web_link"
    assert path.name.startswith("Wechat_Article_Title_")
    assert "## Wechat Article Title" in text
    assert "Wechat Article Title" in text
    assert "Test Account" in text
    assert "Author A" in text
    assert "wechat paragraph one" in text
    assert "browser_harness_wechat_dom" in text


def test_v2_collect_raw_markdown_rejects_douyin_from_web_link_queue():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "web_link",
            "title": "douyin-test",
            "items": [{"url": "https://v.douyin.com/hdsMHiD-gSw/", "title": "douyin temporary"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is False
    assert "音视频" in payload["data"]["error"]
    assert "普通网页链接" in payload["data"]["error"]


def test_v2_collect_raw_markdown_merges_text_queue_into_one_file():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={
            "material_type": "text",
            "items": [
                {"content": "first raw paragraph", "title": "first"},
                {"content": "second raw paragraph", "title": "second"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert payload["data"]["ok"] is True
    assert item["material_type"] == "text"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "first raw paragraph" in text
    assert "second raw paragraph" in text


def test_v2_collect_raw_markdown_polishes_screenshot_title_and_body(monkeypatch):
    def fake_ocr(image_paths):
        assert image_paths
        return "OCR noise\\nAI算力的超级周期正在展开\\n重复按钮 文末广告"

    def fake_polish(raw_text: str, material_type: str = "raw", setting=None):
        assert material_type == "screenshot"
        assert "AI算力" in raw_text
        return RawMaterialPolishResult(
            title="AI算力超级周期",
            markdown="# AI算力超级周期\n\nAI算力的超级周期正在展开。",
        )

    monkeypatch.setattr(api_v2.ocr_client, "recognize_screenshots", fake_ocr)
    monkeypatch.setattr(api_v2.deepseek_client, "polish_raw_material", fake_polish)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    screenshot = storage.save_image_bytes(png, filename="clip.png", content_type="image/png")
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={"material_type": "screenshot", "items": [{"id": screenshot["id"], "title": "截图原料"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is True, payload
    assert payload["data"]["polish"]["status"] == "completed"
    item = payload["data"]["item"]
    assert item["title"] == "AI算力超级周期"
    assert "AI算力超级周期" in item["markdown_path"]
    text = (storage.ROOT / item["markdown_path"]).read_text(encoding="utf-8")
    assert "AI算力的超级周期正在展开" in text
    assert "文末广告" not in text


def test_v2_collect_readable_draft_strips_screenshot_wrappers_and_sorts_article(monkeypatch):
    ocr_text = (
        "[Screenshot 1]\n"
        "Title hint: 4）M2持平、M1上升\n"
        "Topic hint: unknown\n"
        "Recognized text:\n"
        "4）M2持平、M1上升，居民存款搬家现象延续。\n\n---\n\n"
        "[Screenshot 2]\n"
        "Title hint: 2）融资结构分化加大\n"
        "Topic hint: unknown\n"
        "Recognized text:\n"
        "2）融资结构分化加大，直接融资改善。\n"
        "3）信贷结构偏弱，企业贷款多增。\n\n---\n\n"
        "[Screenshot 3]\n"
        "Title hint: 居民存款搬家\n"
        "Topic hint: unknown\n"
        "Recognized text:\n"
        "居民存款搬家\n"
        "5月金融数据显示，宏观流动性环境宽松。\n"
        "1）社融回落，流动性环境宽松。"
    )
    seen_paths: list[str] = []
    seen_llm_input: dict[str, str] = {}

    def fake_ocr(image_paths):
        seen_paths.extend(path.name for path in image_paths)
        return ocr_text

    def fake_polish(raw_text: str, material_type: str = "raw", setting=None):
        seen_llm_input["raw_text"] = raw_text
        assert material_type == "screenshot"
        assert "[Screenshot" not in raw_text
        assert "Title hint:" not in raw_text
        assert "Recognized text:" not in raw_text
        return RawMaterialPolishResult(
            title="居民存款搬家",
            markdown=(
                "# 居民存款搬家\n\n"
                "5月金融数据显示，宏观流动性环境宽松。\n\n"
                "1）社融回落，流动性环境宽松。\n\n"
                "2）融资结构分化加大，直接融资改善。\n\n"
                "3）信贷结构偏弱，企业贷款多增。\n\n"
                "4）M2持平、M1上升，居民存款搬家现象延续。"
            ),
        )

    monkeypatch.setattr(api_v2.ocr_client, "recognize_screenshots", fake_ocr)
    monkeypatch.setattr(api_v2.deepseek_client, "polish_raw_material", fake_polish)
    monkeypatch.setattr(api_v2.api_settings, "active_setting", lambda: {"api_key": "test-key"})
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    screenshots = [
        storage.save_image_bytes(png + bytes([index]), filename=f"clip-{index}.png", content_type="image/png")
        for index in range(1, 5)
    ]
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "screenshot",
            "items": [
                {"id": item["id"], "title": f"截图 {index}"}
                for index, item in enumerate(screenshots, start=1)
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True, payload
    markdown = payload["markdown"]
    assert [seen_paths.index(Path(item["image_path"]).name) for item in screenshots] == [0, 1, 2, 3]
    assert seen_llm_input["raw_text"]
    assert "[Screenshot" not in markdown
    assert "Title hint:" not in markdown
    assert "Recognized text:" not in markdown
    assert markdown.index("居民存款搬家") < markdown.index("1）社融回落") < markdown.index("2）融资结构") < markdown.index("3）信贷结构") < markdown.index("4）M2持平")


def test_v2_collect_raw_markdown_extracts_uploaded_documents():
    client = TestClient(create_app())
    upload = client.post(
        "/api/files",
        files={"files": ("research-note.txt", b"document raw text", "text/plain")},
    )
    assert upload.status_code == 200
    file_id = upload.json()["items"][0]["id"]

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={"material_type": "document", "items": [{"id": file_id, "title": "research-note.txt"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert payload["data"]["ok"] is True
    assert item["material_type"] == "document"
    assert path.exists()
    assert "document raw text" in path.read_text(encoding="utf-8")


def test_v2_collect_readable_document_uses_ai_vision_for_pdf_pages(monkeypatch):
    calls: dict[str, object] = {}

    def fake_extract_text(path, visual_recognizer=None, prefer_visual=False):
        calls["path"] = path
        calls["prefer_visual"] = prefer_visual
        calls["visual_text"] = visual_recognizer([path]) if visual_recognizer else ""
        return "pdf image text from api vision"

    monkeypatch.setattr(api_v2.document_parser, "extract_text", fake_extract_text)
    monkeypatch.setattr(api_v2.deepseek_client, "recognize_screenshots_with_ai", lambda paths, setting=None: "api vision text")
    monkeypatch.setattr(
        api_v2,
        "_polish_raw_material",
        lambda material_type, body, title: {"markdown": body, "title": title, "response": {"status": "skipped"}},
    )
    client = TestClient(create_app())
    upload = client.post(
        "/api/files",
        files={"files": ("scan.pdf", b"%PDF-1.4\nfake", "application/pdf")},
    )
    file_id = upload.json()["items"][0]["id"]

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={
            "material_type": "document",
            "parser_mode": "ai_vision",
            "items": [{"id": file_id, "title": "scan.pdf"}],
        },
    )

    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["ok"] is True, payload
    assert calls["prefer_visual"] is True
    assert calls["visual_text"] == "api vision text"
    assert "pdf image text from api vision" in payload["markdown"]


def test_v2_collect_document_uses_resolved_storage_path(monkeypatch, tmp_path):
    outside_documents = tmp_path / "external-documents"
    monkeypatch.setattr(storage, "DOCUMENT_DIR", outside_documents)
    storage.init_storage()
    seen: dict[str, object] = {}

    def fake_extract_text(path, visual_recognizer=None, prefer_visual=False):
        seen["path"] = path
        return "external storage document text"

    monkeypatch.setattr(api_v2.document_parser, "extract_text", fake_extract_text)
    monkeypatch.setattr(
        api_v2,
        "_polish_raw_material",
        lambda material_type, body, title: {"markdown": body, "title": title, "response": {"status": "skipped"}},
    )
    client = TestClient(create_app())
    upload = client.post(
        "/api/files",
        files={"files": ("external.txt", b"external raw text", "text/plain")},
    )
    item = upload.json()["items"][0]

    response = client.post(
        "/api/v2/collect/readable-draft",
        json={"material_type": "document", "items": [{"id": item["id"], "title": "external.txt"}]},
    )

    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["ok"] is True, payload
    assert seen["path"].exists()
    assert str(seen["path"]).startswith(str(outside_documents))
    assert "external storage document text" in payload["markdown"]


def test_v2_collect_raw_markdown_transcribes_uploaded_subtitle_media():
    client = TestClient(create_app())
    subtitle = b"1\n00:00:00,000 --> 00:00:01,000\nsubtitle raw text\n"
    upload = client.post(
        "/api/media/upload",
        files={"files": ("clip.srt", subtitle, "application/x-subrip")},
    )
    assert upload.status_code == 200
    media_id = upload.json()["items"][0]["id"]

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={"material_type": "media", "items": [{"id": media_id, "title": "clip.srt"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    assert payload["data"]["ok"] is True
    assert item["material_type"] == "media"
    assert path.exists()
    assert "subtitle raw text" in path.read_text(encoding="utf-8")


def test_v2_collect_raw_markdown_imports_douyin_detail_for_media_queue(monkeypatch):
    calls = {"ensure": 0, "import": 0}

    def fake_ensure_transcript(item: dict) -> tuple[str, str]:
        calls["ensure"] += 1
        if calls["ensure"] == 1:
            raise RuntimeError("Douyin full subtitles are not exposed by this page.")
        return "media queue douyin transcript", "asr"

    def fake_import(video_id: str, url: str):
        calls["import"] += 1
        assert video_id == "7645662793240815025"
        return storage.MEDIA_DIR / "douyin_detail" / f"{video_id}.json"

    monkeypatch.setattr(api_v2.media_parser, "ensure_transcript", fake_ensure_transcript)
    monkeypatch.setattr(api_v2, "_import_douyin_detail_with_browser", fake_import)
    media_item = storage.create_remote_media_source(
        platform="douyin",
        source_url="https://v.douyin.com/hdsMHiD-gSw/",
        canonical_url="https://www.douyin.com/video/7645662793240815025",
        title="Douyin 7645662793240815025",
        status="resolved",
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/collect/raw-markdown",
        json={"material_type": "media", "items": [{"id": media_item["id"], "title": media_item["title"]}]},
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"]["item"]
    path = storage.ROOT / item["markdown_path"]
    text = path.read_text(encoding="utf-8")
    assert payload["data"]["ok"] is True
    assert calls == {"ensure": 2, "import": 1}
    assert item["title"] == "media queue douyin transcript"
    assert "media queue douyin transcript" in text
