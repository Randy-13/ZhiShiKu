import pytest

from src.shared.app_shell import (
    GLOBAL_LIBRARIES,
    PRIMARY_SECTIONS,
    WORKSPACE_ENTRIES,
    WORKSPACE_PLACEMENTS,
    entries_for_section,
    entry_by_id,
    placement_for_capability,
    section_by_id,
)


def test_primary_sections_match_mature_app_shell_order():
    assert [section.id for section in PRIMARY_SECTIONS] == [
        "collect",
        "learn",
        "mine",
        "create",
        "xhs",
        "library",
        "settings",
        "docs",
    ]


def test_primary_sections_carry_navigation_copy():
    assert section_by_id("xhs").nav_label == "小红书"
    assert section_by_id("xhs").route == "/xhs"
    assert all(section.nav_description for section in PRIMARY_SECTIONS)


def test_input_methods_are_not_primary_sections():
    section_ids = {section.id for section in PRIMARY_SECTIONS}

    assert "screenshot" not in section_ids
    assert "document" not in section_ids
    assert "media" not in section_ids
    assert "link" not in section_ids
    assert "library" in section_ids
    assert "docs" in section_ids


def test_global_libraries_are_right_sidebar_resources_not_primary_sections():
    assert [library.id for library in GLOBAL_LIBRARIES] == ["raw", "focus", "perspective"]
    assert [library.label for library in GLOBAL_LIBRARIES] == ["原料库", "重点库", "视角库"]


def test_workspace_entries_model_mature_route_hierarchy():
    entry_ids = [entry.id for entry in WORKSPACE_ENTRIES]

    assert "collect-media" in entry_ids
    assert entry_by_id("collect-media").route == "/collect/media"
    assert entry_by_id("collect-media").shell_section == "collect"
    assert entry_by_id("create-wechat-article").route == "/create"
    assert entry_by_id("create-xhs-image-text").route == "/xhs"
    assert entry_by_id("create-xhs-image-text").shell_section == "xhs"
    assert entry_by_id("docs-help").route == "/docs"


def test_collect_section_owns_general_and_specialized_intake():
    collect_entries = entries_for_section("collect")

    assert [entry.id for entry in collect_entries] == ["collect-materials", "collect-media"]
    assert all(entry.capability_id == "capture_materials" for entry in collect_entries)


def test_capabilities_have_single_workspace_placement():
    capability_ids = [placement.capability_id for placement in WORKSPACE_PLACEMENTS]

    assert len(capability_ids) == len(set(capability_ids))


def test_generation_lives_in_learn_not_collect():
    placement = placement_for_capability("generate_knowledge")

    assert placement.shell_section == "learn"
    assert placement.interaction_stage == "raw_to_focus_and_graph"


def test_strategy_learning_lives_in_mine():
    placement = placement_for_capability("interpret_perspectives")

    assert placement.shell_section == "mine"


def test_create_section_uses_linear_creation_stage():
    placement = placement_for_capability("create_wechat_article")

    assert placement.shell_section == "create"
    assert placement.interaction_stage == "quote_libraries_to_wechat_article"


def test_xhs_section_uses_dedicated_image_text_stage():
    placement = placement_for_capability("create_xhs_image_text")

    assert placement.shell_section == "xhs"
    assert placement.interaction_stage == "quote_libraries_to_xhs_image_text"


def test_docs_section_uses_read_only_help_stage():
    placement = placement_for_capability("read_documentation")

    assert placement.shell_section == "docs"
    assert placement.interaction_stage == "read_help_and_troubleshoot"


def test_unknown_section_and_capability_raise_key_error():
    with pytest.raises(KeyError):
        section_by_id("unknown")

    with pytest.raises(KeyError):
        placement_for_capability("unknown")

    with pytest.raises(KeyError):
        entry_by_id("unknown")
