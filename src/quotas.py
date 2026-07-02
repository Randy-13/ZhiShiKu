from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import storage
from src import db as database


DEFAULT_LIMITS = {
    "link_parse_daily": 30,
    "llm_generate_daily": 50,
    "concurrent_jobs": 2,
    "single_upload_bytes": 100 * 1024 * 1024,
    "storage_bytes": 2 * 1024 * 1024 * 1024,
}


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_enforced(context: dict[str, object]) -> bool:
    user = context.get("user") or {}
    return context.get("deploymentMode") == "cloud" and isinstance(user, dict) and user.get("role") != "admin"


def user_ids(context: dict[str, object]) -> tuple[str, str]:
    user = context.get("user") or {}
    workspace = context.get("workspace") or {}
    if not isinstance(user, dict) or not isinstance(workspace, dict):
        return "", ""
    return str(user.get("id") or ""), str(workspace.get("id") or "")


def check_daily(conn: sqlite3.Connection, *, user_id: str, workspace_id: str, key: str, limit: int | None = None) -> dict[str, object]:
    actual_limit = int(limit if limit is not None else DEFAULT_LIMITS[key])
    row = conn.execute(
        """
        SELECT count FROM usage_counters
        WHERE user_id = ? AND workspace_id = ? AND counter_key = ? AND counter_date = ?
        """,
        (user_id, workspace_id, key, today_key()),
    ).fetchone()
    used = int(row["count"] if row else 0)
    return {"allowed": used < actual_limit, "used": used, "limit": actual_limit, "remaining": max(0, actual_limit - used)}


def consume_daily(conn: sqlite3.Connection, *, user_id: str, workspace_id: str, key: str, amount: int = 1, limit: int | None = None) -> dict[str, object]:
    actual_limit = int(limit if limit is not None else DEFAULT_LIMITS[key])
    if amount > actual_limit:
        status = check_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key, limit=actual_limit)
        return {**status, "allowed": False}
    if database.configured_backend() == "mysql":
        before = check_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key, limit=actual_limit)
        conn.execute(
            """
            INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, workspace_id, counter_key, counter_date)
            DO UPDATE SET count = IF(count + excluded.count <= ?, count + excluded.count, count)
            """,
            (user_id, workspace_id, key, today_key(), amount, actual_limit),
        )
        updated = check_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key, limit=actual_limit)
        return {**updated, "allowed": int(updated["used"]) >= int(before["used"]) + amount}
    status = check_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key, limit=limit)
    if int(status["used"]) + amount > int(status["limit"]):
        return {**status, "allowed": False}
    conn.execute(
        """
        INSERT INTO usage_counters (user_id, workspace_id, counter_key, counter_date, count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, workspace_id, counter_key, counter_date)
        DO UPDATE SET count = count + excluded.count
        """,
        (user_id, workspace_id, key, today_key(), amount),
    )
    updated = check_daily(conn, user_id=user_id, workspace_id=workspace_id, key=key, limit=limit)
    return {**updated, "allowed": True}


def active_jobs(conn: sqlite3.Connection, *, user_id: str, workspace_id: str | None = None) -> int:
    workspace_filter = "AND workspace_id = ?" if workspace_id else ""
    params: tuple[object, ...] = (user_id, workspace_id) if workspace_id else (user_id,)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS count FROM jobs
        WHERE owner_user_id = ? AND status IN ('queued', 'running')
        {workspace_filter}
        """,
        params,
    ).fetchone()
    return int(row["count"] if row else 0)


def check_concurrent_jobs(conn: sqlite3.Connection, *, user_id: str, workspace_id: str | None = None, limit: int | None = None) -> dict[str, object]:
    actual_limit = int(limit if limit is not None else DEFAULT_LIMITS["concurrent_jobs"])
    used = active_jobs(conn, user_id=user_id, workspace_id=workspace_id)
    return {"allowed": used < actual_limit, "used": used, "limit": actual_limit, "remaining": max(0, actual_limit - used)}


def check_upload_size(size_bytes: int, limit: int | None = None) -> dict[str, object]:
    actual_limit = int(limit if limit is not None else DEFAULT_LIMITS["single_upload_bytes"])
    size = max(0, int(size_bytes))
    return {"allowed": size <= actual_limit, "used": size, "limit": actual_limit, "remaining": max(0, actual_limit - size)}


def storage_usage_bytes(conn: sqlite3.Connection, *, user_id: str) -> int:
    paths: set[Path] = set()
    for table, columns in (
        ("screenshots", ("image_path",)),
        ("source_files", ("file_path",)),
        ("media_sources", ("file_path", "transcript_path")),
    ):
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE owner_user_id = ?",
            (user_id,),
        ).fetchall()
        for row in rows:
            for column in columns:
                path_value = row[column]
                if not path_value:
                    continue
                path = storage.resolve_root_path(path_value)
                if path and path.exists() and path.is_file():
                    paths.add(path.resolve())
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def check_storage(conn: sqlite3.Connection, *, user_id: str, incoming_bytes: int = 0, limit: int | None = None) -> dict[str, object]:
    actual_limit = int(limit if limit is not None else DEFAULT_LIMITS["storage_bytes"])
    used = storage_usage_bytes(conn, user_id=user_id)
    projected = used + max(0, int(incoming_bytes))
    return {"allowed": projected <= actual_limit, "used": used, "projected": projected, "limit": actual_limit, "remaining": max(0, actual_limit - projected)}
