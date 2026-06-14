from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any


TERMINAL_STATUSES = {"success", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_job(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    workspace_id: str,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    job_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO jobs (
            id, owner_user_id, workspace_id, kind, status, payload_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)
        """,
        (
            job_id,
            user_id,
            workspace_id,
            kind.strip(),
            json.dumps(payload or {}, ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )
    append_job_event(conn, job_id=job_id, status="queued", message="任务已进入队列")
    conn.commit()
    return get_job(conn, user_id=user_id, job_id=job_id)


def list_jobs(conn: sqlite3.Connection, *, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM jobs
        WHERE owner_user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, max(1, min(limit, 100))),
    ).fetchall()
    return [job_row_to_dict(row) for row in rows]


def get_job(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM jobs WHERE id = ? AND owner_user_id = ?",
        (job_id, user_id),
    ).fetchone()
    if not row:
        raise KeyError(job_id)
    item = job_row_to_dict(row)
    item["events"] = list_job_events(conn, job_id=job_id)
    return item


def cancel_job(conn: sqlite3.Connection, *, user_id: str, job_id: str) -> dict[str, Any]:
    job = get_job(conn, user_id=user_id, job_id=job_id)
    if job["status"] in TERMINAL_STATUSES:
        return job
    timestamp = now_iso()
    conn.execute(
        """
        UPDATE jobs
        SET status = 'cancelled', updated_at = ?, finished_at = ?
        WHERE id = ? AND owner_user_id = ?
        """,
        (timestamp, timestamp, job_id, user_id),
    )
    append_job_event(conn, job_id=job_id, status="cancelled", message="任务已取消")
    conn.commit()
    return get_job(conn, user_id=user_id, job_id=job_id)


def start_job(conn: sqlite3.Connection, *, job_id: str) -> bool:
    timestamp = now_iso()
    cursor = conn.execute(
        """
        UPDATE jobs
        SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?)
        WHERE id = ? AND status = 'queued'
        """,
        (timestamp, timestamp, job_id),
    )
    if cursor.rowcount != 1:
        conn.commit()
        return False
    append_job_event(conn, job_id=job_id, status="running", message="任务开始处理")
    conn.commit()
    return True


def complete_job(conn: sqlite3.Connection, *, job_id: str, result: dict[str, Any] | None = None, message: str = "任务处理完成") -> None:
    timestamp = now_iso()
    conn.execute(
        """
        UPDATE jobs
        SET status = 'success', result_json = ?, error_message = NULL,
            updated_at = ?, finished_at = ?
        WHERE id = ?
        """,
        (json.dumps(result or {}, ensure_ascii=False), timestamp, timestamp, job_id),
    )
    append_job_event(conn, job_id=job_id, status="success", message=message, detail=result or {})
    conn.commit()


def fail_job(conn: sqlite3.Connection, *, job_id: str, error: str, detail: dict[str, Any] | None = None) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        UPDATE jobs
        SET status = 'failed', error_message = ?, updated_at = ?, finished_at = ?
        WHERE id = ?
        """,
        (error, timestamp, timestamp, job_id),
    )
    append_job_event(conn, job_id=job_id, status="failed", message=error, detail=detail or {})
    conn.commit()


def append_job_event(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    status: str,
    message: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO job_events (job_id, status, message, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, status, message, json.dumps(detail or {}, ensure_ascii=False), now_iso()),
    )


def list_job_events(conn: sqlite3.Connection, *, job_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM job_events
        WHERE job_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (job_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "jobId": row["job_id"],
            "status": row["status"],
            "message": row["message"] or "",
            "detail": _loads(row["detail_json"], {}),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def job_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ownerUserId": row["owner_user_id"],
        "workspaceId": row["workspace_id"],
        "kind": row["kind"],
        "status": row["status"],
        "payload": _loads(row["payload_json"], {}),
        "result": _loads(row["result_json"], None),
        "errorMessage": row["error_message"] or "",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
    }


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
