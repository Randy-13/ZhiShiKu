import storage


def test_safe_filename_removes_unsafe_characters():
    value = storage.safe_filename('Nvidia/Rubin: 780? "test"')
    assert "/" not in value
    assert ":" not in value
    assert "?" not in value
    assert value.startswith("Nvidia_Rubin")


def test_hash_bytes_is_stable():
    assert storage.hash_bytes(b"abc") == storage.hash_bytes(b"abc")
    assert storage.hash_bytes(b"abc") != storage.hash_bytes(b"abcd")


def test_markdown_path_uses_date_and_hash():
    path = storage.markdown_path_for("Dreamenext Launch", "abcdef123456", "2026-04-29T10:00:00")
    assert path.parent == storage.KNOWLEDGE_DIR / "2026-04-29"
    assert path.name.endswith("_abcdef12.md")


def test_combined_hash_is_order_sensitive():
    first = [{"image_hash": "a"}, {"image_hash": "b"}]
    second = [{"image_hash": "b"}, {"image_hash": "a"}]
    assert storage.combined_hash(first) != storage.combined_hash(second)
