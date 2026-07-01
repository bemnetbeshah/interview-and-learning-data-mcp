import sqlite3
import unittest

from interview_prep_mcp.db import connect

from scripts.check_database_schema import check_database_schema, table_columns


class CheckDatabaseSchemaTests(unittest.TestCase):
    def test_current_sqlite_schema_passes(self):
        db = connect(":memory:")

        checks = check_database_schema(db)

        self.assertFalse([check for check in checks if not check.ok])
        self.assertIn("owner_subject", table_columns(db, "studies"))

    def test_missing_required_column_fails(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE studies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT,
                deleted_at TEXT
            )
            """
        )
        db = _FakeDb(conn)

        checks = check_database_schema(db)
        failures = {check.name: check.detail for check in checks if not check.ok}

        self.assertIn("table.studies", failures)
        self.assertIn("owner_subject", failures["table.studies"])


class _FakeDb:
    dialect = "sqlite"

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql, tuple(params))
