from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: F401 - loads .env for local CLI usage
from src import db as database
import storage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only FigureLearning database health report.")
    parser.add_argument("--backend", choices=("sqlite", "mysql"), default=os.getenv("FIGURELEARNING_DB_BACKEND", ""))
    parser.add_argument("--mysql-dsn", default=os.getenv("FIGURELEARNING_MYSQL_DSN", ""))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.backend:
        os.environ["FIGURELEARNING_DB_BACKEND"] = args.backend
    if args.mysql_dsn:
        os.environ["FIGURELEARNING_MYSQL_DSN"] = args.mysql_dsn

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_human(report)
    return 0 if report.get("ok") else 1


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "backend": database.configured_backend(),
        "storage_root": str(storage.STORAGE_ROOT),
        "ok": False,
        "error": "",
    }
    try:
        with storage.connect() as conn:
            report.update(
                {
                    "schema_version": database.schema_version(conn),
                    "tables": database.table_counts(conn),
                    "migrations": database.migration_history(conn),
                    "foreign_keys": database.foreign_key_report(conn),
                    "orphans": database.orphan_record_report(conn),
                    "owner_workspace": database.owner_workspace_report(conn),
                    "path_columns": database.path_column_report(conn),
                    "duplicate_hashes": database.duplicate_hash_report(conn),
                    "ok": True,
                }
            )
    except Exception as exc:
        report["error"] = str(exc)
    return report


def print_human(report: dict[str, Any]) -> None:
    print(f"FigureLearning database doctor")
    print(f"- backend: {report.get('backend')}")
    print(f"- storage_root: {report.get('storage_root')}")
    print(f"- ok: {report.get('ok')}")
    if report.get("error"):
        print(f"- error: {report['error']}")
        return
    print(f"- schema_version: {report.get('schema_version')}")
    foreign_keys = report.get("foreign_keys") or {}
    print(f"- foreign_keys: {foreign_keys.get('count', 0)}")
    print("- migrations:")
    for item in report.get("migrations") or []:
        print(f"  {item.get('version')} {item.get('status')} {item.get('applied_at')}")
    print("- table counts:")
    for table, count in (report.get("tables") or {}).items():
        print(f"  {table}: {count}")
    print("- orphan records:")
    for key, count in (report.get("orphans") or {}).items():
        print(f"  {key}: {count}")
    print("- owner/workspace empties:")
    for table, item in (report.get("owner_workspace") or {}).items():
        print(f"  {table}: owner={item.get('empty_owner')} workspace={item.get('empty_workspace')}")


if __name__ == "__main__":
    raise SystemExit(main())
