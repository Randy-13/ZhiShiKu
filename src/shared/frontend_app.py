from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_DIST = ROOT / "frontend" / "workbench" / "dist"
LEGACY_FRONTEND_DIST = ROOT / "frontend" / "dist"
FRONTEND_DIST = WORKBENCH_DIST if WORKBENCH_DIST.exists() else LEGACY_FRONTEND_DIST


def react_app_response() -> HTMLResponse:
    index = WORKBENCH_DIST / "index.html"
    if not index.exists():
        index = LEGACY_FRONTEND_DIST / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse(
        """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>知识酷</title>
  </head>
  <body>
    <div id="root">React app has not been built. Run npm.cmd run build in frontend/workbench/.</div>
  </body>
</html>"""
    )
