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
    api_source = read(WORKBENCH / "src" / "apiCollect.ts")
    hook_source = read(WORKBENCH / "src" / "hooks" / "useCollectFlow.ts")

    assert 'onCreateMaterial({ type: "text"' in source
    assert 'onDrop={(event) => handleDrop(event, "image")}' in source
    assert 'onDrop={(event) => handleDrop(event, "file")}' in source
    assert 'onDrop={(event) => handleDrop(event, "media")}' in source
    assert "onPaste={handlePaste}" in source
    assert "onResolveLinks(urls)" in source
    assert "const inspected = await collectApi.inspectLink(url);" in hook_source
    assert "/api/images" in api_source
    assert "/api/images/paste" in api_source
    assert "/api/files" in api_source
    assert "/api/media/upload" in api_source
    assert "/api/media/resolve-url" in api_source
    assert "/api/v2/collect/inspect-link" in api_source


def test_collect_workspace_routes_url_only_text_to_link_resolution():
    source = read(WORKBENCH / "src" / "workspaces" / "CollectWorkspace.tsx")
    api_source = read(WORKBENCH / "src" / "apiCollect.ts")

    assert "const urls = urlsFromUrlOnlyText(value);" in source
    assert "onResolveLinks(urls);" in source
    assert "function urlsFromUrlOnlyText" in source
    assert "materials = await this.normalizeUrlTextMaterials(materials);" in api_source
    assert "async normalizeUrlTextMaterials" in api_source
    assert "looksLikeMediaUrl(url)" in api_source
    assert "const resolved = await this.resolveMediaUrl(url);" in api_source


def test_collect_queue_surfaces_link_strategy_and_access_metadata():
    source = read(WORKBENCH / "src" / "components" / "ObjectList.tsx")
    i18n_source = read(WORKBENCH / "src" / "i18n.ts")

    assert "buildLinkMeta(item, t)" in source
    assert 't("collect.meta.strategy")' in source
    assert 't("collect.meta.access")' in source
    assert "item.extractionStrategy" in source
    assert "item.accessStatus" in source
    assert '"collect.strategy.agentReach"' in i18n_source
    assert '"collect.strategy.staticFetch"' in i18n_source


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
    source = read(WORKBENCH / "src" / "hooks" / "useCollectFlow.ts")
    api_source = read(WORKBENCH / "src" / "apiCollect.ts")

    assert "const [collectDraft, setCollectDraft] = useState<ReadableDraftInput>()" in source
    assert "const [isCollectingReadable, setIsCollectingReadable] = useState(false)" in source
    assert "const [isSavingRawDraft, setIsSavingRawDraft] = useState(false)" in source
    assert "const generateCollectReadableDraft = useCallback(" in source
    assert "const saveCollectDraftToOriginalLibrary = useCallback(async () => {" in source
    assert "await collectApi.createReadableDraft(selectedItems, textExtractionMode)" in source
    assert "const item = await collectApi.saveRawDraft(collectDraft);" in source
    assert "setCollectDraft(undefined);" in source
    assert "await refreshLibraries();" in source
    assert "createReadableDraft(materials: SourceMaterial[], parserMode: TextExtractionMode)" in api_source
    assert "saveRawDraft(draft: ReadableDraftInput)" in api_source
    assert '"/api/v2/collect/readable-draft"' in api_source
    assert "localReadableDocument" not in api_source


def test_collect_raw_draft_save_prefers_raw_file_and_falls_back_to_raw_markdown():
    api_source = read(WORKBENCH / "src" / "apiCollect.ts")

    assert '"/api/v2/collect/raw-file"' in api_source
    assert 'if (!message.includes("Not Found") && !message.includes("404")) throw error;' in api_source
    assert "const fallback = await this.createRawLibraryFile(" in api_source


def test_create_workspace_requires_explicit_topic_confirmation():
    source = read(WORKBENCH / "src" / "workspaces" / "CreateWorkspace.tsx")
    topic_section = source.split("function TopicCards")[1].split("function ArticleEditor")[0]

    assert "pendingTopic" in topic_section
    assert "onPendingTopicChange(topic)" in topic_section
    assert "onSelectTopic(pendingTopic)" in topic_section
    assert "Confirm topic" in topic_section
    assert "onClick={() => onSelectTopic(topic)}" not in topic_section


