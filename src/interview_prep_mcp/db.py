"""Database persistence setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Union

PathLike = Union[str, Path]
SCHEMA_MIGRATIONS = [
    ("001_public_multi_user_schema", "Initial public multi-user study, OAuth, and review-state schema."),
]


class Database:
    def __init__(self, conn: Any, dialect: str, database_url: str | None = None):
        self.conn = conn
        self.dialect = dialect
        self.database_url = database_url

    def execute(self, sql: str, params: Iterable[Any] = ()):
        self._ensure_connection()
        if self.dialect == "postgres":
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, tuple(params))

    def commit(self) -> None:
        self._ensure_connection()
        self.conn.commit()

    def rollback(self) -> None:
        self._ensure_connection()
        self.conn.rollback()

    def _ensure_connection(self) -> None:
        """Reopen an idle Postgres connection closed by the hosting platform."""

        if self.dialect != "postgres" or not getattr(self.conn, "closed", False):
            return
        if not self.database_url:
            raise RuntimeError("Cannot reconnect to Postgres without DATABASE_URL")
        self.conn = _open_postgres_connection(self.database_url)


def connect(db_path: PathLike, database_url: str | None = None) -> Database:
    if database_url:
        return connect_postgres(database_url)
    return connect_sqlite(db_path)


def connect_sqlite(db_path: PathLike) -> Database:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db = Database(conn, "sqlite")
    initialize_schema(db)
    return db


def connect_postgres(database_url: str) -> Database:
    db = Database(_open_postgres_connection(database_url), "postgres", database_url)
    initialize_schema(db)
    return db


def _open_postgres_connection(database_url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row)


def initialize_schema(db: Database) -> None:
    if db.dialect == "postgres":
        initialize_postgres_schema(db)
    else:
        initialize_sqlite_schema(db)


def initialize_sqlite_schema(db: Database) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_subject TEXT NOT NULL DEFAULT 'bem',
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id INTEGER NOT NULL REFERENCES studies(id),
            name TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS subtopics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL REFERENCES topics(id),
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subtopic_id INTEGER NOT NULL REFERENCES subtopics(id),
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
            model_notes TEXT NOT NULL,
            question_asked TEXT
        );

        CREATE TABLE IF NOT EXISTS subtopic_state (
            subtopic_id INTEGER PRIMARY KEY REFERENCES subtopics(id),
            mastery_level INTEGER NOT NULL DEFAULT 0,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            next_review_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            last_reviewed_at TEXT,
            consecutive_correct INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_topics_study_id ON topics(study_id);
        CREATE INDEX IF NOT EXISTS idx_subtopics_topic_id ON subtopics(topic_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_subtopic_id ON attempts(subtopic_id);
        CREATE INDEX IF NOT EXISTS idx_state_next_review ON subtopic_state(next_review_date);

        CREATE TABLE IF NOT EXISTS oauth_clients (
            client_id TEXT PRIMARY KEY,
            client_info TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS oauth_pending_authorizations (
            request_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            state TEXT,
            scopes_json TEXT NOT NULL,
            code_challenge TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            redirect_uri_provided_explicitly INTEGER NOT NULL,
            resource TEXT,
            expires_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
            code TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            code_challenge TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            redirect_uri_provided_explicitly INTEGER NOT NULL,
            resource TEXT,
            subject TEXT,
            expires_at REAL NOT NULL,
            used_at TEXT
        );

        CREATE TABLE IF NOT EXISTS oauth_access_tokens (
            token TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            resource TEXT,
            subject TEXT,
            expires_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
            token TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            subject TEXT,
            expires_at INTEGER NOT NULL
        );
        """
    )
    db.commit()
    _ensure_sqlite_column(db, "studies", "owner_subject", "TEXT NOT NULL DEFAULT 'bem'")
    db.conn.execute("CREATE INDEX IF NOT EXISTS idx_studies_owner_subject ON studies(owner_subject)")
    _record_schema_migrations(db)
    db.commit()


