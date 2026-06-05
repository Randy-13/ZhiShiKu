from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "frontend" / "workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_collect_workspace_exposes_five_material_input_modes():
    source = read(WORKBENCH / "src" / "workspaces" / "CollectWorkspace.tsx")

    assert 'const [activePane, setActivePane] = useState<MaterialType>("text")' in source
    assert '{ id: "text", labelKey: "collect.type.text"' in source
    assert '{ id: "image", labelKey: "collect.type.image"' in source
    assert '{ id: "file", labelKey: "collect.type.file"' in source
    assert '{ id: "media", labelKey: "collect.type.media"' in source
    assert '{ id: "link", labelKey: "collect.type.link"' in source


def test_collect_workspace_routes_each_material_type_to_real_handlers():
    source = read(WORKBENCH / "src" / "workspaces" / "CollectWorkspace.tsx")
    api_source = read(WORKBENCH / "src" / "api.ts")
    app_source = read(WORKBENCH / "src" / "App.tsx")

    assert "onCreateMaterial({ type: \"text\"" in source
    assert 'onDrop={(event) => handleDrop(event, "image")}' in source
    assert 'onDrop={(event) => handleDrop(event, "file")}' in source
    assert 'onDrop={(event) => handleDrop(event, "media")}' in source
    assert "onPaste={handlePaste}" in source
    assert "onResolveLinks(urls)" in source
    assert "const resolveLinksV2 = useCallback(" in app_source
    assert "const inspected = await api.inspectLink(url);" in app_source
    assert "/api/images" in api_source
    assert "/api/images/paste" in api_source
    assert "/api/files" in api_source
    assert "/api/media/upload" in api_source
    assert "/api/media/resolve-url" in api_source
    assert "/api/v2/collect/inspect-link" in api_source


def test_collect_workspace_has_queue_generate_original_and_preview_flow():
    source = read(WORKBENCH / "src" / "workspaces" / "CollectWorkspace.tsx")

    assert 't("collect.queue")' in source
    assert 't("collect.generateOriginal")' in source
    assert "onGenerateReadableDraft(selectedIds)" in source
    assert 't("collect.preview")' in source
    assert 't("collect.addToOriginalLibrary")' in source
    assert "onSaveReadableDraft" in source
    assert source.index('t("collect.queue")') < source.index('t("collect.preview")')


def test_collect_workspace_preview_editor_supports_title_note_and_body():
    source = read(WORKBENCH / "src" / "workspaces" / "CollectWorkspace.tsx")

    assert 't("collect.draft.title")' in source
    assert 't("collect.draft.note")' in source
    assert 't("collect.draft.body")' in source
    assert "onUpdateReadableDraft({ ...readableDraft, title: event.target.value })" in source
    assert "onUpdateReadableDraft({ ...readableDraft, note: event.target.value })" in source
    assert "onUpdateReadableDraft({ ...readableDraft, body: event.target.value })" in source


def test_collect_app_flow_generates_readable_draft_then_saves_to_originals():
    source = read(WORKBENCH / "src" / "App.tsx")
    api_source = read(WORKBENCH / "src" / "api.ts")

    assert "const [collectDraft, setCollectDraft] = useState<ReadableDraftInput>()" in source
    assert "const [isCollectingReadable, setIsCollectingReadable] = useState(false)" in source
    assert "const [isSavingRawDraft, setIsSavingRawDraft] = useState(false)" in source
    assert "const generateCollectReadableDraft = useCallback(" in source
    assert "const saveCollectDraftToOriginalLibrary = useCallback(async () => {" in source
    assert "const draft = await api.createReadableDraft(selectedItems, textExtractionMode);" in source
    assert "const item = await api.saveRawDraft(collectDraft);" in source
    assert "setCollectDraft(undefined);" in source
    assert "await refreshLibraries();" in source
    assert "createReadableDraft(materials: SourceMaterial[], parserMode: TextExtractionMode)" in api_source
    assert "saveRawDraft(draft: ReadableDraftInput)" in api_source
    assert '"/api/v2/collect/readable-draft"' in api_source


def test_collect_raw_draft_save_prefers_raw_file_and_falls_back_to_raw_markdown():
    api_source = read(WORKBENCH / "src" / "api.ts")

    assert '"/api/v2/collect/raw-file"' in api_source
    assert 'if (!message.includes("Not Found") && !message.includes("404")) throw error;' in api_source
    assert "const fallback = await this.createRawLibraryFile(" in api_source
