from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "workbench"


def read_source(relative_path: str) -> str:
    return (FRONTEND / "src" / relative_path).read_text(encoding="utf-8")


def test_xhs_setup_matches_wechat_selected_file_module():
    source = read_source("workspaces/XhsWorkspace.tsx")
    styles = read_source("styles.css")

    assert 'className="project-section setup-selected-files"' in source
    assert 'className="reference-list compact"' in source
    assert "选中文件列表" in source
    assert "右侧勾选文件后会显示在这里" in source
    assert "创建并进入工作流" in source
    assert "xhs-selected-source-bar" not in source
    assert "xhs-selected-source-bar" not in styles


def test_xhs_setup_requires_account_profile_before_project_creation():
    source = read_source("workspaces/XhsWorkspace.tsx")
    flow_source = read_source("hooks/useXhsFlow.ts")
    api_source = read_source("apiXhs.ts")
    domain_source = read_source("domain.ts")

    assert "账号定位" in source
    assert "选择已有账号定位" in source
    assert "新建账号定位" in source
    assert "请先选择或新建账号定位" in source
    assert "AccountProfileDialog" in source
    assert "audience_pain_points" in source
    assert "content_pillars" in source
    assert "tag_strategy" in source
    assert "avoid_topics" in source
    assert "account_profile_id" in api_source
    assert "createProject(name" in api_source
    assert "accountProfileId" in flow_source
    assert "XhsAccountProfile" in domain_source


def test_xhs_project_name_validation_does_not_disable_create_button():
    source = read_source("workspaces/XhsWorkspace.tsx")
    create_button = source[source.index('taskId="create_project"') - 420 : source.index('taskId="create_project"') + 220]

    assert "projectNameInputRef.current?.value.trim()" in source
    assert "setProjectNameTouched(true)" in source
    assert "projectNameMissingReason" in source
    assert "disabled={isRunning || Boolean(createDisabledReason)}" in create_button
    assert "Boolean(visibleCreateReason)" not in create_button
    assert "onClick={submitCreateProject}" in create_button


def test_xhs_frontend_api_covers_project_images_and_staged_publish():
    source = read_source("apiXhs.ts")

    for endpoint in [
        "/api/xhs/account-profiles",
        "/api/xhs/projects",
        "/api/xhs/publish/preflight",
        "/export-package",
        "/publish/fill",
        "/publish/confirm",
        "/publish/save-draft",
    ]:
        assert endpoint in source


def test_xhs_flow_and_domain_types_are_wired():
    flow_source = read_source("hooks/useXhsFlow.ts")
    domain_source = read_source("domain.ts")

    assert 'workspace: "xhs"' in flow_source
    assert "XhsProjectState" in domain_source
    assert "XhsLoginStatus" in domain_source


def test_xhs_running_task_labels_are_wired_to_buttons():
    source = read_source("workspaces/XhsWorkspace.tsx")
    flow_source = read_source("hooks/useXhsFlow.ts")
    app_source = read_source("App.tsx")
    styles = read_source("styles.css")

    assert "XhsRunningTask" in flow_source
    assert "xhsRunningTask" in flow_source
    assert "runningTask={xhsRunningTask}" in app_source
    assert "function RunningButtonLabel" in source
    assert "formatElapsedTime" in source
    assert "font-variant-numeric: tabular-nums" in styles

    for task_id in [
        "generate_topics",
        "generate_draft",
        "revise_draft",
        "suggest_images",
        "confirm_image_suggestions",
        "generate_images",
        "refresh_login",
        "run_preflight",
        "export_package",
        "fill_publish",
        "confirm_publish",
        "save_publish_draft",
    ]:
        assert f'id: "{task_id}"' in flow_source
        assert f'taskId="{task_id}"' in source or f'taskId={{isConfigured ? "{task_id}"' in source


def test_xhs_running_topic_action_has_room_for_timer():
    styles = read_source("styles.css")
    topic_context_styles = styles[styles.index(".xhs-topic-context {") : styles.index(".xhs-topic-context span")]

    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(188px, auto);" in topic_context_styles
    assert ".xhs-topic-context .primary-cta" in styles
    assert "min-width: 188px;" in styles[styles.index(".xhs-topic-context .primary-cta") : styles.index(".xhs-stage-actions")]


def test_xhs_export_package_triggers_browser_download():
    flow_source = read_source("hooks/useXhsFlow.ts")

    export_block = flow_source[flow_source.index("const exportXhsPackage") : flow_source.index("return {", flow_source.index("const exportXhsPackage"))]
    assert "downloadXhsPackage(state)" in export_block
    assert "xhsApi.exportPackage(requireProjectId())" in export_block
    assert "xhsApi.fileUrl(packagePath)" in flow_source
    assert 'link.download = state.project.export_package?.filename || "xhs_publish_package.zip"' in flow_source
    assert "link.click()" in flow_source


