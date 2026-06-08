import base64
import io
import json
import urllib.error

from fastapi.testclient import TestClient

import api_settings
import app
import deepseek_client
import document_parser
import graph_core
import image_api_settings
import media_parser
import ocr_client
import storage
import writer_tools
from schemas import (
    CreationStrategyResult,
    DocumentPlanResult,
    DocumentPlanSegment,
    ExtractedTermNode,
    GraphGroup,
    GraphOrganizationResult,
    KnowledgeNetworkExtraction,
    KnowledgeResult,
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
    monkeypatch.setattr(storage, "TRASH_DIR", runtime_root / "trash")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.db")
    monkeypatch.setattr(writer_tools, "WRITER_DIR", runtime_root / "writer")
    storage.init_storage()
    graph_core.init_graph()


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
    assert body["item"]["graph_status"] == "not_ingested"

    listed = client.get("/api/knowledge")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    preview = client.get(f"/api/knowledge/{body['item']['id']}")
    assert preview.status_code == 200
    assert "combined raw text" in preview.json()["content"]

    graph = client.get("/api/graph")
    assert graph.status_code == 200
    assert not any(node["label"] == "OpenAI" for node in graph.json()["nodes"])
    assert not any(node["label"] == "OpenAI" for node in graph.json()["pending_nodes"])

    ingested = client.post("/api/knowledge/ingest-to-graph", json={"knowledge_ids": [body["item"]["id"]]})
    assert ingested.status_code == 200
    assert ingested.json()["results"][0]["ok"] is True
    assert ingested.json()["pending_node_ids"]
    listed_after_ingest = client.get("/api/knowledge")
    assert listed_after_ingest.json()["items"][0]["graph_status"] == "pending"

    graph = client.get("/api/graph")
    pending = next(node for node in graph.json()["pending_nodes"] if node["label"] == "OpenAI")
    approved = client.post(f"/api/graph/pending/{pending['id']}/approve")
    assert approved.status_code == 200
    assert any(node["label"] == "OpenAI" for node in approved.json()["nodes"])
    listed_after_approve = client.get("/api/knowledge")
    assert listed_after_approve.json()["items"][0]["graph_status"] == "ingested"


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
    assert body["item"]["graph_status"] == "not_ingested"

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


def test_graph_rebuild_and_node_detail(tmp_path, monkeypatch):
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
    monkeypatch.setattr(ocr_client, "recognize_screenshots", lambda paths: "长鑫科技 DRAM 信息")
    monkeypatch.setattr(
        deepseek_client,
        "generate_knowledge_from_text",
        lambda raw_text, setting=None: (
            KnowledgeResult(
                title="长鑫科技与国产DRAM",
                topic="半导体",
                tags=["长鑫科技", "DRAM"],
                focus_question="长鑫科技有哪些信息？",
                clusters=[],
                investment_insights="国产替代值得跟踪。",
            ),
            raw_text,
        ),
    )
    monkeypatch.setattr(
        deepseek_client,
        "extract_knowledge_network",
        lambda knowledge, existing_nodes=None, setting=None: KnowledgeNetworkExtraction(
            nodes=[
                ExtractedTermNode(name="长鑫科技", category="信息视野拓展", term_type="公司"),
                ExtractedTermNode(name="DRAM", category="信息视野拓展", term_type="技术"),
            ],
            relations=[],
        ),
    )
    client = TestClient(app.app)
    uploaded = client.post("/api/images", files={"files": ("shot.png", PNG_1X1, "image/png")})
    image_id = uploaded.json()["items"][0]["id"]
    generated = client.post("/api/knowledge/generate", json={"image_ids": [image_id]})
    assert generated.status_code == 200

    rebuilt = client.post("/api/graph/rebuild")
    assert rebuilt.status_code == 200
    assert rebuilt.json()["rebuilt"] == 1
    topic_node = next(node for node in rebuilt.json()["nodes"] if node["label"] == "长鑫科技")
    detail = client.get(f"/api/graph/node/{topic_node['id']}")
    assert detail.status_code == 200
    assert detail.json()["knowledge"][0]["title"] == "长鑫科技与国产DRAM"


def test_retrieval_chat_uses_local_matches(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    client = TestClient(app.app)
    now = "2026-05-28T10:00:00"
    md_path = storage.markdown_path_for("长鑫科技信息", "abc123456789", now)
    md_path.write_text("# 长鑫科技信息\n\n长鑫科技与 DRAM 国产替代。\n", encoding="utf-8")
    entry = storage.create_or_update_knowledge_entry([1], "abc123456789")
    storage.update_knowledge_entry(
        entry["id"],
        markdown_path=str(md_path.relative_to(storage.ROOT)),
        title="长鑫科技信息",
        topic="半导体",
        tags='["长鑫科技"]',
        status="ready",
    )
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
        "answer_retrieval_question",
        lambda question, markdown_files, setting=None: RetrievalAnswer(
            answer="你收集了长鑫科技与 DRAM 国产替代相关信息。",
            matched_categories=["半导体"],
            reference_files=[markdown_files[0][0]],
            follow_up_suggestions=["继续了解 DRAM 业务"],
        ),
    )

    response = client.post("/api/retrieval/chat", json={"question": "我收集了哪些有关于长鑫科技的信息"})
    assert response.status_code == 200
    body = response.json()
    assert "长鑫科技" in body["answer"]
    assert body["matches"][0]["title"] == "长鑫科技信息"


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


def test_graph_node_can_be_renamed_and_deleted(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "edit-node-hash")
    knowledge = KnowledgeResult(
        title="长鑫科技 DRAM",
        topic="半导体",
        tags=["长鑫科技", "DRAM"],
        focus_question="",
        clusters=[],
        investment_insights="",
    )
    graph_core.ingest_knowledge_network(
        entry,
        knowledge,
        KnowledgeNetworkExtraction(
            nodes=[
                ExtractedTermNode(name="长鑫科技", category="信息视野拓展"),
                ExtractedTermNode(name="DRAM", category="信息视野拓展"),
            ],
            relations=[],
        ),
    )
    client = TestClient(app.app)
    node = next(item for item in graph_core.graph_payload()["nodes"] if item["label"] == "长鑫科技")

    renamed = client.patch(f"/api/graph/node/{node['id']}", json={"label": "CXMT"})
    assert renamed.status_code == 200
    assert any(item["label"] == "CXMT" for item in renamed.json()["nodes"])

    deleted = client.delete(f"/api/graph/node/{renamed.json()['id']}")
    assert deleted.status_code == 200
    assert all(item["label"] != "CXMT" for item in deleted.json()["nodes"])


def test_graph_refresh_merges_duplicate_node_labels(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first = storage.create_or_update_knowledge_entry([1], "dup-a")
    second = storage.create_or_update_knowledge_entry([2], "dup-b")
    knowledge = KnowledgeResult(
        title="长鑫科技",
        topic="半导体",
        tags=["长鑫科技"],
        focus_question="",
        clusters=[],
        investment_insights="",
    )
    graph_core.ingest_knowledge_network(
        first,
        knowledge,
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="长鑫科技", category="信息视野拓展")], relations=[]),
    )
    with storage.connect() as conn:
        graph_core.upsert_node(
            conn,
            {
                "id": "term:manual-duplicate",
                "label": "长鑫科技",
                "level": 2,
                "node_type": "term",
                "primary_category": "信息视野拓展",
                "secondary_category": "概念",
                "summary": "manual duplicate",
                "keywords": "[]",
                "created_at": graph_core.now_iso(),
                "updated_at": graph_core.now_iso(),
            },
        )
        graph_core.link_knowledge(conn, second["id"], "term:manual-duplicate", "term")
        conn.commit()

    client = TestClient(app.app)
    refreshed = client.post("/api/graph/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["merged"] == 1
    nodes = [node for node in refreshed.json()["nodes"] if node["node_type"] == "term" and node["label"] == "长鑫科技"]
    assert len(nodes) == 1
    detail = graph_core.node_detail(nodes[0]["id"])
    assert len(detail["knowledge"]) == 2


def test_graph_rename_to_existing_node_merges_without_error(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first = storage.create_or_update_knowledge_entry([1], "rename-merge-a")
    second = storage.create_or_update_knowledge_entry([2], "rename-merge-b")
    graph_core.ingest_knowledge_network(
        first,
        KnowledgeResult(title="国产芯爆发", topic="国产芯", tags=["国产芯爆发"], focus_question="", clusters=[], investment_insights=""),
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="国产芯爆发", category="信息视野拓展")], relations=[]),
    )
    graph_core.ingest_knowledge_network(
        second,
        KnowledgeResult(title="国产芯", topic="国产芯", tags=["国产芯"], focus_question="", clusters=[], investment_insights=""),
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="国产芯", category="信息视野拓展")], relations=[]),
    )
    payload = graph_core.graph_payload()
    source = next(node for node in payload["nodes"] if node["label"] == "国产芯爆发")

    client = TestClient(app.app)
    renamed = client.patch(f"/api/graph/node/{source['id']}", json={"label": "国产芯"})

    assert renamed.status_code == 200
    nodes = [node for node in renamed.json()["nodes"] if node["node_type"] == "term" and node["label"] == "国产芯"]
    assert len(nodes) == 1
    detail = graph_core.node_detail(nodes[0]["id"])
    assert len(detail["knowledge"]) == 2


