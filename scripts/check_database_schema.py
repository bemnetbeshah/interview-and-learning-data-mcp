#!/usr/bin/env python3
"""Validate the configured database schema and migration ledger."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from interview_prep_mcp.config import load_settings  # noqa: E402
from interview_prep_mcp.db import SCHEMA_MIGRATIONS, Database, applied_schema_migrations, connect  # noqa: E402


REQUIRED_COLUMNS = {
    "studies": {"id", "owner_subject", "name", "created_at", "deleted_at"},
    "topics": {"id", "study_id", "name", "order_index", "created_at", "deleted_at"},
    "subtopics": {"id", "topic_id", "name", "description", "created_at", "deleted_at"},
    "attempts": {"id", "subtopic_id", "timestamp", "score", "model_notes", "question_asked"},
    "subtopic_state": {
        "subtopic_id",
        "mastery_level",
        "ease_factor",
        "interval_days",
        "next_review_date",
        "last_reviewed_at",
        "consecutive_correct",
    },
    "schema_migrations": {"version", "description", "applied_at"},
    "oauth_clients": {"client_id", "client_info", "created_at"},
    "oauth_pending_authorizations": {
        "request_id",
        "client_id",
        "state",
        "scopes_json",
        "code_challenge",
        "redirect_uri",
        "redirect_uri_provided_explicitly",
        "resource",
        "expires_at",
    },
    "oauth_authorization_codes": {
        "code",
        "client_id",
        "scopes_json",
        "code_challenge",
        "redirect_uri",
        "redirect_uri_provided_explicitly",
        "resource",
        "subject",
        "expires_at",
        "used_at",
    },
    "oauth_access_tokens": {"token", "client_id", "scopes_json", "resource", "subject", "expires_at"},
    "oauth_refresh_tokens": {"token", "client_id", "scopes_json", "subject", "expires_at"},
}


@dataclass(frozen=True)
class SchemaCheck:
    ok: bool
    name: str
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Interview Prep MCP database schema.")
    parser.parse_args()

    settings = load_settings()
    db = connect(settings.db_path, settings.database_url)
    checks = check_database_schema(db)
    for check in checks:
        status = "ok" if check.ok else "fail"
        print(f"{status}: {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


def check_database_schema(db: Database) -> list[SchemaCheck]:
    checks: list[SchemaCheck] = []
    expected_migrations = [version for version, _description in SCHEMA_MIGRATIONS]
    actual_migrations = applied_schema_migrations(db)
    checks.append(
        SchemaCheck(
            actual_migrations == expected_migrations,
            "schema_migrations",
            f"expected {expected_migrations}, found {actual_migrations}",
        )
    )

    for table, required_columns in REQUIRED_COLUMNS.items():
        columns = table_columns(db, table)
        missing = sorted(required_columns - columns)
        checks.append(
            SchemaCheck(
                not missing,
                f"table.{table}",
                "required columns present" if not missing else f"missing columns: {', '.join(missing)}",
            )
        )
    return checks


def table_columns(db: Database, table: str) -> set[str]:
    if db.dialect == "postgres":
        rows = db.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table,),
        ).fetchall()
        return {_row_value(row, "column_name") for row in rows}

    rows = db.conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {_row_value(row, "name") for row in rows}


def _row_value(row, key: str):
    if hasattr(row, "keys"):
        return row[key]
    return row[0]


if __name__ == "__main__":
    sys.exit(main())
