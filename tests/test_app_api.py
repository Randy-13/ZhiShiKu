import base64
import io
import json
import urllib.error
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api_settings
import asr_settings
import app
import deepseek_client
import document_parser
import graph_core
import image_api_settings
import media_parser
import ocr_client
import storage
import workbench_settings
import writer_tools
import xhs_tools
import src.api_v2 as api_v2
from src.auth import bootstrap_admin
from schemas import (
    CreationStrategyResult,
    DocumentPlanResult,
    DocumentPlanSegment,
    ExtractedTermNode,
    GraphGroup,
    GraphOrganizationResult,
    KnowledgeNetworkExtraction,
    KnowledgeResult,
    PerspectiveFinding,
    PerspectiveInterpretationResult,
    RetrievalAnswer,
    WriterArticleResult,
    WriterImageSuggestionResult,
    WriterRevisionResult,
)


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00"
    b"\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
    monkeypatch.setattr(storage, "XHS_DIR", runtime_root / "xhs")
    monkeypatch.setattr(storage, "TRASH_DIR", runtime_root / "trash")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.db")
    monkeypatch.setattr(workbench_settings, "SETTINGS_PATH", tmp_path / "workbench_settings.json")
    monkeypatch.setattr(writer_tools, "WRITER_DIR", runtime_root / "writer")
    storage.init_storage()


def xhs_profile_payload(name="知识酷产业观察"):
    return {
        "name": name,
        "account_name": "知识酷",
        "positioning": "面向职场人的产业趋势图文账号",
        "target_audience": "关注产业、就业和科技趋势的职场人",
        "audience_pain_points": ["看不懂政策影响", "缺少结构化行业判断"],
        "content_pillars": ["产业趋势", "政策解读", "就业观察"],
        "tone": "克制、清晰、像可信赖的研究助理",
        "value_promise": "把复杂产业信息讲成能收藏的判断框架",
        "content_formats": ["清单", "避坑", "对比"],
        "tag_strategy": {
            "broad_tags": ["职场"],
            "niche_tags": ["产业趋势", "政策解读"],
            "trend_tags": ["就业"],
            "branded_tags": ["知识酷笔记"],
        },
        "avoid_topics": ["无来源预测", "情绪化唱衰"],
        "notes": "优先做可收藏的图文轮播",
    }


def create_xhs_profile(name="知识酷产业观察"):
    return xhs_tools.create_account_profile(xhs_profile_payload(name))


