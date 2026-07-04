import pytest

from src.shared.product_architecture import (
    CAPABILITIES,
    backend_domains_for_capability,
    capabilities_by_priority,
    capabilities_for_frontend_area,
)


def test_product_capability_ids_are_unique():
    ids = [item.id for item in CAPABILITIES]

    assert len(ids) == len(set(ids))


def test_p0_capabilities_define_the_primary_workflow():
    p0_ids = [item.id for item in capabilities_by_priority("P0")]

    assert p0_ids == [
        "capture_materials",
        "generate_knowledge",
        "manage_library",
        "organize_network",
        "retrieve_answers",
    ]


def test_create_area_is_separate_from_perspective_mining():
    create_ids = {item.id for item in capabilities_for_frontend_area("create")}
    mining_ids = {item.id for item in capabilities_for_frontend_area("mine")}

    assert create_ids == {"create_wechat_article"}
    assert mining_ids == {"interpret_perspectives"}


def test_backend_domains_follow_capability_not_legacy_page_shape():
    assert backend_domains_for_capability("generate_knowledge") == (
        "materials",
        "knowledge",
        "documents",
        "media",
        "llm",
        "ocr",
    )


def test_unknown_capability_raises_key_error():
    with pytest.raises(KeyError):
        backend_domains_for_capability("unknown")
