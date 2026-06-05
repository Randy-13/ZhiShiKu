from __future__ import annotations

import json
import re
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import storage
from schemas import (
    ExtractedTermNode,
    GraphIngestionResult,
    GraphOrganizationResult,
    KnowledgeNetworkExtraction,
    KnowledgeResult,
    TermRelation,
)


CATEGORY_DESCRIPTIONS = {
    "底层思维": "根基层：通用思维模型、逻辑、方法论、价值观。",
    "社会宏观认知": "环境层：经济、政策、历史、社会规律与外部世界运行规则。",
    "个人核心能力": "成长层：情绪、时间、决策、沟通、心态等个人成长能力。",
    "专业职业技能": "生存层：职业能力、行业认知、变现能力与谋生技能。",
    "生活生存认知": "落地层：健康、理财、法律、亲密关系等人生基本盘。",
    "信息视野拓展": "迭代层：前沿新知、科学通识、全球视野与认知更新。",
}

CATEGORY_ORDER = list(CATEGORY_DESCRIPTIONS)
DEFAULT_SECONDARY = "未细分"

ENTITY_ALIASES = [
    "长鑫科技",
    "华为",
    "OpenAI",
    "Anthropic",
    "SpaceX",
    "Starlink星链",
    "Grok AI",
    "Token",
    "DRAM",
    "DDR5",
    "LPDDR5",
    "IPO",
    "AI",
    "美股",
    "商业航天",
    "摩尔定律",
    "康波周期",
    "K型经济",
    "国产替代",
    "半导体",
    "存储芯片",
]

STOP_TERMS = {
    "巨无霸",
    "疯狂",
    "核心",
    "逻辑",
    "分析",
    "方向",
    "原因",
    "确定性",
    "新趋势",
    "知识簇",
    "信息",
    "内容",
    "截图",
    "本轮",
    "主题",
    "市场观察",
    "行业分析",
    "科技行情",
    "业绩变化",
    "业绩驱动",
    "业务结构",
    "产品布局",
    "产能进展",
    "风险提示",
    "风险",
    "影响",
    "联系",
    "机会",
    "驱动",
    "配置",
    "行业",
    "产业",
    "产品",
    "产能",
    "研发",
    "融资",
    "估值",
    "营收",
    "财富",
    "经济",
    "资产",
    "知识点",
    "独立知识簇",
}

TERM_SPLIT_RE = re.compile(r"(?:[；;、，,。.!！?？：:\s/|｜+\-—_·]+|的|与|和|及)")
BAD_TERM_PATTERNS = [
    r"\d{4}年.*(变化|业绩|一季度|季度|年度)",
    r"(什么|哪些|如何|为何|为什么|是否|怎么|呈现|体现|带来|判断|把握|根据|关系|联系|分别|多少)",
    r"(层面|相关|文本|OCR|基于|站在|之间|它们|它|其|哪些)",
]
COMPANY_SUFFIXES = ("科技", "集团", "股份", "银行", "证券", "资本", "能源", "汽车", "电子", "半导体")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def node_id(prefix: str, value: str) -> str:
    text = re.sub(r"\s+", "-", value.strip())
    text = re.sub(r"[^\w\u4e00-\u9fff\-]+", "", text, flags=re.UNICODE)
    return f"{prefix}:{text[:80] or 'unknown'}"


def normalize_category(value: str | None) -> str:
    if value in CATEGORY_DESCRIPTIONS:
        return value
    text = value or ""
    rules = {
        "思维": "底层思维",
        "模型": "底层思维",
        "宏观": "社会宏观认知",
        "经济": "社会宏观认知",
        "政策": "社会宏观认知",
        "能力": "个人核心能力",
        "情绪": "个人核心能力",
        "时间": "个人核心能力",
        "职业": "专业职业技能",
        "行业": "专业职业技能",
        "技能": "专业职业技能",
        "生活": "生活生存认知",
        "健康": "生活生存认知",
        "理财": "生活生存认知",
        "AI": "信息视野拓展",
        "科技": "信息视野拓展",
        "前沿": "信息视野拓展",
    }
    for key, category in rules.items():
        if key in text:
            return category
    return "信息视野拓展"


def normalize_keywords(values: list[str] | None) -> list[str]:
    seen = set()
    result = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text[:48])
    return result[:12]


