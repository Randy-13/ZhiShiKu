from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import db as database
import storage


SKIPPED_TABLES = {"schema_migrations"}
OWNER_SCOPED_TABLES = {
    "screenshots",
    "source_files",
    "media_sources",
    "knowledge_entries",
    "mining_projects",
    "perspective_profiles",
    "writer_projects",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate FigureLearning SQLite metadata to MySQL.")
    parser.add_argument("--sqlite", default=str(ROOT / "knowledge.db"), help="Source SQLite database path.")
    parser.add_argument("--mysql-dsn", default=os.getenv("FIGURELEARNING_MYSQL_DSN", ""), help="Target MySQL DSN.")
    parser.add_argument(
        "--storage-root",
        default=os.getenv("FIGURELEARNING_STORAGE_ROOT", str(storage.STORAGE_ROOT)),
        help="Storage root for path checks.",
    )
    parser.add_argument("--apply", action="store_true", help="Write rows to MySQL. Omit for dry-run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--legacy-owner-user-id", default="local-user", help="Owner used for legacy rows without owner_user_id.")
    parser.add_argument("--legacy-workspace-id", default="local-workspace", help="Workspace used for legacy rows without workspace_id.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = Path(args.sqlite).expanduser().resolve()
    if not sqlite_path.exists():
        print(f"SQLite database not found: {sqlite_path}", file=sys.stderr)
        return 2
    if not args.mysql_dsn:
        print("MySQL DSN is required via --mysql-dsn or FIGURELEARNING_MYSQL_DSN.", file=sys.stderr)
        return 2

    os.environ["FIGURELEARNING_DB_BACKEND"] = "mysql"
    os.environ["FIGURELEARNING_MYSQL_DSN"] = args.mysql_dsn

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "sqlite": str(sqlite_path),
        "tables": {},
        "missing_paths": [],
        "duplicate_hashes": {},
        "legacy_owner_backfill": {},
        "ok": True,
    }

    try:
        with database.connect_mysql() as target:
            database.init_mysql_schema(target)
            for table in database.MYSQL_TABLES:
                if table in SKIPPED_TABLES or not sqlite_table_exists(source, table):
                    continue
                rows = [dict(row) for row in source.execute(f"SELECT * FROM {table}").fetchall()]
                backfilled = backfill_legacy_owner(
                    table,
                    rows,
                    owner_user_id=args.legacy_owner_user_id,
                    workspace_id=args.legacy_workspace_id,
                )
                if backfilled:
                    report["legacy_owner_backfill"][table] = backfilled
                report["tables"][table] = {"source_rows": len(rows), "inserted": 0}
                check_paths(table, rows, Path(args.storage_root), report)
                if args.apply and rows:
                    inserted = insert_rows(target, table, rows)
                    report["tables"][table]["inserted"] = inserted
            report["duplicate_hashes"] = database.duplicate_hash_report(target)
            if not args.apply:
                target.rollback()
    finally:
        source.close()

    if report["missing_paths"] or any(report["duplicate_hashes"].values()):
        report["ok"] = False
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 0 if report["ok"] else 1


def sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return bool(row)


def insert_rows(conn: database.MySqlConnection, table: str, rows: list[dict[str, Any]]) -> int:
    columns = list(rows[0].keys())
    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in columns if column != "id")
    sql = f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders})"
    if updates:
        sql += f" ON DUPLICATE KEY UPDATE {updates}"
    values = [tuple(normalize_value(row.get(column)) for column in columns) for row in rows]
    conn.executemany(sql, values)
    conn.commit()
    return len(values)


def backfill_legacy_owner(table: str, rows: list[dict[str, Any]], *, owner_user_id: str, workspace_id: str) -> int:
    if table not in OWNER_SCOPED_TABLES:
        return 0
    count = 0
    for row in rows:
        if "owner_user_id" in row and not str(row.get("owner_user_id") or "").strip():
            row["owner_user_id"] = owner_user_id
            count += 1
        if "workspace_id" in row and not str(row.get("workspace_id") or "").strip():
            row["workspace_id"] = workspace_id
    return count


def normalize_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def check_paths(table: str, rows: list[dict[str, Any]], storage_root: Path, report: dict[str, Any]) -> None:
    for column in database.PATH_COLUMNS.get(table, ()):
        for row in rows:
            value = str(row.get(column) or "").strip()
            if not value or value.startswith("http://") or value.startswith("https://"):
                continue
            path = Path(value)
            if not path.is_absolute():
                path = storage_root / value
            if not path.exists():
                report["missing_paths"].append({"table": table, "column": column, "path": value})


def print_report(report: dict[str, Any]) -> None:
    print(f"FigureLearning SQLite -> MySQL migration {report['mode']}")
    print(f"Source: {report['sqlite']}")
    for table, item in report["tables"].items():
        print(f"- {table}: {item['source_rows']} source row(s), {item['inserted']} inserted")
    print(f"Missing path references: {len(report['missing_paths'])}")
    duplicate_count = sum(len(items) for items in report["duplicate_hashes"].values())
    print(f"Duplicate scoped hashes: {duplicate_count}")
    backfilled = sum(int(value) for value in report["legacy_owner_backfill"].values())
    print(f"Legacy owner backfilled: {backfilled}")


if __name__ == "__main__":
    raise SystemExit(main())
