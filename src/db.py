from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


SCHEMA_VERSION = "20260702_01_harden_core_schema"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "mysql"

MYSQL_TABLES = [
    "users",
    "workspaces",
    "sessions",
    "invitations",
    "audit_logs",
    "usage_counters",
    "jobs",
    "job_events",
    "screenshots",
    "source_files",
    "media_sources",
    "knowledge_entries",
    "mining_projects",
    "mining_project_sources",
    "mining_strategy_versions",
    "perspective_profiles",
    "writer_projects",
    "workspace_members",
    "storage_objects",
    "schema_migrations",
]

PATH_COLUMNS = {
    "screenshots": ("image_path", "markdown_path"),
    "source_files": ("file_path",),
    "media_sources": ("file_path", "transcript_path"),
    "knowledge_entries": ("markdown_path",),
    "mining_projects": ("artifact_path",),
    "mining_project_sources": ("text_path",),
    "mining_strategy_versions": ("artifact_path",),
    "writer_projects": ("workspace_path", "article_path", "html_path"),
}


def configured_backend(deployment_mode: str | None = None) -> str:
    explicit = os.getenv("FIGURELEARNING_DB_BACKEND", "").strip().lower()
    if explicit in {"sqlite", "mysql"}:
        return explicit
    mode = (deployment_mode or os.getenv("FIGURELEARNING_DEPLOYMENT_MODE") or "local").strip().lower()
    return "mysql" if mode == "cloud" and os.getenv("FIGURELEARNING_MYSQL_DSN") else "sqlite"


def connect(sqlite_path: Path) -> sqlite3.Connection | "MySqlConnection":
    if configured_backend() == "mysql":
        return connect_mysql()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def connect_mysql() -> "MySqlConnection":
    dsn = os.getenv("FIGURELEARNING_MYSQL_DSN", "").strip()
    if not dsn:
        raise RuntimeError("FIGURELEARNING_MYSQL_DSN is required when FIGURELEARNING_DB_BACKEND=mysql")
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:
        raise RuntimeError("PyMySQL is required for FIGURELEARNING_DB_BACKEND=mysql") from exc

    parsed = urlparse(dsn)
    query = dict(parse_qsl(parsed.query))
    conn = pymysql.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=parsed.username or "",
        password=parsed.password or "",
        database=(parsed.path or "/").lstrip("/"),
        charset=query.get("charset") or "utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    return MySqlConnection(conn)


class MySqlCursor:
    def __init__(self, cursor: Any, rows: list[dict[str, Any]] | None = None):
        self._cursor = cursor
        self._rows = rows
        self.rowcount = getattr(cursor, "rowcount", -1)
        self.lastrowid = getattr(cursor, "lastrowid", None)

    def fetchone(self) -> dict[str, Any] | None:
        if self._rows is not None:
            return self._rows.pop(0) if self._rows else None
        return self._cursor.fetchone()

    def fetchall(self) -> list[dict[str, Any]]:
        if self._rows is not None:
            rows = self._rows
            self._rows = []
            return rows
        return list(self._cursor.fetchall())


class MySqlConnection:
    def __init__(self, conn: Any):
        self._conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> MySqlCursor:
        pragma_table = _pragma_table_name(sql)
        if pragma_table:
            return self._column_info_cursor(pragma_table)
        translated = translate_sqlite_sql(sql)
        cursor = self._conn.cursor()
        if params:
            cursor.execute(translated, tuple(params))
        else:
            cursor.execute(translated)
        return MySqlCursor(cursor)

    def executemany(self, sql: str, seq_of_params: list[tuple[Any, ...]]) -> MySqlCursor:
        cursor = self._conn.cursor()
        cursor.executemany(translate_sqlite_sql(sql), seq_of_params)
        return MySqlCursor(cursor)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MySqlConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()

    def _column_info_cursor(self, table: str) -> MySqlCursor:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME AS name
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table,),
        )
        return MySqlCursor(cursor)


