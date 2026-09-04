import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from interview_prep_mcp.db import (
    Database,
    SCHEMA_MIGRATIONS,
    applied_schema_migrations,
    connect,
    initialize_postgres_schema,
)


class DatabaseSchemaTests(unittest.TestCase):
    def test_closed_postgres_connection_is_reopened_before_query(self):
        closed_connection = Mock(closed=True)
        replacement_connection = Mock(closed=False)
        replacement_connection.execute.return_value = "query-result"
        db = Database(closed_connection, "postgres", "postgresql://example")

        with patch("interview_prep_mcp.db._open_postgres_connection", return_value=replacement_connection) as reconnect:
            result = db.execute("SELECT ?", ("value",))

        self.assertEqual(result, "query-result")
        reconnect.assert_called_once_with("postgresql://example")
        replacement_connection.execute.assert_called_once_with("SELECT %s", ("value",))

    def test_schema_migration_ledger_is_recorded(self):
        db = connect(":memory:")

        self.assertEqual(applied_schema_migrations(db), [version for version, _description in SCHEMA_MIGRATIONS])

    def test_current_postgres_schema_skips_startup_ddl(self):
        migration_table_cursor = Mock()
        migration_table_cursor.fetchone.return_value = {"schema_migrations": "schema_migrations"}
        versions_cursor = Mock()
        versions_cursor.fetchall.return_value = [
            {"version": version} for version, _description in SCHEMA_MIGRATIONS
        ]
        connection = Mock(closed=False)
        connection.execute.side_effect = [migration_table_cursor, versions_cursor]
        db = Database(connection, "postgres", "postgresql://example")

        initialize_postgres_schema(db)

        self.assertEqual(connection.execute.call_count, 2)
        connection.commit.assert_called_once_with()

    def test_reinitializing_existing_database_preserves_migration_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "study.sqlite3"
            first = connect(db_path)
            first.conn.close()

            second = connect(db_path)

        self.assertEqual(applied_schema_migrations(second), [version for version, _description in SCHEMA_MIGRATIONS])

    def test_existing_single_user_database_gets_owner_subject_and_migration_ledger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE studies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()

            db = connect(db_path)
            columns = {row["name"] for row in db.conn.execute("PRAGMA table_info(studies)").fetchall()}

        self.assertIn("owner_subject", columns)
        self.assertEqual(applied_schema_migrations(db), [version for version, _description in SCHEMA_MIGRATIONS])
