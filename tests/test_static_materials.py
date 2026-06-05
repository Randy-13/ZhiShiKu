from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def parse_index():
    return BeautifulSoup((ROOT / "static" / "index.html").read_text(encoding="utf-8"), "html.parser")


def test_collect_stage_models_inputs_as_material_types():
    soup = parse_index()
    material_types = [item["data-material-type"] for item in soup.select("[data-material-type]")]

    assert material_types == ["text", "screenshot", "document", "media", "link"]
    assert soup.select_one(".material-type-card.active")["data-material-type"] == "screenshot"
    assert all(item.name == "button" for item in soup.select("[data-material-type]"))
    assert all(item.get("type") == "button" for item in soup.select("[data-material-type]"))


def test_text_and_link_material_panes_exist():
    soup = parse_index()

    assert soup.find(id="textInputPane")["data-input-pane"] == "text"
    assert soup.find(id="linkInputPane")["data-input-pane"] == "link"
    assert soup.find(id="textMaterialInput") is not None
    assert soup.find(id="linkMaterialInput") is not None
    assert soup.find(id="addTextMaterial") is not None
    assert soup.find(id="addLinkMaterial") is not None


def test_unified_learning_plan_preview_exists():
    soup = parse_index()

    assert soup.find(id="planLearningMaterials") is not None
    assert soup.find(id="unifiedLearningPlan") is not None
    assert soup.find(id="unifiedLearningPlanMeta") is not None
    assert soup.find(id="unifiedLearningPlanList") is not None


def test_material_queue_language_is_available_for_current_queues():
    soup = parse_index()

    assert len(soup.select(".queue-kicker")) >= 2


def test_material_cards_are_wired_in_app_script():
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "materialTypeCards" in script
    assert "function selectMaterialType" in script
    assert 'switchInputTab("text")' in script
    assert 'switchInputTab("screenshots")' in script
    assert 'switchInputTab("files")' in script
    assert 'switchInputTab("link")' in script
    assert "function addTextMaterial" in script
    assert "function addLinkMaterials" in script
    assert "function renderUnifiedLearningPlan" in script
    assert "function materialLearningPlanItems" in script


def test_frontend_loads_v2_contracts_progressively():
    script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "function loadV2Contracts" in script
    assert 'requestJson("/api/v2/app-shell")' in script
    assert 'requestJson("/api/v2/material-types")' in script
    assert 'requestJson("/api/v2/settings/overview")' in script
    assert 'data-contract-loaded", "true"' in script
    assert "function renderSettingsOverviewStatus" in script