def translate_sqlite_sql(sql: str) -> str:
    translated = sql
    translated = translated.replace("INSERT OR IGNORE INTO", "INSERT IGNORE INTO")
    translated = translated.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGINT AUTO_INCREMENT PRIMARY KEY")
    translated = re.sub(r"\bexcluded\.([a-zA-Z_][a-zA-Z0-9_]*)\b", r"VALUES(\1)", translated)
    translated = re.sub(
        r"ON CONFLICT\(([^)]+)\)\s+DO UPDATE SET",
        r"ON DUPLICATE KEY UPDATE",
        translated,
        flags=re.IGNORECASE | re.DOTALL,
    )
    translated = translated.replace("?", "%s")
    return translated


def init_mysql_schema(conn: MySqlConnection) -> None:
    for statement in MYSQL_SCHEMA:
        conn.execute(statement)
    ensure_schema_migrations(conn)
    apply_mysql_migrations(conn)
    conn.commit()


def schema_version(conn: sqlite3.Connection | MySqlConnection) -> str:
    if configured_backend() == "mysql":
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE status = 'success' ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()
        return str(row["version"] if row else "")
    return "sqlite-inline-schema"


def table_counts(conn: sqlite3.Connection | MySqlConnection, tables: list[str] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables or MYSQL_TABLES:
        try:
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"] if row else 0)
        except Exception:
            counts[table] = -1
    return counts


def path_column_report(conn: sqlite3.Connection | MySqlConnection) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    for table, columns in PATH_COLUMNS.items():
        table_report: dict[str, int] = {}
        for column in columns:
            try:
                row = conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE {column} IS NOT NULL AND {column} != ''"
                ).fetchone()
                table_report[column] = int(row["count"] if row else 0)
            except Exception:
                table_report[column] = -1
        report[table] = table_report
    return report


def duplicate_hash_report(conn: sqlite3.Connection | MySqlConnection) -> dict[str, list[dict[str, Any]]]:
    duplicates: dict[str, list[dict[str, Any]]] = {}
    for table, column in (
        ("screenshots", "image_hash"),
        ("source_files", "file_hash"),
        ("media_sources", "media_hash"),
        ("knowledge_entries", "image_hash"),
    ):
        try:
            rows = conn.execute(
                f"""
                SELECT owner_user_id, {column} AS value, COUNT(*) AS count
                FROM {table}
                GROUP BY owner_user_id, {column}
                HAVING COUNT(*) > 1
                LIMIT 20
                """
            ).fetchall()
            duplicates[table] = rows
        except Exception:
            duplicates[table] = []
    return duplicates