def initialize_postgres_schema(db: Database) -> None:
    # A normal application restart should not reacquire DDL locks for a schema
    # whose migration ledger is already current. This also lets rolling
    # deployments start while an older instance is serving read traffic.
    if _postgres_schema_is_current(db):
        return

    db.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studies (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            owner_subject TEXT NOT NULL DEFAULT 'bem',
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            study_id INTEGER NOT NULL REFERENCES studies(id),
            name TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS subtopics (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            topic_id INTEGER NOT NULL REFERENCES topics(id),
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            subtopic_id INTEGER NOT NULL REFERENCES subtopics(id),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
            model_notes TEXT NOT NULL,
            question_asked TEXT
        );

        CREATE TABLE IF NOT EXISTS subtopic_state (
            subtopic_id INTEGER PRIMARY KEY REFERENCES subtopics(id),
            mastery_level INTEGER NOT NULL DEFAULT 0,
            ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
            interval_days INTEGER NOT NULL DEFAULT 0,
            next_review_date DATE NOT NULL DEFAULT CURRENT_DATE,
            last_reviewed_at TIMESTAMPTZ,
            consecutive_correct INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_topics_study_id ON topics(study_id);
        CREATE INDEX IF NOT EXISTS idx_subtopics_topic_id ON subtopics(topic_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_subtopic_id ON attempts(subtopic_id);
        CREATE INDEX IF NOT EXISTS idx_state_next_review ON subtopic_state(next_review_date);

        CREATE TABLE IF NOT EXISTS oauth_clients (
            client_id TEXT PRIMARY KEY,
            client_info TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS oauth_pending_authorizations (
            request_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            state TEXT,
            scopes_json TEXT NOT NULL,
            code_challenge TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            redirect_uri_provided_explicitly BOOLEAN NOT NULL,
            resource TEXT,
            expires_at DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
            code TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            code_challenge TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            redirect_uri_provided_explicitly BOOLEAN NOT NULL,
            resource TEXT,
            subject TEXT,
            expires_at DOUBLE PRECISION NOT NULL,
            used_at TIMESTAMPTZ
        );

        CREATE TABLE IF NOT EXISTS oauth_access_tokens (
            token TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            resource TEXT,
            subject TEXT,
            expires_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
            token TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            scopes_json TEXT NOT NULL,
            subject TEXT,
            expires_at INTEGER NOT NULL
        );
        """
    )
    db.conn.execute("ALTER TABLE studies ADD COLUMN IF NOT EXISTS owner_subject TEXT NOT NULL DEFAULT 'bem'")
    db.conn.execute("CREATE INDEX IF NOT EXISTS idx_studies_owner_subject ON studies(owner_subject)")
    _record_schema_migrations(db)
    db.commit()


def _postgres_schema_is_current(db: Database) -> bool:
    migration_table = db.conn.execute(
        "SELECT to_regclass('public.schema_migrations') AS schema_migrations"
    ).fetchone()
    if not migration_table or not _row_value(migration_table, "schema_migrations"):
        db.commit()
        return False

    rows = db.conn.execute("SELECT version FROM schema_migrations").fetchall()
    applied = {_row_value(row, "version") for row in rows}
    expected = {version for version, _description in SCHEMA_MIGRATIONS}
    db.commit()
    return expected.issubset(applied)


def applied_schema_migrations(db: Database) -> list[str]:
    """Return applied schema migration ids in order."""

    _ensure_schema_migrations_table(db)
    rows = db.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    versions = [_row_value(row, "version") for row in rows]
    db.conn.commit()
    return versions


def _record_schema_migrations(db: Database) -> None:
    _ensure_schema_migrations_table(db)
    for version, description in SCHEMA_MIGRATIONS:
        row = db.execute("SELECT version FROM schema_migrations WHERE version = ?", (version,)).fetchone()
        if row is None:
            db.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (version, description),
            )


def _ensure_schema_migrations_table(db: Database) -> None:
    timestamp_type = "TIMESTAMPTZ" if db.dialect == "postgres" else "TEXT"
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at {timestamp_type} NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _ensure_sqlite_column(db: Database, table: str, column: str, definition: str) -> None:
    columns = db.conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row["name"] if hasattr(row, "keys") else row[1] for row in columns}
    if column not in names:
        db.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _row_value(row: Any, key: str) -> Any:
    if hasattr(row, "keys"):
        return row[key]
    return row[0]
