import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "workbench"


def test_react_frontend_project_declares_vite_shell():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["build"] == "node scripts/build-served.mjs"
    assert "react" in package["dependencies"]
    assert "vite" in package["dependencies"]
    assert "lucide-react" in package["dependencies"]


def test_react_build_outputs_fastapi_static_entrypoint():
    pointer_name = (FRONTEND / ".served-dist").read_text(encoding="utf-8").strip()
    index_html = (FRONTEND / pointer_name / "index.html").read_text(encoding="utf-8")

    assert '<div id="root"></div>' in index_html
    assert "/frontend/assets/" in index_html


def test_react_shell_uses_workbench_app_with_six_workspaces_and_library_rail():
    source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")

    for workspace_component in [
        "CollectWorkspace",
        "LearnWorkspace",
        "MineWorkspace",
        "CreateWorkspace",
        "LibraryWorkspace",
        "SettingsWorkspace",
    ]:
        assert workspace_component in source

    assert 'const { activeWorkspace, selectWorkspace } = useWorkspaceRoute("collect");' in source
    assert 'const libraryKinds: LibraryKind[] = ["original", "focus", "perspective"];' in source
    assert "KnowledgeLibraryRail" in source


def test_react_library_rail_uses_live_library_api_and_workspace_bucket():
    source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "libraryApi.listLibraryFiles(kind)" in source
    assert "libraryApi.listKnowledge()" in source
    assert 'case "library":' in source
    assert "activeBucket={libraryRailBucket}" in source
    assert "knowledge={libraryRailKnowledge}" in source


def test_react_styles_keep_long_paths_and_cards_wrapped():
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

    assert "overflow-wrap: anywhere" in styles
    assert ".storage-location-row input" in styles
    assert ".trash-file-row em" in styles
    assert ".dependency-path" in styles


def test_react_learn_workspace_uses_real_learning_flow():
    app_source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    flow_source = (FRONTEND / "src" / "hooks" / "useLearningFlow.ts").read_text(encoding="utf-8")

    assert "useLearningFlow" in app_source
    assert "addSelectedOriginalsToLearningQueue" in app_source
    assert "generateKnowledge" in app_source
    assert "commitKnowledgeDraft" in app_source
    assert "collectApi.saveFocusFile" in flow_source
    assert "collectApi.refineKnowledgeCluster" in flow_source


def test_react_mine_workspace_uses_real_perspective_api_flow():
    app_source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    flow_source = (FRONTEND / "src" / "hooks" / "useMineFlow.ts").read_text(encoding="utf-8")

    assert "useMineFlow" in app_source
    assert "savePerspectiveProfile" in app_source
    assert "deletePerspectiveProfile" in app_source
    assert "runPerspectiveInterpretation" in app_source
    assert "mineApi.listPerspectiveProfiles()" in flow_source
    assert "mineApi.interpretPerspective(" in flow_source
    assert "mineApi.savePerspectiveFile(" in flow_source


def test_react_settings_center_uses_real_settings_and_api_forms():
    source = (FRONTEND / "src" / "workspaces" / "SettingsWorkspace.tsx").read_text(encoding="utf-8")

    assert "settingsApi.workbenchSettings()" in source
    assert "settingsApi.mediaDependencies()" in source
    assert "settingsApi.apiSettings()" in source
    assert "settingsApi.imageApiSettings()" in source
    assert "settingsApi.asrSettings()" in source
    assert '"chat" | "image" | "audio"' in source
    assert "DependencyStatusModal" in source
    assert "Audio ASR" in source


def test_react_workspaces_keep_module_boundaries_visible():
    app_source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    create_source = (FRONTEND / "src" / "workspaces" / "CreateWorkspace.tsx").read_text(encoding="utf-8")
    settings_source = (FRONTEND / "src" / "workspaces" / "SettingsWorkspace.tsx").read_text(encoding="utf-8")

    assert "CollectWorkspace" in app_source
    assert "LearnWorkspace" in app_source
    assert "MineWorkspace" in app_source
    assert "CreateWorkspace" in app_source
    assert "LibraryWorkspace" in app_source
    assert "SettingsWorkspace" in app_source

    assert "imageStylePresets" in create_source
    assert "designStrategyPresets" in create_source
    assert "onConfirmDesign" in create_source
    assert "publish_check" in create_source

    assert "DependencyStatusModal" in settings_source
    assert "TrashModal" in settings_source
    assert "ApiSettingsModal" in settings_source
