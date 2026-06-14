from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response, status


SESSION_COOKIE_NAME = "figurelearning_session"
LOCAL_USER_ID = "local-user"
LOCAL_WORKSPACE_ID = "local-workspace"
PBKDF2_ITERATIONS = 210_000
SESSION_DAYS = 14


def deployment_mode() -> str:
    value = os.getenv("FIGURELEARNING_DEPLOYMENT_MODE", "local").strip().lower()
    return "cloud" if value == "cloud" else "local"


def is_cloud_mode() -> bool:
    return deployment_mode() == "cloud"


def session_cookie_secure() -> bool:
    configured = os.getenv("FIGURELEARNING_SESSION_COOKIE_SECURE", "").strip().lower()
    if configured in {"0", "false", "no", "off"}:
        return False
    if configured in {"1", "true", "yes", "on"}:
        return True
    return is_cloud_mode()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(candidate, digest)


def init_auth_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS invitations (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'member',
            max_uses INTEGER NOT NULL DEFAULT 1,
            used_count INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT,
            created_by_user_id TEXT,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            user_agent TEXT,
            ip_address TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            detail_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_counters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            counter_key TEXT NOT NULL,
            counter_date TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, workspace_id, counter_key, counter_date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            detail_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    for table in (
        "screenshots",
        "knowledge_entries",
        "source_files",
        "media_sources",
        "mining_projects",
        "perspective_profiles",
    ):
        _ensure_column(conn, table, "owner_user_id", "TEXT")
        _ensure_column(conn, table, "workspace_id", "TEXT")
    ensure_local_identity(conn)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_local_identity(conn: sqlite3.Connection) -> dict[str, Any]:
    timestamp = now_iso()
    password_hash = hash_password(secrets.token_urlsafe(24))
    conn.execute(
        """
        INSERT OR IGNORE INTO users (
            id, email, username, password_hash, role, status, created_at, updated_at
        ) VALUES (?, 'local@figurelearning.local', 'local', ?, 'admin', 'active', ?, ?)
        """,
        (LOCAL_USER_ID, password_hash, timestamp, timestamp),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO workspaces (
            id, owner_user_id, name, created_at, updated_at, status
        ) VALUES (?, ?, '本地工作台', ?, ?, 'active')
        """,
        (LOCAL_WORKSPACE_ID, LOCAL_USER_ID, timestamp, timestamp),
    )
    return {
        "id": LOCAL_USER_ID,
        "email": "local@figurelearning.local",
        "username": "local",
        "role": "admin",
        "status": "active",
    }


def current_context(request: Request, conn: sqlite3.Connection) -> dict[str, Any]:
    if not is_cloud_mode():
        user = get_user(conn, LOCAL_USER_ID)
        workspace = get_default_workspace(conn, LOCAL_USER_ID)
        return _context_payload(user, workspace, authenticated=True)

    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录知识酷内测账号")
    session = conn.execute(
        """
        SELECT * FROM sessions
        WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
        """,
        (_hash_token(token), now_iso()),
    ).fetchone()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")
    user = get_user(conn, session["user_id"])
    if not user or user["status"] != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不可用")
    workspace = get_default_workspace(conn, user["id"])
    return _context_payload(user, workspace, authenticated=True)


def anonymous_context(conn: sqlite3.Connection, request: Request | None = None) -> dict[str, Any]:
    try:
        if request is not None:
            return current_context(request, conn)
    except HTTPException:
        pass
    if not is_cloud_mode():
        return current_context(request or _NullRequest(), conn)
    return {
        "deploymentMode": deployment_mode(),
        "authenticated": False,
        "user": None,
        "workspace": None,
    }


class _NullRequest:
    cookies: dict[str, str] = {}


def get_user(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_default_workspace(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM workspaces WHERE owner_user_id = ? AND status = 'active' ORDER BY created_at LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        return row
    workspace_id = str(uuid.uuid4())
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO workspaces (id, owner_user_id, name, created_at, updated_at, status)
        VALUES (?, ?, '默认工作台', ?, ?, 'active')
        """,
        (workspace_id, user_id, timestamp, timestamp),
    )
    return conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()


def login(conn: sqlite3.Connection, response: Response, email_or_username: str, password: str, request: Request) -> dict[str, Any]:
    identifier = email_or_username.strip().lower()
    user = conn.execute(
        "SELECT * FROM users WHERE lower(email) = ? OR lower(username) = ?",
        (identifier, identifier),
    ).fetchone()
    if not user or user["status"] != "active" or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码不正确")
    token = secrets.token_urlsafe(32)
    timestamp = now_iso()
    expires_at = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at, user_agent, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            user["id"],
            _hash_token(token),
            timestamp,
            expires_at,
            request.headers.get("user-agent", ""),
            request.client.host if request.client else "",
        ),
    )
    conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (timestamp, timestamp, user["id"]))
    conn.commit()
    _set_session_cookie(response, token)
    workspace = get_default_workspace(conn, user["id"])
    return _context_payload(user, workspace, authenticated=True)


