from __future__ import annotations

from datetime import datetime

from schemas import CreationStrategyResult, KnowledgeResult


def bullet_list(values: list[str]) -> str:
    if not values:
        return "- 无"
    return "\n".join(f"- {value}" for value in values)


def render_knowledge_markdown(
    result: KnowledgeResult,
    raw_text: str,
    imported_at: str | None = None,
    source: str = "截图",
) -> str:
    imported_at = imported_at or datetime.now().isoformat(timespec="seconds")
    tags = "、".join(result.tags) if result.tags else "未标注"
    cluster_count = len(result.clusters)

    sections = [
        f"# {result.title}",
        "",
        f"- 来源：{source}",
        f"- 导入时间：{imported_at}",
        f"- 主题：{result.topic}",
        f"- 标签：{tags}",
        f"- 原子知识点数量：{cluster_count}",
        "",
        "## 截图关注的问题",
        "",
        result.focus_question.strip() or "未识别出明确问题。",
        "",
        "## 核心知识簇",
        "",
    ]

    if result.clusters:
        for index, cluster in enumerate(result.clusters, start=1):
            sections.extend(
                [
                    f"### {index}. {cluster.name}",
                    f"- 领域：{cluster.domain}",
                    f"- 出现次数：{cluster.occurrence_count}",
                    f"- 信息含义：{cluster.meaning}",
                    "- 关键信息元：",
                    bullet_list(cluster.key_information),
                    "",
                ]
            )
    else:
        sections.extend(["未提取出可独立解释的知识簇。", ""])

    sections.extend(
        [
            "## 外化思考与投资启发",
            "",
            result.investment_insights.strip() or "暂无。",
            "",
            "## 原始识别文本",
            "",
            "```text",
            raw_text.strip(),
            "```",
            "",
        ]
    )
    return "\n".join(sections)


def render_creation_strategy_markdown(
    result: CreationStrategyResult,
    sources: list[tuple[str, str]],
    previous_strategy: str = "",
    imported_at: str | None = None,
) -> str:
    imported_at = imported_at or datetime.now().isoformat(timespec="seconds")

    def section(title: str, values: list[str]) -> list[str]:
        return [f"## {title}", "", bullet_list(values), ""]

    source_lines = []
    for index, (title, text) in enumerate(sources, start=1):
        source_lines.extend(
            [
                f"### S{index}. {title}",
                "",
                "```text",
                text.strip()[:4000],
                "```",
                "",
            ]
        )

    sections = [
        f"# {result.title}",
        "",
        f"- 来源：创作策略学习",
        f"- 导入时间：{imported_at}",
        f"- 策略类型：{result.strategy_type}",
        f"- 样本数量：{len(sources)}",
        "",
        "## 策略摘要",
        "",
        result.summary.strip() or "暂无摘要。",
        "",
    ]
    sections.extend(section("适用场景", result.applicable_scenarios))
    sections.extend(section("作者风格画像", result.author_style_profile))
    sections.extend(section("选题策略", result.topic_strategy))
    sections.extend(section("结构策略", result.structure_strategy))
    sections.extend(section("开头套路", result.opening_patterns))
    sections.extend(section("转场套路", result.transition_patterns))
    sections.extend(section("结尾套路", result.ending_patterns))
    sections.extend(section("语言风格", result.language_style))
    sections.extend(section("节奏与情绪", result.rhythm_and_emotion))
    sections.extend(section("短视频话术策略", result.short_video_talk_strategy))
    sections.extend(section("可复用模板", result.reusable_templates))
    sections.extend(section("反例与边界", result.anti_patterns))
    sections.extend(section("证据索引", result.evidence))
    sections.extend(
        [
            "## 使用说明",
            "",
            result.usage_notes.strip() or "可把本策略作为创作前的检查清单使用。",
            "",
        ]
    )
    if previous_strategy.strip():
        sections.extend(
            [
                "## 上一版策略摘要输入",
                "",
                "```markdown",
                previous_strategy.strip()[:6000],
                "```",
                "",
            ]
        )
    sections.extend(["## 学习素材摘录", "", *source_lines])
    return "\n".join(sections)
