from __future__ import annotations

from fastapi import FastAPI

import app as legacy_app
from src.api_v2 import router as api_v2_router
from src.pages import router as pages_router


def create_app() -> FastAPI:
    """Return the current FastAPI app through the new architecture entrypoint."""
    app = legacy_app.app
    if not getattr(app.state, "api_v2_contracts_mounted", False):
        app.include_router(api_v2_router)
        app.include_router(pages_router)
        app.state.api_v2_contracts_mounted = True
    return app
