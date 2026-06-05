from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def parse_media():
    return BeautifulSoup((ROOT / "static" / "media.html").read_text(encoding="utf-8"), "html.parser")


def test_media_page_has_mature_app_shell():
    soup = parse_media()

    assert soup.select_one(".media-shell .app-rail") is not None
    assert soup.select_one(".media-workspace-shell") is not None
    assert soup.select_one('.app-nav-item.active[href="/collect"]') is not None


def test_media_existing_controls_are_preserved():
    soup = parse_media()
    required_ids = [
        "openAsrSettings",
        "urlInput",
        "resolveUrls",
        "mediaInput",
        "transcribeMedia",
        "planMedia",
        "generateKnowledge",
    ]

    for element_id in required_ids:
        assert soup.find(id=element_id) is not None


def test_media_shell_css_has_mobile_layout():
    css = (ROOT / "static" / "media.css").read_text(encoding="utf-8")

    assert "@media (max-width: 900px)" in css
    assert "grid-template-columns: 1fr;" in css
    assert ".app-rail" in css
    assert "position: static;" in css