def canonical_term(value: str, context: str = "") -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[#《「【\[(（]+|[#》」】\])）]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip("：:，,。；;、-—_ ")
    if not text:
        return ""
    lowered = text.lower()
    alias_map = {
        "starlink": "Starlink星链",
        "星链": "Starlink星链",
        "grok": "Grok AI",
        "grok ai": "Grok AI",
        "deepseek": "DeepSeek",
        "deepseekv4": "DeepSeek",
        "open ai": "OpenAI",
        "人工智能": "AI",
        "科创板ipo": "IPO",
    }
    if lowered in alias_map:
        return alias_map[lowered]
    for alias in sorted(ENTITY_ALIASES, key=len, reverse=True):
        if alias.lower() == lowered:
            return alias
        if alias.lower() in lowered:
            return alias
    text = re.sub(r"(的)?(核心|关键|主要|疯狂|巨无霸|最新|完整|深度|全面|分析|逻辑|原因|方向|趋势|框架|时代|主线)+", "", text)
    text = text.strip("：:，,。；;、-—_ ")
    if text == "星链":
        return "Starlink星链"
    if text == "Grok" and "AI" in context:
        return "Grok AI"
    return text


def looks_like_named_term(value: str) -> bool:
    text = value.strip()
    if text in ENTITY_ALIASES:
        return True
    if re.fullmatch(r"[A-Z][A-Za-z0-9+.-]{1,15}", text):
        return True
    if re.search(r"[A-Za-z]", text) and len(text) <= 18:
        return True
    if text.endswith(COMPANY_SUFFIXES) and 3 <= len(text) <= 12:
        return True
    if text in {"美股", "港股", "A股", "IPO", "AI", "半导体", "国产替代", "商业航天", "存储芯片", "摩尔定律", "康波周期", "K型经济"}:
        return True
    if 2 <= len(text) <= 8 and re.search(r"(定律|周期|模型|芯片|股市|算力|电力|DRAM|DDR)", text):
        return True
    return False


def is_valid_term(value: str) -> bool:
    text = value.strip()
    if not text or text in STOP_TERMS:
        return False
    if len(text) < 2 or len(text) > 24:
        return False
    if re.fullmatch(r"\d+", text):
        return False
    if any(re.search(pattern, text) for pattern in BAD_TERM_PATTERNS):
        return False
    if re.search(r"(分析|逻辑|原因|方向|问题|启发)$", text) and text not in {"AI"}:
        return False
    if looks_like_named_term(text):
        return True
    if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", text):
        return True
    return False


def terms_from_text(text: str) -> list[str]:
    context = text or ""
    found: list[str] = []
    for alias in sorted(ENTITY_ALIASES, key=len, reverse=True):
        if alias.lower() in context.lower():
            found.append(alias)
    for raw in TERM_SPLIT_RE.split(context):
        term = canonical_term(raw, context)
        if is_valid_term(term):
            found.append(term)
    seen = set()
    result = []
    for term in found:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(term)
    return result[:18]


def fallback_network_extraction(knowledge: KnowledgeResult) -> KnowledgeNetworkExtraction:
    text_parts = [knowledge.title, knowledge.topic, *knowledge.tags, knowledge.focus_question]
    for cluster in knowledge.clusters:
        text_parts.extend([cluster.name, cluster.domain, cluster.meaning, *cluster.key_information])
    joined = " ".join(part for part in text_parts if part)
    names = terms_from_text(joined)
    if not names:
        names = [canonical_term(knowledge.title) or "未命名知识"]
    nodes = [
        ExtractedTermNode(
            name=name,
            category=normalize_category(" ".join([knowledge.topic, *knowledge.tags, name])),
            term_type="概念",
            aliases=[],
            importance=5 if name in ENTITY_ALIASES else 3,
            summary=(knowledge.focus_question or knowledge.investment_insights or knowledge.title)[:300],
        )
        for name in names
        if is_valid_term(name)
    ]
    relations: list[TermRelation] = []
    if len(nodes) > 1:
        anchor = nodes[0].name
        for node in nodes[1:9]:
            relations.append(
                TermRelation(
                    source=anchor,
                    target=node.name,
                    relation_type="关联",
                    evidence=f"{anchor} 与 {node.name} 在同一轮知识输入中共同出现。",
                    confidence=0.65,
                )
            )
    return KnowledgeNetworkExtraction(nodes=nodes, relations=relations)


def compact_label(value: str, fallback: str = "未命名节点", max_len: int = 18) -> str:
    text = re.sub(r"[：:丨|、，,；;]+", " ", value or "").strip()
    text = re.sub(r"\s+", " ", text)
    for alias in ENTITY_ALIASES:
        if alias.lower() in text.lower():
            return alias
    if "K型" in text or "K 型" in text:
        return "K型经济"
    if "康波" in text:
        return "康波周期"
    if "科技牛" in text:
        return "科技牛行情"
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text or fallback


def topic_key(knowledge: KnowledgeResult, ingestion: GraphIngestionResult, secondary: str) -> str:
    candidates = [
        ingestion.node_name or "",
        knowledge.title or "",
        secondary or "",
        " ".join(knowledge.tags),
    ]
    joined = " ".join(candidates)
    for alias in ENTITY_ALIASES:
        if alias.lower() in joined.lower():
            return alias
    if "K型" in joined or "K 型" in joined:
        return "K型经济"
    if "康波" in joined:
        return "康波周期"
    if "科技牛" in joined:
        return "科技牛行情"
    base = ingestion.node_name or knowledge.title or secondary or "未命名知识"
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "", base, flags=re.UNICODE)
    return base[:24] or "未命名知识"


