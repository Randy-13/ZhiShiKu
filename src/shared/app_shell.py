from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShellSection:
    id: str
    label: str
    nav_label: str
    nav_description: str
    route: str
    priority: str
    purpose: str


@dataclass(frozen=True)
class LibraryKind:
    id: str
    label: str
    source_module: str
    default_status: str
    purpose: str


@dataclass(frozen=True)
class WorkspacePlacement:
    capability_id: str
    shell_section: str
    primary_region: str
    secondary_region: str
    interaction_stage: str


@dataclass(frozen=True)
class WorkspaceEntry:
    id: str
    label: str
    route: str
    shell_section: str
    capability_id: str
    priority: str
    surface: str


PRIMARY_SECTIONS: tuple[ShellSection, ...] = (
    ShellSection(
        id="collect",
        label="Collect",
        nav_label="收集",
        nav_description="读取信息并保存原料",
        route="/collect",
        priority="P0",
        purpose="Convert text, screenshots, documents, media, and links into raw Markdown in the raw library.",
    ),
    ShellSection(
        id="learn",
        label="Learn",
        nav_label="学习",
        nav_description="提炼重点并构建关系网",
        route="/learn",
        priority="P0",
        purpose="Extract knowledge clusters from raw files, save focus Markdown, ingest nodes, and retrieve knowledge.",
    ),
    ShellSection(
        id="mine",
        label="Mine",
        nav_label="挖掘",
        nav_description="多视角解读重点知识",
        route="/mine",
        priority="P1",
        purpose="Interpret focus-library files from configurable perspectives and save perspective Markdown.",
    ),
    ShellSection(
        id="create",
        label="WeChat Article",
        nav_label="公众号文章创作",
        nav_description="写作、美编与发布检查",
        route="/create",
        priority="P1",
        purpose="Write, design, preflight, and publish-check WeChat public-account articles from all libraries.",
    ),
    ShellSection(
        id="library",
        label="Library",
        nav_label="知识库",
        nav_description="管理三库文件和知识正文",
        route="/library",
        priority="P2",
        purpose="Manage raw, focus, and perspective Markdown files, edit metadata, and maintain saved knowledge.",
    ),
    ShellSection(
        id="settings",
        label="Settings",
        nav_label="设置中心",
        nav_description="模型、ASR、图片与视角模板",
        route="/settings",
        priority="P3",
        purpose="Manage model, ASR, image processing, perspective templates, and system configuration.",
    ),
    ShellSection(
        id="docs",
        label="Docs",
        nav_label="文档",
        nav_description="工作区说明与排障指南",
        route="/docs",
        priority="P3",
        purpose="Explain workspace workflows, dependencies, and troubleshooting paths for users.",
    ),
)


GLOBAL_LIBRARIES: tuple[LibraryKind, ...] = (
    LibraryKind(
        id="raw",
        label="原料库",
        source_module="collect",
        default_status="未处理",
        purpose="Store unprocessed original-level Markdown converted from collected inputs.",
    ),
    LibraryKind(
        id="focus",
        label="重点库",
        source_module="learn",
        default_status="已提炼",
        purpose="Store structured knowledge-cluster Markdown with source citation markers.",
    ),
    LibraryKind(
        id="perspective",
        label="视角库",
        source_module="mine",
        default_status="已解读",
        purpose="Store perspective-tagged interpretation Markdown with source citations.",
    ),
)


WORKSPACE_ENTRIES: tuple[WorkspaceEntry, ...] = (
    WorkspaceEntry(
        id="collect-materials",
        label="Material intake",
        route="/collect",
        shell_section="collect",
        capability_id="capture_materials",
        priority="P0",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="collect-media",
        label="Audio and video intake",
        route="/collect/media",
        shell_section="collect",
        capability_id="capture_materials",
        priority="P0",
        surface="specialized_workspace",
    ),
    WorkspaceEntry(
        id="learn-knowledge",
        label="Knowledge learning",
        route="/learn",
        shell_section="learn",
        capability_id="generate_knowledge",
        priority="P0",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="mine-perspectives",
        label="Perspective mining",
        route="/mine",
        shell_section="mine",
        capability_id="interpret_perspectives",
        priority="P1",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="create-wechat-article",
        label="WeChat article studio",
        route="/create",
        shell_section="create",
        capability_id="create_wechat_article",
        priority="P1",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="library-files",
        label="Knowledge library",
        route="/library",
        shell_section="library",
        capability_id="manage_libraries",
        priority="P2",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="settings-center",
        label="Settings center",
        route="/settings",
        shell_section="settings",
        capability_id="configure_system",
        priority="P3",
        surface="main_workspace",
    ),
    WorkspaceEntry(
        id="docs-help",
        label="Documentation",
        route="/docs",
        shell_section="docs",
        capability_id="read_documentation",
        priority="P3",
        surface="main_workspace",
    ),
)


WORKSPACE_PLACEMENTS: tuple[WorkspacePlacement, ...] = (
    WorkspacePlacement(
        capability_id="capture_materials",
        shell_section="collect",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="read_extract_save_raw_markdown",
    ),
    WorkspacePlacement(
        capability_id="generate_knowledge",
        shell_section="learn",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="raw_to_focus_and_graph",
    ),
    WorkspacePlacement(
        capability_id="organize_network",
        shell_section="learn",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="focus_to_knowledge_graph",
    ),
    WorkspacePlacement(
        capability_id="retrieve_answers",
        shell_section="learn",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="ask_with_sources",
    ),
    WorkspacePlacement(
        capability_id="interpret_perspectives",
        shell_section="mine",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="focus_to_perspective_markdown",
    ),
    WorkspacePlacement(
        capability_id="create_wechat_article",
        shell_section="create",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="quote_libraries_to_wechat_article",
    ),
    WorkspacePlacement(
        capability_id="manage_libraries",
        shell_section="library",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="edit_library_markdown_and_metadata",
    ),
    WorkspacePlacement(
        capability_id="configure_system",
        shell_section="settings",
        primary_region="workspace",
        secondary_region="global_library",
        interaction_stage="configure_and_test",
    ),
    WorkspacePlacement(
        capability_id="read_documentation",
        shell_section="docs",
        primary_region="workspace",
        secondary_region="documentation",
        interaction_stage="read_help_and_troubleshoot",
    ),
)


def section_by_id(section_id: str) -> ShellSection:
    for section in PRIMARY_SECTIONS:
        if section.id == section_id:
            return section
    raise KeyError(section_id)


def placement_for_capability(capability_id: str) -> WorkspacePlacement:
    for placement in WORKSPACE_PLACEMENTS:
        if placement.capability_id == capability_id:
            return placement
    raise KeyError(capability_id)


def entries_for_section(section_id: str) -> tuple[WorkspaceEntry, ...]:
    return tuple(entry for entry in WORKSPACE_ENTRIES if entry.shell_section == section_id)


def entry_by_id(entry_id: str) -> WorkspaceEntry:
    for entry in WORKSPACE_ENTRIES:
        if entry.id == entry_id:
            return entry
    raise KeyError(entry_id)
