from bs4 import BeautifulSoup

from src.shared.app_shell import PRIMARY_SECTIONS
from src.shared.navigation import render_app_rail, replace_active_shell_section, replace_app_rail


def test_render_app_rail_uses_primary_sections():
    soup = BeautifulSoup(render_app_rail("create"), "html.parser")
    items = soup.select(".app-nav-item")

    assert [item["data-shell-section"] for item in items] == [section.id for section in PRIMARY_SECTIONS]
    assert [item["href"] for item in items] == [section.route for section in PRIMARY_SECTIONS]
    assert [item.select_one("span").get_text(strip=True) for item in items] == [section.nav_label for section in PRIMARY_SECTIONS]
    assert [item.select_one("small").get_text(strip=True) for item in items] == [section.nav_description for section in PRIMARY_SECTIONS]
    assert [item["data-shell-section"] for item in items if "active" in item.get("class", [])] == ["create"]


def test_replace_app_rail_replaces_existing_shell_once():
    page_html = '<body><main><aside class="app-rail"><a href="/old">Old</a></aside><section>Body</section></main></body>'

    updated = replace_app_rail(page_html, "settings")

    assert "/old" not in updated
    assert updated.count('class="app-rail"') == 1
    assert 'data-shell-section="settings"' in updated
    assert 'data-active-shell-section="settings"' in updated


def test_replace_active_shell_section_updates_existing_body_state():
    page_html = '<body class="page" data-active-shell-section="collect"><main>Body</main></body>'

    updated = replace_active_shell_section(page_html, "mine")

    assert '<body class="page" data-active-shell-section="mine">' in updated
    assert "collect" not in updated
