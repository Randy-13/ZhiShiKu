from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_ROOT = ROOT / "frontend" / "workbench"
WORKBENCH_DIST = WORKBENCH_ROOT / "dist"
WORKBENCH_DIST_POINTER = WORKBENCH_ROOT / ".served-dist"
LEGACY_FRONTEND_DIST = ROOT / "frontend" / "dist"
FRONTEND_DIST = WORKBENCH_DIST if WORKBENCH_DIST.exists() else LEGACY_FRONTEND_DIST


def current_frontend_dist() -> Path:
    pointer = _pointer_dist()
    if pointer:
        return pointer
    if WORKBENCH_DIST.exists():
        return WORKBENCH_DIST
    return LEGACY_FRONTEND_DIST


def current_frontend_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=404, detail="Frontend asset not found")
    root = current_frontend_dist().resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=404, detail="Frontend asset not found")
    return path


def frontend_file_response(asset_path: str) -> FileResponse:
    path = current_frontend_path(asset_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Frontend asset not found")
    return FileResponse(path)


def react_app_response() -> HTMLResponse:
    index = current_frontend_path("index.html")
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


def _pointer_dist() -> Path | None:
    if not WORKBENCH_DIST_POINTER.exists():
        return None
    name = WORKBENCH_DIST_POINTER.read_text(encoding="utf-8", errors="ignore").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None
    path = (WORKBENCH_ROOT / name).resolve()
    try:
        path.relative_to(WORKBENCH_ROOT.resolve())
    except ValueError:
        return None
    if (path / "index.html").exists():
        return path
    return None
