from pathlib import Path

from bs4 import BeautifulSoup

from src.shared.app_shell import PRIMARY_SECTIONS


ROOT = Path(__file__).resolve().parents[1]


def primary_nav_items(page: str) -> list[dict[str, str]]:
    soup = BeautifulSoup((ROOT / "static" / page).read_text(encoding="utf-8"), "html.parser")
    return [
        {
            "section": link.get("data-shell-section", ""),
            "href": link["href"],
            "label": link.select_one("span").get_text(strip=True),
            "description": link.select_one("small").get_text(strip=True),
            "active": "active" in (link.get("class") or []),
        }
        for link in soup.select(".app-rail nav:first-of-type .app-nav-item")
    ]


def test_specialized_pages_share_primary_app_navigation():
    expected = [
        {
            "section": section.id,
            "href": section.route,
            "label": section.nav_label,
            "description": section.nav_description,
        }
        for section in PRIMARY_SECTIONS
    ]

    for page in ["settings.html", "media.html", "writer.html"]:
        actual = primary_nav_items(page)
        assert [{key: item[key] for key in ["section", "href", "label", "description"]} for item in actual] == expected


def test_specialized_pages_mark_only_their_current_section_active():
    active_by_page = {
        "settings.html": "settings",
        "media.html": "collect",
        "writer.html": "create",
    }

    for page, active_section in active_by_page.items():
        active_items = [item for item in primary_nav_items(page) if item["active"]]
        assert [item["section"] for item in active_items] == [active_section]