def test_graph_organize_creates_middle_group_nodes(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "organize-hash")
    knowledge = KnowledgeResult(
        title="半导体知识",
        topic="半导体",
        tags=["半导体"],
        focus_question="",
        clusters=[],
        investment_insights="",
    )
    graph_core.ingest_knowledge_network(
        entry,
        knowledge,
        KnowledgeNetworkExtraction(
            nodes=[
                ExtractedTermNode(name="长鑫科技", category="信息视野拓展"),
                ExtractedTermNode(name="DRAM", category="信息视野拓展"),
                ExtractedTermNode(name="国产芯", category="信息视野拓展"),
            ],
            relations=[],
        ),
    )
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
        "organize_graph_nodes",
        lambda nodes, setting=None: GraphOrganizationResult(
            groups=[
                GraphGroup(
                    name="国产半导体",
                    category="信息视野拓展",
                    summary="整理国产半导体相关节点。",
                    child_nodes=["长鑫科技", "DRAM", "国产芯"],
                )
            ]
        ),
    )

    client = TestClient(app.app)
    response = client.post("/api/graph/organize")

    assert response.status_code == 200
    body = response.json()
    assert body["groups"] == 1
    assert any(node["node_type"] == "group" and node["label"] == "国产半导体" for node in body["nodes"])
    group = next(node for node in body["nodes"] if node["node_type"] == "group")
    detail = graph_core.node_detail(group["id"])
    child_labels = {child["label"] for child in detail["children"]}
    assert {"长鑫科技", "DRAM", "国产芯"}.issubset(child_labels)


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


