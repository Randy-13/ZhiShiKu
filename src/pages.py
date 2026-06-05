from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.shared.frontend_app import react_app_response
from src.shared.navigation import replace_app_rail


ROOT = Path(__file__).resolve().parents[1]
router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
    return react_app_response()


@router.get("/collect/media", response_class=HTMLResponse)
def collect_media_page() -> HTMLResponse:
    return _static_page("media.html", active_section="collect")


@router.get("/create", response_class=HTMLResponse)
def create_page() -> HTMLResponse:
    return react_app_response()


@router.get("/collect", response_class=HTMLResponse)
@router.get("/learn", response_class=HTMLResponse)
@router.get("/mine", response_class=HTMLResponse)
def app_workspace_alias(request: Request) -> HTMLResponse:
    return react_app_response()


def _static_page(filename: str, active_section: str) -> HTMLResponse:
    page_html = (ROOT / "static" / filename).read_text(encoding="utf-8")
    return HTMLResponse(replace_app_rail(page_html, active_section))