def migration_history(conn: sqlite3.Connection | MySqlConnection, limit: int = 20) -> list[dict[str, Any]]:
    if configured_backend() != "mysql":
        return []
    try:
        return conn.execute(
            """
            SELECT version, name, checksum, applied_at, execution_ms, status, error_message
            FROM schema_migrations
            ORDER BY applied_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 100)),),
        ).fetchall()
    except Exception:
        return []


def foreign_key_report(conn: sqlite3.Connection | MySqlConnection) -> dict[str, Any]:
    if configured_backend() != "mysql":
        return {"count": 0, "items": []}
    rows = conn.execute(
        """
        SELECT
            TABLE_NAME AS table_name,
            CONSTRAINT_NAME AS constraint_name,
            COLUMN_NAME AS column_name,
            REFERENCED_TABLE_NAME AS referenced_table_name,
            REFERENCED_COLUMN_NAME AS referenced_column_name
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
        """
    ).fetchall()
    return {"count": len(rows), "items": rows}


def orphan_record_report(conn: sqlite3.Connection | MySqlConnection) -> dict[str, int]:
    checks = {
        "workspaces_without_owner": """
            SELECT COUNT(*) AS count
            FROM workspaces w LEFT JOIN users u ON u.id = w.owner_user_id
            WHERE u.id IS NULL
        """,
        "sessions_without_user": """
            SELECT COUNT(*) AS count
            FROM sessions s LEFT JOIN users u ON u.id = s.user_id
            WHERE u.id IS NULL
        """,
        "jobs_without_user": """
            SELECT COUNT(*) AS count
            FROM jobs j LEFT JOIN users u ON u.id = j.owner_user_id
            WHERE u.id IS NULL
        """,
        "jobs_without_workspace": """
            SELECT COUNT(*) AS count
            FROM jobs j LEFT JOIN workspaces w ON w.id = j.workspace_id
            WHERE w.id IS NULL
        """,
        "job_events_without_job": """
            SELECT COUNT(*) AS count
            FROM job_events e LEFT JOIN jobs j ON j.id = e.job_id
            WHERE j.id IS NULL
        """,
        "usage_counters_without_user": """
            SELECT COUNT(*) AS count
            FROM usage_counters c LEFT JOIN users u ON u.id = c.user_id
            WHERE u.id IS NULL
        """,
        "usage_counters_without_workspace": """
            SELECT COUNT(*) AS count
            FROM usage_counters c LEFT JOIN workspaces w ON w.id = c.workspace_id
            WHERE w.id IS NULL
        """,
        "mining_sources_without_project": """
            SELECT COUNT(*) AS count
            FROM mining_project_sources s LEFT JOIN mining_projects p ON p.id = s.project_id
            WHERE p.id IS NULL
        """,
        "mining_versions_without_project": """
            SELECT COUNT(*) AS count
            FROM mining_strategy_versions v LEFT JOIN mining_projects p ON p.id = v.project_id
            WHERE p.id IS NULL
        """,
    }
    report: dict[str, int] = {}
    for key, sql in checks.items():
        try:
            row = conn.execute(sql).fetchone()
            report[key] = int(row["count"] if row else 0)
        except Exception:
            report[key] = -1
    return report


def owner_workspace_report(conn: sqlite3.Connection | MySqlConnection) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    for table in (
        "screenshots",
        "source_files",
        "media_sources",
        "knowledge_entries",
        "mining_projects",
        "perspective_profiles",
        "writer_projects",
        "storage_objects",
    ):
        try:
            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(owner_user_id IS NULL OR owner_user_id = '') AS empty_owner,
                    SUM(workspace_id IS NULL OR workspace_id = '') AS empty_workspace
                FROM {table}
                """
            ).fetchone()
            report[table] = {
                "total": int(row["total"] if row else 0),
                "empty_owner": int(row["empty_owner"] or 0 if row else 0),
                "empty_workspace": int(row["empty_workspace"] or 0 if row else 0),
            }
        except Exception:
            report[table] = {"total": -1, "empty_owner": -1, "empty_workspace": -1}
    return report


def ensure_schema_migrations(conn: MySqlConnection) -> None:
    existing_columns = _mysql_columns(conn, "schema_migrations")
    desired = {
        "name": "VARCHAR(255)",
        "checksum": "VARCHAR(64)",
        "execution_ms": "INT NOT NULL DEFAULT 0",
        "status": "VARCHAR(32) NOT NULL DEFAULT 'success'",
        "error_message": "TEXT",
    }
    for column, definition in desired.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE schema_migrations ADD COLUMN {column} {definition}")
    conn.execute(
        """
        UPDATE schema_migrations
        SET
            name = COALESCE(name, version),
            checksum = COALESCE(checksum, ''),
            status = COALESCE(status, 'success')
        """
    )


