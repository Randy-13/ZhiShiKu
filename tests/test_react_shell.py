import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_react_frontend_project_declares_vite_shell():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["build"] == "vite build"
    assert "react" in package["dependencies"]
    assert "vite" in package["dependencies"]
    assert "lucide-react" in package["dependencies"]


def test_react_build_outputs_fastapi_static_entrypoint():
    index_html = (FRONTEND / "dist" / "index.html").read_text(encoding="utf-8")

    assert '<div id="root"></div>' in index_html
    assert "/frontend/assets/" in index_html


def test_react_shell_has_only_five_primary_modules_and_global_library():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")

    for module_id in ["collect", "learn", "mine", "create", "settings"]:
        assert f'id: "{module_id}"' in source

    assert 'id: "library"' not in source
    assert "GlobalLibraryPanel" in source
    assert "原料库" in source
    assert "重点库" in source
    assert "视角库" in source


def test_react_global_library_fetches_live_library_files():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    panel_section = source.split("function GlobalLibraryPanel")[1].split("function FileStub")[0]

    assert "/api/v2/libraries/" in panel_section
    assert "research-os:library-updated" in source
    assert "setInterval" in panel_section
    assert "sampleFiles[activeLibrary]" not in panel_section


def test_react_global_library_cards_do_not_overflow_side_panel():
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

    assert "overflow-x: hidden" in styles
    assert ".file-card strong" in styles
    assert "overflow-wrap: anywhere" in styles
    assert ".file-path" in styles


def test_react_learn_workspace_uses_raw_library_and_focus_generation_api():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    learn_section = source.split("function LearnWorkspace")[1].split("function MineWorkspace")[0]

    assert "/api/v2/libraries/raw/files?pending_focus=true" in learn_section
    assert "/api/v2/learn/refine-knowledge-cluster" in learn_section
    assert "/api/v2/learn/focus-file" in learn_section
    assert "LibrarySelectionList" in learn_section
    assert "提炼" in learn_section
    assert "保存" in learn_section
    assert "research-os:library-updated" in learn_section
    assert "learn-panel" in learn_section


def test_react_mine_workspace_uses_global_library_queue_and_perspective_api():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    panel_section = source.split("function GlobalLibraryPanel")[1].split("function FileStub")[0]
    mine_section = source.split("function MineWorkspace")[1].split("function CreateWorkspace")[0]

    assert "research-os:mine-add-sources" in panel_section
    assert "加入待解读队列" in panel_section
    assert "/api/v2/mine/perspectives" in mine_section
    assert "/api/v2/mine/interpret" in mine_section
    assert "/api/v2/mine/perspective-file" in mine_section
    assert "savePerspectiveProfile" in mine_section
    assert "deletePerspectiveProfile" in mine_section
    assert "复制为自定义" in mine_section
    assert "draftPerspective.focus_dimensions" in mine_section
    assert "draftPerspective.analysis_questions" in mine_section
    assert "原料库或重点库" in mine_section


def test_react_settings_center_uses_real_settings_forms_and_v2_api():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    settings_section = source.split("function SettingsWorkspace")[1].split("function GlobalLibraryPanel")[0]

    assert "网页基本设置" in settings_section
    assert "模型配置" in settings_section
    assert "ASR 配置" in settings_section
    assert "API 配置" in settings_section
    assert "/api/v2/settings/web" in settings_section
    assert "/api/v2/settings/api" in settings_section
    assert "/api/v2/settings/asr" in settings_section
    assert "WebSettingsForm" in settings_section
    assert "ModelSettingsPanel" in settings_section
    assert "ApiSettingsForm" in source
    assert "AsrSettingsForm" in source


def test_react_workspaces_keep_module_boundaries_visible():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")

    collect_section = source.split("function CollectWorkspace")[1].split("function LearnWorkspace")[0]
    learn_section = source.split("function LearnWorkspace")[1].split("function MineWorkspace")[0]
    mine_section = source.split("function MineWorkspace")[1].split("function CreateWorkspace")[0]
    create_section = source.split("function CreateWorkspace")[1].split("function SettingsWorkspace")[0]
    settings_section = source.split("function SettingsWorkspace")[1]

    assert "文本" in collect_section
    assert "截图" in collect_section
    assert "文档" in collect_section
    assert "音视频" in collect_section
    assert "网页链接" in collect_section
    assert "提炼" not in collect_section
    assert "创作" not in collect_section

    assert "核心知识簇" in learn_section
    assert "知识关系网" in learn_section
    assert "知识拉取" in learn_section

    assert "视角管理" in mine_section
    assert "视角库" in mine_section
    assert "解读结果" in mine_section

    assert "文章项目" in create_section
    assert "小红书图文" in create_section
    assert "短视频脚本" in create_section
    assert "长视频脚本" in create_section

    assert "模型配置" in settings_section
    assert "ASR" in settings_section
    assert "网页基本设置" in settings_section
    assert "API 配置" in settings_section
