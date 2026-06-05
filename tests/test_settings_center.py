from pathlib import Path

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from src.main import create_app


ROOT = Path(__file__).resolve().parents[1]


def assert_react_app_shell(response):
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
    assert '/frontend/assets/' in response.text


def test_settings_page_route_is_served_by_new_app_factory():
    client = TestClient(create_app())

    response = client.get("/settings")

    assert_react_app_shell(response)


def test_mature_workspace_alias_routes_are_served_by_new_app_factory():
    client = TestClient(create_app())

    for route in ["/collect", "/learn", "/mine", "/create", "/settings"]:
        response = client.get(route)
        assert_react_app_shell(response)


def test_collect_media_route_is_served_as_collection_subpage():
    client = TestClient(create_app())

    response = client.get("/collect/media")

    assert response.status_code == 200
    assert "media-shell" in response.text
    assert "transcribeMedia" in response.text


def test_create_route_is_served_as_creation_workspace():
    client = TestClient(create_app())

    response = client.get("/create")

    assert_react_app_shell(response)


def test_main_workspace_routes_are_react_app_routes_not_server_rendered_rails():
    client = TestClient(create_app())

    for route in ["/collect", "/learn", "/mine", "/create", "/settings"]:
        soup = BeautifulSoup(client.get(route).text, "html.parser")
        assert soup.find(id="root") is not None
        assert soup.select(".app-rail .app-nav-item") == []


def test_legacy_page_routes_reuse_server_rendered_app_rail():
    client = TestClient(create_app())
    expectations = {
        "/media": "collect",
        "/writer": "create",
    }

    for route, active_section in expectations.items():
        soup = BeautifulSoup(client.get(route).text, "html.parser")
        assert soup.body["data-active-shell-section"] == active_section
        active_items = soup.select(".app-rail .app-nav-item.active")
        assert [item["data-shell-section"] for item in active_items] == [active_section]
        assert [item["data-shell-section"] for item in soup.select(".app-rail .app-nav-item")] == [
            "collect",
            "learn",
            "mine",
            "create",
            "settings",
        ]


def test_settings_page_has_app_shell_and_overview_targets():
    soup = BeautifulSoup((ROOT / "static" / "settings.html").read_text(encoding="utf-8"), "html.parser")

    assert soup.select_one(".settings-shell") is not None
    assert soup.select_one(".app-rail") is not None
    assert soup.find(id="settingsOverviewMeta") is not None
    assert soup.find(id="settingsOverviewList") is not None
    assert soup.select_one('script[src^="/static/settings.js"]') is not None


def test_settings_page_has_edit_surface_links():
    soup = BeautifulSoup((ROOT / "static" / "settings.html").read_text(encoding="utf-8"), "html.parser")
    links = {link.get_text(" ", strip=True): link["href"] for link in soup.select(".settings-action-card")}

    assert any("LLM API" in label and href == "/#openApiSettings" for label, href in links.items())
    assert any("ASR" in label and href == "/collect/media" for label, href in links.items())
    assert any("图片 API" in label and href == "/create" for label, href in links.items())


def test_settings_shell_uses_mature_workspace_routes():
    soup = BeautifulSoup((ROOT / "static" / "settings.html").read_text(encoding="utf-8"), "html.parser")
    nav_links = {link.get_text(" ", strip=True): link["href"] for link in soup.select(".app-rail .app-nav-item")}

    assert any(label.startswith("收集") and href == "/collect" for label, href in nav_links.items())
    assert any(label.startswith("学习") and href == "/learn" for label, href in nav_links.items())
    assert any(label.startswith("挖掘") and href == "/mine" for label, href in nav_links.items())


def test_settings_script_reads_v2_overview():
    script = (ROOT / "static" / "settings.js").read_text(encoding="utf-8")

    assert 'requestJson("/api/v2/settings/overview")' in script
    assert "function renderSettingsOverview" in script
