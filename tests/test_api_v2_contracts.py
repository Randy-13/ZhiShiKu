import base64
import json

from fastapi.testclient import TestClient
import pytest

import graph_core
import storage
import src.api_v2 as api_v2
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
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(storage, "IMAGE_DIR", tmp_path / "images")
    monkeypatch.setattr(storage, "DOCUMENT_DIR", tmp_path / "documents")
    monkeypatch.setattr(storage, "KNOWLEDGE_DIR", tmp_path / "knowledge")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "MINING_DIR", tmp_path / "mining")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.test.db")
    monkeypatch.setattr(api_v2.writer_tools, "WRITER_DIR", tmp_path / "writer")
    monkeypatch.setattr(api_v2.api_settings, "SETTINGS_PATH", tmp_path / "data" / "api_settings.json")
    monkeypatch.setattr(api_v2.asr_settings, "SETTINGS_PATH", tmp_path / "data" / "asr_settings.json")
    monkeypatch.setattr(api_v2.image_api_settings, "SETTINGS_PATH", tmp_path / "data" / "image_api_settings.json")
    monkeypatch.setattr(api_v2.web_settings, "SETTINGS_PATH", tmp_path / "data" / "web_settings.json")
    storage.init_storage()
    graph_core.init_graph()


def test_v2_material_types_contract():
    client = TestClient(create_app())

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
    client = TestClient(create_app())

    response = client.get("/api/v2/app-shell")

    assert response.status_code == 200
    payload = response.json()
    sections = payload["data"]["primarySections"]
    entries = payload["data"]["workspaceEntries"]
    libraries = payload["data"]["globalLibraries"]
    assert [item["id"] for item in sections] == ["collect", "learn", "mine", "create", "settings"]
    assert [item["navLabel"] for item in sections] == ["收集", "学习", "挖掘", "创作", "设置中心"]
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
