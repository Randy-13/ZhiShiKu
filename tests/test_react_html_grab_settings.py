from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "workbench"


def test_settings_workspace_wires_html_grab_checks():
    source = (FRONTEND / "src" / "workspaces" / "SettingsWorkspace.tsx").read_text(encoding="utf-8")
    api_source = (FRONTEND / "src" / "apiSettings.ts").read_text(encoding="utf-8")

    assert "settingsApi.htmlGrabCheck()" in source
    assert "settingsApi.htmlGrabAuthorize()" in source
    assert "HTML grabbing" in source
    assert "Open Edge session" in source
    assert "Web article extraction status" in source
    assert "Opened Edge dev session window." in source
    assert "htmlGrabStatus" in source
    assert "onRefreshHtmlGrab" in source
    assert "async htmlGrabCheck" in api_source
    assert "async htmlGrabAuthorize" in api_source
