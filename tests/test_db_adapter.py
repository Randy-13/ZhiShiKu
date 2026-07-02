from __future__ import annotations

from src import db
from tools import migrate_sqlite_to_mysql


def test_configured_backend_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DB_BACKEND", raising=False)
    monkeypatch.delenv("FIGURELEARNING_MYSQL_DSN", raising=False)
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "local")

    assert db.configured_backend() == "sqlite"


def test_configured_backend_uses_mysql_for_cloud_with_dsn(monkeypatch):
    monkeypatch.delenv("FIGURELEARNING_DB_BACKEND", raising=False)
    monkeypatch.setenv("FIGURELEARNING_DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("FIGURELEARNING_MYSQL_DSN", "mysql+pymysql://user:pass@127.0.0.1:3306/figurelearning")

    assert db.configured_backend() == "mysql"


def test_translate_sqlite_upsert_to_mysql():
    sql = """
        INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, workspace_id, counter_key, counter_date)
        DO UPDATE SET count = count + excluded.count
    """

    translated = db.translate_sqlite_sql(sql)

    assert "%s" in translated
    assert "ON DUPLICATE KEY UPDATE" in translated
    assert "VALUES(count)" in translated


def test_migration_skips_internal_schema_only():
    assert "schema_migrations" in migrate_sqlite_to_mysql.SKIPPED_TABLES
    assert "sessions" not in migrate_sqlite_to_mysql.SKIPPED_TABLES
    assert "users" not in migrate_sqlite_to_mysql.SKIPPED_TABLES


def test_mysql_migration_file_exists():
    migration = db.MIGRATIONS_DIR / "20260702_01_harden_core_schema.sql"

    assert migration.exists()
    assert "workspace_members" in migration.read_text(encoding="utf-8")
    assert "storage_objects" in migration.read_text(encoding="utf-8")


def test_split_sql_statements_ignores_comments_and_semicolons_in_strings():
    sql = """
    -- ignored;
    CREATE TABLE demo (name VARCHAR(64));
    INSERT INTO demo (name) VALUES ('a;b');
    """

    statements = db.split_sql_statements(sql)

    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE")
    assert "'a;b'" in statements[1]