def test_xhs_topic_configured_stays_in_config_stage_before_draft():
    source = read_source("workspaces/XhsWorkspace.tsx")
    styles = read_source("styles.css")
    stage_call = source[source.index("<XhsStage") : source.index("/>", source.index("<XhsStage"))]
    stage_start = source.index("function XhsStage")
    stage_signature = source[stage_start : source.index('if (step === "created")', stage_start)]

    assert 'if (step === "topic" || step === "topic_configured")' in source
    assert 'isConfigured={step === "topic_configured"}' in source
    assert 'onClick={isConfigured ? onGenerateDraft : onConfirm}' in source
    assert "onGenerateDraft={() => {" in stage_call
    assert "onGenerateDraft();" in stage_call
    assert "onGenerateDraft," in stage_signature
    assert "onGenerateDraft: () => void;" in stage_signature
    assert "图文配置已确认，下一步先生成正文，再生成配图建议。" in source


def test_xhs_stage_controls_are_wired_to_handlers():
    source = read_source("workspaces/XhsWorkspace.tsx")
    stage_call = source[source.index("<XhsStage") : source.index("/>", source.index("<XhsStage"))]
    stage_start = source.index("function XhsStage")
    stage_source = source[stage_start : source.index("function ImageTextConfigPanel")]

    required_handlers = [
        "onImportKnowledge",
        "onGenerateTopics",
        "onSelectTopic",
        "onConfirmImageTextConfig",
        "onGenerateDraft",
        "onConfirmDraft",
        "onRevise",
        "onSuggestImages",
        "onConfirmImageSuggestions",
        "onGenerateImages",
        "onPreflight",
        "onFillPublish",
        "onConfirmPublish",
        "onSavePublishDraft",
    ]
    for handler in required_handlers:
        assert f"{handler}=" in stage_call
        assert f"{handler}," in stage_source
        assert f"{handler}:" in stage_source

    assert "onClick={onImportKnowledge}" in stage_source
    assert "onClick={onGenerateTopics}" in stage_source
    assert "onClick={() => pendingTopic ? onSelectTopic(pendingTopic) : undefined}" in stage_source
    assert "onClick={onConfirmDraft}" in stage_source
    assert "onClick={onRevise}" in stage_source


def test_xhs_image_generation_is_split_from_draft_and_preview_is_modal():
    source = read_source("workspaces/XhsWorkspace.tsx")
    stage_start = source.index("function XhsStage")
    stage_source = source[stage_start : source.index("function ImageTextConfigPanel")]
    draft_block = stage_source[stage_source.index('if (step === "draft")') : stage_source.index('          <span>{language === "zh" ? "图片生成"')]
    image_panel = source[source.index("function ImageGenerationPanel") : source.index("function XhsPreviewDialog")]

    assert "图片生成" in source
    assert "轮播图片" not in source
    assert "确认草稿，进入图片生成" in draft_block
    assert "onSuggestImages" not in draft_block
    assert "onGenerateImages" not in draft_block
    assert "生成配图建议" in image_panel
    assert "确认配图建议" in image_panel
    assert "生成图片" in image_panel
    assert "进入预检" in image_panel
    assert "执行发布预检" not in image_panel
    assert "XhsPreviewDialog" in source
    assert "xhs-preview-modal" in source
    assert "xhs-phone-preview" in source[source.index("function XhsPreviewDialog") :]
    preview_dialog = source[source.index("function XhsPreviewDialog") : source.index("function SlidePlan")]
    assert "activeIndex" in preview_dialog
    assert "xhs-carousel-button" in preview_dialog
    assert "xhs-carousel-dots" in preview_dialog
    assert "activeSlide" in preview_dialog
    assert "<SlidePlan" not in preview_dialog
    assert "image_suggestion_rationale" not in preview_dialog


def test_xhs_preview_control_is_visible_in_image_generation_panel():
    source = read_source("workspaces/XhsWorkspace.tsx")
    styles = read_source("styles.css")
    image_panel = source[source.index("function ImageGenerationPanel") : source.index("function XhsPreviewDialog")]

    assert 'className="create-summary-bar xhs-summary-bar"' not in source
    assert "setPreviewOpen(true)" in source
    assert "XhsPreviewDialog" in source
    assert "onPreview" in image_panel
    assert 'className="xhs-preview-inline"' in image_panel
    assert "预览" in image_panel
    assert ".xhs-preview-inline" in styles
    assert ".create-summary-bar.xhs-summary-bar" not in styles


