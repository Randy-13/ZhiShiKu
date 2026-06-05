import pytest

from src.materials.entities import MaterialStatus, MaterialType, infer_material_title
from src.materials.service import MaterialCollection


def test_material_types_match_collect_ui_order():
    assert [item.value for item in MaterialType] == ["text", "screenshot", "document", "media", "link"]


def test_add_text_material_creates_local_item():
    collection = MaterialCollection()

    item = collection.add_text("  important market signal from a report  ")

    assert item.id == "text-1"
    assert item.material_type == MaterialType.TEXT
    assert item.status == MaterialStatus.LOCAL
    assert item.title == "important market signal from a report"


def test_add_link_material_deduplicates_by_url():
    collection = MaterialCollection()

    first = collection.add_link("https://example.com/research")
    second = collection.add_link("https://example.com/research")

    assert first is second
    assert len(collection.items) == 1
    assert first.source_ref == "https://example.com/research"


def test_add_link_material_requires_http_url():
    collection = MaterialCollection()

    with pytest.raises(ValueError):
        collection.add_link("example.com/research")


def test_external_refs_cover_existing_upload_backends():
    collection = MaterialCollection()

    screenshot = collection.add_external_ref(MaterialType.SCREENSHOT, "image:1", title="Screenshot 1")
    document = collection.add_external_ref(MaterialType.DOCUMENT, "file:1", title="Report")
    media = collection.add_external_ref(MaterialType.MEDIA, "media:1", title="Interview")

    assert [item.material_type for item in collection.ready_for_learning()] == [
        MaterialType.SCREENSHOT,
        MaterialType.DOCUMENT,
        MaterialType.MEDIA,
    ]
    assert screenshot.title == "Screenshot 1"
    assert document.source_ref == "file:1"
    assert media.source_ref == "media:1"


def test_infer_material_title_uses_fallback_for_empty_content():
    assert infer_material_title(MaterialType.TEXT, "", fallback="Note") == "text: Note"