def init_graph() -> None:
    storage.init_storage()
    with storage.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                level INTEGER NOT NULL,
                node_type TEXT NOT NULL,
                primary_category TEXT,
                secondary_category TEXT,
                summary TEXT,
                keywords TEXT NOT NULL DEFAULT '[]',
                source_knowledge_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                description TEXT,
                confidence REAL NOT NULL DEFAULT 0.7,
                source_knowledge_id INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(source_id, target_id, relation_type, source_knowledge_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_node_links (
                knowledge_id INTEGER NOT NULL,
                node_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (knowledge_id, node_id, role)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_graph_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                primary_category TEXT,
                term_type TEXT,
                summary TEXT,
                keywords TEXT NOT NULL DEFAULT '[]',
                knowledge_id INTEGER NOT NULL,
                raw_payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    ensure_category_nodes()


def ensure_category_nodes() -> None:
    timestamp = now_iso()
    with storage.connect() as conn:
        for category, summary in CATEGORY_DESCRIPTIONS.items():
            upsert_node(
                conn,
                {
                    "id": node_id("cat", category),
                    "label": category,
                    "level": 1,
                    "node_type": "category",
                    "primary_category": category,
                    "secondary_category": "",
                    "summary": summary,
                    "keywords": json.dumps([category], ensure_ascii=False),
                    "source_knowledge_id": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        conn.commit()


def upsert_node(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO graph_nodes (
            id, label, level, node_type, primary_category, secondary_category,
            summary, keywords, source_knowledge_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            label = excluded.label,
            level = excluded.level,
            node_type = excluded.node_type,
            primary_category = excluded.primary_category,
            secondary_category = excluded.secondary_category,
            summary = excluded.summary,
            keywords = excluded.keywords,
            source_knowledge_id = COALESCE(excluded.source_knowledge_id, graph_nodes.source_knowledge_id),
            updated_at = excluded.updated_at
        """,
        (
            item["id"],
            item["label"],
            item["level"],
            item["node_type"],
            item.get("primary_category"),
            item.get("secondary_category"),
            item.get("summary"),
            item.get("keywords") or "[]",
            item.get("source_knowledge_id"),
            item.get("created_at") or now_iso(),
            item.get("updated_at") or now_iso(),
        ),
    )


def upsert_edge(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    relation_type: str,
    description: str = "",
    confidence: float = 0.7,
    source_knowledge_id: int | None = None,
) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO graph_edges (
            source_id, target_id, relation_type, description, confidence, source_knowledge_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (source_id, target_id, relation_type, description, confidence, source_knowledge_id, timestamp),
    )


def link_knowledge(conn: sqlite3.Connection, knowledge_id: int, nid: str, role: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO knowledge_node_links (knowledge_id, node_id, role, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (knowledge_id, nid, role, now_iso()),
    )


def pending_id(knowledge_id: int, label: str) -> str:
    digest = hashlib.sha1(f"{knowledge_id}:{label}".encode("utf-8")).hexdigest()[:12]
    return f"pending:{digest}"


def fallback_ingestion(knowledge: KnowledgeResult) -> GraphIngestionResult:
    text = " ".join([knowledge.title, knowledge.topic, *knowledge.tags, *(cluster.domain for cluster in knowledge.clusters)])
    primary = normalize_category(text)
    secondary = knowledge.topic or (knowledge.tags[0] if knowledge.tags else DEFAULT_SECONDARY)
    keywords = [knowledge.topic, *knowledge.tags, *(cluster.name for cluster in knowledge.clusters[:4])]
    summary = knowledge.focus_question or knowledge.investment_insights or knowledge.title
    return GraphIngestionResult(
        primary_category=primary,
        secondary_category=secondary or DEFAULT_SECONDARY,
        node_name=knowledge.title,
        summary=summary[:500],
        keywords=normalize_keywords(keywords),
        relation_type="关联",
        relation_description="由本轮知识簇自动收纳入网。",
    )


def merge_keywords(*values: list[str]) -> list[str]:
    merged: list[str] = []
    for group in values:
        for item in group or []:
            if item and item not in merged:
                merged.append(item)
    return normalize_keywords(merged)


def ingest_knowledge_network(
    knowledge_entry: dict[str, Any],
    knowledge: KnowledgeResult,
    extraction: KnowledgeNetworkExtraction | None = None,
    as_pending: bool = False,
) -> dict[str, Any]:
    init_graph()
    extraction = extraction or fallback_network_extraction(knowledge)
    if not extraction.nodes:
        extraction = fallback_network_extraction(knowledge)

    knowledge_id = int(knowledge_entry["id"])
    timestamp = now_iso()
    pending_ids: list[str] = []

    if not as_pending:
        term_ids: dict[str, str] = {}
        with storage.connect() as conn:
            for raw_node in extraction.nodes:
                label = canonical_term(raw_node.name, knowledge.title)
                if not is_valid_term(label):
                    continue
                primary = normalize_category(raw_node.category or " ".join([knowledge.topic, *knowledge.tags, label]))
                term_id = node_id("term", label)
                category_id = node_id("cat", primary)
                aliases = [canonical_term(alias, label) for alias in raw_node.aliases]
                summary = raw_node.summary or knowledge.focus_question or knowledge.investment_insights or knowledge.title
                upsert_node(
                    conn,
                    {
                        "id": term_id,
                        "label": label,
                        "level": 2,
                        "node_type": "term",
                        "primary_category": primary,
                        "secondary_category": raw_node.term_type or "概念",
                        "summary": summary[:1000],
                        "keywords": json.dumps(merge_keywords([label, *aliases], knowledge.tags), ensure_ascii=False),
                        "source_knowledge_id": None,
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                )
                upsert_edge(conn, category_id, term_id, "包含", f"{label} 归入 {primary}", 0.9)
                link_knowledge(conn, knowledge_id, term_id, "term")
                term_ids[label.lower()] = term_id

            for relation in extraction.relations[:32]:
                source = canonical_term(relation.source, knowledge.title)
                target = canonical_term(relation.target, knowledge.title)
                if source.lower() == target.lower():
                    continue
                source_id = term_ids.get(source.lower())
                target_id = term_ids.get(target.lower())
                if not source_id or not target_id:
                    continue
                upsert_edge(conn, source_id, target_id, relation.relation_type or "关联", (relation.evidence or "")[:500], float(relation.confidence or 0.75), knowledge_id)

            if not extraction.relations and len(term_ids) > 1:
                ids = list(term_ids.values())
                for source_id, target_id in zip(ids, ids[1:9]):
                    upsert_edge(conn, source_id, target_id, "共现", "同一轮知识输入中共同出现。", 0.6, knowledge_id)
            conn.commit()
        primary = normalize_category(extraction.nodes[0].category if extraction.nodes else knowledge.topic)
        return {"term_node_ids": list(term_ids.values()), "pending_node_ids": [], "primary_category": primary, "secondary_category": "名词网络"}

    with storage.connect() as conn:
        for raw_node in extraction.nodes:
            label = canonical_term(raw_node.name, knowledge.title)
            if not is_valid_term(label):
                continue
            primary = normalize_category(raw_node.category or " ".join([knowledge.topic, *knowledge.tags, label]))
            aliases = [canonical_term(alias, label) for alias in raw_node.aliases]
            summary = raw_node.summary or knowledge.focus_question or knowledge.investment_insights or knowledge.title
            pid = pending_id(knowledge_id, label)
            raw_payload = {
                "knowledge_title": knowledge.title,
                "relations": [
                    relation.model_dump()
                    for relation in extraction.relations
                    if canonical_term(relation.source, knowledge.title).lower() == label.lower()
                    or canonical_term(relation.target, knowledge.title).lower() == label.lower()
                ],
            }
            conn.execute(
                """
                INSERT INTO pending_graph_nodes (
                    id, label, primary_category, term_type, summary, keywords,
                    knowledge_id, raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    primary_category = excluded.primary_category,
                    term_type = excluded.term_type,
                    summary = excluded.summary,
                    keywords = excluded.keywords,
                    raw_payload = excluded.raw_payload,
                    updated_at = excluded.updated_at
                """,
                (
                    pid,
                    label,
                    primary,
                    raw_node.term_type or "概念",
                    summary[:1000],
                    json.dumps(merge_keywords([label, *aliases], knowledge.tags), ensure_ascii=False),
                    knowledge_id,
                    json.dumps(raw_payload, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            pending_ids.append(pid)
        conn.commit()

    primary = normalize_category(extraction.nodes[0].category if extraction.nodes else knowledge.topic)
    return {"pending_node_ids": pending_ids, "term_node_ids": [], "primary_category": primary, "secondary_category": "待入网"}


def ingest_knowledge(
    knowledge_entry: dict[str, Any],
    knowledge: KnowledgeResult,
    ingestion: GraphIngestionResult | None = None,
) -> dict[str, Any]:
    if ingestion:
        names = [ingestion.node_name, *ingestion.keywords]
        nodes = [
            ExtractedTermNode(
                name=canonical_term(name, knowledge.title),
                category=ingestion.primary_category,
                term_type="关键词",
                summary=ingestion.summary,
            )
            for name in names
            if is_valid_term(canonical_term(name, knowledge.title))
        ]
        return ingest_knowledge_network(
            knowledge_entry,
            knowledge,
            KnowledgeNetworkExtraction(nodes=nodes, relations=[]),
        )
    return ingest_knowledge_network(knowledge_entry, knowledge, fallback_network_extraction(knowledge))


def row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["keywords"] = json.loads(item.get("keywords") or "[]")
    except json.JSONDecodeError:
        item["keywords"] = []
    return item


def graph_payload() -> dict[str, Any]:
    init_graph()
    with storage.connect() as conn:
        nodes = [row_to_node(row) for row in conn.execute("SELECT * FROM graph_nodes ORDER BY level, label").fetchall()]
        edges = [dict(row) for row in conn.execute("SELECT * FROM graph_edges ORDER BY id").fetchall()]
        pending = [pending_row_to_node(row) for row in conn.execute("SELECT * FROM pending_graph_nodes ORDER BY created_at DESC, label").fetchall()]
    return {"nodes": nodes, "edges": edges, "pending_nodes": pending, "categories": CATEGORY_ORDER}


def pending_row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["keywords"] = json.loads(item.get("keywords") or "[]")
    except json.JSONDecodeError:
        item["keywords"] = []
    try:
        item["raw_payload"] = json.loads(item.get("raw_payload") or "{}")
    except json.JSONDecodeError:
        item["raw_payload"] = {}
    item["node_type"] = "pending"
    return item


def update_pending_node(pid: str, label: str) -> dict[str, Any]:
    init_graph()
    clean_label = canonical_term(label)
    if not clean_label:
        raise ValueError("节点名称不能为空")
    if not is_valid_term(clean_label):
        raise ValueError("这个名称不像可入网的名词节点，请换一个更明确的名词")
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM pending_graph_nodes WHERE id = ?", (pid,)).fetchone()
        if row is None:
            raise KeyError("Pending node not found")
        conn.execute(
            "UPDATE pending_graph_nodes SET label = ?, updated_at = ? WHERE id = ?",
            (clean_label, now_iso(), pid),
        )
        conn.commit()
    return {"id": pid, "label": clean_label}


def delete_pending_node(pid: str) -> dict[str, Any]:
    init_graph()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM pending_graph_nodes WHERE id = ?", (pid,)).fetchone()
        if row is None:
            raise KeyError("Pending node not found")
        conn.execute("DELETE FROM pending_graph_nodes WHERE id = ?", (pid,))
        conn.commit()
    return {"deleted": pid}


def _node_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_terms = {canonical_term(left.get("label") or "").lower()}
    right_terms = {canonical_term(right.get("label") or "").lower()}
    left_terms.update(str(item).lower() for item in left.get("keywords") or [])
    right_terms.update(str(item).lower() for item in right.get("keywords") or [])
    left_terms = {item for item in left_terms if item}
    right_terms = {item for item in right_terms if item}
    if not left_terms or not right_terms:
        return 0.0
    overlap = left_terms & right_terms
    if overlap:
        return len(overlap) / max(len(left_terms), len(right_terms))
    left_label = canonical_term(left.get("label") or "").lower()
    right_label = canonical_term(right.get("label") or "").lower()
    if not left_label or not right_label:
        return 0.0
    if left_label in right_label or right_label in left_label:
        return 0.45
    return 0.0


def organize_new_nodes(node_ids: list[str]) -> dict[str, int]:
    init_graph()
    if not node_ids:
        return {"organized": 0, "linked": 0, "merged": 0}
    merged = merge_duplicate_nodes()["merged"]
    linked = 0
    organized = 0
    with storage.connect() as conn:
        nodes = [row_to_node(row) for row in conn.execute("SELECT * FROM graph_nodes").fetchall()]
        by_id = {node["id"]: node for node in nodes}
        new_nodes = [by_id[node_id] for node_id in node_ids if node_id in by_id]
        if not new_nodes:
            return {"organized": 0, "linked": 0, "merged": merged}
        group_nodes = [node for node in nodes if node.get("node_type") == "group"]
        term_nodes = [node for node in nodes if node.get("node_type") == "term"]

        for node in new_nodes:
            organized += 1
            primary = normalize_category(node.get("primary_category"))
            category_id = node_id("cat", primary)
            upsert_edge(conn, category_id, node["id"], "包含", f"{node['label']} 归入 {primary}", 0.75)

            matched_group = False
            group_candidates = [
                group
                for group in group_nodes
                if normalize_category(group.get("primary_category")) == primary
            ]
            group_candidates.sort(key=lambda group: _node_similarity(node, group), reverse=True)
            for group in group_candidates[:3]:
                if _node_similarity(node, group) < 0.18:
                    continue
                upsert_edge(conn, group["id"], node["id"], "整理归类", f"{node['label']} 增量归入 {group['label']}", 0.72)
                linked += 1
                matched_group = True

            peer_candidates = [
                peer
                for peer in term_nodes
                if peer["id"] != node["id"]
                and normalize_category(peer.get("primary_category")) == primary
            ]
            peer_candidates.sort(key=lambda peer: _node_similarity(node, peer), reverse=True)
            for peer in peer_candidates[:5]:
                score = _node_similarity(node, peer)
                if score < 0.16:
                    continue
                upsert_edge(conn, node["id"], peer["id"], "关联", f"{node['label']} 与 {peer['label']} 在知识网中相近", max(0.55, score), None)
                linked += 1

            if matched_group:
                conn.execute(
                    """
                    DELETE FROM graph_edges
                    WHERE source_id = ? AND target_id = ? AND relation_type = ?
                    """,
                    (category_id, node["id"], "包含"),
                )
        conn.commit()
    return {"organized": organized, "linked": linked, "merged": merged}


def approve_pending_node(pid: str) -> dict[str, Any]:
    init_graph()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM pending_graph_nodes WHERE id = ?", (pid,)).fetchone()
        if row is None:
            raise KeyError("Pending node not found")
        pending = pending_row_to_node(row)
        label = canonical_term(pending["label"])
        if not is_valid_term(label):
            raise ValueError("这个名称不像可入网的名词节点，请先改名")
        knowledge_id = int(pending["knowledge_id"])
        term_id = node_id("term", label)
        category_id = node_id("cat", normalize_category(pending.get("primary_category")))
        timestamp = now_iso()
        upsert_node(
            conn,
            {
                "id": term_id,
                "label": label,
                "level": 2,
                "node_type": "term",
                "primary_category": normalize_category(pending.get("primary_category")),
                "secondary_category": pending.get("term_type") or "概念",
                "summary": pending.get("summary") or "",
                "keywords": json.dumps(normalize_keywords([label, *pending.get("keywords", [])]), ensure_ascii=False),
                "source_knowledge_id": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )
        upsert_edge(conn, category_id, term_id, "包含", f"{label} 归入 {pending.get('primary_category')}", 0.9)
        link_knowledge(conn, knowledge_id, term_id, "term")
        conn.execute(
            """
            UPDATE knowledge_entries
            SET graph_status = 'ingested', graph_error_message = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), knowledge_id),
        )

        siblings = conn.execute(
            "SELECT * FROM pending_graph_nodes WHERE knowledge_id = ? AND id != ?",
            (knowledge_id, pid),
        ).fetchall()
        for sibling_row in siblings:
            sibling = pending_row_to_node(sibling_row)
            sibling_label = canonical_term(sibling["label"])
            sibling_id = node_id("term", sibling_label)
            exists = conn.execute("SELECT 1 FROM graph_nodes WHERE id = ?", (sibling_id,)).fetchone()
            if not exists:
                continue
            upsert_edge(conn, term_id, sibling_id, "共现", "同一轮知识输入中共同出现。", 0.6, knowledge_id)

        conn.execute("DELETE FROM pending_graph_nodes WHERE id = ?", (pid,))
        conn.commit()
    organized = organize_new_nodes([term_id])
    return {"node_id": term_id, "label": label, **organized}


def node_detail(nid: str) -> dict[str, Any]:
    init_graph()
    with storage.connect() as conn:
        node = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (nid,)).fetchone()
        if node is None:
            raise KeyError("Graph node not found")
        linked = conn.execute(
            """
            SELECT k.*, l.role FROM knowledge_node_links l
            JOIN knowledge_entries k ON k.id = l.knowledge_id
            WHERE l.node_id = ?
            ORDER BY k.created_at DESC
            """,
            (nid,),
        ).fetchall()
        edges = conn.execute(
            """
            SELECT e.*, s.label AS source_label, t.label AS target_label
            FROM graph_edges e
            LEFT JOIN graph_nodes s ON s.id = e.source_id
            LEFT JOIN graph_nodes t ON t.id = e.target_id
            WHERE e.source_id = ? OR e.target_id = ?
            ORDER BY e.id
            """,
            (nid, nid),
        ).fetchall()
        children = conn.execute(
            """
            SELECT DISTINCT n.*
            FROM graph_edges e
            JOIN graph_nodes n ON n.id = CASE
                WHEN e.source_id = ? THEN e.target_id
                ELSE e.source_id
            END
            WHERE e.source_id = ? OR e.target_id = ?
            ORDER BY
                CASE n.node_type
                    WHEN 'category' THEN 1
                    WHEN 'group' THEN 2
                    WHEN 'term' THEN 3
                    ELSE 4
                END,
                n.label
            """,
            (nid, nid, nid),
        ).fetchall()
    return {
        "node": row_to_node(node),
        "children": [row_to_node(row) for row in children],
        "knowledge": [dict(row) for row in linked],
        "edges": [dict(row) for row in edges],
    }


def rename_node(nid: str, new_label: str) -> dict[str, Any]:
    init_graph()
    label = canonical_term(new_label)
    if not label:
        raise ValueError("节点名称不能为空")
    if not is_valid_term(label):
        raise ValueError("这个名称不像可入网的名词节点，请换一个更明确的名词")
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (nid,)).fetchone()
        if row is None:
            raise KeyError("Graph node not found")
        node = row_to_node(row)
        if node["node_type"] == "category":
            raise ValueError("一级类目不能改名")
        new_id = node_id("term", label)
        timestamp = now_iso()
        if new_id != nid:
            existing = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (new_id,)).fetchone()
            if existing:
                links = conn.execute(
                    "SELECT knowledge_id, role FROM knowledge_node_links WHERE node_id = ?",
                    (nid,),
                ).fetchall()
                for link in links:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO knowledge_node_links (knowledge_id, node_id, role, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (link["knowledge_id"], new_id, link["role"], now_iso()),
                    )
                edges = conn.execute(
                    "SELECT * FROM graph_edges WHERE source_id = ? OR target_id = ?",
                    (nid, nid),
                ).fetchall()
                for edge in edges:
                    source_id = new_id if edge["source_id"] == nid else edge["source_id"]
                    target_id = new_id if edge["target_id"] == nid else edge["target_id"]
                    if source_id == target_id:
                        continue
                    upsert_edge(
                        conn,
                        source_id,
                        target_id,
                        edge["relation_type"],
                        edge["description"] or "",
                        float(edge["confidence"] or 0.7),
                        edge["source_knowledge_id"],
                    )
                conn.execute("DELETE FROM knowledge_node_links WHERE node_id = ?", (nid,))
                conn.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (nid, nid))
                conn.execute("DELETE FROM graph_nodes WHERE id = ?", (nid,))
                conn.execute(
                    "UPDATE graph_nodes SET label = ?, updated_at = ? WHERE id = ?",
                    (label, timestamp, new_id),
                )
            else:
                conn.execute(
                    "UPDATE graph_nodes SET id = ?, label = ?, updated_at = ? WHERE id = ?",
                    (new_id, label, timestamp, nid),
                )
                conn.execute("UPDATE OR IGNORE knowledge_node_links SET node_id = ? WHERE node_id = ?", (new_id, nid))
                conn.execute("DELETE FROM knowledge_node_links WHERE node_id = ?", (nid,))
                conn.execute("UPDATE graph_edges SET source_id = ? WHERE source_id = ?", (new_id, nid))
                conn.execute("UPDATE graph_edges SET target_id = ? WHERE target_id = ?", (new_id, nid))
        else:
            conn.execute("UPDATE graph_nodes SET label = ?, updated_at = ? WHERE id = ?", (label, timestamp, nid))
        conn.commit()
    return {"id": new_id, "label": label}


