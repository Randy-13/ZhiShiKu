from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response


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


def current_frontend_asset_path(relative_path: str) -> Path:
    path = current_frontend_path(relative_path)
    if path.exists() and path.is_file():
        return path
    if not relative_path.startswith("assets/"):
        return path
    fallback = _served_asset_fallback(Path(relative_path).name)
    return fallback or path


def frontend_file_response(asset_path: str) -> FileResponse | Response:
    path = current_frontend_asset_path(asset_path)
    if not path.exists() or not path.is_file():
        stale_module = _stale_frontend_module_response(asset_path)
        if stale_module:
            return stale_module
        raise HTTPException(status_code=404, detail="Frontend asset not found")
    return FileResponse(path, headers=_frontend_asset_headers(path))


def react_app_response() -> HTMLResponse:
    index = current_frontend_path("index.html")
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"), headers=_react_app_headers())
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
        ,
        headers=_react_app_headers(),
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


def _served_asset_fallback(filename: str) -> Path | None:
    if not filename:
        return None
    current_root = current_frontend_dist().resolve()
    for dist in sorted(WORKBENCH_ROOT.glob("dist-served-*"), reverse=True):
        try:
            if dist.resolve() == current_root:
                continue
            dist.relative_to(WORKBENCH_ROOT)
        except ValueError:
            continue
        candidate = dist / "assets" / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _react_app_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
    }


def _frontend_asset_headers(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".html":
        return _react_app_headers()
    return {"Cache-Control": "public, max-age=31536000, immutable"}


def _stale_frontend_module_response(asset_path: str) -> Response | None:
    name = Path(asset_path).name
    if not asset_path.startswith("assets/") or not name.startswith("index-") or not name.endswith(".js"):
        return None
    script = """
const url = new URL(window.location.href);
url.searchParams.set("frontend_ts", Date.now().toString());
window.location.replace(url.toString());
"""
    return Response(
        script.strip() + "\n",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )
