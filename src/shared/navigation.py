from __future__ import annotations

import html
import re

from src.shared.app_shell import PRIMARY_SECTIONS


APP_RAIL_PATTERN = re.compile(r'<aside\b[^>]*class="app-rail"[\s\S]*?</aside>')
BODY_PATTERN = re.compile(r"<body(?P<attrs>[^>]*)>")


def render_app_rail(active_section: str) -> str:
    nav_items = "\n".join(_render_nav_item(section, active_section) for section in PRIMARY_SECTIONS)
    return f"""<aside class="app-rail" aria-label="知识酷主导航">
        <div class="app-brand">
          <strong>知识酷</strong>
          <span>Research OS</span>
        </div>
        <nav class="app-nav" aria-label="工作区">
{nav_items}
        </nav>
      </aside>"""


def replace_app_rail(page_html: str, active_section: str) -> str:
    rendered = render_app_rail(active_section)
    updated, count = APP_RAIL_PATTERN.subn(rendered, page_html, count=1)
    if count != 1:
        raise ValueError("Expected exactly one app rail in page HTML")
    return replace_active_shell_section(updated, active_section)


def replace_active_shell_section(page_html: str, active_section: str) -> str:
    def replace_body(match: re.Match[str]) -> str:
        attrs = re.sub(r'\sdata-active-shell-section="[^"]*"', "", match.group("attrs"))
        return f'<body{attrs} data-active-shell-section="{html.escape(active_section)}">'

    updated, count = BODY_PATTERN.subn(replace_body, page_html, count=1)
    if count != 1:
        raise ValueError("Expected exactly one body tag in page HTML")
    return updated


def _render_nav_item(section, active_section: str) -> str:
    class_name = "app-nav-item active" if section.id == active_section else "app-nav-item"
    return (
        f'          <a class="{class_name}" data-shell-section="{html.escape(section.id)}" '
        f'href="{html.escape(section.route)}"><span>{html.escape(section.nav_label)}</span>'
        f"<small>{html.escape(section.nav_description)}</small></a>"
    )
