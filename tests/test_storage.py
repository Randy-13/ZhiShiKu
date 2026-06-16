import storage
import workbench_settings
import writer_tools


def setup_storage(tmp_path, monkeypatch):
    runtime_root = tmp_path
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(storage, "STORAGE_ROOT", runtime_root)
    monkeypatch.setattr(storage, "IMAGE_DIR", runtime_root / "images")
    monkeypatch.setattr(storage, "DOCUMENT_DIR", runtime_root / "documents")
    monkeypatch.setattr(storage, "KNOWLEDGE_DIR", runtime_root / "knowledge")
    monkeypatch.setattr(storage, "MEDIA_DIR", runtime_root / "media")
    monkeypatch.setattr(storage, "MINING_DIR", runtime_root / "mining")
    monkeypatch.setattr(storage, "RAW_MATERIAL_DIR", runtime_root / "raw_materials")
    monkeypatch.setattr(storage, "WRITER_DIR", runtime_root / "writer")
    monkeypatch.setattr(storage, "TRASH_DIR", runtime_root / "trash")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "knowledge.db")
    monkeypatch.setattr(workbench_settings, "SETTINGS_PATH", tmp_path / "workbench_settings.json")
    monkeypatch.setattr(writer_tools, "WRITER_DIR", runtime_root / "writer")
    storage.init_storage()


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


def test_create_or_update_knowledge_entry_preserves_existing_graph_fields(tmp_path, monkeypatch):
    setup_storage(tmp_path, monkeypatch)
    entry = storage.create_or_update_knowledge_entry([1], "same-hash")

    with storage.connect() as conn:
        conn.execute(
            """
            UPDATE knowledge_entries
            SET graph_status = 'pending', graph_error_message = 'keep me'
            WHERE id = ?
            """,
            (entry["id"],),
        )
        conn.commit()

    updated = storage.create_or_update_knowledge_entry([2], "same-hash")

    assert updated["id"] == entry["id"]
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT graph_status, graph_error_message FROM knowledge_entries WHERE id = ?",
            (entry["id"],),
        ).fetchone()
    assert row["graph_status"] == "pending"
    assert row["graph_error_message"] == "keep me"