def test_approving_pending_node_runs_incremental_organization(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first = storage.create_or_update_knowledge_entry([1], "incremental-base")
    second = storage.create_or_update_knowledge_entry([2], "incremental-pending")
    graph_core.ingest_knowledge_network(
        first,
        KnowledgeResult(title="OpenAI", topic="AI", tags=["AI"], focus_question="", clusters=[], investment_insights=""),
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="OpenAI", category="信息视野拓展")], relations=[]),
    )
    graph_core.apply_graph_organization(
        GraphOrganizationResult(
            groups=[
                GraphGroup(
                    name="AI",
                    category="信息视野拓展",
                    summary="AI related nodes.",
                    child_nodes=["OpenAI"],
                )
            ]
        )
    )
    graph_core.ingest_knowledge_network(
        second,
        KnowledgeResult(title="Anthropic", topic="AI", tags=["AI"], focus_question="", clusters=[], investment_insights=""),
        KnowledgeNetworkExtraction(nodes=[ExtractedTermNode(name="Anthropic", category="信息视野拓展")], relations=[]),
        as_pending=True,
    )

    pending = next(node for node in graph_core.graph_payload()["pending_nodes"] if node["label"] == "Anthropic")
    client = TestClient(app.app)
    response = client.post(f"/api/graph/pending/{pending['id']}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["organized"] == 1
    assert body["linked"] >= 1
    group = next(node for node in body["nodes"] if node["node_type"] == "group" and node["label"] == "AI")
    detail = graph_core.node_detail(group["id"])
    child_labels = {child["label"] for child in detail["children"]}
    assert "Anthropic" in child_labels


def test_manual_graph_ingest_marks_failed_files_without_blocking_success(tmp_path, monkeypatch):
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
    statuses = {item["id"]: item["graph_status"] for item in client.get("/api/knowledge").json()["items"]}
    assert statuses[first_id] == "pending"
    assert statuses[second_id] == "graph_error"


def test_delete_not_ingested_knowledge_protects_graph_items(tmp_path, monkeypatch):
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

    def fake_publish(workspace_path, title, author="Bobo", digest=None, cover_path=None):
        captured["author"] = author
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
    assert result["fallback"] is True
    assert "formatted.html" in result["path"]
    assert "正文" in result["html"]


def test_format_article_falls_back_when_formatter_script_missing(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("missing-formatter")
    writer_tools.write_article(workspace, "# 标题\n\n## 小节\n\n正文")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "missing_formatter.py")

    result = writer_tools.format_article(workspace)

    assert result["fallback"] is True
    assert "formatter script not found" in result["stderr"]
    assert "formatted.html" in result["path"]
    assert "正文" in result["html"]


def test_format_article_prefers_api_design_formatter(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    workspace = writer_tools.dated_workspace("api-format")
    writer_tools.write_article(workspace, "# 标题\n\n## 小节\n\n正文")
    monkeypatch.setattr(writer_tools, "FORMATTER_SCRIPT", tmp_path / "missing_formatter.py")
    monkeypatch.setattr(writer_tools.api_settings, "active_setting", lambda: {"api_key": "test", "model": "format-model"})

    def fake_design(markdown, design_strategy="", setting=None):
        assert "# 标题" in markdown
        assert "强调重点句" in design_strategy
        assert setting["model"] == "format-model"
        return "<html><body><section style='padding:24px'><blockquote>设计化导语</blockquote><p>正文</p></section></body></html>"

    monkeypatch.setattr(writer_tools.deepseek_client, "design_wechat_article_html", fake_design)

    result = writer_tools.format_article(workspace, design_strategy="强调重点句")

    assert result["fallback"] is False
    assert result["ai_formatted"] is True
    assert "设计化导语" in result["html"]
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
