from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def parse_writer():
    return BeautifulSoup((ROOT / "static" / "writer.html").read_text(encoding="utf-8"), "html.parser")


def test_writer_page_has_mature_app_shell():
    soup = parse_writer()

    assert soup.select_one(".writer-page .app-rail") is not None
    assert soup.select_one(".writer-workspace-shell") is not None
    assert soup.select_one('.app-nav-item.active[href="/create"]') is not None


def test_writer_existing_workflow_controls_are_preserved():
    soup = parse_writer()
    required_ids = [
        "openImageApiSettings",
        "generateWriterTopics",
        "generateArticle",
        "articleMarkdown",
        "suggestImages",
        "formatArticle",
        "publishDraft",
    ]

    for element_id in required_ids:
        assert soup.find(id=element_id) is not None
