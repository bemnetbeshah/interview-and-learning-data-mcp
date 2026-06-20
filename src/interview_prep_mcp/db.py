"""SQLite persistence setup."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def connect(db_path: PathLike) -> sqlite3.Connection:
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        """
    )
    conn.commit()
