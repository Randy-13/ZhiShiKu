from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "frontend" / "workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_create_workspace_image_suggestions_require_explicit_trigger_and_have_readable_dropdowns():
    source = read(WORKBENCH / "src" / "workspaces" / "CreateWorkspace.tsx")

    assert "imageSuggestionsVisible" in source
    assert "setImageSuggestionsVisible(true)" in source
    assert "hasImageSuggestions" in source
    assert "hasSuggestions={hasImageSuggestions}" in source
    assert '{visibleStage === "images" && hasSuggestions ? (' in source
    assert "{hasSuggestions && rationale.trim() ? (" in source
    assert "\u914d\u56fe\u5efa\u8bae\u8bbe\u7f6e" in source
    assert "\u6b63\u6587\u56fe\u7247\u6570\u91cf" in source
    assert "\u914d\u56fe\u98ce\u683c" in source
    assert "\u751f\u6210\u914d\u56fe\u5efa\u8bae" in source
    assert "\u91cd\u65b0\u751f\u6210\u5efa\u8bae" in source
    assert "value={imageStylePreset}" in source
    assert "onImageStylePresetChange(event.target.value)" in source
    assert "value={value}" in source
    assert "onChange(Number(event.target.value))" in source
    assert "image-count-buttons" not in source
    assert "image-style-preset-grid" not in source
    assert "image-choice-button active" not in source
    assert "????" not in source


def test_create_workspace_image_suggestion_dropdown_styles_are_not_button_groups():
    styles = read(WORKBENCH / "src" / "styles.css")

    assert ".image-count-select select" in styles
    assert ".image-style-select select" in styles
    assert ".image-count-buttons" not in styles
    assert ".image-style-preset-grid" not in styles
    assert ".image-choice-button" not in styles



def test_create_workspace_design_requires_strategy_before_html_generation():
    source = read(WORKBENCH / "src" / "workspaces" / "CreateWorkspace.tsx")

    assert "imagesConfirmedProjectId" in source
    assert "return imagesConfirmed ? \"design\" : \"images\"" in source
    assert "return \"confirm_images\"" in source
    assert "onConfirmImages" in source
    assert "setImagesConfirmedProjectId(project.id)" in source
    assert "if (!project?.html_path) return \"format_article\"" in source
    assert "\u751f\u6210\u7f8e\u7f16 HTML" in source
    assert "\u786e\u8ba4\u914d\u56fe\u5e76\u751f\u6210 HTML" not in source
