from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductCapability:
    id: str
    label: str
    priority: str
    product_layer: str
    user_goal: str
    frontend_area: str
    backend_domains: tuple[str, ...]


CAPABILITIES: tuple[ProductCapability, ...] = (
    ProductCapability(
        id="capture_materials",
        label="Collect raw materials",
        priority="P0",
        product_layer="raw_library_pipeline",
        user_goal="Convert text, screenshots, documents, media, and links into original-level Markdown files.",
        frontend_area="collect",
        backend_domains=("materials", "uploads", "documents", "media", "ocr"),
    ),
    ProductCapability(
        id="generate_knowledge",
        label="Extract focus knowledge",
        priority="P0",
        product_layer="focus_library_pipeline",
        user_goal="Extract structured knowledge clusters with source citation markers from raw library files.",
        frontend_area="learn",
        backend_domains=("materials", "knowledge", "documents", "media", "llm", "ocr"),
    ),
    ProductCapability(
        id="manage_library",
        label="Manage global libraries",
        priority="P0",
        product_layer="global_library",
        user_goal="Find, filter, select, delete, and reference raw, focus, and perspective files from the fixed right sidebar.",
        frontend_area="global_library",
        backend_domains=("materials", "knowledge", "mining"),
    ),
    ProductCapability(
        id="organize_network",
        label="Organize knowledge network",
        priority="P0",
        product_layer="knowledge_network",
        user_goal="Ingest knowledge into a graph, review pending nodes, and browse relationships.",
        frontend_area="learn",
        backend_domains=("graph", "knowledge", "llm"),
    ),
    ProductCapability(
        id="retrieve_answers",
        label="Retrieve answers",
        priority="P0",
        product_layer="knowledge_network",
        user_goal="Ask questions against the local knowledge network with source references.",
        frontend_area="learn",
        backend_domains=("graph", "knowledge", "llm"),
    ),
    ProductCapability(
        id="create_wechat_article",
        label="Create WeChat articles",
        priority="P1",
        product_layer="writing_studio",
        user_goal="Write, design, preflight, and publish-check WeChat public-account articles from all three libraries.",
        frontend_area="create",
        backend_domains=("writer", "knowledge", "llm"),
    ),
    ProductCapability(
        id="interpret_perspectives",
        label="Interpret from perspectives",
        priority="P2",
        product_layer="perspective_library_pipeline",
        user_goal="Interpret focus-library files from writer, investor, student, founder, and industry-research perspectives.",
        frontend_area="mine",
        backend_domains=("mining", "knowledge", "llm"),
    ),
    ProductCapability(
        id="configure_system",
        label="Configure system",
        priority="P3",
        product_layer="settings_center",
        user_goal="Configure LLM, ASR, image generation, and local dependency settings.",
        frontend_area="settings",
        backend_domains=("settings",),
    ),
)


def capabilities_by_priority(priority: str) -> tuple[ProductCapability, ...]:
    return tuple(item for item in CAPABILITIES if item.priority == priority)


def capabilities_for_frontend_area(frontend_area: str) -> tuple[ProductCapability, ...]:
    return tuple(item for item in CAPABILITIES if item.frontend_area == frontend_area)


def backend_domains_for_capability(capability_id: str) -> tuple[str, ...]:
    for item in CAPABILITIES:
        if item.id == capability_id:
            return item.backend_domains
    raise KeyError(capability_id)