def apply_mysql_migrations(conn: MySqlConnection) -> None:
    if not MIGRATIONS_DIR.exists():
        return
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        row = conn.execute(
            "SELECT checksum, status FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row and row["status"] == "success":
            recorded_checksum = str(row.get("checksum") or "")
            if recorded_checksum and recorded_checksum != checksum:
                raise RuntimeError(f"MySQL migration checksum changed after apply: {version}")
            continue
        started = time.perf_counter()
        try:
            for statement in split_sql_statements(sql):
                conn.execute(statement)
            ensure_mysql_hardening(conn)
            conn.execute(
                """
                INSERT INTO schema_migrations (
                    version, name, checksum, applied_at, execution_ms, status, error_message
                ) VALUES (?, ?, ?, NOW(6), ?, 'success', NULL)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    checksum = VALUES(checksum),
                    applied_at = VALUES(applied_at),
                    execution_ms = VALUES(execution_ms),
                    status = 'success',
                    error_message = NULL
                """,
                (version, migration_name(version), checksum, int((time.perf_counter() - started) * 1000)),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            conn.execute(
                """
                INSERT INTO schema_migrations (
                    version, name, checksum, applied_at, execution_ms, status, error_message
                ) VALUES (?, ?, ?, NOW(6), ?, 'failed', ?)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    checksum = VALUES(checksum),
                    applied_at = VALUES(applied_at),
                    execution_ms = VALUES(execution_ms),
                    status = 'failed',
                    error_message = VALUES(error_message)
                """,
                (version, migration_name(version), checksum, int((time.perf_counter() - started) * 1000), str(exc)[:2000]),
            )
            conn.commit()
            raise
    ensure_mysql_hardening(conn)


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    line_comment = False
    block_comment = False
    index = 0
    while index < len(sql):
        char = sql[index]
        nxt = sql[index + 1] if index + 1 < len(sql) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if not in_single and not in_double and char == "-" and nxt == "-":
            line_comment = True
            index += 2
            continue
        if not in_single and not in_double and char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def migration_name(version: str) -> str:
    return version.split("_", 2)[-1].replace("_", " ")


def ensure_mysql_hardening(conn: MySqlConnection) -> None:
    _ensure_mysql_hardening_columns(conn)
    _backfill_workspace_members(conn)
    _backfill_storage_objects(conn)
    _backfill_knowledge_hardening(conn)
    _ensure_content_scope_not_null(conn)
    _ensure_mysql_indexes(conn)
    _ensure_mysql_foreign_keys(conn)


def _ensure_mysql_hardening_columns(conn: MySqlConnection) -> None:
    for table in (
        "users",
        "workspaces",
        "invitations",
        "sessions",
        "audit_logs",
        "usage_counters",
        "jobs",
        "job_events",
        "screenshots",
        "source_files",
        "media_sources",
        "knowledge_entries",
        "mining_projects",
        "mining_project_sources",
        "mining_strategy_versions",
        "perspective_profiles",
        "writer_projects",
    ):
        if not _mysql_table_exists(conn, table):
            continue
        for column in ("created_at", "updated_at", "expires_at", "revoked_at", "started_at", "finished_at", "last_login_at", "synced_at"):
            if _mysql_column_exists(conn, table, column) and not _mysql_column_exists(conn, table, f"{column}_dt"):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column}_dt DATETIME(6)")
                conn.execute(
                    f"""
                    UPDATE {table}
                    SET {column}_dt = COALESCE(
                        STR_TO_DATE(REPLACE({column}, 'T', ' '), '%Y-%m-%d %H:%i:%s.%f'),
                        STR_TO_DATE(REPLACE({column}, 'T', ' '), '%Y-%m-%d %H:%i:%s')
                    )
                    WHERE {column} IS NOT NULL AND {column} != ''
                    """
                )
    _ensure_mysql_column(conn, "audit_logs", "workspace_id", "VARCHAR(64)")
    _ensure_mysql_column(conn, "audit_logs", "request_id", "VARCHAR(128)")
    _ensure_mysql_column(conn, "audit_logs", "ip_address", "VARCHAR(128)")
    _ensure_mysql_column(conn, "audit_logs", "user_agent", "TEXT")
    _ensure_mysql_column(conn, "audit_logs", "result_status", "VARCHAR(32)")
    _ensure_mysql_column(conn, "audit_logs", "error_message", "TEXT")
    _ensure_mysql_column(conn, "knowledge_entries", "entry_type", "VARCHAR(64)")
    _ensure_mysql_column(conn, "knowledge_entries", "content_hash", "VARCHAR(128)")
    _ensure_mysql_column(conn, "knowledge_entries", "primary_object_id", "BIGINT")
    _ensure_mysql_column(conn, "knowledge_entries", "source_summary", "TEXT")
    _ensure_mysql_column(conn, "knowledge_entries", "synced_at", "VARCHAR(32)")
    _ensure_mysql_column(conn, "knowledge_entries", "synced_at_dt", "DATETIME(6)")
    _ensure_mysql_column(conn, "storage_objects", "relative_path_hash", "VARCHAR(64)")
    if _mysql_table_exists(conn, "storage_objects"):
        conn.execute(
            """
            UPDATE storage_objects
            SET relative_path_hash = SHA2(relative_path, 256)
            WHERE relative_path_hash IS NULL OR relative_path_hash = ''
            """
        )


def _ensure_mysql_column(conn: MySqlConnection, table: str, column: str, definition: str) -> None:
    if _mysql_table_exists(conn, table) and not _mysql_column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _backfill_workspace_members(conn: MySqlConnection) -> None:
    conn.execute(
        """
        INSERT IGNORE INTO workspace_members (
            workspace_id, user_id, role, status, created_at, updated_at,
            created_at_dt, updated_at_dt
        )
        SELECT
            id, owner_user_id, 'owner', status, created_at, updated_at,
            COALESCE(created_at_dt, NOW(6)), COALESCE(updated_at_dt, NOW(6))
        FROM workspaces
        WHERE owner_user_id IS NOT NULL AND owner_user_id != ''
        """
    )


def _backfill_storage_objects(conn: MySqlConnection) -> None:
    statements = [
        """
        INSERT IGNORE INTO storage_objects (
            owner_user_id, workspace_id, object_type, relative_path, relative_path_hash, content_hash,
            mime_type, status, source_table, source_id, created_at, updated_at,
            created_at_dt, updated_at_dt
        )
        SELECT owner_user_id, workspace_id, 'image', image_path, SHA2(image_path, 256), image_hash,
            NULL, status, 'screenshots', id, created_at, updated_at,
            created_at_dt, updated_at_dt
        FROM screenshots
        WHERE image_path IS NOT NULL AND image_path != ''
        """,
        """
        INSERT IGNORE INTO storage_objects (
            owner_user_id, workspace_id, object_type, relative_path, relative_path_hash, content_hash,
            mime_type, status, source_table, source_id, created_at, updated_at,
            created_at_dt, updated_at_dt
        )
        SELECT owner_user_id, workspace_id, 'document', file_path, SHA2(file_path, 256), file_hash,
            content_type, status, 'source_files', id, created_at, updated_at,
            created_at_dt, updated_at_dt
        FROM source_files
        WHERE file_path IS NOT NULL AND file_path != ''
        """,
        """
        INSERT IGNORE INTO storage_objects (
            owner_user_id, workspace_id, object_type, relative_path, relative_path_hash, content_hash,
            mime_type, status, source_table, source_id, created_at, updated_at,
            created_at_dt, updated_at_dt
        )
        SELECT owner_user_id, workspace_id, 'media', file_path, SHA2(file_path, 256), media_hash,
            content_type, status, 'media_sources', id, created_at, updated_at,
            created_at_dt, updated_at_dt
        FROM media_sources
        WHERE file_path IS NOT NULL AND file_path != ''
        """,
        """
        INSERT IGNORE INTO storage_objects (
            owner_user_id, workspace_id, object_type, relative_path, relative_path_hash, content_hash,
            status, source_table, source_id, created_at, updated_at,
            created_at_dt, updated_at_dt
        )
        SELECT owner_user_id, workspace_id, 'markdown', markdown_path,
            SHA2(markdown_path, 256), COALESCE(source_hash, image_hash), status, 'knowledge_entries', id,
            created_at, updated_at, created_at_dt, updated_at_dt
        FROM knowledge_entries
        WHERE markdown_path IS NOT NULL AND markdown_path != ''
        """,
    ]
    for statement in statements:
        conn.execute(statement)


def _backfill_knowledge_hardening(conn: MySqlConnection) -> None:
    conn.execute(
        """
        UPDATE knowledge_entries
        SET
            entry_type = COALESCE(NULLIF(entry_type, ''), source_type, 'knowledge'),
            content_hash = COALESCE(NULLIF(content_hash, ''), source_hash, image_hash),
            synced_at = COALESCE(synced_at, updated_at),
            synced_at_dt = COALESCE(synced_at_dt, updated_at_dt)
        """
    )
    conn.execute(
        """
        UPDATE knowledge_entries k
        JOIN storage_objects o
            ON o.source_table = 'knowledge_entries'
            AND o.source_id = k.id
            AND o.relative_path = k.markdown_path
        SET k.primary_object_id = COALESCE(k.primary_object_id, o.id)
        WHERE k.markdown_path IS NOT NULL AND k.markdown_path != ''
        """
    )


def _ensure_content_scope_not_null(conn: MySqlConnection) -> None:
    for table in (
        "screenshots",
        "source_files",
        "media_sources",
        "knowledge_entries",
        "mining_projects",
        "perspective_profiles",
        "writer_projects",
        "storage_objects",
    ):
        if not _mysql_table_exists(conn, table):
            continue
        conn.execute(
            f"""
            UPDATE {table}
            SET owner_user_id = 'local-user'
            WHERE owner_user_id IS NULL OR owner_user_id = ''
            """
        )
        conn.execute(
            f"""
            UPDATE {table}
            SET workspace_id = 'local-workspace'
            WHERE workspace_id IS NULL OR workspace_id = ''
            """
        )
        for column in ("owner_user_id", "workspace_id"):
            if _mysql_column_nullable(conn, table, column) == "YES":
                conn.execute(f"ALTER TABLE {table} MODIFY {column} VARCHAR(64) NOT NULL")


def _ensure_mysql_indexes(conn: MySqlConnection) -> None:
    indexes = [
        ("audit_logs", "idx_audit_workspace_created", "workspace_id, created_at_dt"),
        ("jobs", "idx_jobs_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("usage_counters", "idx_usage_workspace_date", "workspace_id, counter_date"),
        ("screenshots", "idx_screenshots_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("source_files", "idx_source_files_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("media_sources", "idx_media_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("knowledge_entries", "idx_knowledge_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("knowledge_entries", "idx_knowledge_owner_workspace_updated", "owner_user_id, workspace_id, updated_at_dt"),
        ("mining_projects", "idx_mining_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("perspective_profiles", "idx_perspective_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("writer_projects", "idx_writer_workspace_status_updated", "workspace_id, status, updated_at_dt"),
        ("workspace_members", "idx_workspace_members_user_status", "user_id, status"),
        ("storage_objects", "idx_storage_workspace_type_status", "workspace_id, object_type, status"),
    ]
    for table, name, columns in indexes:
        if _mysql_table_exists(conn, table) and not _mysql_index_exists(conn, table, name):
            conn.execute(f"CREATE INDEX {name} ON {table} ({columns})")


def _ensure_mysql_foreign_keys(conn: MySqlConnection) -> None:
    foreign_keys = [
        ("workspaces", "fk_workspaces_owner", "owner_user_id", "users", "id", "RESTRICT", "CASCADE"),
        ("workspace_members", "fk_workspace_members_workspace", "workspace_id", "workspaces", "id", "CASCADE", "CASCADE"),
        ("workspace_members", "fk_workspace_members_user", "user_id", "users", "id", "CASCADE", "CASCADE"),
        ("sessions", "fk_sessions_user", "user_id", "users", "id", "CASCADE", "CASCADE"),
        ("usage_counters", "fk_usage_counters_user", "user_id", "users", "id", "CASCADE", "CASCADE"),
        ("usage_counters", "fk_usage_counters_workspace", "workspace_id", "workspaces", "id", "CASCADE", "CASCADE"),
        ("jobs", "fk_jobs_owner", "owner_user_id", "users", "id", "CASCADE", "CASCADE"),
        ("jobs", "fk_jobs_workspace", "workspace_id", "workspaces", "id", "CASCADE", "CASCADE"),
        ("job_events", "fk_job_events_job", "job_id", "jobs", "id", "CASCADE", "CASCADE"),
        ("mining_project_sources", "fk_mining_sources_project", "project_id", "mining_projects", "id", "CASCADE", "CASCADE"),
        ("mining_strategy_versions", "fk_mining_versions_project", "project_id", "mining_projects", "id", "CASCADE", "CASCADE"),
        ("storage_objects", "fk_storage_objects_owner", "owner_user_id", "users", "id", "CASCADE", "CASCADE"),
        ("storage_objects", "fk_storage_objects_workspace", "workspace_id", "workspaces", "id", "CASCADE", "CASCADE"),
        ("knowledge_entries", "fk_knowledge_primary_object", "primary_object_id", "storage_objects", "id", "SET NULL", "CASCADE"),
    ]
    for table, name, column, ref_table, ref_column, on_delete, on_update in foreign_keys:
        if (
            _mysql_table_exists(conn, table)
            and _mysql_table_exists(conn, ref_table)
            and _mysql_column_exists(conn, table, column)
            and not _mysql_constraint_exists(conn, table, name)
        ):
            conn.execute(
                f"""
                ALTER TABLE {table}
                ADD CONSTRAINT {name}
                FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column})
                ON DELETE {on_delete} ON UPDATE {on_update}
                """
            )


def _mysql_table_exists(conn: MySqlConnection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT TABLE_NAME AS name
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?
        """,
        (table,),
    ).fetchone()
    return bool(row)


def _mysql_columns(conn: MySqlConnection, table: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT COLUMN_NAME AS name
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?
        """,
        (table,),
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _mysql_column_exists(conn: MySqlConnection, table: str, column: str) -> bool:
    return column in _mysql_columns(conn, table)


def _mysql_column_nullable(conn: MySqlConnection, table: str, column: str) -> str:
    row = conn.execute(
        """
        SELECT IS_NULLABLE AS nullable
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?
        """,
        (table, column),
    ).fetchone()
    return str(row["nullable"] if row else "")


def _mysql_index_exists(conn: MySqlConnection, table: str, index_name: str) -> bool:
    row = conn.execute(
        """
        SELECT INDEX_NAME AS name
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND INDEX_NAME = ?
        LIMIT 1
        """,
        (table, index_name),
    ).fetchone()
    return bool(row)


def _mysql_constraint_exists(conn: MySqlConnection, table: str, constraint_name: str) -> bool:
    row = conn.execute(
        """
        SELECT CONSTRAINT_NAME AS name
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND CONSTRAINT_NAME = ?
        LIMIT 1
        """,
        (table, constraint_name),
    ).fetchone()
    return bool(row)


def _pragma_table_name(sql: str) -> str:
    match = re.search(r"PRAGMA\s+table_info\(([^)]+)\)", sql.strip(), flags=re.IGNORECASE)
    return match.group(1).strip("`\"' ") if match else ""


MYSQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(128) PRIMARY KEY,
        applied_at DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(64) PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        username VARCHAR(128) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(32) NOT NULL DEFAULT 'member',
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        last_login_at VARCHAR(32)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        id VARCHAR(64) PRIMARY KEY,
        owner_user_id VARCHAR(64) NOT NULL,
        name VARCHAR(255) NOT NULL,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        INDEX idx_workspaces_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS invitations (
        id VARCHAR(64) PRIMARY KEY,
        code VARCHAR(128) NOT NULL UNIQUE,
        role VARCHAR(32) NOT NULL DEFAULT 'member',
        max_uses INT NOT NULL DEFAULT 1,
        used_count INT NOT NULL DEFAULT 0,
        expires_at VARCHAR(32),
        created_by_user_id VARCHAR(64),
        created_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'active'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        token_hash VARCHAR(255) NOT NULL UNIQUE,
        created_at VARCHAR(32) NOT NULL,
        expires_at VARCHAR(32) NOT NULL,
        revoked_at VARCHAR(32),
        user_agent TEXT,
        ip_address VARCHAR(128),
        INDEX idx_sessions_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        actor_user_id VARCHAR(64),
        action VARCHAR(128) NOT NULL,
        target_type VARCHAR(128),
        target_id VARCHAR(128),
        detail_json JSON,
        created_at VARCHAR(32) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_counters (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        workspace_id VARCHAR(64) NOT NULL,
        counter_key VARCHAR(128) NOT NULL,
        counter_date VARCHAR(16) NOT NULL,
        count INT NOT NULL DEFAULT 0,
        UNIQUE KEY uq_usage_counter (user_id, workspace_id, counter_key, counter_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id VARCHAR(64) PRIMARY KEY,
        owner_user_id VARCHAR(64) NOT NULL,
        workspace_id VARCHAR(64) NOT NULL,
        kind VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'queued',
        payload_json JSON NOT NULL,
        result_json JSON,
        error_message TEXT,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        started_at VARCHAR(32),
        finished_at VARCHAR(32),
        INDEX idx_jobs_owner_status (owner_user_id, status),
        INDEX idx_jobs_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS job_events (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        job_id VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        message TEXT,
        detail_json JSON,
        created_at VARCHAR(32) NOT NULL,
        INDEX idx_job_events_job (job_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS screenshots (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        image_path TEXT NOT NULL,
        image_hash VARCHAR(128) NOT NULL,
        markdown_path TEXT,
        title TEXT,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
        error_message TEXT,
        topic TEXT,
        tags JSON,
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        UNIQUE KEY uq_screenshots_owner_hash (owner_user_id, image_hash),
        INDEX idx_screenshots_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS source_files (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        file_path TEXT NOT NULL,
        file_hash VARCHAR(128) NOT NULL,
        original_name TEXT,
        content_type VARCHAR(255),
        file_type VARCHAR(64) NOT NULL,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
        error_message TEXT,
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        UNIQUE KEY uq_source_files_owner_hash (owner_user_id, file_hash),
        INDEX idx_source_files_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS media_sources (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        source_kind VARCHAR(64) NOT NULL,
        platform VARCHAR(64) NOT NULL,
        source_url TEXT,
        canonical_url TEXT,
        file_path TEXT,
        media_hash VARCHAR(128) NOT NULL,
        original_name TEXT,
        title TEXT,
        duration_seconds DOUBLE,
        transcript_path TEXT,
        transcript_kind VARCHAR(64) NOT NULL DEFAULT 'none',
        content_type VARCHAR(255),
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
        error_message TEXT,
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        UNIQUE KEY uq_media_sources_owner_hash (owner_user_id, media_hash),
        INDEX idx_media_sources_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_entries (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        image_ids JSON NOT NULL,
        image_hash VARCHAR(128) NOT NULL,
        markdown_path TEXT,
        title TEXT,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'processing',
        error_message TEXT,
        topic TEXT,
        tags JSON,
        graph_status VARCHAR(64) NOT NULL DEFAULT 'not_ingested',
        graph_error_message TEXT,
        source_type VARCHAR(64) NOT NULL DEFAULT 'screenshots',
        source_ids JSON,
        source_hash VARCHAR(128),
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        UNIQUE KEY uq_knowledge_owner_hash (owner_user_id, image_hash),
        INDEX idx_knowledge_owner (owner_user_id),
        INDEX idx_knowledge_workspace (workspace_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS mining_projects (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        name TEXT NOT NULL,
        strategy_type VARCHAR(64) NOT NULL DEFAULT 'creation_strategy',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        artifact_path TEXT,
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        INDEX idx_mining_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS mining_project_sources (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT NOT NULL,
        source_type VARCHAR(64) NOT NULL,
        source_id BIGINT NOT NULL,
        title TEXT,
        text_path TEXT,
        created_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'ready',
        error_message TEXT,
        UNIQUE KEY uq_mining_source (project_id, source_type, source_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS mining_strategy_versions (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        project_id BIGINT NOT NULL,
        version INT NOT NULL,
        artifact_path TEXT NOT NULL,
        created_at VARCHAR(32) NOT NULL,
        summary TEXT,
        UNIQUE KEY uq_mining_version (project_id, version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS perspective_profiles (
        id VARCHAR(128) PRIMARY KEY,
        name TEXT NOT NULL,
        profile_json JSON NOT NULL,
        origin VARCHAR(64) NOT NULL DEFAULT 'custom',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        INDEX idx_perspective_owner (owner_user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS writer_projects (
        id VARCHAR(128) PRIMARY KEY,
        owner_user_id VARCHAR(64),
        workspace_id VARCHAR(64),
        name TEXT NOT NULL,
        project_type VARCHAR(64) NOT NULL DEFAULT 'article',
        status VARCHAR(64) NOT NULL DEFAULT 'created',
        workspace_path TEXT,
        article_path TEXT,
        html_path TEXT,
        metadata_json JSON,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        INDEX idx_writer_projects_owner (owner_user_id, updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]