def test_public_beta_info_pages_and_favicon_are_available():
    client = TestClient(app.app)

    for path, expected_text in [
        ("/public-beta", "知识酷内测说明"),
        ("/privacy", "隐私说明"),
        ("/data-retention", "数据保存说明"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected_text in response.text

    favicon_response = client.get("/favicon.ico")
    assert favicon_response.status_code == 200
    assert favicon_response.headers["content-type"] in {"image/x-icon", "image/vnd.microsoft.icon"}


def test_html_to_text_prefers_article_body_over_navigation():
    html = """
    <html>
      <body>
        <nav>Home Pricing Login Subscribe</nav>
        <main>
          <article>
            <h1>Research Note</h1>
            <p>This is the first paragraph of the article body with enough detail to look like real prose.</p>
            <p>This second paragraph continues the actual content and should be kept in the extracted text.</p>
          </article>
        </main>
        <footer>Contact Terms Privacy</footer>
      </body>
    </html>
    """

    text = api_v2._html_to_text(html)

    assert "Research Note" in text
    assert "first paragraph of the article body" in text
    assert "second paragraph continues" in text
    assert "Home Pricing Login" not in text
    assert "Contact Terms Privacy" not in text


def test_document_parser_filters_repeated_headers_and_page_numbers(tmp_path):
    raw = "\n".join(
        [
            "Quarterly Research Memo",
            "1 / 3",
            "The first page contains the opening argument.",
            "",
            "Quarterly Research Memo",
            "2 / 3",
            "The second page continues the useful evidence.",
            "",
            "Quarterly Research Memo",
            "3 / 3",
            "The final page keeps the conclusion.",
        ]
    )

    cleaned = document_parser.clean_extracted_document_text(raw)

    assert "Quarterly Research Memo" not in cleaned
    assert "1 / 3" not in cleaned
    assert "2 / 3" not in cleaned
    assert "opening argument" in cleaned
    assert "useful evidence" in cleaned
    assert "conclusion" in cleaned


def test_document_extract_text_applies_basic_noise_filter(tmp_path):
    path = tmp_path / "memo.txt"
    path.write_text("Page 1\n\nUseful paragraph from uploaded document.\n\nCopyright 2026 Example", encoding="utf-8")

    text = document_parser.extract_text(path)

    assert "Useful paragraph" in text
    assert "Page 1" not in text
    assert "Copyright 2026" not in text


def test_document_parser_removes_catalog_and_contact_noise(tmp_path):
    raw = "\n".join(
        [
            "Contents",
            "1. Executive Summary ........ 1",
            "2. Market Outlook ........ 3",
            "",
            "Executive summary starts here with the first useful paragraph.",
            "The second useful paragraph keeps the real body content readable.",
            "",
            "Email: analyst@example.com",
            "https://example.com/report",
        ]
    )

    cleaned = document_parser.clean_extracted_document_text(raw)

    assert "Contents" not in cleaned
    assert "Executive Summary ........ 1" not in cleaned
    assert "Market Outlook ........ 3" not in cleaned
    assert "analyst@example.com" not in cleaned
    assert "https://example.com/report" not in cleaned
    assert "Executive summary starts here" in cleaned
    assert "second useful paragraph" in cleaned


def test_upload_image_and_dedupe(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    response = client.post("/api/images", files={"files": ("shot.png", PNG_1X1, "image/png")})
    assert response.status_code == 200
    first = response.json()["items"][0]
    assert first["duplicate"] is False
    assert first["status"] == "uploaded"

    duplicate = client.post("/api/images", files={"files": ("shot.png", PNG_1X1, "image/png")})
    assert duplicate.status_code == 200
    second = duplicate.json()["items"][0]
    assert second["duplicate"] is True
    assert second["id"] == first["id"]

    image_response = client.get(f"/api/images/{first['id']}/file")
    assert image_response.status_code == 200


def _register_app_cloud_member(invite_code: str, email: str, username: str) -> tuple[TestClient, dict[str, object]]:
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
    client = TestClient(app.app, base_url="http://testserver")
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


def _login_app_cloud_admin(email: str = "admin@example.test", username: str = "admin") -> tuple[TestClient, dict[str, object]]:
    with storage.connect() as conn:
        bootstrap_admin(conn, email=email, username=username, password="password-123")
    client = TestClient(app.app, base_url="http://testserver")
    response = client.post("/api/auth/login", json={"identifier": username, "password": "password-123"})
    assert response.status_code == 200
    return client, response.json()["data"]


def test_cloud_admin_can_manage_users_and_invitations(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    admin_client, _admin_payload = _login_app_cloud_admin()
    member_client, member_payload = _register_app_cloud_member("ADMIN-MANAGE", "managed@example.test", "managed")

    users = admin_client.get("/api/auth/admin/users")
    assert users.status_code == 200
    assert {item["username"] for item in users.json()["data"]["items"]} >= {"admin", "managed"}

    invitation = admin_client.post("/api/auth/admin/invitations", json={"role": "member", "max_uses": 2, "days": 7})
    assert invitation.status_code == 200
    assert invitation.json()["data"]["maxUses"] == 2

    invitations = admin_client.get("/api/auth/admin/invitations")
    assert invitations.status_code == 200
    assert any(item["code"] == invitation.json()["data"]["code"] for item in invitations.json()["data"]["items"])

    disabled = admin_client.post(
        f"/api/auth/admin/users/{member_payload['user']['id']}/status",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["item"]["status"] == "disabled"
    assert member_client.get("/api/auth/me").status_code == 401


def test_cloud_member_cannot_access_user_admin_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    member_client, _payload = _register_app_cloud_member("ADMIN-FORBID", "forbid@example.test", "forbid")

    assert member_client.get("/api/auth/admin/users").status_code == 403
    assert member_client.get("/api/auth/admin/invitations").status_code == 403


def test_workbench_settings_default_to_ai_vision(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    response = client.get("/api/workbench-settings")

    assert response.status_code == 200
    assert response.json()["text_extraction_mode"] == "ai_vision"


def test_mine_interpret_renders_five_part_perspective_markdown(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    raw_dir = storage.RAW_MATERIAL_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_path = raw_dir / "perspective-source.md"
    source_path.write_text("# 测试原文\n\n这里有一段可供视角解读的原文内容。", encoding="utf-8")

    def fake_interpret_from_perspective(material_blocks, perspective, setting=None):
        return PerspectiveInterpretationResult(
            title="行业研究视角解读",
            perspective_name="行业研究",
            tags=["行业研究", "测试"],
            summary="这是一段摘要。",
            criteria="优先判断行业结构、变量关系和后续验证重点。",
            core_facts=[
                PerspectiveFinding(
                    dimension="原文事实",
                    interpretation="材料明确提到了一个关键变化信号。",
                    evidence_refs=["S1"],
                )
            ],
            deep_analysis=[
                PerspectiveFinding(
                    dimension="延伸判断",
                    interpretation="基于 S1 可以推断该变化信号背后存在结构性约束，但这属于从原文出发的推断，不是额外事实。",
                    evidence_refs=["S1"],
                )
            ],
            risks_and_questions=["还需要补充更多样本验证这个判断是否具有普遍性。"],
            conclusion_and_actions=["先补证据，再决定是否把这个判断沉淀为长期研究线索。"],
        )

    monkeypatch.setattr(deepseek_client, "interpret_from_perspective", fake_interpret_from_perspective)

    response = client.post(
        "/api/v2/mine/interpret",
        json={
            "sources": [
                {
                    "library": "raw",
                    "markdown_path": source_path.name,
                    "title": "测试原文",
                }
            ],
            "perspective": {
                "id": "industry-research",
                "name": "行业研究",
                "positioning": "判断行业结构与关键变量",
                "core_goal": "沉淀可复用的研究判断",
                "stance": "只接受可回到原文的判断",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is True
    markdown = payload["markdown"]
    assert "## 视角立场与标准" in markdown
    assert "## 原文信息提炼" in markdown
    assert "## 专属分析" in markdown
    assert "## 风险疑问" in markdown
    assert "## 结论建议" in markdown
    assert "优先判断行业结构、变量关系和后续验证重点。" in markdown
    assert "还需要补充更多样本验证这个判断是否具有普遍性。" in markdown
    assert "- 引用：" not in markdown


def test_structured_json_generation_repairs_invalid_first_response(monkeypatch):
    calls: list[list[dict[str, str]]] = []

    def fake_chat_completion(messages, json_mode=False, setting=None):
        calls.append(messages)
        if len(calls) == 1:
            return '{"title":"坏掉的 JSON"'
        return json.dumps(
            {
                "title": "修复后的视角解读",
                "perspective_name": "记者视角",
                "tags": ["记者视角"],
                "summary": "修复后可以解析。",
                "criteria": "先看事实链，再看表达张力。",
                "core_facts": [],
                "deep_analysis": [],
                "risks_and_questions": [],
                "conclusion_and_actions": [],
                "findings": [],
                "writing_implications": [],
                "risks_and_limits": [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(deepseek_client, "sdk_chat_completion", fake_chat_completion)

    result = deepseek_client.parse_json_model(
        PerspectiveInterpretationResult,
        [{"role": "user", "content": "生成视角解读 JSON"}],
        setting={"provider": "compatible", "api_key": "test-key", "base_url": "https://example.test/v1", "model": "test"},
    )

    assert result.title == "修复后的视角解读"
    assert len(calls) == 2
    assert "上一条回复不是合法 JSON" in calls[1][-1]["content"]


def test_mine_interpret_returns_ok_false_when_model_json_fails(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    raw_dir = storage.RAW_MATERIAL_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_path = raw_dir / "perspective-runtime-error.md"
    source_path.write_text("# 测试原文\n\n这里有一段可供视角解读的原文内容。", encoding="utf-8")

    def fail_interpret_from_perspective(material_blocks, perspective, setting=None):
        raise RuntimeError("compatible 返回的 JSON 不符合应用 schema")

    monkeypatch.setattr(deepseek_client, "interpret_from_perspective", fail_interpret_from_perspective)

    response = client.post(
        "/api/v2/mine/interpret",
        json={
            "sources": [{"library": "raw", "markdown_path": source_path.name, "title": "测试原文"}],
            "perspective": {
                "id": "reporter",
                "name": "记者视角",
                "positioning": "检查事实链",
                "core_goal": "形成可用解读",
                "stance": "不扩大材料",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["ok"] is False
    assert "JSON 不符合应用 schema" in payload["error"]


def test_cloud_upload_rejects_single_file_over_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setitem(app.quota_service.DEFAULT_LIMITS, "single_upload_bytes", 4)
    setup_storage(tmp_path, monkeypatch)
    client, _payload = _register_app_cloud_member("UPLOAD-SIZE", "upload-size@example.test", "upload_size")

    response = client.post("/api/files", files={"files": ("too-large.txt", b"12345", "text/plain")})

    assert response.status_code == 413
    assert "4 bytes" in response.json()["detail"]


def test_cloud_upload_rejects_when_storage_quota_would_be_exceeded(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setitem(app.quota_service.DEFAULT_LIMITS, "single_upload_bytes", 100)
    monkeypatch.setitem(app.quota_service.DEFAULT_LIMITS, "storage_bytes", 8)
    setup_storage(tmp_path, monkeypatch)
    client, payload = _register_app_cloud_member("UPLOAD-STORAGE", "upload-storage@example.test", "upload_storage")

    first = client.post("/api/files", files={"files": ("first.txt", b"123456", "text/plain")})
    assert first.status_code == 200
    item = first.json()["items"][0]
    assert item["owner_user_id"] == payload["user"]["id"]

    response = client.post("/api/files", files={"files": ("second.txt", b"abcd", "text/plain")})

    assert response.status_code == 429
    assert "8 bytes" in response.json()["detail"]


def test_cloud_upload_duplicate_scope_is_per_user(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, first_payload = _register_app_cloud_member("UPLOAD-OWNER-A", "owner-a@example.test", "owner_a")
    second_client, second_payload = _register_app_cloud_member("UPLOAD-OWNER-B", "owner-b@example.test", "owner_b")

    content = b"same-user-visible-content"
    first = first_client.post("/api/files", files={"files": ("same.txt", content, "text/plain")})
    assert first.status_code == 200
    first_item = first.json()["items"][0]
    assert first_item["duplicate"] is False
    assert first_item["owner_user_id"] == first_payload["user"]["id"]
    assert first_item["workspace_id"] == first_payload["workspace"]["id"]

    first_again = first_client.post("/api/files", files={"files": ("same.txt", content, "text/plain")})
    assert first_again.status_code == 200
    first_again_item = first_again.json()["items"][0]
    assert first_again_item["duplicate"] is True
    assert first_again_item["id"] == first_item["id"]

    second = second_client.post("/api/files", files={"files": ("same.txt", content, "text/plain")})
    assert second.status_code == 200
    second_item = second.json()["items"][0]
    assert second_item["duplicate"] is False
    assert second_item["id"] != first_item["id"]
    assert second_item["file_hash"] != first_item["file_hash"]
    assert second_item["file_path"] == first_item["file_path"]
    assert second_item["owner_user_id"] == second_payload["user"]["id"]
    assert second_item["workspace_id"] == second_payload["workspace"]["id"]


def test_cloud_uploaded_file_reads_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, _first_payload = _register_app_cloud_member("READ-OWNER-A", "read-a@example.test", "read_a")
    second_client, _second_payload = _register_app_cloud_member("READ-OWNER-B", "read-b@example.test", "read_b")

    uploaded = first_client.post("/api/files", files={"files": ("private.txt", b"private text", "text/plain")})
    assert uploaded.status_code == 200
    file_id = uploaded.json()["items"][0]["id"]

    owner_read = first_client.get(f"/api/files/{file_id}/raw")
    assert owner_read.status_code == 200
    assert owner_read.content == b"private text"

    other_read = second_client.get(f"/api/files/{file_id}/raw")
    assert other_read.status_code == 404


def test_cloud_media_transcripts_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, _first_payload = _register_app_cloud_member("MEDIA-OWNER-A", "media-a@example.test", "media_a")
    second_client, _second_payload = _register_app_cloud_member("MEDIA-OWNER-B", "media-b@example.test", "media_b")

    uploaded = first_client.post(
        "/api/media/upload",
        files={
            "files": (
                "private.srt",
                "1\n00:00:01,000 --> 00:00:03,000\n私有字幕\n".encode("utf-8"),
                "application/x-subrip",
            )
        },
    )
    assert uploaded.status_code == 200
    media_id = uploaded.json()["items"][0]["id"]

    owner_list = first_client.get("/api/media/transcripts")
    assert owner_list.status_code == 200
    assert [item["id"] for item in owner_list.json()["items"]] == [media_id]

    other_list = second_client.get("/api/media/transcripts")
    assert other_list.status_code == 200
    assert other_list.json()["items"] == []

    other_read = second_client.get(f"/api/media/{media_id}/transcript")
    assert other_read.status_code == 404


def test_cloud_knowledge_reads_and_mutations_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, first_payload = _register_app_cloud_member("KNOW-OWNER-A", "know-a@example.test", "know_a")
    second_client, _second_payload = _register_app_cloud_member("KNOW-OWNER-B", "know-b@example.test", "know_b")

    created = first_client.post(
        "/api/knowledge/commit-draft",
        json={"title": "A 的知识", "note": "只属于 A", "body": "A 的正文", "source_ids": []},
    )
    assert created.status_code == 200
    knowledge_id = created.json()["item"]["id"]
    assert created.json()["item"]["owner_user_id"] == first_payload["user"]["id"]

    first_list = first_client.get("/api/knowledge")
    assert first_list.status_code == 200
    assert [item["id"] for item in first_list.json()["items"]] == [knowledge_id]

    second_list = second_client.get("/api/knowledge")
    assert second_list.status_code == 200
    assert second_list.json()["items"] == []

    second_read = second_client.get(f"/api/knowledge/{knowledge_id}")
    assert second_read.status_code == 404

    second_update = second_client.post(
        f"/api/knowledge/{knowledge_id}",
        json={"title": "被越权修改", "note": "", "body": "不应写入"},
    )
    assert second_update.status_code == 404

    still_visible = first_client.get(f"/api/knowledge/{knowledge_id}")
    assert still_visible.status_code == 200
    assert still_visible.json()["content"] == "> 只属于 A\n\nA 的正文"


def test_cloud_generate_file_knowledge_is_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Cloud File API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "file-model",
            "api_key": "test-key",
        },
    )
    monkeypatch.setattr(
        deepseek_client,
        "generate_knowledge_from_text",
        lambda raw_text, setting=None: (
            KnowledgeResult(
                title="Cloud 文件知识",
                topic="文件输入",
                tags=["文件"],
                focus_question="文件讲了什么？",
                clusters=[],
                investment_insights="文件输入洞察。",
            ),
            raw_text,
        ),
    )
    first_client, first_payload = _register_app_cloud_member("KNOW-FILE-A", "know-file-a@example.test", "know_file_a")
    second_client, second_payload = _register_app_cloud_member("KNOW-FILE-B", "know-file-b@example.test", "know_file_b")

    first_file = first_client.post("/api/files", files={"files": ("same.md", b"# Same\n\nAlpha", "text/markdown")})
    second_file = second_client.post("/api/files", files={"files": ("same.md", b"# Same\n\nAlpha", "text/markdown")})
    assert first_file.status_code == 200
    assert second_file.status_code == 200

    first_generated = first_client.post(
        "/api/knowledge/generate-from-files",
        json={"file_ids": [first_file.json()["items"][0]["id"]]},
    )
    second_generated = second_client.post(
        "/api/knowledge/generate-from-files",
        json={"file_ids": [second_file.json()["items"][0]["id"]]},
    )
    assert first_generated.status_code == 200
    assert second_generated.status_code == 200
    first_item = first_generated.json()["item"]
    second_item = second_generated.json()["item"]
    assert first_item["id"] != second_item["id"]
    assert first_item["image_hash"] != second_item["image_hash"]
    assert first_item["owner_user_id"] == first_payload["user"]["id"]
    assert second_item["owner_user_id"] == second_payload["user"]["id"]

    assert [item["id"] for item in first_client.get("/api/knowledge").json()["items"]] == [first_item["id"]]
    assert [item["id"] for item in second_client.get("/api/knowledge").json()["items"]] == [second_item["id"]]


def test_cloud_focus_library_list_falls_back_to_db_owner_when_markdown_meta_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, first_payload = _register_app_cloud_member("LIB-FOCUS-A", "focus-a@example.test", "focus_a")
    second_client, _second_payload = _register_app_cloud_member("LIB-FOCUS-B", "focus-b@example.test", "focus_b")

    source_hash = "focus-owner-fallback"
    entry = storage.create_or_update_knowledge_entry(
        [],
        source_hash,
        source_type="raw_materials",
        source_ids=[],
        owner_user_id=first_payload["user"]["id"],
        workspace_id=first_payload["workspace"]["id"],
    )
    markdown_path = storage.markdown_path_for("只写进数据库归属的重点文件", source_hash, entry.get("created_at"))
    markdown_path.write_text("# 只写进数据库归属的重点文件\n\n## 核心知识簇\n\n- 条目一\n", encoding="utf-8")
    storage.update_knowledge_entry(
        entry["id"],
        markdown_path=storage.storage_relative(markdown_path),
        title="只写进数据库归属的重点文件",
        status="ready",
        owner_user_id=first_payload["user"]["id"],
        workspace_id=first_payload["workspace"]["id"],
    )

    first_list = first_client.get("/api/v2/libraries/focus/files")
    assert first_list.status_code == 200
    first_paths = [item["markdown_path"] for item in first_list.json()["data"]["items"]]
    assert storage.storage_relative(markdown_path) in first_paths

    second_list = second_client.get("/api/v2/libraries/focus/files")
    assert second_list.status_code == 200
    second_paths = [item["markdown_path"] for item in second_list.json()["data"]["items"]]
    assert storage.storage_relative(markdown_path) not in second_paths

    first_read = first_client.get(
        "/api/v2/libraries/focus/file",
        params={"markdown_path": storage.storage_relative(markdown_path)},
    )
    assert first_read.status_code == 200

    second_read = second_client.get(
        "/api/v2/libraries/focus/file",
        params={"markdown_path": storage.storage_relative(markdown_path)},
    )
    assert second_read.status_code == 404


def _disabled_cloud_graph_ingest_cannot_touch_other_users_knowledge(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, _first_payload = _register_app_cloud_member("GRAPH-OWNER-A", "graph-a@example.test", "graph_a")
    second_client, _second_payload = _register_app_cloud_member("GRAPH-OWNER-B", "graph-b@example.test", "graph_b")

    created = first_client.post(
        "/api/knowledge/commit-draft",
        json={"title": "A 图谱知识", "note": "", "body": "# A 图谱知识\n\n正文", "source_ids": []},
    )
    assert created.status_code == 200
    knowledge_id = created.json()["item"]["id"]

    blocked = second_client.post("/api/knowledge/ingest-to-graph", json={"knowledge_ids": [knowledge_id]})
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["ok"] is False
    assert body["results"][0]["ok"] is False
    assert body["results"][0]["error"] == "Knowledge not found"

    still_owned = first_client.get(f"/api/knowledge/{knowledge_id}")
    assert still_owned.status_code == 200
    assert "graph_status" not in still_owned.json()["item"]


def test_cloud_writer_projects_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, first_payload = _register_app_cloud_member("WRITER-OWNER-A", "writer-a@example.test", "writer_a")
    second_client, second_payload = _register_app_cloud_member("WRITER-OWNER-B", "writer-b@example.test", "writer_b")

    first_knowledge = first_client.post(
        "/api/knowledge/commit-draft",
        json={"title": "A 写作素材", "note": "", "body": "A 写作素材正文", "source_ids": []},
    )
    second_knowledge = second_client.post(
        "/api/knowledge/commit-draft",
        json={"title": "B 写作素材", "note": "", "body": "B 写作素材正文", "source_ids": []},
    )
    assert first_knowledge.status_code == 200
    assert second_knowledge.status_code == 200

    created = first_client.post(
        "/api/writer/projects",
        json={"name": "A 的创作项目", "knowledge_ids": [first_knowledge.json()["item"]["id"]]},
    )
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["owner_user_id"] == first_payload["user"]["id"]
    assert project["workspace_id"] == first_payload["workspace"]["id"]

    assert [item["id"] for item in first_client.get("/api/writer/projects").json()["items"]] == [project["id"]]
    assert second_client.get("/api/writer/projects").json()["items"] == []
    assert second_client.get(f"/api/writer/projects/{project['id']}").status_code == 404

    other_confirm = second_client.post(
        f"/api/writer/projects/{project['id']}/knowledge",
        json={"knowledge_ids": [second_knowledge.json()["item"]["id"]], "library_files": []},
    )
    assert other_confirm.status_code == 404

    own_confirm_other_knowledge = first_client.post(
        f"/api/writer/projects/{project['id']}/knowledge",
        json={"knowledge_ids": [second_knowledge.json()["item"]["id"]], "library_files": []},
    )
    assert own_confirm_other_knowledge.status_code == 404

    own_read = first_client.get(f"/api/writer/projects/{project['id']}")
    assert own_read.status_code == 200
    assert own_read.json()["project"]["owner_user_id"] == first_payload["user"]["id"]


def _create_writer_project_ready_for_images(client: TestClient, name: str = "Image retry project") -> str:
    created = client.post("/api/writer/projects", json={"name": name, "knowledge_ids": []})
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]
    workspace = writer_tools.resolve_project_workspace(project_id)
    article_path = writer_tools.write_article(workspace, "# Article\n\nBody")
    writer_tools.update_project(
        project_id,
        article_path=storage.storage_relative(article_path),
        cover_prompt="cover prompt",
        content_image_prompts=["content prompt 1"],
    )
    return project_id


def test_writer_image_failures_keep_project_on_retry_action(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    project_id = _create_writer_project_ready_for_images(client)

    def fail_image(*args, **kwargs):
        raise RuntimeError("image api unavailable")

    monkeypatch.setattr(writer_tools, "generate_image", fail_image)
    response = client.post(f"/api/writer/projects/{project_id}/images", json={})

    assert response.status_code == 200
    payload = response.json()
    images = payload["project"]["images"]
    assert payload["step"] == "images"
    assert payload["next_action"] == "retry_failed_images"
    assert images["partial"] is True
    assert images["ok"] is False
    assert len(images["errors"]) == 2
    assert images["items"] == []


def test_writer_partial_image_success_preserves_success_and_requires_retry(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    project_id = _create_writer_project_ready_for_images(client)

    def generate_some(prompt, output_path, setting=None):
        if output_path.name == "cover.png":
            output_path.write_bytes(PNG_1X1)
            return {"path": storage.storage_relative(output_path), "prompt": prompt}
        raise RuntimeError("content image failed")

    monkeypatch.setattr(writer_tools, "generate_image", generate_some)
    response = client.post(f"/api/writer/projects/{project_id}/images", json={})

    assert response.status_code == 200
    payload = response.json()
    images = payload["project"]["images"]
    assert payload["step"] == "images"
    assert payload["next_action"] == "retry_failed_images"
    assert images["cover"]["path"].endswith("cover.png")
    assert images["content_images"] == []
    assert images["errors"][0]["kind"] == "content"


def test_writer_image_success_allows_format_action(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    project_id = _create_writer_project_ready_for_images(client)

    def generate_image(prompt, output_path, setting=None):
        output_path.write_bytes(PNG_1X1)
        return {"path": storage.storage_relative(output_path), "prompt": prompt}

    monkeypatch.setattr(writer_tools, "generate_image", generate_image)
    response = client.post(f"/api/writer/projects/{project_id}/images", json={})

    assert response.status_code == 200
    payload = response.json()
    images = payload["project"]["images"]
    assert payload["step"] == "images"
    assert payload["next_action"] == "format_article"
    assert images["ok"] is True
    assert images["cover"]["path"].endswith("cover.png")
    assert images["content_images"][0]["index"] == 1


def test_writer_failed_image_item_can_retry_to_format_action(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    project_id = _create_writer_project_ready_for_images(client)
    attempts = {"cover": 0, "content": 0}

    def fail_then_generate(prompt, output_path, setting=None):
        kind = "cover" if output_path.name == "cover.png" else "content"
        attempts[kind] += 1
        if kind == "content" and attempts[kind] == 1:
            raise RuntimeError("temporary image outage")
        output_path.write_bytes(PNG_1X1)
        return {"path": storage.storage_relative(output_path), "prompt": prompt}

    monkeypatch.setattr(writer_tools, "generate_image", fail_then_generate)
    failed = client.post(f"/api/writer/projects/{project_id}/images", json={})
    assert failed.status_code == 200
    assert failed.json()["next_action"] == "retry_failed_images"
    assert len(failed.json()["project"]["images"]["errors"]) == 1

    retried = client.post(
        f"/api/writer/projects/{project_id}/images/item",
        json={"kind": "content", "index": 1, "prompt": "content prompt retry"},
    )

    assert retried.status_code == 200
    payload = retried.json()
    images = payload["project"]["images"]
    assert payload["step"] == "images"
    assert payload["next_action"] == "format_article"
    assert images["errors"] == []
    assert images["cover"]["path"].endswith("cover.png")
    assert images["content_images"][0]["path"].endswith("content-1.png")
    assert images["content_images"][0]["prompt"] == "content prompt retry"


def test_cloud_legacy_writer_paths_are_scoped_to_owned_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, _first_payload = _register_app_cloud_member("WRITER-LEGACY-A", "writer-legacy-a@example.test", "writer_legacy_a")
    second_client, _second_payload = _register_app_cloud_member("WRITER-LEGACY-B", "writer-legacy-b@example.test", "writer_legacy_b")

    second_knowledge = second_client.post(
        "/api/knowledge/commit-draft",
        json={"title": "B 的旧入口素材", "note": "", "body": "B 的素材正文", "source_ids": []},
    )
    assert second_knowledge.status_code == 200
    second_knowledge_id = second_knowledge.json()["item"]["id"]

    assert first_client.get(f"/api/writer/session?ids={second_knowledge_id}").status_code == 404
    assert first_client.post("/api/writer/topics", json={"knowledge_ids": [second_knowledge_id]}).status_code == 404

    legacy_workspace = writer_tools.dated_workspace("legacy-shared-workspace")
    legacy_html = legacy_workspace / "formatted.html"
    legacy_html.write_text("<html><body>legacy</body></html>", encoding="utf-8")
    legacy_workspace_path = str(legacy_workspace.relative_to(storage.ROOT))
    legacy_html_path = str(legacy_html.relative_to(storage.ROOT))

    assert first_client.get("/api/writer/workspaces").json()["items"] == []
    assert first_client.get("/api/writer/workspace", params={"path": legacy_workspace_path}).status_code == 404
    assert first_client.get("/api/writer/file", params={"path": legacy_html_path}).status_code == 404

    first_project = first_client.post("/api/writer/projects", json={"name": "A 旧预览项目", "knowledge_ids": []})
    second_project = second_client.post("/api/writer/projects", json={"name": "B 旧预览项目", "knowledge_ids": []})
    assert first_project.status_code == 200
    assert second_project.status_code == 200
    first_workspace = writer_tools.resolve_project_workspace(first_project.json()["project"]["id"])
    second_workspace = writer_tools.resolve_project_workspace(second_project.json()["project"]["id"])
    first_html = first_workspace / "formatted.html"
    second_html = second_workspace / "formatted.html"
    first_html.write_text("<html><body>first owned</body></html>", encoding="utf-8")
    second_html.write_text("<html><body>second owned</body></html>", encoding="utf-8")

    owner_preview = first_client.get("/api/writer/file", params={"path": str(first_html.relative_to(storage.ROOT))})
    other_preview = first_client.get("/api/writer/file", params={"path": str(second_html.relative_to(storage.ROOT))})
    owner_workspace = first_client.get("/api/writer/workspace", params={"path": str(first_workspace.relative_to(storage.ROOT))})
    other_workspace = first_client.get("/api/writer/workspace", params={"path": str(second_workspace.relative_to(storage.ROOT))})

    assert owner_preview.status_code == 200
    assert "first owned" in owner_preview.text
    assert other_preview.status_code == 404
    assert owner_workspace.status_code == 200
    assert other_workspace.status_code == 404


def test_cloud_member_cannot_operate_wechat_publish_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    client, _payload = _register_app_cloud_member("PUBLISH-TOOLS", "publish-tools@example.test", "publish_tools")

    def forbidden_call(*args, **kwargs):
        raise AssertionError("publish tool should not be called for cloud members")

    monkeypatch.setattr(writer_tools, "check_wechat_publish_ip", forbidden_call)
    monkeypatch.setattr(writer_tools, "refresh_wechat_access_token", forbidden_call)
    monkeypatch.setattr(writer_tools, "publish_preflight", forbidden_call)
    monkeypatch.setattr(writer_tools, "publish_draft", forbidden_call)

    project_response = client.post("/api/writer/projects", json={"name": "发布权限项目", "knowledge_ids": []})
    assert project_response.status_code == 200
    project_id = project_response.json()["project"]["id"]
    workspace = writer_tools.resolve_project_workspace(project_id)
    (workspace / "formatted.html").write_text("<html><body>ready</body></html>", encoding="utf-8")
    workspace_path = str(workspace.relative_to(storage.ROOT))

    assert client.get("/api/writer/publish/ip-check").status_code == 403
    assert client.post("/api/writer/publish/token/refresh").status_code == 403
    assert client.post("/api/writer/publish/preflight", json={"workspace": workspace_path, "title": "标题"}).status_code == 403
    assert client.post("/api/writer/publish", json={"workspace": workspace_path, "title": "标题"}).status_code == 403
    assert client.post(f"/api/writer/projects/{project_id}/publish/preflight", json={"title": "标题"}).status_code == 403
    assert client.post(f"/api/writer/projects/{project_id}/publish", json={"title": "标题"}).status_code == 403


def test_cloud_mining_projects_are_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    first_client, first_payload = _register_app_cloud_member("MINING-OWNER-A", "mining-a@example.test", "mining_a")
    second_client, second_payload = _register_app_cloud_member("MINING-OWNER-B", "mining-b@example.test", "mining_b")

    created = first_client.post("/api/mining/projects", json={"name": "A 的策略学习"})
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["owner_user_id"] == first_payload["user"]["id"]
    assert project["workspace_id"] == first_payload["workspace"]["id"]

    first_list = first_client.get("/api/mining/projects")
    second_list = second_client.get("/api/mining/projects")
    assert first_list.status_code == 200
    assert second_list.status_code == 200
    assert [item["id"] for item in first_list.json()["items"]] == [project["id"]]
    assert second_list.json()["items"] == []

    assert second_client.get(f"/api/mining/projects/{project['id']}").status_code == 404
    assert second_client.patch(f"/api/mining/projects/{project['id']}", json={"name": "越权改名"}).status_code == 404
    assert second_client.post(f"/api/mining/projects/{project['id']}/learn-creation-strategy").status_code == 404

    first_file = first_client.post("/api/files", files={"files": ("first.txt", b"first sample", "text/plain")})
    second_file = second_client.post("/api/files", files={"files": ("second.txt", b"second sample", "text/plain")})
    assert first_file.status_code == 200
    assert second_file.status_code == 200
    first_file_id = first_file.json()["items"][0]["id"]
    second_file_item = second_file.json()["items"][0]
    assert second_file_item["owner_user_id"] == second_payload["user"]["id"]

    own_attach = first_client.post(
        f"/api/mining/projects/{project['id']}/sources",
        json={"sources": [{"source_type": "file", "source_id": first_file_id, "title": "A 样本"}]},
    )
    assert own_attach.status_code == 200
    assert own_attach.json()["results"][0]["ok"] is True
    assert len(own_attach.json()["sources"]) == 1

    other_source_attach = first_client.post(
        f"/api/mining/projects/{project['id']}/sources",
        json={"sources": [{"source_type": "file", "source_id": second_file_item["id"], "title": "B 样本"}]},
    )
    assert other_source_attach.status_code == 200
    assert other_source_attach.json()["results"][0]["ok"] is False
    assert len(other_source_attach.json()["sources"]) == 1

    other_project_attach = second_client.post(
        f"/api/mining/projects/{project['id']}/sources",
        json={"sources": [{"source_type": "file", "source_id": second_file_item["id"], "title": "B 样本"}]},
    )
    assert other_project_attach.status_code == 404


def test_mining_project_create_rename_and_empty_learn(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    created = client.post("/api/mining/projects", json={"name": "作者策略学习"})
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["name"] == "作者策略学习"

    renamed = client.patch(f"/api/mining/projects/{project['id']}", json={"name": "新名字"})
    assert renamed.status_code == 200
    assert renamed.json()["project"]["name"] == "新名字"

    empty = client.post(f"/api/mining/projects/{project['id']}/learn-creation-strategy")
    assert empty.status_code == 400


def test_mining_file_source_and_strategy_version(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    monkeypatch.setattr(
        api_settings,
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
        deepseek_client,
        "learn_creation_strategy",
        lambda materials, previous_strategy="", setting=None: CreationStrategyResult(
            title="作者创作策略",
            applicable_scenarios=["公众号文章"],
            author_style_profile=["用强问题开场"],
            topic_strategy=["围绕读者痛点选题"],
            structure_strategy=["问题-原因-方案"],
            opening_patterns=["先抛反常识判断"],
            transition_patterns=["用递进句转入解释"],
            ending_patterns=["以行动清单收束"],
            language_style=["短句密集"],
            rhythm_and_emotion=["先紧张后确定"],
            short_video_talk_strategy=["前三秒给冲突"],
            reusable_templates=["痛点 -> 误区 -> 新框架"],
            anti_patterns=["不要平铺事实"],
            evidence=["S1 显示开头先制造冲突"],
            usage_notes="写作前作为检查清单。",
            summary="学习到一版策略。",
        ),
    )

    project = client.post("/api/mining/projects", json={"name": "作者策略学习"}).json()["project"]
    upload = client.post("/api/files", files={"files": ("sample.txt", b"hook\nbody\nending", "text/plain")})
    assert upload.status_code == 200
    file_id = upload.json()["items"][0]["id"]

    attached = client.post(
        f"/api/mining/projects/{project['id']}/sources",
        json={"sources": [{"source_type": "file", "source_id": file_id, "title": "样本文章"}]},
    )
    assert attached.status_code == 200
    assert len(attached.json()["sources"]) == 1

    learned = client.post(f"/api/mining/projects/{project['id']}/learn-creation-strategy")
    assert learned.status_code == 200
    payload = learned.json()
    assert payload["project"]["artifact_path"]
    assert payload["versions"][0]["version"] == 1
    assert "作者创作策略" in payload["artifact_content"]


def test_generate_knowledge_combines_one_round(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )

    def fake_ocr(image_paths):
        assert len(image_paths) == 2
        return "combined raw text"

    def fake_generate(raw_text, setting=None):
        assert raw_text == "combined raw text"
        assert setting["model"] == "test-model"
        return (
            KnowledgeResult(
                title="OpenAI",
                topic="market",
                tags=["round"],
                focus_question="What do the screenshots show?",
                clusters=[],
                investment_insights="Combined insight.",
            ),
            raw_text,
        )

    monkeypatch.setattr(ocr_client, "recognize_screenshots", fake_ocr)
    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    monkeypatch.setattr(
        deepseek_client,
        "extract_knowledge_network",
        lambda knowledge, existing_nodes=None, setting=None: KnowledgeNetworkExtraction(
            nodes=[
                ExtractedTermNode(
                    name=knowledge.title,
                    category="信息视野拓展",
                    term_type="主题",
                    summary="A graph summary.",
                )
            ],
            relations=[],
        ),
    )

    client = TestClient(app.app)
    response = client.post(
        "/api/images",
        files=[
            ("files", ("one.png", PNG_1X1, "image/png")),
            ("files", ("two.png", PNG_1X1 + b"2", "image/png")),
        ],
    )
    assert response.status_code == 200
    image_ids = [item["id"] for item in response.json()["items"]]

    generated = client.post("/api/knowledge/generate", json={"image_ids": image_ids})
    assert generated.status_code == 200
    body = generated.json()
    assert body["item"]["title"] == "OpenAI"
    assert body["skipped"] is False
    assert "graph_status" not in body["item"]

    listed = client.get("/api/knowledge")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    preview = client.get(f"/api/knowledge/{body['item']['id']}")
    assert preview.status_code == 200
    assert "combined raw text" in preview.json()["content"]

def test_generate_knowledge_uses_ai_vision_mode(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Vision API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "vision-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )

    def fail_local_ocr(_image_paths):
        raise AssertionError("local OCR should not be used")

    def fake_ai_ocr(image_paths, setting=None):
        assert len(image_paths) == 2
        assert setting["model"] == "vision-model"
        return "ai recognized text"

    def fake_generate(raw_text, setting=None):
        assert raw_text == "ai recognized text"
        assert setting["model"] == "vision-model"
        return (
            KnowledgeResult(
                title="AI Vision Round",
                topic="vision",
                tags=["vision"],
                focus_question="What do the screenshots say?",
                clusters=[],
                investment_insights="Vision insight.",
            ),
            raw_text,
        )

    monkeypatch.setattr(ocr_client, "recognize_screenshots", fail_local_ocr)
    monkeypatch.setattr(deepseek_client, "recognize_screenshots_with_ai", fake_ai_ocr)
    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    monkeypatch.setattr(
        deepseek_client,
        "extract_knowledge_network",
        lambda knowledge, existing_nodes=None, setting=None: KnowledgeNetworkExtraction(
            nodes=[
                ExtractedTermNode(
                    name=knowledge.title,
                    category="信息视野拓展",
                    term_type="主题",
                    summary="Vision graph summary.",
                )
            ],
            relations=[],
        ),
    )

    client = TestClient(app.app)
    response = client.post(
        "/api/images",
        files=[
            ("files", ("one.png", PNG_1X1, "image/png")),
            ("files", ("two.png", PNG_1X1 + b"2", "image/png")),
        ],
    )
    assert response.status_code == 200
    image_ids = [item["id"] for item in response.json()["items"]]

    generated = client.post(
        "/api/knowledge/generate",
        json={"image_ids": image_ids, "parser_mode": "ai_vision"},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["item"]["title"] == "AI Vision Round"
    assert body["parser_mode"] == "ai_vision"


def test_upload_files_and_generate_knowledge_round(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "File API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "file-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )

    def fake_generate(raw_text, setting=None):
        assert "[File 1: one.md]" in raw_text
        assert "[File 2: two.txt]" in raw_text
        assert "Markdown input" in raw_text
        assert setting["model"] == "file-model"
        return (
            KnowledgeResult(
                title="文件知识",
                topic="文件输入",
                tags=["文件"],
                focus_question="文件讲了什么？",
                clusters=[],
                investment_insights="文件输入洞察。",
            ),
            raw_text,
        )

    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "File API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "file-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/files",
        files=[
            ("files", ("one.md", b"# Markdown input\n\nAlpha", "text/markdown")),
            ("files", ("two.txt", "文本输入".encode("utf-8"), "text/plain")),
        ],
    )
    assert uploaded.status_code == 200
    file_ids = [item["id"] for item in uploaded.json()["items"]]

    generated = client.post("/api/knowledge/generate-from-files", json={"file_ids": file_ids})
    assert generated.status_code == 200
    body = generated.json()
    assert body["item"]["title"] == "文件知识"
    assert body["item"]["source_type"] == "files"
    assert "graph_status" not in body["item"]

    repeated = client.post("/api/knowledge/generate-from-files", json={"file_ids": file_ids})
    assert repeated.status_code == 200
    assert repeated.json()["skipped"] is True


def test_media_upload_transcript_and_generate_knowledge(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)

    def fake_generate(raw_text, setting=None):
        assert "[Platform: local]" in raw_text
        assert "第一句话" in raw_text
        return (
            KnowledgeResult(
                title="音视频知识",
                topic="媒体学习",
                tags=["音视频"],
                focus_question="媒体讲了什么",
                clusters=[],
                investment_insights="媒体启发",
            ),
            raw_text,
        )

    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Media API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "media-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/media/upload",
        files={
            "files": (
                "demo.srt",
                "1\n00:00:01,000 --> 00:00:03,000\n第一句话\n".encode("utf-8"),
                "application/x-subrip",
            )
        },
    )
    assert uploaded.status_code == 200
    media_id = uploaded.json()["items"][0]["id"]

    transcribed = client.post("/api/media/transcript", json={"media_ids": [media_id]})
    assert transcribed.status_code == 200
    assert transcribed.json()["items"][0]["ok"] is True
    transcripts = client.get("/api/media/transcripts")
    assert transcripts.status_code == 200
    assert transcripts.json()["items"][0]["id"] == media_id
    transcript_preview = client.get(f"/api/media/{media_id}/transcript")
    assert transcript_preview.status_code == 200
    assert "第一句话" in transcript_preview.json()["content"]

    generated = client.post("/api/knowledge/generate-from-media", json={"media_ids": [media_id]})
    assert generated.status_code == 200
    body = generated.json()
    assert body["item"]["source_type"] == "media"
    assert body["item"]["title"] == "音视频知识"
    assert client.get("/api/knowledge").json()["items"][0]["title"] == "音视频知识"


def test_media_plan_generates_segment_knowledge(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Media API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "media-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )

    def fake_generate(raw_text, setting=None):
        assert "[Time Range:" in raw_text
        assert "第二句话" in raw_text
        return (
            KnowledgeResult(
                title="规划知识",
                topic="媒体规划",
                tags=["规划"],
                focus_question="规划段讲了什么",
                clusters=[],
                investment_insights="规划启发",
            ),
            raw_text,
        )

    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/media/upload",
        files={
            "files": (
                "demo.srt",
                "1\n00:00:01,000 --> 00:00:03,000\n第一句话\n\n2\n00:00:04,000 --> 00:00:06,000\n第二句话\n".encode("utf-8"),
                "application/x-subrip",
            )
        },
    )
    media_id = uploaded.json()["items"][0]["id"]
    planned = client.post("/api/media/plan-ranges", json={"media_ids": [media_id]})
    assert planned.status_code == 200
    segment = planned.json()["plan"]["segments"][0]
    segment["title"] = "测试规划段"
    generated = client.post("/api/knowledge/generate-from-media-plan", json={"segments": [segment]})
    assert generated.status_code == 200
    assert generated.json()["items"][0]["item"]["title"] == "规划知识"


def test_media_resolve_url_examples(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(media_parser, "ytdlp_dump_json", lambda url: None)
    monkeypatch.setattr(
        media_parser,
        "follow_redirect",
        lambda url: "https://www.iesdouyin.com/share/video/7645662793240815025/?from=web_code_link",
    )
    client = TestClient(app.app)

    bilibili = client.post(
        "/api/media/resolve-url",
        json={"url": "https://www.bilibili.com/video/BV1A7V36BEc9?t=25.8"},
    )
    assert bilibili.status_code == 200
    assert bilibili.json()["item"]["platform"] == "bilibili"
    assert "BV1A7V36BEc9" in bilibili.json()["item"]["canonical_url"]

    douyin = client.post("/api/media/resolve-url", json={"url": "https://v.douyin.com/zXGKv6QWCM4/"})
    assert douyin.status_code == 200
    assert douyin.json()["item"]["platform"] == "douyin"
    assert "7645662793240815025" in douyin.json()["item"]["canonical_url"]


def test_bilibili_cookie_settings_endpoints(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    cookie_file = tmp_path / "auth" / "bilibili.cookies.txt"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tDedeUserID\t123\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tbili_jct\tcsrf\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(media_parser.YTDLP_COOKIES_FILE_ENV, str(cookie_file))
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, raising=False)
    monkeypatch.setattr(media_parser, "launch_bilibili_cookie_login", lambda url=None: {"ok": True, "message": "opened", "url": url})
    client = TestClient(app.app)

    status = client.get("/api/media/bilibili-cookies")
    assert status.status_code == 200
    assert status.json()["ok"] is True

    launched = client.post("/api/media/bilibili-cookies/login", json={"url": "https://space.bilibili.com/520819684"})
    assert launched.status_code == 200
    assert launched.json()["ok"] is True


def test_doc_upload_is_rejected_with_clear_message(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    response = client.post("/api/files", files={"files": ("legacy.doc", b"doc", "application/msword")})
    assert response.status_code == 400
    assert ".doc" in response.json()["detail"]


def test_media_dependencies_include_asr_status_and_cookie_auth(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    cookie_file = tmp_path / "bilibili.cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tDedeUserID\t123\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tbili_jct\tcsrf\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(media_parser.YTDLP_COOKIES_FILE_ENV, str(cookie_file))
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, raising=False)
    monkeypatch.setattr(media_parser, "ytdlp_command", lambda: "yt-dlp")
    monkeypatch.setattr(media_parser, "ffmpeg_command", lambda: "ffmpeg")

    asr_setting_file = tmp_path / "asr_settings.json"
    monkeypatch.setattr(app.asr_settings, "SETTINGS_PATH", asr_setting_file)
    monkeypatch.setattr(media_parser.asr_settings, "SETTINGS_PATH", asr_setting_file)
    saved = app.asr_settings.save_setting(
        {
          "provider": "openai",
          "base_url": "https://api.openai.com/v1",
          "model": "gpt-4o-mini-transcribe",
          "api_key": "asr-secret-key",
          "timeout": 90,
        }
    )
    app.asr_settings.mark_test_result(True, "ASR ready")

    client = TestClient(app.app)
    response = client.get("/api/media/dependencies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["bilibili_subtitle"]["available"] is True
    assert "已配置登录 Cookie" in payload["bilibili_subtitle"]["auth"]
    assert payload["local_audio_extract"]["available"] is True
    assert payload["speech_to_text"]["configured"] is True
    assert payload["speech_to_text"]["verified"] is True
    assert payload["speech_to_text"]["provider"] == saved["provider"]
    assert payload["speech_to_text"]["model"] == saved["model"]


def test_plan_file_and_generate_selected_segments(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Planning API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "plan-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/files",
        files={"files": ("long.md", b"# Report\n\nAlpha section\n\nBeta section", "text/markdown")},
    )
    file_id = uploaded.json()["items"][0]["id"]

    def fake_pages(_path):
        return [
            {"page": 1, "text": "Alpha section", "char_count": 13, "used_ocr": False},
            {"page": 2, "text": "Beta section", "char_count": 12, "used_ocr": False},
        ]

    monkeypatch.setattr(document_parser, "document_pages", fake_pages)
    monkeypatch.setattr(
        deepseek_client,
        "plan_document_knowledge",
        lambda **kwargs: DocumentPlanResult(
            summary="Split by theme.",
            segments=[
                DocumentPlanSegment(id="s1", title="Alpha", theme="Alpha theme", page_start=1, page_end=1, estimated_chars=13),
                DocumentPlanSegment(id="s2", title="Beta", theme="Beta theme", page_start=2, page_end=2, estimated_chars=12),
            ],
        ),
    )

    planned = client.post("/api/files/plan", json={"file_id": file_id})
    assert planned.status_code == 200
    plan = planned.json()["plan"]
    assert plan["file_id"] == file_id
    assert len(plan["segments"]) == 2

    generated_titles = []

    def fake_generate(raw_text, setting=None):
        title = "Alpha Knowledge" if "Alpha section" in raw_text else "Beta Knowledge"
        generated_titles.append(title)
        return (
            KnowledgeResult(
                title=title,
                topic="planned",
                tags=["planned"],
                focus_question="What does this segment say?",
                clusters=[],
                investment_insights="Segment insight.",
            ),
            raw_text,
        )

    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    selected_segments = plan["segments"]
    selected_segments[1]["selected"] = False
    generated = client.post(
        "/api/knowledge/generate-from-file-plan",
        json={"file_id": file_id, "segments": selected_segments},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["generated"] == 1
    assert body["items"][0]["item"]["title"] == "Alpha Knowledge"
    assert generated_titles == ["Alpha Knowledge"]

    listed = client.get("/api/knowledge")
    assert any(item["title"] == "Alpha Knowledge" for item in listed.json()["items"])


def test_multi_file_page_ranges_plan_and_generate(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Planning API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "plan-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/files",
        files=[
            ("files", ("first.md", b"first", "text/markdown")),
            ("files", ("second.md", b"second", "text/markdown")),
        ],
    )
    file_ids = [item["id"] for item in uploaded.json()["items"]]

    def fake_pages(path):
        if path.read_text(encoding="utf-8") == "first":
            return [
                {"page": 1, "text": "First p1", "char_count": 8, "used_ocr": False},
                {"page": 2, "text": "First p2", "char_count": 8, "used_ocr": False},
                {"page": 3, "text": "First p3", "char_count": 8, "used_ocr": False},
            ]
        return [
            {"page": 1, "text": "Second p1", "char_count": 9, "used_ocr": False},
            {"page": 2, "text": "Second p2", "char_count": 9, "used_ocr": False},
        ]

    monkeypatch.setattr(document_parser, "document_pages", fake_pages)

    def fake_plan(file_name, file_type, page_count, total_chars, page_overview, setting=None):
        assert "p3" not in page_overview
        return DocumentPlanResult(
            summary=f"Plan {file_name}",
            segments=[
                DocumentPlanSegment(
                    id="segment-1",
                    title=f"{file_name} selected",
                    theme="selected range",
                    page_start=1,
                    page_end=page_count,
                    estimated_chars=total_chars,
                )
            ],
        )

    monkeypatch.setattr(deepseek_client, "plan_document_knowledge", fake_plan)
    page_info = client.post("/api/files/page-info", json={"file_ids": file_ids})
    assert page_info.status_code == 200
    assert [item["page_count"] for item in page_info.json()["items"]] == [3, 2]

    planned = client.post(
        "/api/files/plan-ranges",
        json={
            "files": [
                {"file_id": file_ids[0], "page_ranges": "1-2"},
                {"file_id": file_ids[1], "page_ranges": "2"},
            ]
        },
    )
    assert planned.status_code == 200
    segments = planned.json()["plan"]["segments"]
    assert len(segments) == 2
    assert {segment["file_id"] for segment in segments} == set(file_ids)
    by_file = {segment["file_id"]: segment for segment in segments}
    assert by_file[file_ids[0]]["page_ranges"] == "1-2"
    assert by_file[file_ids[1]]["page_ranges"] == "2"

    monkeypatch.setattr(
        deepseek_client,
        "generate_knowledge_from_text",
        lambda raw_text, setting=None: (
            KnowledgeResult(
                title="Range Knowledge",
                topic="range",
                tags=["range"],
                focus_question="Range?",
                clusters=[],
                investment_insights="Range insight.",
            ),
            raw_text,
        ),
    )
    segments[0]["selected"] = True
    segments[1]["selected"] = False
    generated = client.post("/api/knowledge/generate-from-plan-segments", json={"segments": segments})
    assert generated.status_code == 200
    assert generated.json()["generated"] == 1


def test_file_plan_clips_ai_segments_to_selected_pages(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {"id": "test", "name": "Planning API", "model": "plan-model", "api_key": "test-key"},
    )
    client = TestClient(app.app)
    uploaded = client.post(
        "/api/files",
        files={"files": ("range.md", b"range", "text/markdown")},
    )
    file_id = uploaded.json()["items"][0]["id"]

    monkeypatch.setattr(
        document_parser,
        "document_pages",
        lambda path: [
            {"page": index, "text": f"Page {index}", "char_count": 6, "used_ocr": False}
            for index in range(1, 6)
        ],
    )

    monkeypatch.setattr(
        deepseek_client,
        "plan_document_knowledge",
        lambda **kwargs: DocumentPlanResult(
            segments=[
                DocumentPlanSegment(
                    id="segment-1",
                    title="Out of range plan",
                    theme="range",
                    page_start=1,
                    page_end=5,
                )
            ]
        ),
    )
    planned = client.post(
        "/api/files/plan-ranges",
        json={"files": [{"file_id": file_id, "page_ranges": "1;3-4"}]},
    )
    assert planned.status_code == 200
    segment = planned.json()["plan"]["segments"][0]
    assert segment["page_start"] == 1
    assert segment["page_end"] == 4
    assert segment["page_ranges"] == "1;3-4"

    captured = {}

    def fake_generate(raw_text, setting=None):
        captured["raw_text"] = raw_text
        return (
            KnowledgeResult(
                title="Selected Pages",
                topic="range",
                tags=["range"],
                focus_question="Range?",
                clusters=[],
                investment_insights="Range insight.",
            ),
            raw_text,
        )

    monkeypatch.setattr(deepseek_client, "generate_knowledge_from_text", fake_generate)
    generated = client.post("/api/knowledge/generate-from-plan-segments", json={"segments": [segment]})
    assert generated.status_code == 200
    assert "Page 1" in captured["raw_text"]
    assert "Page 2" not in captured["raw_text"]
    assert "Page 3" in captured["raw_text"]
    assert "Page 4" in captured["raw_text"]
    assert "Page 5" not in captured["raw_text"]


def test_pasted_image_upload_uses_data_url(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    data_url = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii")
    client = TestClient(app.app)

    response = client.post(
        "/api/images/paste",
        json={"images": [{"filename": "clipboard.png", "content_type": "image/png", "data_url": data_url}]},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "uploaded"
    assert item["image_path"].endswith(".png")


def test_pasted_duplicate_image_reuses_existing_record(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    data_url = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii")
    client = TestClient(app.app)
    payload = {"images": [{"filename": "clipboard.png", "content_type": "image/png", "data_url": data_url}]}

    first = client.post("/api/images/paste", json=payload)
    second = client.post("/api/images/paste", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_item = first.json()["items"][0]
    second_item = second.json()["items"][0]
    assert second_item["duplicate"] is True
    assert second_item["id"] == first_item["id"]


def test_api_settings_save_and_activate(tmp_path, monkeypatch):
    monkeypatch.setattr(api_settings, "SETTINGS_PATH", tmp_path / "api_settings.json")
    monkeypatch.setattr(api_settings, "_env_setting", lambda: None)
    client = TestClient(app.app)

    saved = client.post(
        "/api/api-settings",
        json={
            "name": "Relay",
            "provider": "compatible",
            "base_url": "https://relay.example.com/v1",
            "model": "relay-model",
            "api_key": "secret-key",
            "timeout": 90,
            "max_retries": 1,
            "make_active": True,
        },
    )

    assert saved.status_code == 200
    body = saved.json()
    item = body["item"]
    assert body["active_id"] == item["id"]
    assert item["api_key_masked"] == "secr...-key"
    assert "api_key" not in item

    listed = client.get("/api/api-settings")
    assert listed.status_code == 200
    assert any(item["name"] == "Relay" for item in listed.json()["items"])

    updated = client.post(
        "/api/api-settings",
        json={
            "id": item["id"],
            "name": "Relay Updated",
            "provider": "compatible",
            "base_url": "https://relay2.example.com/v1",
            "model": "relay-model-2",
            "api_key": "",
            "timeout": 120,
            "max_retries": 2,
            "make_active": True,
        },
    )

    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["item"]["id"] == item["id"]
    assert updated_body["item"]["name"] == "Relay Updated"
    assert updated_body["item"]["model"] == "relay-model-2"
    assert len(updated_body["items"]) == 1


def test_api_settings_test_uses_form_payload_for_existing_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(api_settings, "SETTINGS_PATH", tmp_path / "api_settings.json")
    monkeypatch.setattr(api_settings, "_env_setting", lambda: None)
    client = TestClient(app.app)

    saved = client.post(
        "/api/api-settings",
        json={
            "name": "Relay",
            "provider": "compatible",
            "base_url": "https://relay.example.com/v1",
            "model": "old-model",
            "api_key": "secret-key",
            "timeout": 90,
            "max_retries": 1,
            "make_active": True,
        },
    )
    setting_id = saved.json()["item"]["id"]

    captured = {}

    def fake_diagnose(setting=None):
        captured.update(setting)
        return {"ok": "true", "model": setting["model"], "provider": setting["provider"]}

    monkeypatch.setattr(deepseek_client, "diagnose", fake_diagnose)

    response = client.post(
        "/api/api-settings/test",
        json={
            "id": setting_id,
            "setting": {
                "id": setting_id,
                "name": "Relay",
                "provider": "compatible",
                "base_url": "https://relay-new.example.com/v1",
                "model": "new-model",
                "api_key": "",
                "timeout": 120,
                "max_retries": 2,
                "make_active": True,
            },
        },
    )

    assert response.status_code == 200
    assert captured["model"] == "new-model"
    assert captured["base_url"] == "https://relay-new.example.com/v1"
    assert captured["api_key"] == "secret-key"


def test_image_api_settings_test_uses_form_payload_for_existing_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(image_api_settings, "SETTINGS_PATH", tmp_path / "image_api_settings.json")
    client = TestClient(app.app)

    saved = client.post(
        "/api/image-api-settings",
        json={
            "name": "Image Relay",
            "provider": "compatible",
            "base_url": "https://relay.example.com/v1",
            "model": "old-image-model",
            "api_key": "secret-key",
            "size": "1024x1024",
            "quality": "auto",
            "timeout": 90,
            "make_active": True,
        },
    )
    setting_id = saved.json()["item"]["id"]

    captured = {}

    def fake_image_diagnose(setting=None):
        captured.update(setting)
        return {"ok": "true", "model": setting["model"], "provider": setting["provider"]}

    monkeypatch.setattr(image_api_settings, "diagnose", fake_image_diagnose)

    response = client.post(
        "/api/image-api-settings/test",
        json={
            "id": setting_id,
            "setting": {
                "id": setting_id,
                "name": "Image Relay",
                "provider": "compatible",
                "base_url": "https://relay-new.example.com/v1",
                "model": "new-image-model",
                "api_key": "",
                "size": "1536x1024",
                "quality": "hd",
                "response_format": "b64_json",
                "timeout": 120,
                "make_active": True,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] == "true"
    assert captured["model"] == "new-image-model"
    assert captured["base_url"] == "https://relay-new.example.com/v1"
    assert captured["api_key"] == "secret-key"
    assert captured["size"] == "1536x1024"
    assert captured["quality"] == "hd"


def test_asr_settings_test_reuses_saved_api_key_when_form_omits_it(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_settings, "SETTINGS_PATH", tmp_path / "asr_settings.json")
    client = TestClient(app.app)

    saved = client.post(
        "/api/asr-settings",
        json={
            "provider": "compatible",
            "base_url": "https://asr.example.com/v1",
            "model": "paraformer-v1",
            "api_key": "secret-asr-key",
            "timeout": 45,
        },
    )

    assert saved.status_code == 200

    captured = {}

    def fake_transcribe(url, setting):
        captured["url"] = url
        captured["setting"] = dict(setting)
        return {"text": "ok"}

    monkeypatch.setattr(app, "transcribe_audio_url", fake_transcribe)

    tested = client.post(
        "/api/asr-settings/test",
        json={
            "provider": "dashscope",
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "model": "paraformer-v2",
            "api_key": "",
            "timeout": 30,
        },
    )

    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert captured["setting"]["api_key"] == "secret-asr-key"
    assert captured["setting"]["provider"] == "dashscope"
    assert captured["setting"]["model"] == "paraformer-v2"


def test_asr_settings_test_supports_minimax_local_audio_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(asr_settings, "SETTINGS_PATH", tmp_path / "asr_settings.json")
    client = TestClient(app.app)
    captured = {}

    def fake_transcribe_audio(path: Path):
        captured["path"] = path
        captured["setting"] = dict(asr_settings.active_setting())
        return "ok"

    def fail_transcribe_url(url, setting):
        raise AssertionError("MiniMax ASR must not use DashScope URL transcription")

    monkeypatch.setattr(app, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(app, "transcribe_audio_url", fail_transcribe_url)

    tested = client.post(
        "/api/asr-settings/test",
        json={
            "provider": "minimax",
            "base_url": "https://api.minimaxi.com/v1",
            "model": "Speech-2.8-HD",
            "api_key": "minimax-secret",
            "timeout": 30,
        },
    )

    assert tested.status_code == 200
    payload = tested.json()
    assert payload["ok"] is True
    assert payload["item"]["provider"] == "minimax"
    assert payload["item"]["model"] == "Speech-2.8-HD"
    assert "minimax-secret" not in str(payload)
    assert captured["path"].suffix == ".wav"
    assert captured["setting"]["provider"] == "minimax"


@pytest.mark.skip(reason="graph_core specific coverage moved to tests/test_graph_core.py")
def test_graph_merges_related_markdowns_into_one_topic_node(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first = storage.create_or_update_knowledge_entry([1], "merge-hash-1")
    second = storage.create_or_update_knowledge_entry([2], "merge-hash-2")
    knowledge_one = KnowledgeResult(
        title="长鑫科技科创板IPO",
        topic="长鑫科技、DRAM、IPO",
        tags=["长鑫科技", "DRAM"],
        focus_question="长鑫科技 IPO 信息",
        clusters=[],
        investment_insights="",
    )
    knowledge_two = KnowledgeResult(
        title="长鑫科技与国产DRAM",
        topic="长鑫科技、国产存储",
        tags=["长鑫科技", "DRAM"],
        focus_question="长鑫科技 DRAM 信息",
        clusters=[],
        investment_insights="",
    )
    extraction_one = KnowledgeNetworkExtraction(
        nodes=[
            ExtractedTermNode(name="长鑫科技", category="信息视野拓展", term_type="公司"),
            ExtractedTermNode(name="DRAM", category="信息视野拓展", term_type="技术"),
            ExtractedTermNode(name="IPO", category="社会宏观认知", term_type="事件"),
        ],
        relations=[],
    )
    extraction_two = KnowledgeNetworkExtraction(
        nodes=[
            ExtractedTermNode(name="长鑫科技", category="信息视野拓展", term_type="公司"),
            ExtractedTermNode(name="DRAM", category="信息视野拓展", term_type="技术"),
        ],
        relations=[],
    )

    graph_core.ingest_knowledge_network(first, knowledge_one, extraction_one)
    graph_core.ingest_knowledge_network(second, knowledge_two, extraction_two)

    payload = graph_core.graph_payload()
    changxin_nodes = [
        node for node in payload["nodes"]
        if node["node_type"] == "term" and node["label"] == "长鑫科技"
    ]
    assert len(changxin_nodes) == 1
    detail = graph_core.node_detail(changxin_nodes[0]["id"])
    assert len(detail["knowledge"]) == 2


@pytest.mark.skip(reason="graph_core specific coverage moved to tests/test_graph_core.py")
def test_graph_fallback_splits_compound_title_into_clean_terms(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "compound-hash")
    knowledge = KnowledgeResult(
        title="美股三大巨无霸IPO AI 商业航天",
        topic="美股、IPO、AI、商业航天",
        tags=["美股", "IPO", "AI", "商业航天"],
        focus_question="SpaceX、Starlink星链、Grok AI、Anthropic 的信息",
        clusters=[],
        investment_insights="",
    )

    graph_core.ingest_knowledge_network(entry, knowledge, graph_core.fallback_network_extraction(knowledge))

    labels = {node["label"] for node in graph_core.graph_payload()["nodes"]}
    for expected in {"美股", "IPO", "AI", "商业航天", "SpaceX", "Starlink星链", "Grok AI", "Anthropic"}:
        assert expected in labels
    assert "巨无霸" not in labels


@pytest.mark.skip(reason="graph_core specific coverage moved to tests/test_graph_core.py")
def test_graph_rejects_question_fragments_and_metric_descriptions(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "dirty-node-hash")
    knowledge = KnowledgeResult(
        title="2025年至2026年一季度业绩变化与长鑫科技",
        topic="长鑫科技、DRAM、业绩变化",
        tags=["长鑫科技", "DRAM"],
        focus_question="OCR文本呈现了哪些信息，业绩变化是什么？",
        clusters=[],
        investment_insights="",
    )
    extraction = KnowledgeNetworkExtraction(
        nodes=[
            ExtractedTermNode(name="2025年至2026年一季度业绩变化", category="信息视野拓展"),
            ExtractedTermNode(name="OCR文本呈现了哪些", category="信息视野拓展"),
            ExtractedTermNode(name="长鑫科技", category="信息视野拓展"),
            ExtractedTermNode(name="DRAM", category="信息视野拓展"),
        ],
        relations=[],
    )

    graph_core.ingest_knowledge_network(entry, knowledge, extraction)

    labels = {node["label"] for node in graph_core.graph_payload()["nodes"]}
    assert "长鑫科技" in labels
    assert "DRAM" in labels
    assert "2025年至2026年一季度业绩变化" not in labels
    assert "OCR文本呈现了哪些" not in labels


@pytest.mark.skip(reason="graph_core specific coverage moved to tests/test_graph_core.py")
def test_graph_duplicate_labels_keep_higher_level_node(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "level-dup-hash")
    knowledge = KnowledgeResult(
        title="国产芯",
        topic="国产芯",
        tags=["国产芯"],
        focus_question="",
        clusters=[],
        investment_insights="",
    )
    graph_core.ingest_knowledge_network(
        entry,
        knowledge,
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="国产芯", category="信息视野拓展")], relations=[]),
    )
    graph_core.apply_graph_organization(
        GraphOrganizationResult(
            groups=[
                GraphGroup(
                    name="国产芯",
                    category="信息视野拓展",
                    summary="同名高层分组",
                    child_nodes=["国产芯"],
                )
            ]
        )
    )

    nodes = [node for node in graph_core.graph_payload()["nodes"] if node["label"] == "国产芯"]
    assert len(nodes) == 1
    assert nodes[0]["node_type"] == "group"


def _disabled_manual_graph_ingest_marks_failed_files_without_blocking_success(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first_id = make_ready_knowledge("OpenAI", "manual-ingest-ok")
    second_id = make_ready_knowledge("Broken", "manual-ingest-fail")
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )

    def fake_extract(knowledge, existing_nodes=None, setting=None):
        if knowledge.title == "Broken":
            raise RuntimeError("extract failed")
        return KnowledgeNetworkExtraction(
            nodes=[ExtractedTermNode(name=knowledge.title, category="信息视野拓展")],
            relations=[],
        )

    def fake_fallback(knowledge):
        if knowledge.title == "Broken":
            raise RuntimeError("fallback failed")
        return KnowledgeNetworkExtraction(
            nodes=[ExtractedTermNode(name=knowledge.title, category="信息视野拓展")],
            relations=[],
        )

    monkeypatch.setattr(deepseek_client, "extract_knowledge_network", fake_extract)
    monkeypatch.setattr(graph_core, "fallback_network_extraction", fake_fallback)
    client = TestClient(app.app)

    response = client.post("/api/knowledge/ingest-to-graph", json={"knowledge_ids": [first_id, second_id]})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    items = {item["id"]: item for item in client.get("/api/knowledge").json()["items"]}
    assert "graph_status" not in items[first_id]
    assert "graph_status" not in items[second_id]


def _disabled_delete_not_ingested_knowledge_protects_graph_items(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    deletable_id = make_ready_knowledge("未入网知识", "delete-not-ingested")
    protected_id = make_ready_knowledge("已入网知识", "delete-ingested")
    protected = storage.get_knowledge_entry(protected_id)
    graph_core.ingest_knowledge_network(
        protected,
        KnowledgeResult(title="已入网知识", topic="AI", tags=["AI"], focus_question="", clusters=[], investment_insights=""),
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="OpenAI", category="信息视野拓展")], relations=[]),
    )
    deletable_path = storage.resolve_root_path(storage.get_knowledge_entry(deletable_id)["markdown_path"])
    protected_path = storage.resolve_root_path(storage.get_knowledge_entry(protected_id)["markdown_path"])
    client = TestClient(app.app)

    response = client.post(
        "/api/knowledge/delete-not-ingested",
        json={"knowledge_ids": [deletable_id, protected_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["deleted"]] == [deletable_id]
    assert body["skipped"][0]["id"] == protected_id
    assert deletable_path is not None and not deletable_path.exists()
    assert protected_path is not None and protected_path.exists()
    remaining_ids = {item["id"] for item in body["items"]}
    assert deletable_id not in remaining_ids
    assert protected_id in remaining_ids


def test_update_knowledge_edits_metadata_and_markdown(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    knowledge_id = make_ready_knowledge("旧标题", "update-knowledge")

    response = client.post(
        f"/api/knowledge/{knowledge_id}",
        json={
            "title": "新标题",
            "note": "新的备注",
            "body": "# 新标题\n\n正文第一段。\n\n- 要点",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["item"]["title"] == "新标题"
    assert payload["item"]["topic"] == "新的备注"
    assert payload["content"] == "# 新标题\n\n正文第一段。\n\n- 要点"
    updated = storage.get_knowledge_entry(knowledge_id)
    path = storage.resolve_root_path(updated["markdown_path"])
    assert path is not None
    assert path.read_text(encoding="utf-8") == "# 新标题\n\n正文第一段。\n\n- 要点"


def test_commit_draft_updates_existing_markdown_without_injecting_note(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    knowledge_id = make_ready_knowledge("旧标题", "commit-existing")

    body = "# 新标题\n\n正文原样保存。\n\n- 不应该被备注包裹"
    response = client.post(
        "/api/knowledge/commit-draft",
        json={
            "backend_id": knowledge_id,
            "title": "新标题",
            "note": "只进入备注字段",
            "body": body,
            "source_ids": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["item"]["title"] == "新标题"
    assert payload["item"]["topic"] == "只进入备注字段"
    assert payload["content"] == body
    updated = storage.get_knowledge_entry(knowledge_id)
    path = storage.resolve_root_path(updated["markdown_path"])
    assert path is not None
    assert path.read_text(encoding="utf-8") == body
    assert "> 只进入备注字段" not in path.read_text(encoding="utf-8")


def test_update_knowledge_strips_repeated_note_quotes_from_existing_body(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    knowledge_id = make_ready_knowledge("旧标题", "strip-repeated-note")

    note = "内容主要来自三张图片素材，正文为赴美考察后的个人感受与观点汇总；请重点核对人物引述、时间点和具体预测表述是否准确。"
    polluted_body = f"> {note}\n\n> {note}\n\n> {note}\n\n# 赴美考察后的AI与无人驾驶观察\n\n正文内容。"
    response = client.post(
        f"/api/knowledge/{knowledge_id}",
        json={"title": "新标题", "note": note, "body": polluted_body},
    )

    assert response.status_code == 200
    cleaned = "# 赴美考察后的AI与无人驾驶观察\n\n正文内容。"
    assert response.json()["content"] == cleaned
    updated = storage.get_knowledge_entry(knowledge_id)
    path = storage.resolve_root_path(updated["markdown_path"])
    assert path is not None
    assert path.read_text(encoding="utf-8") == cleaned


def make_ready_knowledge(title: str, image_hash: str) -> int:
    entry = storage.create_or_update_knowledge_entry([1], image_hash)
    md_path = storage.markdown_path_for(title, image_hash, "2026-05-29T10:00:00")
    md_path.write_text(f"# {title}\n\n## 核心知识簇\n\n- 长鑫科技\n- DRAM\n", encoding="utf-8")
    updated = storage.update_knowledge_entry(
        entry["id"],
        markdown_path=str(md_path.relative_to(storage.ROOT)),
        title=title,
        topic="半导体",
        tags='["长鑫科技","DRAM"]',
        status="ready",
    )
    return updated["id"]


def test_writer_page_and_session_load_selected_markdowns(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    knowledge_id = make_ready_knowledge("长鑫科技信息", "writer-session-hash")

    page = client.get("/writer")
    assert page.status_code == 200
    assert "写文工具" in page.text

    session = client.get(f"/api/writer/session?ids={knowledge_id}")
    assert session.status_code == 200
    body = session.json()
    assert body["knowledge_ids"] == [knowledge_id]
    assert body["items"][0]["item"]["title"] == "长鑫科技信息"
    assert "核心知识簇" in body["items"][0]["content"]


def test_writer_article_creates_workspace_and_markdown(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    knowledge_id = make_ready_knowledge("长鑫科技信息", "writer-article-hash")

    def fake_article(topic, markdown_files, setting=None):
        assert markdown_files[0][0].endswith(".md")
        assert setting["model"] == "test-model"
        return WriterArticleResult(
            title="长鑫科技为何重要",
            markdown="# 长鑫科技为何重要\n\n![封面图](cover.png)\n\n正文",
            cover_prompt="长鑫科技 公众号封面，简体中文，少量文字",
            content_image_prompts=["DRAM 产业链结构图"],
            digest="长鑫科技与国产 DRAM 的一条观察线。",
        )

    monkeypatch.setattr(deepseek_client, "generate_wechat_article", fake_article)
    client = TestClient(app.app)
    response = client.post(
        "/api/writer/article",
        json={"knowledge_ids": [knowledge_id], "topic": {"title": "长鑫科技选题"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "长鑫科技为何重要"
    article_path = tmp_path / body["article_path"]
    assert article_path.exists()
    assert "封面图" in article_path.read_text(encoding="utf-8")


def test_writer_project_saved_strategies_are_used_for_draft_generation(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    knowledge_id = make_ready_knowledge("策略测试原文", "writer-strategy-project-hash")
    captured = {}

    def fake_article(topic, markdown_files, writing_strategy="", setting=None):
        captured["writing_strategy"] = writing_strategy
        return WriterArticleResult(
            title="策略生效文章",
            markdown="# 策略生效文章\n\n正文",
            cover_prompt="封面提示词",
            content_image_prompts=["配图提示词"],
            digest="摘要",
        )

    monkeypatch.setattr(deepseek_client, "generate_wechat_article", fake_article)
    client = TestClient(app.app)

    created = client.post(
        "/api/writer/projects",
        json={
            "name": "策略项目",
            "knowledge_ids": [knowledge_id],
            "writing_strategy": "旧写文策略",
            "design_strategy": "旧美编策略",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]

    saved = client.post(
        f"/api/writer/projects/{project_id}/strategies",
        json={
            "writing_strategy": "新的写文策略：先讲结论，再给证据。",
            "design_strategy": "新的美编策略：强调重点句。",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["project"]["writing_strategy"] == "新的写文策略：先讲结论，再给证据。"
    assert saved.json()["project"]["design_strategy"] == "新的美编策略：强调重点句。"

    picked = client.post(
        f"/api/writer/projects/{project_id}/topic",
        json={"topic": {"title": "策略测试选题"}},
    )
    assert picked.status_code == 200

    drafted = client.post(
        f"/api/writer/projects/{project_id}/draft",
        json={},
    )
    assert drafted.status_code == 200
    assert captured["writing_strategy"] == "新的写文策略：先讲结论，再给证据。"
    assert drafted.json()["project"]["title"] == "策略生效文章"


def test_writer_writing_strategy_library_crud_is_independent_from_knowledge_libraries(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    listed = client.get("/api/writer/writing-strategies")
    assert listed.status_code == 200
    body = listed.json()
    default_id = body["default_id"]
    assert any(item["id"] == default_id and item["readonly"] for item in body["items"])

    created = client.post(
        "/api/writer/writing-strategies",
        json={"name": "Evidence first", "body": "Open with the conclusion, then show evidence."},
    )
    assert created.status_code == 200
    item = created.json()["item"]
    assert item["name"] == "Evidence first"
    assert item["readonly"] is False

    updated = client.post(
        "/api/writer/writing-strategies",
        json={"id": item["id"], "name": "Evidence first v2", "body": "Lead with facts before opinion."},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["body"] == "Lead with facts before opinion."

    assert client.delete(f"/api/writer/writing-strategies/{default_id}").status_code == 400
    deleted = client.delete(f"/api/writer/writing-strategies/{item['id']}")
    assert deleted.status_code == 200
    assert all(strategy["id"] != item["id"] for strategy in deleted.json()["items"])

    assert (storage.WRITER_DIR / "writing_strategies.json").exists()
    assert not list(storage.RAW_MATERIAL_DIR.rglob("*Evidence first*"))
    assert not list(storage.KNOWLEDGE_DIR.rglob("*Evidence first*"))
    assert not list(storage.MINING_DIR.rglob("*Evidence first*"))


def test_writer_project_can_apply_custom_writing_strategy_from_library(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    knowledge_id = make_ready_knowledge("strategy source", "writer-strategy-library-hash")
    captured = {}

    def fake_article(topic, markdown_files, writing_strategy="", setting=None):
        captured["writing_strategy"] = writing_strategy
        return WriterArticleResult(
            title="Strategy library article",
            markdown="# Strategy library article\n\nBody",
            cover_prompt="cover",
            content_image_prompts=["image"],
            digest="digest",
        )

    monkeypatch.setattr(deepseek_client, "generate_wechat_article", fake_article)
    client = TestClient(app.app)

    preset = client.post(
        "/api/writer/writing-strategies",
        json={"name": "Custom library strategy", "body": "Use this saved library strategy."},
    )
    assert preset.status_code == 200
    strategy_body = preset.json()["item"]["body"]

    created = client.post("/api/writer/projects", json={"name": "library strategy project", "knowledge_ids": [knowledge_id]})
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]

    saved = client.post(f"/api/writer/projects/{project_id}/strategies", json={"writing_strategy": strategy_body})
    assert saved.status_code == 200
    assert saved.json()["project"]["writing_strategy"] == strategy_body

    picked = client.post(f"/api/writer/projects/{project_id}/topic", json={"topic": {"title": "topic"}})
    assert picked.status_code == 200
    drafted = client.post(f"/api/writer/projects/{project_id}/draft", json={})
    assert drafted.status_code == 200
    assert captured["writing_strategy"] == strategy_body


def test_writer_project_design_must_be_confirmed_before_preflight(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    created = client.post(
        "/api/writer/projects",
        json={"name": "美编确认项目", "knowledge_ids": []},
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]

    def fake_format(workspace_path, markdown=None, theme="tech", design_strategy="", use_ai=True):
        path = workspace_path / "formatted.html"
        path.write_text("<html><body>preview</body></html>", encoding="utf-8")
        return {"path": str(path.relative_to(storage.ROOT)), "html": path.read_text(encoding="utf-8")}

    monkeypatch.setattr(writer_tools, "format_article", fake_format)
    monkeypatch.setattr(writer_tools, "publish_preflight", lambda *args, **kwargs: {"ok": True, "checks": [], "blocking": [], "digest": "摘要"})

    formatted = client.post(
        f"/api/writer/projects/{project_id}/format",
        json={"markdown": "# 标题\n\n正文", "design_strategy": "强调重点"},
    )
    assert formatted.status_code == 200
    assert formatted.json()["project"]["design_confirmed"] is False
    assert formatted.json()["next_action"] == "confirm_design"

    blocked = client.post(
        f"/api/writer/projects/{project_id}/publish/preflight",
        json={"title": "标题"},
    )
    assert blocked.status_code == 400
    assert "确认美编预览" in blocked.json()["detail"]

    confirmed = client.post(
        f"/api/writer/projects/{project_id}/confirm-design",
        json={"confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["project"]["design_confirmed"] is True
    assert confirmed.json()["next_action"] == "run_preflight"

    preflight = client.post(
        f"/api/writer/projects/{project_id}/publish/preflight",
        json={"title": "标题"},
    )
    assert preflight.status_code == 200
    assert preflight.json()["project"]["preflight"]["ok"] is True

    reformatted = client.post(
        f"/api/writer/projects/{project_id}/format",
        json={"markdown": "# 标题\n\n重新生成", "design_strategy": "重新强调重点"},
    )
    assert reformatted.status_code == 200
    assert reformatted.json()["project"]["design_confirmed"] is False
    assert reformatted.json()["next_action"] == "confirm_design"
    assert not reformatted.json()["project"].get("preflight")


def test_image_api_settings_save_update_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(image_api_settings, "SETTINGS_PATH", tmp_path / "image_api_settings.json")
    client = TestClient(app.app)

    saved = client.post(
        "/api/image-api-settings",
        json={
            "name": "Image Relay",
            "provider": "compatible",
            "base_url": "https://relay.example.com/v1",
            "model": "image-model",
            "api_key": "secret-key",
            "size": "1024x1024",
            "quality": "auto",
            "timeout": 90,
            "make_active": True,
        },
    )

    assert saved.status_code == 200
    item = saved.json()["item"]
    assert item["api_key_masked"] == "secr...-key"
    assert "api_key" not in item

    tested = client.post("/api/image-api-settings/test", json={"id": item["id"]})
    assert tested.status_code == 200
    assert tested.json()["ok"] == "true"

    deleted = client.delete(f"/api/image-api-settings/{item['id']}")
    assert deleted.status_code == 200


def test_v2_settings_api_and_image_routes_return_expected_data(tmp_path, monkeypatch):
    monkeypatch.setattr(api_settings, "SETTINGS_PATH", tmp_path / "api_settings.json")
    monkeypatch.setattr(image_api_settings, "SETTINGS_PATH", tmp_path / "image_api_settings.json")
    client = TestClient(app.app)

    saved_api = client.post(
        "/api/v2/settings/api",
        json={
            "name": "Relay",
            "provider": "compatible",
            "base_url": "https://relay.example.com/v1",
            "model": "chat-model",
            "api_key": "secret-key",
            "timeout": 60,
            "max_retries": 1,
            "make_active": True,
        },
    )
    assert saved_api.status_code == 200
    assert saved_api.json()["data"]["item"]["name"] == "Relay"
    assert saved_api.json()["data"]["active_id"] == saved_api.json()["data"]["item"]["id"]

    tested_api = client.post("/api/v2/settings/api/test", json={"id": saved_api.json()["data"]["item"]["id"]})
    assert tested_api.status_code == 200
    assert "ok" in tested_api.json()["data"]
    assert "provider" in tested_api.json()["data"]
    assert "model" in tested_api.json()["data"]

    saved_image = client.post(
        "/api/v2/settings/image",
        json={
            "name": "Image Relay",
            "provider": "minimax",
            "protocol": "minimax",
            "base_url": "https://api.minimaxi.com/v1/image_generation",
            "model": "image-01",
            "api_key": "secret-key",
            "size": "1024x1024",
            "quality": "",
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "timeout": 90,
            "make_active": True,
        },
    )
    assert saved_image.status_code == 200
    assert saved_image.json()["data"]["item"]["name"] == "Image Relay"
    assert saved_image.json()["data"]["item"]["protocol"] == "minimax"
    assert saved_image.json()["data"]["item"]["aspect_ratio"] == "1:1"
    assert saved_image.json()["data"]["item"]["response_format"] == "base64"
    image_id = saved_image.json()["data"]["item"]["id"]

    tested_image = client.post("/api/v2/settings/image/test", json={"id": image_id})
    assert tested_image.status_code == 200
    assert tested_image.json()["data"]["ok"] in {"true", "false"}
    assert tested_image.json()["data"]["provider"] == "minimax"
    assert tested_image.json()["data"]["protocol"] == "minimax"
    assert tested_image.json()["data"]["model"] == "image-01"

    deleted_image = client.delete(f"/api/v2/settings/image/{image_id}")
    assert deleted_image.status_code == 200


def test_image_payload_keeps_configured_quality():
    base = {
        "model": "gpt-image-2",
        "base_url": "https://relay.example.com/v1",
        "api_key": "secret-key",
        "size": "1024x1024",
    }

    payload = writer_tools._image_payload({**base, "quality": ""}, "测试图")
    assert payload["model"] == "gpt-image-2"
    assert payload["prompt"] == "测试图"
    assert payload["size"] == "1024x1024"
    assert payload["quality"] == "auto"

    for quality in ("auto", "high", "standard"):
        payload = writer_tools._image_payload({**base, "quality": quality}, "测试图")
        assert payload["quality"] == quality

    payload = writer_tools._image_payload({**base, "size": "1024×1024", "quality": ""}, "测试图")
    assert payload["size"] == "1024x1024"
    assert payload["quality"] == "auto"

    payload = writer_tools._image_payload(
        {**base, "quality": "auto", "response_format": "b64_json"},
        "测试图",
    )
    assert payload["response_format"] == "b64_json"


def test_image_endpoint_respects_protocol():
    assert (
        image_api_settings.image_endpoint(
            {
                "provider": "compatible",
                "protocol": "openai_compatible",
                "base_url": "https://relay.example.com/v1",
            }
        )
        == "https://relay.example.com/v1/images/generations"
    )
    assert (
        image_api_settings.image_endpoint(
            {
                "provider": "compatible",
                "protocol": "openai_compatible",
                "base_url": "https://relay.example.com/v1/images/generations",
            }
        )
        == "https://relay.example.com/v1/images/generations"
    )
    assert (
        image_api_settings.image_endpoint(
            {
                "provider": "minimax",
                "protocol": "minimax",
                "base_url": "https://api.minimaxi.com/v1/image_generation",
            }
        )
        == "https://api.minimaxi.com/v1/image_generation"
    )


def test_minimax_image_payload_uses_native_shape():
    payload = writer_tools._image_payload(
        {
            "provider": "minimax",
            "protocol": "minimax",
            "model": "image-01",
            "base_url": "https://api.minimaxi.com/v1/image_generation",
            "api_key": "secret-key",
            "size": "1024x1024",
            "aspect_ratio": "1:1",
            "response_format": "base64",
        },
        "测试图",
    )

    assert payload == {
        "model": "image-01",
        "prompt": "测试图",
        "aspect_ratio": "1:1",
        "response_format": "base64",
    }
    assert "size" not in payload
    assert "quality" not in payload
    assert "n" not in payload


def test_generate_image_accepts_minimax_image_base64_response(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    setting = {
        "provider": "minimax",
        "protocol": "minimax",
        "model": "image-01",
        "base_url": "https://api.minimaxi.com/v1/image_generation",
        "api_key": "secret-key",
        "size": "1024x1024",
        "aspect_ratio": "1:1",
        "response_format": "base64",
        "timeout": 90,
    }
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"data": {"image_base64": [base64.b64encode(PNG_1X1).decode("ascii")]}}
            ).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    output_path = tmp_path / "generated.png"
    result = writer_tools.generate_image("测试图", output_path, setting=setting)

    assert captured["url"] == "https://api.minimaxi.com/v1/image_generation"
    assert captured["body"] == {
        "model": "image-01",
        "prompt": "测试图",
        "aspect_ratio": "1:1",
        "response_format": "base64",
    }
    assert output_path.read_bytes() == PNG_1X1
    assert result["path"].endswith("generated.png")


def test_generate_image_escapes_non_ascii_prompt_for_compatible_api(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    setting = {
        "provider": "compatible",
        "protocol": "openai_compatible",
        "model": "gpt-image-2",
        "base_url": "https://relay.example.com/v1",
        "api_key": "secret-key",
        "size": "1024x1024",
        "quality": "auto",
        "timeout": 90,
    }
    captured: dict[str, bytes] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")}]}).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        captured["body"] = request.data
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    writer_tools.generate_image("测试图", tmp_path / "escaped.png", setting=setting)

    assert "\\u6d4b\\u8bd5\\u56fe".encode("ascii") in captured["body"]
    assert "测试图".encode("utf-8") not in captured["body"]
    assert json.loads(captured["body"].decode("utf-8"))["prompt"] == "测试图"


def test_onefaka_image_generation_bypasses_environment_proxy(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    setting = {
        "provider": "compatible",
        "protocol": "openai_compatible",
        "model": "gpt-image-2",
        "base_url": "https://api.onefaka.com/v1",
        "api_key": "secret-key",
        "size": "1024x1024",
        "quality": "auto",
        "timeout": 90,
    }
    captured: dict[str, object] = {}

    class FakeHttpxResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")}]}

    class FakeHttpxClient:
        def __init__(self, *args, **kwargs):
            captured["trust_env"] = kwargs.get("trust_env")
            captured["timeout"] = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, endpoint, content=None, headers=None):
            captured["endpoint"] = endpoint
            captured["body"] = content
            captured["headers"] = headers or {}
            return FakeHttpxResponse()

    monkeypatch.setattr(writer_tools.httpx, "Client", FakeHttpxClient)
    result = writer_tools.generate_image("测试图", tmp_path / "onefaka.png", setting=setting)

    assert captured["trust_env"] is False
    assert captured["endpoint"] == "https://api.onefaka.com/v1/images/generations"
    assert "\\u6d4b\\u8bd5\\u56fe".encode("ascii") in captured["body"]
    assert result["path"].endswith("onefaka.png")


def test_generate_image_retries_long_prompt_after_upstream_error(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    setting = {
        "model": "gpt-image-2",
        "base_url": "https://relay.example.com/v1",
        "api_key": "secret-key",
        "size": "1024x1024",
        "quality": "auto",
        "timeout": 90,
    }
    calls: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"data": [{"b64_json": base64.b64encode(PNG_1X1).decode("ascii")}]}).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        body = json.loads(request.data.decode("utf-8"))
        calls.append(body["prompt"])
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                502,
                "Bad Gateway",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"Upstream request failed"}}'),
            )
        return FakeResponse()

    monkeypatch.setattr(writer_tools.urllib.request, "urlopen", fake_urlopen)
    output = tmp_path / "writer" / "cover.png"
    result = writer_tools.generate_image("长提示词" * 500, output, setting=setting)

    assert output.read_bytes().startswith(b"\x89PNG")
    assert result["retry_used"] is True
    assert len(calls) == 2
    assert len(calls[1]) < len(calls[0])
    assert len(calls[1]) <= writer_tools.IMAGE_PROMPT_RETRY_MAX_CHARS


def test_generate_writer_images_keeps_partial_success(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("partial-images")

    def fake_generate_image(prompt, output_path, setting=None):
        if output_path.name == "content-2.png":
            raise RuntimeError("upstream 502")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(PNG_1X1)
        return {
            "path": str(output_path.relative_to(storage.ROOT)),
            "absolute_path": str(output_path),
            "prompt": prompt,
        }

    monkeypatch.setattr(writer_tools, "generate_image", fake_generate_image)
    result = writer_tools.generate_writer_images(
        workspace,
        cover_prompt="封面",
        content_prompts=["正文图一", "正文图二"],
    )

    assert len(result["items"]) == 2
    assert result["partial"] is True
    assert result["errors"][0]["index"] == 2
    assert (workspace / "cover.png").exists()
    assert (workspace / "content-1.png").exists()
    metadata = json.loads((workspace / "image_metadata.json").read_text(encoding="utf-8"))
    assert metadata["cover"]["filename"] == "cover.png"
    assert metadata["content_images"][0]["filename"] == "content-1.png"
    assert metadata["errors"][0]["message"].startswith("生成正文配图 2 失败")

def test_writer_image_metadata_canonicalizes_content_image_names(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("canonical-content-images")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    legacy_path = storage.storage_relative(workspace / "content1.png")
    (workspace / "image_metadata.json").write_text(
        json.dumps(
            {
                "content_images": [
                    {
                        "filename": "content1.png",
                        "path": legacy_path,
                        "prompt": "body prompt",
                        "index": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    metadata = writer_tools.load_writer_image_metadata(workspace)
    items = writer_tools.content_image_items(workspace)

    assert metadata["content_images"][0]["filename"] == "content-1.png"
    assert metadata["content_images"][0]["path"].endswith("content-1.png")
    assert items == [{"index": 1, "path": image_path, "prompt": "body prompt"}]


def test_generate_writer_images_applies_cover_aspect_ratio_only(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("image-ratios")
    seen: list[tuple[str, str | None]] = []

    monkeypatch.setattr(
        image_api_settings,
        "active_setting",
        lambda: {
            "provider": "minimax",
            "protocol": "minimax",
            "base_url": "https://api.example.test/v1/image_generation",
            "model": "image-model",
            "api_key": "secret-key",
            "size": "1024x1024",
            "quality": "",
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "timeout": 60,
        },
    )

    def fake_generate_image(prompt, output_path, setting=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(PNG_1X1)
        seen.append((output_path.name, None if setting is None else setting.get("aspect_ratio")))
        return {"path": storage.storage_relative(output_path), "prompt": prompt}

    monkeypatch.setattr(writer_tools, "generate_image", fake_generate_image)

    result = writer_tools.generate_writer_images(
        workspace,
        cover_prompt="cover",
        content_prompts=["content"],
        cover_aspect_ratio="2.35:1",
        content_aspect_ratio="",
    )

    assert result["ok"] is True
    assert seen == [("cover.png", "2.35:1"), ("content-1.png", None)]


def readable_document_prefers_historical_ocr_text_and_slices_by_screenshot_legacy_encoding_probe(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    old_markdown = tmp_path / "knowledge" / "2026-06-04" / "任泽平赴美考察后提醒：AI不是风口，是海啸_0229ad71.md"
    old_markdown.parent.mkdir(parents=True, exist_ok=True)
    old_markdown.write_text(
        "# 任泽平赴美考察后提醒：AI不是风口，是海啸\n\n## 原始识别文本\n```text\n"
        "[Screenshot 1]\n从美国游学回来提醒：AI不是风口，是海啸。\n"
        "1、CES变成AI展，机器人已“判若两人”\n\n"
        "[Screenshot 2]\n2、亲驾FSD后背发凉，马斯克没吹牛，很丝滑\n\n"
        "[Screenshot 3]\n3、算力的背后是能源，中美竞赛的真正“命门”\n"
        "```\n",
        encoding="utf-8",
    )
    storage.update_screenshot(
        25,
        status="error",
        error_message=str(old_markdown),
        image_path="images\\2026-06-04\\eb01436df1cb2d03.png",
    )
    storage.update_screenshot(
        26,
        status="error",
        error_message=str(old_markdown.with_name("FSD试驾与无人驾驶落地预期_3bb2b72d.md")),
        image_path="images\\2026-06-04\\8b5bebb5a42734d1.png",
    )
    storage.update_screenshot(
        27,
        status="error",
        error_message=str(old_markdown.with_name("算力背后是能源；中美AI竞赛_327fbb82.md")),
        image_path="images\\2026-06-04\\86b23dd7bee9595f.png",
    )
    client = TestClient(app.app)

    one = client.post("/api/materials/readable-document", json={"image_ids": [25], "parser_mode": "local_ocr"})
    two = client.post("/api/materials/readable-document", json={"image_ids": [26], "parser_mode": "local_ocr"})
    three = client.post("/api/materials/readable-document", json={"image_ids": [27], "parser_mode": "local_ocr"})
    combined = client.post("/api/materials/readable-document", json={"image_ids": [25, 26, 27], "parser_mode": "local_ocr"})

    assert one.status_code == two.status_code == three.status_code == combined.status_code == 200
    assert "这是本地生成的知识草稿" not in one.json()["markdown"]
    assert "1、CES变成AI展" in one.json()["markdown"]
    assert "2、亲驾FSD" in two.json()["markdown"]
    assert "3、算力的背后是能源" in three.json()["markdown"]
    combined_markdown = combined.json()["markdown"]
    assert combined_markdown.count("1、CES变成AI展") == 1
    assert combined_markdown.count("2、亲驾FSD") == 1
    assert combined_markdown.count("3、算力的背后是能源") == 1
    assert "这是本地生成的知识草稿" not in combined_markdown


def readable_document_uses_file_and_media_parsers_legacy_encoding_probe(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)

    doc_path = tmp_path / "documents" / "2026-06-04" / "sample.txt"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text("文件正文第一段\n\n文件正文第二段", encoding="utf-8")
    file_item = storage.save_document_upload(type("Upload", (), {"file": open(doc_path, "rb"), "filename": "sample.txt", "content_type": "text/plain"})())

    media_path = tmp_path / "media" / "2026-06-04" / "sample.mp3"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"media")
    media_item = storage.save_media_bytes(media_path.read_bytes(), "sample.mp3", "audio/mpeg")

    monkeypatch.setattr(
        media_parser,
        "ensure_transcript",
        lambda item: ("媒体转写正文第一段\n\n媒体转写正文第二段", "asr"),
    )

    response = client.post(
        "/api/materials/readable-document",
        json={"file_ids": [file_item["id"]], "media_ids": [media_item["id"]]},
    )

    assert response.status_code == 200
    body = response.json()["markdown"]
    assert "文件正文第一段" in body
    assert "媒体转写正文第一段" in body
    assert "这是本地生成的知识草稿" not in body
    assert deleted.json()["items"] == []


def test_readable_document_recovers_and_slices_historical_screenshot_text(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    known_path = tmp_path / "knowledge" / "2026-06-04" / "ai-wave_3811b61f.md"
    known_path.parent.mkdir(parents=True, exist_ok=True)
    known_path.write_text(
        "# AI不是风口，是海啸：CES、FSD、算力与能源、AGI风险\n\n## 原始识别文本\n```text\n"
        "[Screenshot 1]\n从美国游学回来提醒：AI不是风口，是海啸。\n"
        "1、CES变成AI展，机器人已“判若两人”\n\n"
        "[Screenshot 2]\n2、亲驾FSD后背发凉，马斯克没吹牛，很丝滑\n\n"
        "[Screenshot 3]\n3、算力的背后是能源，中美竞赛的真正“命门”\n"
        "```\n",
        encoding="utf-8",
    )
    client = TestClient(app.app)
    first = storage.save_image_bytes(PNG_1X1, "shot1.png", "image/png")
    second = storage.save_image_bytes(PNG_1X1 + b"2", "shot2.png", "image/png")
    third = storage.save_image_bytes(PNG_1X1 + b"3", "shot3.png", "image/png")
    storage.update_screenshot(first["id"], status="error", error_message=f"'{known_path}'", image_path="missing/shot1.png")
    storage.update_screenshot(
        second["id"],
        status="error",
        error_message=f"'{known_path.with_name('FSD试驾与无人驾驶落地预期_3bb2b72d.md')}'",
        image_path="missing/shot2.png",
    )
    storage.update_screenshot(
        third["id"],
        status="error",
        error_message=f"'{known_path.with_name('算力背后是能源；中美AI竞赛_327fbb82.md')}'",
        image_path="missing/shot3.png",
    )
    for item, title_path in (
        (first, known_path),
        (second, known_path),
        (third, known_path),
    ):
        entry = storage.create_or_update_knowledge_entry([item["id"]], f"history-{item['id']}")
        title = (
            "FSD试驾与无人驾驶落地预期"
            if item["id"] == second["id"]
            else "算力背后是能源；中美AI竞赛"
            if item["id"] == third["id"]
            else "任泽平赴美考察后提醒：AI不是风口，是海啸"
        )
        storage.update_knowledge_entry(entry["id"], status="error", error_message=f"'{title_path}'", source_ids=f"[{item['id']}]", title=title)

    one = client.post("/api/materials/readable-document", json={"image_ids": [first["id"]], "parser_mode": "local_ocr"})
    two = client.post("/api/materials/readable-document", json={"image_ids": [second["id"]], "parser_mode": "local_ocr"})
    three = client.post("/api/materials/readable-document", json={"image_ids": [third["id"]], "parser_mode": "local_ocr"})
    combined = client.post(
        "/api/materials/readable-document",
        json={"image_ids": [first["id"], second["id"], third["id"]], "parser_mode": "local_ocr"},
    )

    assert one.status_code == two.status_code == three.status_code == combined.status_code == 200
    assert "这是本地生成的知识草稿" not in one.json()["markdown"]
    assert "1、CES变成AI展" in one.json()["markdown"]
    assert "2、亲驾FSD" in two.json()["markdown"]
    assert "3、算力的背后是能源" in three.json()["markdown"]
    combined_markdown = combined.json()["markdown"]
    assert combined_markdown.count("1、CES变成AI展") == 1
    assert combined_markdown.count("2、亲驾FSD") == 1
    assert combined_markdown.count("3、算力的背后是能源") == 1
    assert "这是本地生成的知识草稿" not in combined_markdown


def test_readable_document_uses_file_and_media_source_text(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    uploaded_file = client.post(
        "/api/files",
        files={"files": ("sample.txt", "文件正文第一段\n\n文件正文第二段".encode("utf-8"), "text/plain")},
    ).json()["items"][0]
    media_item = storage.save_media_bytes(b"media-bytes", "sample.mp3", "audio/mpeg")
    monkeypatch.setattr(media_parser, "ensure_transcript", lambda item: ("媒体转写正文第一段\n\n媒体转写正文第二段", "asr"))

    response = client.post(
        "/api/materials/readable-document",
        json={"file_ids": [uploaded_file["id"]], "media_ids": [media_item["id"]]},
    )

    assert response.status_code == 200
    body = response.json()["markdown"]
    assert "文件正文第一段" in body
    assert "媒体转写正文第一段" in body
    assert "这是本地生成的知识草稿" not in body


def test_writer_revise_format_and_publish_use_workflow_helpers(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    knowledge_id = make_ready_knowledge("长鑫科技信息", "writer-flow-hash")
    workspace = writer_tools.dated_workspace("长鑫科技为何重要")
    writer_tools.write_article(workspace, "# 原文")

    monkeypatch.setattr(
        deepseek_client,
        "revise_wechat_article",
        lambda current_markdown, instruction, markdown_files, setting=None: WriterRevisionResult(
            markdown="# 修改后\n\n![封面图](cover.png)\n\n正文",
            change_summary="已修改。",
        ),
    )

    def fake_format(workspace_path, markdown=None, theme="tech", design_strategy="", use_ai=True):
        path = workspace_path / "formatted.html"
        path.write_text("<html><body>ok</body></html>", encoding="utf-8")
        return {"path": str(path.relative_to(storage.ROOT)), "html": path.read_text(encoding="utf-8")}

    captured = {}

    def fake_publish(workspace_path, title, author="Bobo", digest=None, cover_path=None, account_key=None):
        captured["author"] = author
        captured["account_key"] = account_key
        return {"media_id": "draft-media-id", "author": author}

    monkeypatch.setattr(writer_tools, "format_article", fake_format)
    monkeypatch.setattr(writer_tools, "publish_draft", fake_publish)
    monkeypatch.setattr(writer_tools, "publish_preflight", lambda *args, **kwargs: {"ok": True, "checks": [], "blocking": []})
    client = TestClient(app.app)

    revised = client.post(
        "/api/writer/revise",
        json={
            "knowledge_ids": [knowledge_id],
            "markdown": "# 原文",
            "instruction": "改得更清楚",
            "workspace": str(workspace.relative_to(storage.ROOT)),
        },
    )
    assert revised.status_code == 200
    assert "修改后" in revised.json()["markdown"]

    formatted = client.post(
        "/api/writer/format",
        json={"workspace": str(workspace.relative_to(storage.ROOT)), "markdown": "# 修改后"},
    )
    assert formatted.status_code == 200
    assert formatted.json()["html"].startswith("<html>")

    published = client.post(
        "/api/writer/publish",
        json={"workspace": str(workspace.relative_to(storage.ROOT)), "title": "标题"},
    )
    assert published.status_code == 200
    assert published.json()["media_id"] == "draft-media-id"
    assert captured["author"] == "Bobo"
    assert captured["account_key"] == "local-user"


def test_writer_image_suggestions_and_file_preview(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api_settings,
        "active_setting",
        lambda: {
            "id": "test",
            "name": "Test API",
            "provider": "compatible",
            "base_url": "https://example.com/v1",
            "model": "test-model",
            "api_key": "test-key",
            "timeout": 60,
            "max_retries": 0,
        },
    )
    monkeypatch.setattr(
        deepseek_client,
        "suggest_writer_images",
        lambda article_markdown, topic=None, setting=None: WriterImageSuggestionResult(
            cover_prompt="长鑫科技封面，简体中文，少量文字",
            content_image_prompts=["DRAM 产业链结构图"],
            rationale="需要一张封面和一张结构图。",
        ),
    )
    workspace = writer_tools.dated_workspace("image-preview")
    image_path = workspace / "cover.png"
    image_path.write_bytes(PNG_1X1)
    client = TestClient(app.app)

    suggested = client.post(
        "/api/writer/image-suggestions",
        json={"markdown": "# 长鑫科技\n\n正文", "topic": {"title": "长鑫科技"}},
    )
    assert suggested.status_code == 200
    assert suggested.json()["cover_prompt"].startswith("长鑫科技")

    preview = client.get(f"/api/writer/file?path={str(image_path.relative_to(storage.ROOT))}")
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG")


def test_writer_project_image_suggestions_apply_selected_style_preset(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    project = writer_tools.create_project("配图风格项目", owner_user_id="u-test")

    captured: dict[str, object] = {}

    def fake_suggest(article_markdown, topic=None, content_image_count=1, image_style_preset="", setting=None):
        captured["article_markdown"] = article_markdown
        captured["topic"] = topic
        captured["content_image_count"] = content_image_count
        captured["image_style_preset"] = image_style_preset
        return WriterImageSuggestionResult(
            cover_prompt=f"{image_style_preset} 封面图",
            content_image_prompts=[f"{image_style_preset} 正文图 {index + 1}" for index in range(content_image_count)],
            rationale="已按指定风格生成建议。",
        )

    monkeypatch.setattr(deepseek_client, "suggest_writer_images", fake_suggest)
    client, _ = _login_app_cloud_admin(username="u-test")

    response = client.post(
        f"/api/writer/projects/{project['id']}/image-suggestions",
        json={
            "markdown": "# 标题\n\n正文",
            "topic": {"title": "风格化配图"},
            "content_image_count": 2,
            "image_style_preset": "国潮编辑视觉风格，东方构图，克制装饰。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured["content_image_count"] == 2
    assert captured["image_style_preset"] == "国潮编辑视觉风格，东方构图，克制装饰。"
    assert payload["project"]["image_style_preset"] == "国潮编辑视觉风格，东方构图，克制装饰。"
    assert payload["project"]["cover_prompt"].startswith("国潮编辑视觉风格")
    assert len(payload["project"]["content_image_prompts"]) == 2


def test_writer_html_file_preview(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("html-preview")
    html_path = workspace / "formatted.html"
    html_path.write_text("<html><body><h1>preview ok</h1></body></html>", encoding="utf-8")
    client = TestClient(app.app)

    preview = client.get(f"/api/writer/file?path={str(html_path.relative_to(storage.ROOT))}")

    assert preview.status_code == 200
    assert "preview ok" in preview.text


def test_format_article_falls_back_when_markdown_dependency_missing(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("fallback-format")
    writer_tools.write_article(workspace, "# 标题\n\n## 小节\n\n正文")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "formatter.py")
    writer_tools.FORMATTER_SCRIPT.write_text("print('unused')", encoding="utf-8")

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "markdown":
            raise ImportError("No module named 'markdown'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = writer_tools.format_article(workspace)
    assert result["fallback"] is False
    assert result["template_formatted"] is True
    assert "formatted.html" in result["path"]
    assert "正文" in result["html"]


def test_format_article_falls_back_when_formatter_script_missing(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("missing-formatter")
    writer_tools.write_article(workspace, "# 标题\n\n## 小节\n\n正文")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "missing_formatter.py")

    result = writer_tools.format_article(workspace)

    assert result["fallback"] is False
    assert result["template_formatted"] is True
    assert result["stderr"] == ""
    assert "formatted.html" in result["path"]
    assert "正文" in result["html"]


def test_fallback_markdown_to_html_preserves_ordered_lists(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("ordered-list-fallback")
    writer_tools.write_article(workspace, "# 标题\n\n1. 第一条\n2. 第二条\n3、第三条")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "missing_formatter.py")

    result = writer_tools.format_article(workspace)

    assert "<ol" in result["html"]
    assert "第一条" in result["html"]
    assert "第二条" in result["html"]
    assert "第三条" in result["html"]


def test_format_article_prefers_controlled_template_renderer(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("api-format")
    writer_tools.write_article(workspace, "# 标题\n\n## 小节\n\n正文")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "missing_formatter.py")
    monkeypatch.setattr(writer_tools.api_settings, "active_setting", lambda: {"api_key": "test", "model": "format-model"})

    def fake_design(markdown, design_strategy="", setting=None):
        raise AssertionError("AI formatter should not be the primary HTML generator")

    monkeypatch.setattr(writer_tools.deepseek_client, "design_wechat_article_html", fake_design)

    result = writer_tools.format_article(workspace, design_strategy="强调重点句")

    assert result["fallback"] is False
    assert result["ai_formatted"] is False
    assert result["template_formatted"] is True
    assert result["design_intent"]["theme"] in {"tech", "column", "research", "xiumi"}
    assert 'data-fl-component="title_card"' in result["html"]
    assert "formatted.html" in result["path"]


def test_writer_project_image_generation_persists_failures(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    project = writer_tools.create_project("image failure project")
    workspace = writer_tools.resolve_project_workspace(str(project["id"]))
    writer_tools.write_article(workspace, "# 标题\n\n正文")

    def fake_generate_image(prompt, output_path, setting=None):
        raise RuntimeError("upstream image service failed")

    monkeypatch.setattr(writer_tools, "generate_image", fake_generate_image)
    client = TestClient(app.app)

    response = client.post(
        f"/api/writer/projects/{project['id']}/images",
        json={"cover_prompt": "封面图", "content_image_prompts": ["正文图"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["step"] == "images"
    assert payload["project"]["images"]["ok"] is False
    assert len(payload["project"]["images"]["errors"]) == 2
    assert "upstream image service failed" in payload["project"]["images"]["errors"][0]["message"]
    metadata_path = workspace / "image_metadata.json"
    assert metadata_path.exists()


def test_publish_preflight_truncates_long_digest(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("long-digest")
    (workspace / "formatted.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (workspace / "article.md").write_text("# 标题\n\n正文", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "missing-wechat.json")
    digest = "这是一段会超过公众号摘要字节限制的中文摘要" * 10

    result = writer_tools.publish_preflight(workspace, "标题", digest=digest)
    digest_check = next(item for item in result["checks"] if item["key"] == "digest")

    assert digest_check["ok"] is True
    assert digest_check["fixed"] is True
    assert result["digest_truncated"] is True
    assert writer_tools.utf8_len(result["digest"]) <= 120
    assert result["digest"].encode("utf-8").decode("utf-8") == result["digest"]


def test_publish_preflight_uses_bound_author_when_author_omitted(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("bound-author")
    (workspace / "formatted.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (workspace / "article.md").write_text("# Title\n\nBody", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)

    def fake_wechat_config(account_key=None):
        return {"author": "Alice"} if account_key == "user-1" else {}

    monkeypatch.setattr(writer_tools, "wechat_config", fake_wechat_config)
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda account_key=None: tmp_path / f"{account_key or 'global'}-wechat.json")
    monkeypatch.setattr(writer_tools, "wechat_token_cache_file", lambda account_key=None: tmp_path / f"{account_key or 'global'}-token.json")

    result = writer_tools.publish_preflight(workspace, "Title", account_key="user-1")
    author_check = next(item for item in result["checks"] if item["key"] == "author")

    assert author_check["ok"] is True
    assert author_check["detail"].startswith("Alice")


def test_publish_preflight_verifies_wechat_access_token(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("wechat-token-check")
    (workspace / "formatted.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (workspace / "article.md").write_text("# 标题\n\n正文", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(
        writer_tools,
        "refresh_wechat_access_token",
        lambda timeout=20: {"ok": True, "message": "token ok", "ip": "", "raw": '{"expires_in":7200}'},
    )
    monkeypatch.setattr(writer_tools, "wechat_config", lambda: {"appid": "wx1234567890", "appsecret": "secret"})
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "wechat-config.json")
    (tmp_path / "wechat-config.json").write_text('{"appid":"wx1234567890","appsecret":"secret"}', encoding="utf-8")

    result = writer_tools.publish_preflight(workspace, "标题", digest="摘要")
    api_check = next(item for item in result["checks"] if item["key"] == "wechat_api")

    assert api_check["ok"] is True
    assert api_check["detail"] == "token ok"
    assert result["ok"] is True


def test_publish_preflight_blocks_on_wechat_ip_whitelist_failure(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("wechat-whitelist-check")
    (workspace / "formatted.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (workspace / "article.md").write_text("# 标题\n\n正文", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(
        writer_tools,
        "refresh_wechat_access_token",
        lambda timeout=20: {
            "ok": False,
            "message": "微信接口返回错误：40164 invalid ip 218.94.142.39, not in whitelist",
            "ip": "218.94.142.39",
            "raw": '{"errcode":40164,"errmsg":"invalid ip 218.94.142.39, not in whitelist"}',
        },
    )
    monkeypatch.setattr(writer_tools, "wechat_config", lambda: {"appid": "wx1234567890", "appsecret": "secret"})
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "wechat-config.json")
    (tmp_path / "wechat-config.json").write_text('{"appid":"wx1234567890","appsecret":"secret"}', encoding="utf-8")

    result = writer_tools.publish_preflight(workspace, "标题", digest="摘要")
    api_check = next(item for item in result["checks"] if item["key"] == "wechat_api")

    assert api_check["ok"] is False
    assert api_check["ip"] == "218.94.142.39"
    assert "40164" in api_check["detail"]
    assert result["ok"] is False
    assert any(item["key"] == "wechat_api" for item in result["blocking"])


def test_format_article_injects_content_images(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("content-images")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "formatter.py")
    writer_tools.FORMATTER_SCRIPT.write_text("print('unused')", encoding="utf-8")

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "markdown":
            raise ImportError("No module named 'markdown'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    result = writer_tools.format_article(workspace, "# Article\n\nBody")
    markdown = (workspace / "article.md").read_text(encoding="utf-8")
    assert "content-1.png" in markdown
    assert "content-1.png" in result["html"]


def test_content_images_are_inserted_near_related_paragraphs(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("image-placement")
    (workspace / "content-1.png").write_bytes(PNG_1X1)
    (workspace / "content-2.png").write_bytes(PNG_1X1)
    (workspace / "image_metadata.json").write_text(
        json.dumps(
            {
                "content_images": [
                    {"filename": "content-1.png", "prompt": "数据飞轮 自动驾驶 规模化示意图"},
                    {"filename": "content-2.png", "prompt": "城市出行 Robotaxi 服务网络图"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    markdown = """# Title

## 一、技术

自动驾驶的数据飞轮开始转动，规模化落地更近了。

## 二、城市

城市出行服务会被重新定义，Robotaxi 网络开始扩张。
"""
    result = writer_tools.ensure_content_images_in_markdown(workspace, markdown)
    assert result.index("数据飞轮") < result.index("content-1.png") < result.index("## 二、城市")
    assert result.index("Robotaxi") < result.index("content-2.png")


def test_prepare_html_for_publish_normalizes_images_and_emphasis(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("publish-ready")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    html_path = workspace / "formatted_wechat.html"
    image_src = "/" + str(image_path.relative_to(storage.ROOT)).replace("\\", "/")
    html_path.write_text(
        '<html><body><p>这是一个关键变化，正在走向规模化。</p>'
        f'<p><img src="{image_src}" /></p></body></html>',
        encoding="utf-8",
    )
    prepared = writer_tools.prepare_html_for_publish(workspace, html_path)
    content = prepared.read_text(encoding="utf-8")
    assert str(image_path) in content
    assert "<strong" in content
    assert "关键变化" in content


def test_publish_draft_script_path_uploads_content_images_before_publish(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("publish-script-images")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    html_path = workspace / "formatted.html"
    html_path.write_text(
        '<html><body><p>正文</p><p><img src="content-1.png" /></p></body></html>',
        encoding="utf-8",
    )
    publisher_script = tmp_path / "publisher.py"
    publisher_script.write_text("print('unused')", encoding="utf-8")
    monkeypatch.setattr(writer_tools, "PUBLISHER_SCRIPT", publisher_script)
    monkeypatch.setattr(writer_tools, "wechat_access_token", lambda timeout=20: "token-123")
    monkeypatch.setattr(writer_tools, "_wechat_upload_content_image", lambda access_token, image: f"https://mmbiz.example/{image.name}")

    class FakeCompleted:
        returncode = 0
        stdout = "media_id: draft-media-id"
        stderr = ""

    def fake_run_python(command, cwd=None, timeout=360):
        publish_path = Path(command[4])
        content = publish_path.read_text(encoding="utf-8")
        assert "https://mmbiz.example/content-1.png" in content
        assert 'src="content-1.png"' not in content
        return FakeCompleted()

    monkeypatch.setattr(writer_tools, "_run_python", fake_run_python)

    result = writer_tools.publish_draft(workspace, "标题", digest="摘要")

    assert result["media_id"] == "draft-media-id"
    assert result["uploaded_content_images"] == [
        {"path": str(image_path.resolve()), "url": "https://mmbiz.example/content-1.png"}
    ]
    publish_ready = workspace / "publish_ready.html"
    assert "https://mmbiz.example/content-1.png" in publish_ready.read_text(encoding="utf-8")


def test_wechat_template_renderer_outputs_distinct_themes_and_components():
    markdown = """# Title

> A concise opening quote.

## Section

Body paragraph with **bold** and ==mark==.

- first
- second

| Metric | Value |
| --- | --- |
| Speed | 2x |

![Chart](content-1.png)
"""

    tech = writer_tools.wechat_html_from_markdown(markdown, design_strategy="科技长文", theme="tech")
    xiumi = writer_tools.wechat_html_from_markdown(markdown, design_strategy="秀米 装饰 金句", theme="tech")

    assert tech["intent"]["theme"] == "tech"
    assert xiumi["intent"]["theme"] == "xiumi"
    assert tech["html"] != xiumi["html"]
    assert 'data-fl-component="title_card"' in tech["html"]
    assert 'data-fl-component="data_card"' in tech["html"]
    assert 'data-fl-component="image_caption"' in tech["html"]
    assert "<script" not in xiumi["html"].lower()



def test_publish_preflight_accepts_underscore_content_image_alias(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("content-image-alias")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    (workspace / "formatted.html").write_text(
        '<html><body><p>body</p><img src="content_1.png" /></body></html>',
        encoding="utf-8",
    )
    (workspace / "article.md").write_text("# Title\n\nbody", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "missing-wechat.json")

    result = writer_tools.publish_preflight(workspace, "Title", digest="Digest")
    check_map = {item["key"]: item for item in result["checks"]}

    assert check_map["missing_images"]["ok"] is True
    assert result["publish_inspection"]["missing_images"] == []
    assert result["publish_inspection"]["local_image_paths"] == [str(image_path.resolve())]


def test_publish_preflight_accepts_unseparated_content_image_alias(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("content-image-alias-unseparated")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    (workspace / "formatted.html").write_text(
        '<html><body><p>body</p><img src="content1.png" /></body></html>',
        encoding="utf-8",
    )
    (workspace / "article.md").write_text("# Title\n\nbody", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "missing-wechat.json")

    result = writer_tools.publish_preflight(workspace, "Title", digest="Digest")
    check_map = {item["key"]: item for item in result["checks"]}

    assert check_map["missing_images"]["ok"] is True
    assert result["publish_inspection"]["missing_images"] == []
    assert result["publish_inspection"]["local_image_paths"] == [str(image_path.resolve())]


def test_ensure_content_images_removes_underscore_placeholders(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("strip-content-image-alias")
    (workspace / "content-1.png").write_bytes(PNG_1X1)
    (workspace / "image_metadata.json").write_text(
        json.dumps({"content_images": [{"filename": "content-1.png", "prompt": "body", "index": 1}]}),
        encoding="utf-8",
    )

    markdown = (
        "# Title\n\nbody paragraph.\n\n"
        "![stale placeholder](content_1.png)\n\n"
        "![stale compact placeholder](content1.png)\n"
    )
    result = writer_tools.ensure_content_images_in_markdown(workspace, markdown)

    assert "content_1.png" not in result
    assert "content1.png" not in result
    assert result.count("content-1.png") == 1


def test_ensure_content_images_removes_cover_from_article_markdown(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("strip-cover-image")
    (workspace / "content-1.png").write_bytes(PNG_1X1)
    (workspace / "image_metadata.json").write_text(
        json.dumps({"content_images": [{"filename": "content-1.png", "prompt": "body", "index": 1}]}),
        encoding="utf-8",
    )

    markdown = "# Title\n\n![封面图](cover.png)\n\nbody paragraph.\n"
    result = writer_tools.ensure_content_images_in_markdown(workspace, markdown)

    assert "cover.png" not in result
    assert result.count("content-1.png") == 1


def test_prepare_html_for_publish_prunes_cover_and_duplicate_content_aliases(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("publish-prune-duplicates")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    (workspace / "content-1.png").write_bytes(PNG_1X1)
    (workspace / "content-2.png").write_bytes(PNG_1X1)
    html_path = workspace / "formatted.html"
    html_path.write_text(
        '<html><body>'
        '<section data-fl-component="image_caption"><img src="cover.png" alt="cover" /></section>'
        '<section data-fl-component="image_caption"><img src="content-1.png" alt="first" /></section>'
        '<section data-fl-component="image_caption"><img src="content_1.png" alt="stale first" /></section>'
        '<section data-fl-component="image_caption"><img src="content1.png" alt="stale first compact" /></section>'
        '<section data-fl-component="image_caption"><img src="content-2.png" alt="second" /></section>'
        '</body></html>',
        encoding="utf-8",
    )

    prepared = writer_tools.prepare_html_for_publish(workspace, html_path)
    content = prepared.read_text(encoding="utf-8")

    assert "cover.png" not in content
    assert "content_1.png" not in content
    assert "content1.png" not in content
    assert content.count("content-1.png") == 1
    assert content.count("content-2.png") == 1

def test_publish_preflight_sanitizes_html_and_reports_remaining_publish_risks(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("bad-publish-html")
    (workspace / "formatted.html").write_text(
        '<html><body><p style="text-indent:2em">正文</p><script>alert(1)</script>'
        '<img src="missing.png" /><img src="data:image/png;base64,xx" />'
        '<img src="https://example.com/remote.png" /></body></html>',
        encoding="utf-8",
    )
    (workspace / "article.md").write_text("# 标题\n\n正文", encoding="utf-8")
    (workspace / "cover.png").write_bytes(PNG_1X1)
    monkeypatch.setattr(writer_tools, "wechat_config_file", lambda: tmp_path / "missing-wechat.json")

    result = writer_tools.publish_preflight(workspace, "标题", digest="摘要")
    check_map = {item["key"]: item for item in result["checks"]}

    assert result["ok"] is False
    assert check_map["missing_images"]["ok"] is False
    assert check_map["data_images"]["ok"] is False
    assert check_map["remote_images"]["ok"] is False
    assert check_map["wechat_html_sanitize"]["ok"] is True
    assert result["publish_sanitize"]["content_path"].endswith("publish_ready.html")
    assert (workspace / "publish_ready.html").exists()
    assert (workspace / "publish_preflight_report.json").exists()


def test_prepare_publish_html_upload_report_tracks_replacements(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("upload-report")
    image_path = workspace / "content-1.png"
    image_path.write_bytes(PNG_1X1)
    html_path = workspace / "formatted.html"
    html_path.write_text('<html><body><p>正文</p><img src="content-1.png" /></body></html>', encoding="utf-8")
    monkeypatch.setattr(writer_tools, "_wechat_upload_content_image", lambda access_token, image: f"https://mmbiz.example/{image.name}")

    publish_path, html_text, uploaded = writer_tools.prepare_publish_html_with_wechat_images(workspace, html_path, "token")
    report = json.loads((workspace / "publish_image_uploads.json").read_text(encoding="utf-8"))

    assert publish_path.name == "publish_ready.html"
    assert "https://mmbiz.example/content-1.png" in html_text
    assert uploaded == [{"path": str(image_path.resolve()), "url": "https://mmbiz.example/content-1.png"}]
    assert report["expected_local_image_count"] == 1
    assert report["uploaded_image_count"] == 1
    assert report["replacement_count"] == 1
    assert report["ok"] is True


def test_writer_workspace_directory_status_and_resume(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("resume-work")
    article_path = writer_tools.write_article(workspace, "# Resume Article\n\nBody")
    cover_path = workspace / "cover.png"
    cover_path.write_bytes(PNG_1X1)
    html_path = workspace / "formatted.html"
    html_path.write_text("<html><body>formatted</body></html>", encoding="utf-8")
    publish_path = workspace / "publish_result.json"
    publish_path.write_text('{"media_id":"draft-media-id","returncode":0}', encoding="utf-8")

    client = TestClient(app.app)
    listed = client.get("/api/writer/workspaces")
    assert listed.status_code == 200
    rel_workspace = str(workspace.relative_to(storage.ROOT))
    item = next(item for item in listed.json()["items"] if item["workspace"] == rel_workspace)
    assert item["status"] == "published"
    assert item["checks"] == {"markdown": True, "cover": True, "html": True, "published": True}
    assert item["paths"]["article"] == str(article_path.relative_to(storage.ROOT))
    assert item["paths"]["cover"] == str(cover_path.relative_to(storage.ROOT))

    loaded = client.get("/api/writer/workspace", params={"path": rel_workspace})
    assert loaded.status_code == 200
    body = loaded.json()
    assert body["article_markdown"].startswith("# Resume Article")
    assert body["html"].startswith("<html>")
    assert body["publish_result"]["media_id"] == "draft-media-id"


def test_xhs_preflight_blocks_project_without_images(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(xhs_tools, "login_status", lambda: {"ok": True, "logged_in": True})

    profile = create_xhs_profile()
    project = xhs_tools.create_project("小红书测试", account_profile_id=profile["id"])
    draft = xhs_tools.XhsDraftResult(
        title="测试标题",
        content="正文内容",
        tags=["知识酷"],
        cover_prompt="封面提示词",
        content_image_prompts=["正文图提示词"],
    )
    xhs_tools.save_draft_artifacts(project["id"], draft)
    xhs_tools.confirm_draft(project["id"])
    xhs_tools.confirm_image_suggestions(project["id"])

    result = xhs_tools.publish_preflight(project["id"])

    assert result["ok"] is False
    assert any(item["key"] == "images" for item in result["blocking"])
    project_after_preflight = xhs_tools.load_project(project["id"])
    assert xhs_tools.project_step(project_after_preflight) == "publish_check"
    assert xhs_tools.next_action(project_after_preflight) == "run_preflight"


def test_xhs_generate_images_falls_back_to_saved_prompts_and_persists_failures(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    profile = create_xhs_profile()
    project = xhs_tools.create_project("xhs image failure test", account_profile_id=profile["id"])
    draft = xhs_tools.XhsDraftResult(
        title="Test title",
        content="Body",
        tags=["tag"],
        cover_prompt="cover prompt",
        content_image_prompts=["content prompt"],
    )
    xhs_tools.save_draft_artifacts(project["id"], draft)
    xhs_tools.confirm_draft(project["id"])
    xhs_tools.confirm_image_suggestions(project["id"])

    def fake_generate_image(prompt, output_path, setting=None):
        raise RuntimeError("upstream image service failed")

    monkeypatch.setattr(writer_tools, "generate_image", fake_generate_image)
    client = TestClient(app.app)

    response = client.post(f"/api/xhs/projects/{project['id']}/images", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["step"] == "images"
    assert payload["project"]["images"]["ok"] is False
    assert len(payload["project"]["images"]["errors"]) == 2
    assert "upstream image service failed" in payload["project"]["images"]["errors"][0]["message"]
    assert (xhs_tools.resolve_project_workspace(project["id"]) / "image_metadata.json").exists()


def test_xhs_generate_images_returns_400_without_prompts(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    profile = create_xhs_profile()
    project = xhs_tools.create_project("xhs no prompt test", account_profile_id=profile["id"])
    client = TestClient(app.app)

    response = client.post(f"/api/xhs/projects/{project['id']}/images", json={})

    assert response.status_code == 400
    assert "配图提示词" in response.json()["detail"]


def test_xhs_draft_and_image_suggestion_confirmations_gate_generation(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    profile = create_xhs_profile()
    project = xhs_tools.create_project("xhs staged image flow", account_profile_id=profile["id"])
    draft = xhs_tools.XhsDraftResult(
        title="Test title",
        content="Body",
        tags=["tag"],
        cover_prompt="old cover prompt",
        content_image_prompts=["old content prompt"],
    )
    xhs_tools.save_draft_artifacts(project["id"], draft)
    client = TestClient(app.app)

    loaded = client.get(f"/api/xhs/projects/{project['id']}")
    assert loaded.status_code == 200
    assert loaded.json()["step"] == "draft"
    assert loaded.json()["next_action"] == "confirm_draft"

    blocked_suggestion = client.post(f"/api/xhs/projects/{project['id']}/image-suggestions", json={})
    assert blocked_suggestion.status_code == 400
    assert "确认图文草稿" in blocked_suggestion.json()["detail"]

    confirmed_draft = client.post(f"/api/xhs/projects/{project['id']}/draft/confirm")
    assert confirmed_draft.status_code == 200
    assert confirmed_draft.json()["step"] == "images"
    assert confirmed_draft.json()["next_action"] == "suggest_images"

    monkeypatch.setattr(
        deepseek_client,
        "parse_json_model",
        lambda model, messages, setting=None: xhs_tools.XhsImageSuggestionResult(
            cover_prompt="new cover prompt",
            content_image_prompts=["new content prompt"],
            rationale="image rationale",
        ),
    )
    suggested = client.post(f"/api/xhs/projects/{project['id']}/image-suggestions", json={})
    assert suggested.status_code == 200
    assert suggested.json()["step"] == "images"
    assert suggested.json()["next_action"] == "confirm_image_suggestions"
    assert suggested.json()["project"]["image_suggestions_confirmed"] is False

    blocked_generation = client.post(f"/api/xhs/projects/{project['id']}/images", json={})
    assert blocked_generation.status_code == 400
    assert "确认配图建议" in blocked_generation.json()["detail"]

    confirmed_suggestions = client.post(f"/api/xhs/projects/{project['id']}/image-suggestions/confirm")
    assert confirmed_suggestions.status_code == 200
    assert confirmed_suggestions.json()["step"] == "images"
    assert confirmed_suggestions.json()["next_action"] == "generate_images"
    assert confirmed_suggestions.json()["project"]["image_suggestions_confirmed"] is True


def test_xhs_fill_publish_uses_files_and_absolute_image_paths(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(xhs_tools, "login_status", lambda: {"ok": True, "logged_in": True})
    calls = []

    profile = create_xhs_profile()
    project = xhs_tools.create_project("小红书测试", account_profile_id=profile["id"])
    draft = xhs_tools.XhsDraftResult(
        title="测试标题",
        content="正文内容",
        tags=["知识酷"],
        cover_prompt="封面提示词",
        content_image_prompts=[],
    )
    xhs_tools.save_draft_artifacts(project["id"], draft)
    project_dir = xhs_tools.resolve_project_workspace(project["id"])
    image_path = project_dir / "cover.png"
    image_path.write_bytes(PNG_1X1)
    xhs_tools._write_json(
        project_dir / "image_metadata.json",
        {
            "cover": {"path": storage.storage_relative(image_path), "prompt": "封面提示词"},
            "content_images": [],
            "items": [],
            "errors": [],
        },
    )

    def fake_run(args, timeout=120):
        calls.append(args)
        return {"ok": True, "args": args}

    monkeypatch.setattr(xhs_tools, "_run_xhs_cli", fake_run)

    result = xhs_tools.fill_publish(project["id"])

    assert result["ok"] is True
    args = calls[-1]
    assert args[0] == "fill-publish"
    assert "--title-file" in args
    assert "--content-file" in args
    assert "--images" in args
    assert str(image_path.resolve()) in args
    assert "测试标题" not in args
    assert "正文内容" not in args
    assert (project_dir / "publish_result.json").exists()



def test_xhs_export_package_contains_publish_assets(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    profile = create_xhs_profile()
    project = xhs_tools.create_project("xhs export package", account_profile_id=profile["id"])
    draft = xhs_tools.XhsDraftResult(
        title="Export title",
        content="Export body",
        tags=["tag1", "tag2"],
        cover_prompt="cover prompt",
        content_image_prompts=[],
    )
    xhs_tools.save_draft_artifacts(project["id"], draft)
    project_dir = xhs_tools.resolve_project_workspace(project["id"])
    image_path = project_dir / "cover.png"
    image_path.write_bytes(PNG_1X1)
    xhs_tools._write_json(
        project_dir / "image_metadata.json",
        {"cover": {"path": storage.storage_relative(image_path), "prompt": "cover prompt"}, "content_images": [], "items": [], "errors": []},
    )
    client = TestClient(app.app)

    response = client.post(f"/api/xhs/projects/{project['id']}/export-package")

    assert response.status_code == 200
    package = response.json()["export_package"]
    package_path = storage.resolve_root_path(package["package_path"])
    assert package_path and package_path.exists()
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        assert {"title.txt", "content.txt", "tags.txt", "publish_guide.md", "manifest.json", "images/01.png"} <= names
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert manifest["project_id"] == project["id"]
        assert manifest["images"][0]["filename"] == "images/01.png"
        assert archive.read("title.txt").decode("utf-8").strip() == "Export title"


def test_xhs_export_package_requires_title_content_and_images(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    profile = create_xhs_profile()
    project = xhs_tools.create_project("xhs export missing assets", account_profile_id=profile["id"])
    client = TestClient(app.app)

    response = client.post(f"/api/xhs/projects/{project['id']}/export-package")

    assert response.status_code == 400
    assert response.json()["detail"]


def test_cloud_member_can_export_xhs_package_but_not_use_bridge_publish(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "false")
    setup_storage(tmp_path, monkeypatch)
    client, _payload = _register_app_cloud_member("XHS-EXPORT", "xhs-export@example.test", "xhs_export")

    def forbidden_cli(*args, **kwargs):
        raise AssertionError("XHS bridge CLI should not be called for cloud members")

    monkeypatch.setattr(xhs_tools, "_run_xhs_cli", forbidden_cli)
    profile_response = client.post("/api/xhs/account-profiles", json=xhs_profile_payload("XHS ????"))
    assert profile_response.status_code == 200
    profile = profile_response.json()["profile"]
    project_response = client.post("/api/xhs/projects", json={"name": "??????", "account_profile_id": profile["id"]})
    assert project_response.status_code == 200
    project_id = project_response.json()["project"]["id"]
    draft = xhs_tools.XhsDraftResult(title="Cloud export", content="Cloud body", tags=["cloud"], cover_prompt="cover")
    xhs_tools.save_draft_artifacts(project_id, draft)
    project_dir = xhs_tools.resolve_project_workspace(project_id)
    image_path = project_dir / "cover.png"
    image_path.write_bytes(PNG_1X1)
    xhs_tools._write_json(
        project_dir / "image_metadata.json",
        {"cover": {"path": storage.storage_relative(image_path), "prompt": "cover"}, "content_images": [], "items": [], "errors": []},
    )

    assert client.get("/api/xhs/auth/status").status_code == 403
    preflight = client.post("/api/xhs/publish/preflight", json={"project_id": project_id})
    assert preflight.status_code == 200
    assert preflight.json()["preflight"]["login"]["skipped"] is True
    exported = client.post(f"/api/xhs/projects/{project_id}/export-package")
    assert exported.status_code == 200
    assert exported.json()["export_package"]["image_count"] == 1
    assert client.post(f"/api/xhs/projects/{project_id}/publish/fill").status_code == 403
    assert client.post(f"/api/xhs/projects/{project_id}/publish/confirm").status_code == 403
    assert client.post(f"/api/xhs/projects/{project_id}/publish/save-draft").status_code == 403

def test_xhs_account_profile_crud_uses_local_json_storage(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)

    profile = xhs_tools.create_account_profile(xhs_profile_payload("产业图文号"))
    profile_path = xhs_tools.xhs_profiles_dir() / profile["id"] / "profile.json"

    assert profile_path.exists()
    assert storage.XHS_DIR in profile_path.resolve().parents
    assert storage.WRITER_DIR not in profile_path.resolve().parents
    assert xhs_tools.list_account_profiles()[0]["id"] == profile["id"]

    updated = xhs_tools.update_account_profile(profile["id"], {**xhs_profile_payload("产业图文号升级"), "tone": "更直接、更像研究员"})

    assert updated["name"] == "产业图文号升级"
    assert updated["tone"] == "更直接、更像研究员"

    xhs_tools.delete_account_profile(profile["id"])

    assert not xhs_tools.list_account_profiles()


def test_xhs_projects_and_strategies_use_dedicated_xhs_storage(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)

    profile = xhs_tools.create_account_profile(xhs_profile_payload("小红书专用目录"))
    project = xhs_tools.create_project("目录归类测试", account_profile_id=profile["id"])
    saved_strategy = xhs_tools.save_carousel_strategy(
        "目录策略",
        xhs_tools.default_image_text_config({"note_format": "清单轮播"}),
    )

    project_path = xhs_tools.resolve_project_workspace(project["id"]) / "project.json"
    strategy_path = xhs_tools.xhs_carousel_strategies_file()

    assert project_path.exists()
    assert strategy_path.exists()
    assert storage.XHS_DIR in project_path.resolve().parents
    assert storage.XHS_DIR in strategy_path.resolve().parents
    assert storage.WRITER_DIR not in project_path.resolve().parents
    assert storage.WRITER_DIR not in strategy_path.resolve().parents
    assert Path(xhs_tools.load_project(project["id"])["workspace"]).parts[:2] == ("xhs", "projects")
    assert any(item["id"] == saved_strategy["id"] for item in xhs_tools.list_carousel_strategies()["items"])


def test_xhs_project_creation_requires_and_snapshots_account_profile(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)

    client = TestClient(app.app)
    missing_response = client.post("/api/xhs/projects", json={"name": "缺定位项目"})

    assert missing_response.status_code == 400

    profile_response = client.post("/api/xhs/account-profiles", json=xhs_profile_payload("知识酷定位"))
    assert profile_response.status_code == 200
    profile = profile_response.json()["profile"]

    project_response = client.post(
        "/api/xhs/projects",
        json={"name": "有定位项目", "account_profile_id": profile["id"], "library_files": []},
    )

    assert project_response.status_code == 200
    project = project_response.json()["project"]
    assert project["account_profile_id"] == profile["id"]
    assert project["account_profile"]["positioning"] == profile["positioning"]

    client.put(
        f"/api/xhs/account-profiles/{profile['id']}",
        json={**xhs_profile_payload("知识酷定位新版"), "positioning": "新版定位"},
    )
    loaded = xhs_tools.load_project(project["id"])

    assert loaded["account_profile"]["positioning"] == profile["positioning"]


def test_xhs_generate_topics_includes_account_profile_in_prompt(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    source_path = storage.KNOWLEDGE_DIR / "source.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("这是一份关于产业趋势的素材。", encoding="utf-8")
    profile = create_xhs_profile()
    project = xhs_tools.create_project("小红书测试", account_profile_id=profile["id"])
    xhs_tools.set_project_library_files(
        project["id"],
        [{"library": "original", "title": "产业素材", "markdown_path": storage.storage_relative(source_path)}],
    )
    prompts = []

    class FakeTopics:
        def model_dump(self):
            return {"suggestions": [{"title": "产业趋势怎么读", "angle": "职场视角"}]}

    def fake_parse(model, messages, setting=None):
        prompts.append(messages[0]["content"])
        return FakeTopics()

    monkeypatch.setattr(deepseek_client, "parse_json_model", fake_parse)

    result = xhs_tools.generate_topics(project["id"])

    assert result["suggestions"][0]["title"] == "产业趋势怎么读"
    prompt = prompts[0]
    assert "面向职场人的产业趋势图文账号" in prompt
    assert "关注产业、就业和科技趋势的职场人" in prompt
    assert "产业趋势" in prompt
    assert "情绪化唱衰" in prompt


def test_xhs_generate_topics_blocks_legacy_project_without_account_profile(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    project = xhs_tools.create_project("小红书测试", account_profile_id=create_xhs_profile()["id"])
    xhs_tools.update_project(project["id"], account_profile_id="", account_profile={})

    with pytest.raises(ValueError, match="账号定位"):
        xhs_tools.generate_topics(project["id"])
