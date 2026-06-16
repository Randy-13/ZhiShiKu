from fastapi.testclient import TestClient

import api_settings
import app
import deepseek_client
import graph_core
import storage
import workbench_settings
import writer_tools
from schemas import (
    ExtractedTermNode,
    GraphGroup,
    GraphOrganizationResult,
    KnowledgeNetworkExtraction,
    KnowledgeResult,
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
    monkeypatch.setattr(workbench_settings, "SETTINGS_PATH", tmp_path / "workbench_settings.json")
    monkeypatch.setattr(writer_tools, "WRITER_DIR", runtime_root / "writer")
    storage.init_storage()
    graph_core.init_graph()


def test_graph_merges_related_markdowns_into_one_topic_node(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    first = storage.create_or_update_knowledge_entry([1], "merge-hash-1")
    second = storage.create_or_update_knowledge_entry([2], "merge-hash-2")
    knowledge_one = KnowledgeResult(
        title="长鑫科技科创板 IPO",
        topic="长鑫科技、DRAM、IPO",
        tags=["长鑫科技", "DRAM"],
        focus_question="长鑫科技 IPO 信息",
        clusters=[],
        investment_insights="",
    )
    knowledge_two = KnowledgeResult(
        title="长鑫科技与国产 DRAM",
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
        node for node in payload["nodes"] if node["node_type"] == "term" and node["label"] == "长鑫科技"
    ]
    assert len(changxin_nodes) == 1
    detail = graph_core.node_detail(changxin_nodes[0]["id"])
    assert len(detail["knowledge"]) == 2


def test_graph_fallback_splits_compound_title_into_clean_terms(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "compound-hash")
    knowledge = KnowledgeResult(
        title="美股三大巨无霸 IPO AI 商业航天",
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
        focus_question="OCR 文本呈现了哪些信息，业绩变化是什么？",
        clusters=[],
        investment_insights="",
    )
    extraction = KnowledgeNetworkExtraction(
        nodes=[
            ExtractedTermNode(name="2025年至2026年一季度业绩变化", category="信息视野拓展"),
            ExtractedTermNode(name="OCR 文本呈现了哪些", category="信息视野拓展"),
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
    assert "OCR 文本呈现了哪些" not in labels


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


def make_ready_knowledge(title: str, item_hash: str) -> int:
    entry = storage.create_or_update_knowledge_entry([1], item_hash)
    markdown_path = storage.markdown_path_for(title, item_hash, entry["created_at"])
    markdown_path.write_text(f"# {title}\n\n正文", encoding="utf-8")
    updated = storage.update_knowledge_entry(
        entry["id"],
        markdown_path=storage.storage_relative(markdown_path),
        title=title,
        status="ready",
    )
    return int(updated["id"])