def test_create_workspace_removes_current_guidance_and_shows_image_suggestions_in_draft():
    source = read(WORKBENCH / "src" / "workspaces" / "CreateWorkspace.tsx")
    styles = read(WORKBENCH / "src" / "styles.css")

    assert "<WorkflowGuideCard" not in source
    assert "function WorkflowGuideCard" not in source
    assert "workflow-guide-card" not in styles
    assert "hasImageSuggestions ? (" in source
    assert "prompt-grid" in source
    assert "image-error-list" in source


def test_create_workspace_design_step_layout_and_html_preview_controls():
    source = read(WORKBENCH / "src" / "workspaces" / "CreateWorkspace.tsx")
    styles = read(WORKBENCH / "src" / "styles.css")

    assert 'nextAction === "format_article") return "designed"' in source
    assert "visibleStep={visibleStep}" in source
    assert "DesignStrategySelect" in source
    assert "function DesignStrategyEditor" not in source
    assert "stage-stack" in source
    assert "HtmlPreviewControls" in source
    assert "html-preview-frame" in source
    assert "target=\"_blank\"" in source
    assert ".image-stage-panel .prompt-grid" in styles
    assert "grid-template-columns: 1fr" in styles
    assert ".html-preview-actions" in styles


def test_learn_workspace_adds_originals_to_queue_from_queue_header():
    source = read(WORKBENCH / "src" / "workspaces" / "LearnWorkspace.tsx")
    app_source = read(WORKBENCH / "src" / "App.tsx")
    api_source = read(WORKBENCH / "src" / "api.ts")

    assert 't("learn.addToQueue")' in source
    assert "onAddSelectedOriginalsToQueue" in source
    assert "addToQueueDisabledReason" in source
    assert "const selectedRailOriginals = useMemo(" in app_source
    assert "const addSelectedOriginalsToLearningQueue = useCallback(" in app_source
    assert 'item.markdownPath?.startsWith("raw_materials/")' in app_source
    assert 'return firstString(value).replace(/\\\\/g, "/");' in api_source
    assert 'status: "queued" as const' in app_source


def test_learn_workspace_generates_and_saves_focus_files_only():
    source = read(WORKBENCH / "src" / "workspaces" / "LearnWorkspace.tsx")
    app_source = read(WORKBENCH / "src" / "App.tsx")
    api_source = read(WORKBENCH / "src" / "api.ts")

    assert 't("learn.primaryFocus")' in source
    assert 't("learn.previewFocus")' in source
    assert 't("learn.commitFocus")' in source
    assert "const refined = await api.refineKnowledgeCluster(rawPaths);" in app_source
    assert "setLearningQueue((current) => current.map((item) => (idSet.has(item.id) ? { ...item, status: \"queued\", error: undefined } : item)))" in app_source
    assert "setLearningQueue((current) => current.filter((queueItem) => !sourceIdSet.has(queueItem.source)))" in app_source
    assert "await api.saveFocusFile(knowledgeDraft.sourceIds, knowledgeDraft.body, knowledgeDraft.title)" in app_source
    assert '"/api/v2/learn/refine-knowledge-cluster"' in api_source
    assert '"/api/v2/learn/focus-file"' in api_source


def test_library_workspace_reads_and_updates_v2_library_markdown_files():
    app_source = read(WORKBENCH / "src" / "App.tsx")
    api_source = read(WORKBENCH / "src" / "api.ts")

    assert "api.readLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath)" in app_source
    assert "api.updateLibraryFile(selectedKnowledge.library, selectedKnowledge.markdownPath, trimmed)" in app_source
    assert "readLibraryFile(library: LibraryKind, markdownPath: string)" in api_source
    assert "updateLibraryFile(" in api_source
    assert "body: firstString(raw.markdown)," in api_source
    assert "body: firstString(raw.markdown, raw.source" not in api_source
    assert "/api/v2/libraries/${libraryBucketToV2(library)}/file" in api_source
    assert "markdown_path=${encodeURIComponent(markdownPath)}" in api_source
