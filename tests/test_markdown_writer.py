from markdown_writer import render_knowledge_markdown
from schemas import KnowledgeCluster, KnowledgeResult


def test_render_knowledge_markdown_contains_required_sections():
    result = KnowledgeResult(
        title="Nvidia Rubin Rack Cost",
        topic="AI compute",
        tags=["AI", "chips"],
        focus_question="Why is the rack cost rising?",
        clusters=[
            KnowledgeCluster(
                name="Nvidia; Rubin rack; 7.8 million USD",
                domain="AI infrastructure",
                occurrence_count=1,
                meaning="Rubin rack indicates value growth in next-generation compute hardware.",
                key_information=["7.8 million USD", "Rubin rack"],
            )
        ],
        investment_insights="Watch value migration into cooling, power, and networking.",
    )

    markdown = render_knowledge_markdown(result, "raw text", "2026-05-26T12:00:00")

    assert "# Nvidia Rubin Rack Cost" in markdown
    assert "## 截图关注的问题" in markdown
    assert "## 核心知识簇" in markdown
    assert "## 外化思考与投资启发" in markdown
    assert "## 原始识别文本" in markdown
    assert "Nvidia; Rubin rack; 7.8 million USD" in markdown