def logout(conn: sqlite3.Connection, response: Response, request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if token:
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (now_iso(), _hash_token(token)),
        )
        conn.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


def register_with_invite(
    conn: sqlite3.Connection,
    response: Response,
    request: Request,
    *,
    invite_code: str,
    email: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    if not is_cloud_mode():
        return current_context(request, conn)
    cleaned_code = invite_code.strip()
    invitation = conn.execute(
        """
        SELECT * FROM invitations
        WHERE code = ? AND status = 'active' AND used_count < max_uses
        """,
        (cleaned_code,),
    ).fetchone()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码无效或已用完")
    if invitation["expires_at"] and invitation["expires_at"] <= now_iso():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码已过期")
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少需要 8 位")

    timestamp = now_iso()
    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    try:
        conn.execute(
            """
            INSERT INTO users (
                id, email, username, password_hash, role, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                user_id,
                email.strip().lower(),
                username.strip(),
                hash_password(password),
                invitation["role"],
                timestamp,
                timestamp,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱或用户名已存在") from exc
    conn.execute(
        """
        INSERT INTO workspaces (id, owner_user_id, name, created_at, updated_at, status)
        VALUES (?, ?, ?, ?, ?, 'active')
        """,
        (workspace_id, user_id, f"{username.strip()} 的工作台", timestamp, timestamp),
    )
    conn.execute(
        "UPDATE invitations SET used_count = used_count + 1 WHERE id = ?",
        (invitation["id"],),
    )
    conn.commit()
    return login(conn, response, email, password, request)


def create_invitation(conn: sqlite3.Connection, *, role: str = "member", max_uses: int = 1, days: int = 14) -> dict[str, Any]:
    timestamp = now_iso()
    invitation_id = str(uuid.uuid4())
    code = secrets.token_urlsafe(9)
    expires_at = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds") if days > 0 else None
    conn.execute(
        """
        INSERT INTO invitations (id, code, role, max_uses, used_count, expires_at, created_at, status)
        VALUES (?, ?, ?, ?, 0, ?, ?, 'active')
        """,
        (invitation_id, code, role, max(1, max_uses), expires_at, timestamp),
    )
    conn.commit()
    return {
        "id": invitation_id,
        "code": code,
        "role": role,
        "maxUses": max(1, max_uses),
        "usedCount": 0,
        "expiresAt": expires_at,
        "createdAt": timestamp,
    }


def bootstrap_admin(
    conn: sqlite3.Connection,
    *,
    email: str,
    username: str,
    password: str,
    invite_role: str = "member",
    invite_max_uses: int = 5,
    invite_days: int = 14,
) -> dict[str, Any]:
    cleaned_email = email.strip().lower()
    cleaned_username = username.strip()
    if not cleaned_email or "@" not in cleaned_email:
        raise ValueError("Admin email is required and must look like an email address.")
    if not cleaned_username:
        raise ValueError("Admin username is required.")
    if len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters.")

    timestamp = now_iso()
    existing = conn.execute(
        "SELECT * FROM users WHERE lower(email) = ? OR lower(username) = ?",
        (cleaned_email, cleaned_username.lower()),
    ).fetchone()
    if existing:
        user_id = existing["id"]
        conn.execute(
            """
            UPDATE users
            SET email = ?, username = ?, password_hash = ?, role = 'admin',
                status = 'active', updated_at = ?
            WHERE id = ?
            """,
            (cleaned_email, cleaned_username, hash_password(password), timestamp, user_id),
        )
        created_admin = False
    else:
        user_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO users (
                id, email, username, password_hash, role, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'admin', 'active', ?, ?)
            """,
            (user_id, cleaned_email, cleaned_username, hash_password(password), timestamp, timestamp),
        )
        created_admin = True

    workspace = get_default_workspace(conn, user_id)
    invitation = create_invitation(conn, role=invite_role, max_uses=invite_max_uses, days=invite_days)
    conn.commit()
    return {
        "admin": {
            "id": user_id,
            "email": cleaned_email,
            "username": cleaned_username,
            "created": created_admin,
        },
        "workspace": {
            "id": workspace["id"],
            "name": workspace["name"],
        },
        "invitation": invitation,
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=session_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _context_payload(user: sqlite3.Row | dict[str, Any], workspace: sqlite3.Row | dict[str, Any], *, authenticated: bool) -> dict[str, Any]:
    return {
        "deploymentMode": deployment_mode(),
        "authenticated": authenticated,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "role": user["role"],
            "status": user["status"],
        },
        "workspace": {
            "id": workspace["id"],
            "name": workspace["name"],
            "ownerUserId": workspace["owner_user_id"],
        },
    }
