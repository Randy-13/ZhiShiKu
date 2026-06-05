from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_react_collect_workspace_uses_material_specific_interfaces():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    collect_section = source.split("function CollectWorkspace")[1].split("function LearnWorkspace")[0]

    assert 'useState("text")' in collect_section
    assert 'id: "webLink"' in source
    assert "/api/v2/collect/raw-markdown" in source
    assert "/api/v2/collect/inspect-link" in source
    assert "/api/images" in source
    assert "/api/images/paste" in source
    assert "/api/files" in source
    assert "/api/media/upload" in source
    assert "/api/media/resolve-url" in source
    assert "TextCollectPanel" in source
    assert "ScreenshotCollectPanel" in source
    assert "FileCollectPanel" in source
    assert "MediaCollectPanel" in source
    assert "LinkCollectPanel" in source


def test_web_link_queue_inspects_link_before_enqueueing():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    add_link_section = source.split("function addWebLinksToQueue")[1].split("function resolveMediaLink")[0]

    assert "/api/v2/collect/inspect-link" in add_link_section
    assert "link_type" in add_link_section
    assert "access_status" in add_link_section
    assert "extraction_strategy" in source


def test_collect_workspace_has_queue_before_saved_results():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    collect_section = source.split("function CollectWorkspace")[1].split("function LearnWorkspace")[0]

    assert "CollectQueuePanel" in collect_section
    assert "CollectResultList" in collect_section
    assert collect_section.index("CollectQueuePanel") < collect_section.index("CollectResultList")
    assert "读取为原料 Markdown" in source
    assert "待分析队列" in source
    assert "已保存的原料 Markdown 文件" in source


def test_screenshot_collect_splits_paste_from_upload_dropzone():
    source = (FRONTEND / "src" / "main.jsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")
    screenshot_section = source.split("function ScreenshotCollectPanel")[1].split("function FileCollectPanel")[0]

    assert "paste-box" in screenshot_section
    assert "粘贴截图" in screenshot_section
    assert "上传或拖入截图" in screenshot_section
    assert "onPaste={onPaste}" in screenshot_section
    assert "onDrop={handleDrop}" not in screenshot_section
    assert ".screenshot-workbench" in styles
    assert ".paste-box" in styles