def delete_node(nid: str) -> dict[str, Any]:
    init_graph()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM graph_nodes WHERE id = ?", (nid,)).fetchone()
        if row is None:
            raise KeyError("Graph node not found")
        node = row_to_node(row)
        if node["node_type"] == "category":
            raise ValueError("一级类目不能删除")
        conn.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (nid, nid))
        conn.execute("DELETE FROM knowledge_node_links WHERE node_id = ?", (nid,))
        conn.execute("DELETE FROM graph_nodes WHERE id = ?", (nid,))
        conn.commit()
    return {"deleted": nid}


def merge_duplicate_nodes() -> dict[str, int]:
    init_graph()
    merged = 0
    with storage.connect() as conn:
        rank = {"group": 1, "term": 2, "pending": 3}
        rows = conn.execute(
            """
            SELECT * FROM graph_nodes
            WHERE node_type != 'category'
            """
        ).fetchall()
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            node = row_to_node(row)
            key = canonical_term(node["label"]).lower()
            if not key:
                continue
            groups.setdefault(key, []).append(node)

        for nodes in groups.values():
            if len(nodes) < 2:
                continue
            nodes.sort(key=lambda node: (rank.get(node.get("node_type"), 9), node.get("updated_at") or "", node.get("id") or ""))
            keeper = nodes[0]
            keeper_id = keeper["id"]
            keywords = set(keeper.get("keywords") or [])
            summaries = [keeper.get("summary") or ""]
            for duplicate in nodes[1:]:
                duplicate_id = duplicate["id"]
                keywords.update(duplicate.get("keywords") or [])
                if duplicate.get("summary"):
                    summaries.append(duplicate["summary"])
                conn.execute("UPDATE OR IGNORE knowledge_node_links SET node_id = ? WHERE node_id = ?", (keeper_id, duplicate_id))
                conn.execute("DELETE FROM knowledge_node_links WHERE node_id = ?", (duplicate_id,))
                conn.execute("UPDATE graph_edges SET source_id = ? WHERE source_id = ?", (keeper_id, duplicate_id))
                conn.execute("UPDATE graph_edges SET target_id = ? WHERE target_id = ?", (keeper_id, duplicate_id))
                conn.execute("DELETE FROM graph_nodes WHERE id = ?", (duplicate_id,))
                merged += 1
            conn.execute("DELETE FROM graph_edges WHERE source_id = target_id")
            conn.execute(
                """
                DELETE FROM graph_edges
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM graph_edges
                    GROUP BY source_id, target_id, relation_type, COALESCE(source_knowledge_id, -1)
                )
                """
            )
            conn.execute(
                "UPDATE graph_nodes SET keywords = ?, summary = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(normalize_keywords(list(keywords)), ensure_ascii=False),
                    "\n".join(dict.fromkeys(item for item in summaries if item))[:1000],
                    now_iso(),
                    keeper_id,
                ),
            )
        conn.commit()
    return {"merged": merged}