def test_xhs_preview_modal_shows_full_carousel_image():
    styles = read_source("styles.css")
    note_media_styles = styles[styles.index(".xhs-note-media img") : styles.index(".xhs-image-empty")]
    preview_modal_styles = styles[styles.index(".xhs-preview-modal") : styles.index(":root:not([data-theme=\"light\"]) .xhs-preview-modal")]

    assert "object-fit: contain;" in note_media_styles
    assert "width: min(720px, calc(100vw - 32px));" in preview_modal_styles
    assert "width: min(560px, 100%, calc((100vh - 260px) * 0.75));" in preview_modal_styles


def test_xhs_stepper_can_review_completed_stages():
    source = read_source("workspaces/XhsWorkspace.tsx")
    styles = read_source("styles.css")
    stage_call = source[source.index("<XhsStage") : source.index("/>", source.index("<XhsStage"))]

    assert "reviewStage" in source
    assert "setReviewStage" in source
    assert "xhsStageForStep" in source
    assert "xhsStepForStage" in source
    assert "nextActionForVisibleXhsStep" in source
    assert "progressIndex={actualStageIndex}" in source
    assert "maxSelectableIndex={actualStageIndex}" in source
    assert "onSelect={(index) => setReviewStage(stages[index]?.id ?? null)}" in source
    assert "xhs-review-banner" not in source
    assert "xhs-review-banner" not in styles
    assert "Reviewing a completed step" not in source
    assert "visibleStage !== actualStage" in source
    assert "clearReviewStage();" in source
    assert "step={visibleStep}" in stage_call
    assert "nextAction={visibleNextAction}" in stage_call


def test_xhs_generated_images_make_preflight_stage_reachable():
    source = read_source("workspaces/XhsWorkspace.tsx")
    stage_function = source[source.index("function xhsStageForStep") : source.index("function xhsStepForStage")]

    assert 'if (step === "images" && nextAction === "run_preflight" && imageItems(project).length) return "publish_check";' in stage_function
    assert 'onEnterPreflight={() => setReviewStage("publish_check")}' in source
    assert "maxSelectableIndex={actualStageIndex}" in source


def test_xhs_publish_tools_do_not_render_image_suggestion_controls():
    source = read_source("workspaces/XhsWorkspace.tsx")
    publish_tools_source = source[source.index("function PublishTools") : source.index("function imageGenerationHint")]

    assert "发布预检" in source
    assert "xhs-preflight-summary" in publish_tools_source
    assert "xhs-preflight-files" in publish_tools_source
    assert "执行发布预检" in publish_tools_source
    assert "填入发布页" in publish_tools_source
    assert 'onEnterPreflight={() => setReviewStage("publish_check")}' in source
    assert 'project?.preflight?.ok ? "fill_publish" : "run_preflight"' in source
    assert "onSuggestImages" not in publish_tools_source
    assert "onGenerateImages" not in publish_tools_source
    assert "生成配图建议" not in publish_tools_source
    assert "生成轮播图片" not in publish_tools_source



def test_xhs_cloud_publish_exports_zip_instead_of_bridge_actions():
    source = read_source("workspaces/XhsWorkspace.tsx")
    app_source = read_source("App.tsx")
    flow_source = read_source("hooks/useXhsFlow.ts")
    api_source = read_source("apiXhs.ts")
    styles = read_source("styles.css")
    publish_tools_source = source[source.index("function PublishTools") : source.index("function xhsStageForStep")]
    cloud_branch = publish_tools_source[publish_tools_source.index("if (isCloudMember)") : publish_tools_source.index("return (", publish_tools_source.index("if (isCloudMember)") + 1)]

    assert 'isCloudMember={authContext.deploymentMode === "cloud" && authContext.user?.role !== "admin"}' in app_source
    assert "exportXhsPackage" in flow_source
    assert "exportPackage(projectId" in api_source
    assert "/export-package" in api_source
    assert "本地填入流程" in publish_tools_source
    assert "导出 ZIP" in publish_tools_source
    assert "下载 ZIP" in publish_tools_source
    assert "????" not in publish_tools_source
    assert "xhsApi.fileUrl(exportPackage.package_path)" in publish_tools_source
    assert "onFillPublish" not in cloud_branch
    assert "onConfirmPublish" not in cloud_branch
    assert "onSavePublishDraft" not in cloud_branch
    assert ".xhs-cloud-export-notice" in styles
    assert ".xhs-export-package-card" in styles
