from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "frontend" / "workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_collect_readable_draft_always_uses_v2_backend_api():
    api_source = read(WORKBENCH / "src" / "apiCollect.ts")

    assert '"/api/v2/collect/readable-draft"' in api_source
    assert 'material.type === "text" || material.type === "link" || typeof material.backendId === "number"' in api_source
    assert 'content: material.type === "text" ? material.source : ""' in api_source
    assert "localReadableDocument" not in api_source
    assert '"/api/materials/readable-document"' in api_source


def test_collect_hook_calls_unified_collect_api_for_drafts():
    hook_source = read(WORKBENCH / "src" / "hooks" / "useCollectFlow.ts")

    assert "await collectApi.createReadableDraft(selectedItems, textExtractionMode)" in hook_source
    assert "await collectApi.createReadableDraft([item], parserMode)" in hook_source
    assert "collectApi.saveRawDraft(collectDraft)" in hook_source