def apply_graph_organization(organization: GraphOrganizationResult) -> dict[str, int]:
    init_graph()
    created = 0
    linked = 0
    timestamp = now_iso()
    with storage.connect() as conn:
        term_rows = conn.execute("SELECT * FROM graph_nodes WHERE node_type = 'term'").fetchall()
        term_by_label = {row["label"]: row_to_node(row) for row in term_rows}
        conn.execute("DELETE FROM graph_edges WHERE source_id LIKE 'cat:%' AND target_id LIKE 'term:%'")
        conn.execute("DELETE FROM graph_edges WHERE source_id LIKE 'cat:%' AND target_id LIKE 'group:%'")
        conn.execute("DELETE FROM graph_edges WHERE source_id LIKE 'group:%' OR target_id LIKE 'group:%'")
        conn.execute("DELETE FROM graph_nodes WHERE node_type = 'group'")

        for group in organization.groups:
            label = re.sub(r"\s+", " ", (group.name or "").strip("：:，,。；;、-—_ "))
            if not label:
                continue
            category = normalize_category(group.category)
            group_id = node_id("group", f"{category}-{label}")
            upsert_node(
                conn,
                {
                    "id": group_id,
                    "label": label[:24],
                    "level": 2,
                    "node_type": "group",
                    "primary_category": category,
                    "secondary_category": "整理分组",
                    "summary": (group.summary or "")[:1000],
                    "keywords": json.dumps(normalize_keywords([label, *group.child_nodes]), ensure_ascii=False),
                    "source_knowledge_id": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            created += 1
            upsert_edge(conn, node_id("cat", category), group_id, "包含", f"{label} 归入 {category}", 0.9)
            for child_label in group.child_nodes:
                term = term_by_label.get(child_label)
                if not term:
                    continue
                upsert_edge(conn, group_id, term["id"], "整理归类", f"{term['label']} 归入 {label}", 0.85)
                linked += 1

        grouped_term_ids = {
            edge["target_id"]
            for edge in conn.execute("SELECT target_id FROM graph_edges WHERE source_id LIKE 'group:%'").fetchall()
        }
        for row in term_rows:
            if row["id"] in grouped_term_ids:
                continue
            upsert_edge(
                conn,
                node_id("cat", normalize_category(row["primary_category"])),
                row["id"],
                "包含",
                f"{row['label']} 归入 {row['primary_category']}",
                0.75,
            )
        conn.commit()
    merged = merge_duplicate_nodes()["merged"]
    return {"groups": created, "linked": linked, "merged": merged}


def reset_graph() -> None:
    init_graph()
    with storage.connect() as conn:
        conn.execute("DELETE FROM knowledge_node_links")
        conn.execute("DELETE FROM graph_edges")
        conn.execute("DELETE FROM graph_nodes")
        conn.commit()
    ensure_category_nodes()


def extract_markdown_section(content: str, header: str) -> str:
    pattern = rf"##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, content, flags=re.S)
    return match.group(1).strip() if match else ""


def knowledge_result_from_markdown(item: dict[str, Any], content: str) -> KnowledgeResult:
    title_match = re.search(r"^#\s+(.+)$", content, flags=re.M)
    title = title_match.group(1).strip() if title_match else item.get("title") or "未命名知识"
    tags = []
    try:
        tags = json.loads(item.get("tags") or "[]")
    except json.JSONDecodeError:
        tags = []
    return KnowledgeResult(
        title=title,
        topic=item.get("topic") or "",
        tags=tags,
        focus_question=extract_markdown_section(content, "截图关注的问题"),
        clusters=[],
        investment_insights=extract_markdown_section(content, "外化思考与投资启发"),
    )


def rebuild_from_existing() -> dict[str, int]:
    reset_graph()
    count = 0
    for item in storage.list_knowledge():
        path = storage.resolve_root_path(item.get("markdown_path"))
        if not path or not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        knowledge = knowledge_result_from_markdown(item, content)
        ingest_knowledge_network(item, knowledge, fallback_network_extraction(knowledge))
        count += 1
    return {"rebuilt": count}


def query_terms(question: str) -> list[str]:
    focused = []
    for marker in ("关于", "有关", "有关于"):
        if marker in question:
            tail = question.split(marker, 1)[1]
            tail = re.split(r"[，。！？?；;\s]", tail, 1)[0]
            tail = re.sub(r"(的信息|的内容|知识|资料)$", "", tail)
            if len(tail) >= 2:
                focused.append(tail)
    candidates = [*focused, *re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]{2,}", question)]
    stopwords = {"我收集了哪些有关于", "哪些", "关于", "信息", "内容", "知识", "我想", "了解"}
    result = []
    for candidate in candidates:
        if candidate in stopwords:
            continue
        if candidate == question and focused:
            continue
        result.append(candidate)
    return result or [question.strip()]


def search_knowledge(question: str, limit: int = 8) -> list[dict[str, Any]]:
    terms = query_terms(question)
    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in storage.list_knowledge():
        path = storage.resolve_root_path(item.get("markdown_path"))
        content = path.read_text(encoding="utf-8") if path and path.exists() else ""
        haystack = " ".join(
            [
                item.get("title") or "",
                item.get("topic") or "",
                item.get("tags") or "",
                item.get("markdown_path") or "",
                content[:12000],
            ]
        ).lower()
        score = sum(1 for term in terms if term.lower() in haystack)
        if score <= 0:
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        results.append({"item": item, "content": content, "score": score})
    results.sort(key=lambda value: (value["score"], value["item"].get("created_at") or ""), reverse=True)
    return results[:limit]


def retrieval_context(matches: list[dict[str, Any]]) -> list[tuple[str, str]]:
    payload = []
    for match in matches:
        item = match["item"]
        path = storage.resolve_root_path(item.get("markdown_path"))
        filename = Path(path).name if path else f"knowledge-{item['id']}.md"
        payload.append((filename, match["content"]))
    return payload
