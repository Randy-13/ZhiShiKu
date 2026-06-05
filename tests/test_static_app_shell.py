from pathlib import Path

from bs4 import BeautifulSoup

from src.shared.app_shell import PRIMARY_SECTIONS


ROOT = Path(__file__).resolve().parents[1]


def parse_index():
    return BeautifulSoup((ROOT / "static" / "index.html").read_text(encoding="utf-8"), "html.parser")


def test_index_has_mature_app_shell_regions():
    soup = parse_index()

    assert soup.select_one(".app-rail") is not None
    assert soup.select_one(".workspace") is not None
    assert soup.select_one(".sidebar") is not None
    assert soup.select_one(".context-label") is not None
    assert soup.body["data-active-shell-section"] == "collect"


def test_app_rail_uses_product_level_navigation_not_input_types():
    soup = parse_index()
    labels = [item.select_one("span").get_text(strip=True) for item in soup.select(".app-rail nav:first-of-type .app-nav-item")]

    assert labels == [section.nav_label for section in PRIMARY_SECTIONS]
    assert not any(label in {"截图", "文档", "音视频", "链接"} for label in labels)


def test_existing_business_control_ids_are_preserved():
    soup = parse_index()
    required_ids = [
        "openApiSettings",
        "openGlobalSettings",
        "settingsOverviewStatus",
        "refineModeTab",
        "miningModeTab",
        "screenshotInputTab",
        "fileInputTab",
        "mediaInputTab",
        "generateKnowledge",
        "knowledgePanel",
        "learnKnowledgeWorkspace",
        "graphCanvas",
        "retrievalPanel",
        "createWorkspace",
        "openLegacyWriterTool",
    ]

    for element_id in required_ids:
        assert soup.find(id=element_id) is not None


def test_global_settings_entry_points_to_settings_center():
    soup = parse_index()

    assert soup.find(id="openGlobalSettings").name == "a"
    assert soup.find(id="openGlobalSettings")["href"] == "/settings"
    assert soup.select_one("#openGlobalSettings[data-shell-section='settings']") is not None


def test_app_rail_has_no_duplicate_object_or_settings_entries():
    soup = parse_index()

    assert soup.select_one(".app-rail .secondary-nav") is None
    assert len(soup.select(".app-rail .app-nav-item[href='/settings']")) == 1
    assert soup.select_one(".app-rail .app-nav-item[href='/library']") is None
    assert all(link.get_text(" ", strip=True) not in {"知识库", "知识网络", "知识问答"} for link in soup.select(".app-rail .app-nav-item"))


def test_right_sidebar_is_global_three_library_panel():
    soup = parse_index()
    library_tabs = soup.select(".sidebar .global-library-tabs .library-tab")

    assert soup.select_one(".context-label strong").get_text(strip=True) == "全局库"
    assert [tab.get_text(strip=True) for tab in library_tabs] == ["原料库", "重点库", "视角库"]
    assert [tab["data-library-kind"] for tab in library_tabs] == ["raw", "focus", "perspective"]
    assert soup.find(id="globalLibraryStatus") is not None


def test_learning_workspace_contains_graph_and_retrieval():
    soup = parse_index()

    assert soup.select_one("#learnKnowledgeWorkspace.viewer") is not None
    assert soup.find(id="graphCanvas") is not None
    assert soup.find(id="retrievalPanel") is not None


def test_primary_shell_nav_uses_mature_routes():
    soup = parse_index()
    links = {item["data-shell-section"]: item["href"] for item in soup.select(".app-rail nav:first-of-type [data-shell-section]")}

    assert links == {section.id: section.route for section in PRIMARY_SECTIONS}
    assert "library" not in links


def test_app_script_activates_shell_section_from_route():
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "function shellSectionFromPath" in script
    assert "function activateShellSection" in script
    assert "document.body.dataset.activeShellSection = section" in script
    assert "switchPrimaryMode(\"mining\")" in script
    assert "setActiveGlobalLibrary" in script
    assert '["collect", "learn", "mine", "create", "settings"]' in script


def test_create_workspace_integrates_article_workflow_entry():
    soup = parse_index()
    create_workspace = soup.find(id="createWorkspace")

    assert create_workspace is not None
    assert [card.get_text(" ", strip=True).split()[0] for card in create_workspace.select(".creation-type-card")] == [
        "文章",
        "小红书图文",
        "短视频脚本",
        "长视频脚本",
    ]
    assert create_workspace.find(id="openLegacyWriterTool") is not None


def test_css_hides_non_current_workspace_windows():
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

    assert 'body[data-active-shell-section="mine"] .learn-knowledge-workspace' in css
    assert 'body[data-active-shell-section="learn"] .learn-knowledge-workspace' in css
    assert ".primary-mode-tabs {\n  display: none;" in css


def test_media_entry_uses_collect_subroute():
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'function workspaceEntryRoute' in script
    assert 'navigateToWorkspaceEntry("collect-media", "/collect/media")' in script
    assert 'window.location.href = "/media";' not in script


def test_collect_and_learn_stages_are_explicit_in_refine_workspace():
    soup = parse_index()
    refine = soup.find(id="refineWorkspace")
    stage_text = refine.get_text(" ", strip=True)

    assert "01 收集" in stage_text
    assert "02 学习" in stage_text
