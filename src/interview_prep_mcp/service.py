"""Application service backing the MCP tool surface."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .sm2 import ReviewState, update_review_state


class InterviewPrepService:
    def __init__(self, conn, owner_subject: str = "bem"):
        self.conn = conn
        self.owner_subject = _normalize_subject(owner_subject)

    def for_subject(self, owner_subject: str) -> "InterviewPrepService":
        return InterviewPrepService(self.conn, owner_subject)

    def list_studies(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT id, name, created_at
            FROM studies
            WHERE owner_subject = ? AND deleted_at IS NULL
            ORDER BY created_at, id
            """,
            (self.owner_subject,),
        ).fetchall()
        return [_dict(row) for row in rows]

    def create_study(self, name: str) -> Dict[str, Any]:
        _require_text(name, "name")
        cur = self.conn.execute(
            "INSERT INTO studies (owner_subject, name) VALUES (?, ?) RETURNING id",
            (self.owner_subject, name.strip()),
        )
        study_id = _row_value(cur.fetchone(), "id")
        self.conn.commit()
        return self._get_study(study_id)

    def list_topics(self, study_id: int) -> List[Dict[str, Any]]:
        self._ensure_active("studies", study_id)
        rows = self.conn.execute(
            """
            SELECT id, study_id, name, order_index
            FROM topics
            WHERE study_id = ? AND deleted_at IS NULL
            ORDER BY order_index, id
            """,
            (study_id,),
        ).fetchall()
        return [_dict(row) for row in rows]

    def create_topic(self, study_id: int, name: str) -> Dict[str, Any]:
        self._ensure_active("studies", study_id)
        _require_text(name, "name")
        next_order_row = self.conn.execute(
            """
            SELECT COALESCE(MAX(topics.order_index), -1) + 1 AS next_order
            FROM topics
            JOIN studies ON studies.id = topics.study_id
            WHERE topics.study_id = ? AND studies.owner_subject = ?
            """,
            (study_id, self.owner_subject),
        ).fetchone()
        next_order = _row_value(next_order_row, "next_order")
        cur = self.conn.execute(
            "INSERT INTO topics (study_id, name, order_index) VALUES (?, ?, ?) RETURNING id",
            (study_id, name.strip(), next_order),
        )
        topic_id = _row_value(cur.fetchone(), "id")
        self.conn.commit()
        return self._get_topic(topic_id)

    def list_subtopics(self, topic_id: int) -> List[Dict[str, Any]]:
        self._ensure_active("topics", topic_id)
        rows = self.conn.execute(
            """
            SELECT s.id, s.topic_id, s.name, s.description, st.mastery_level,
                   st.next_review_date, st.interval_days, st.consecutive_correct
            FROM subtopics s
            JOIN subtopic_state st ON st.subtopic_id = s.id
            WHERE s.topic_id = ? AND s.deleted_at IS NULL
            ORDER BY s.id
            """,
            (topic_id,),
        ).fetchall()
        return [_dict(row) for row in rows]

    def create_subtopic(
        self, topic_id: int, name: str, description: Optional[str] = None
    ) -> Dict[str, Any]:
        self._ensure_active("topics", topic_id)
        _require_text(name, "name")
        cur = self.conn.execute(
            "INSERT INTO subtopics (topic_id, name, description) VALUES (?, ?, ?) RETURNING id",
            (topic_id, name.strip(), _clean_optional_text(description)),
        )
        subtopic_id = _row_value(cur.fetchone(), "id")
        self.conn.execute(
            "INSERT INTO subtopic_state (subtopic_id, next_review_date) VALUES (?, ?)",
            (subtopic_id, date.today().isoformat()),
        )
        self.conn.commit()
        return self._get_subtopic(subtopic_id)

    def update_subtopic(
        self,
        subtopic_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_active("subtopics", subtopic_id)
        if name is None and description is None:
            raise ValueError("provide name or description")
        if name is not None:
            _require_text(name, "name")
            self.conn.execute(
                "UPDATE subtopics SET name = ? WHERE id = ?",
                (name.strip(), subtopic_id),
            )
        if description is not None:
            self.conn.execute(
                "UPDATE subtopics SET description = ? WHERE id = ?",
                (_clean_optional_text(description), subtopic_id),
            )
        self.conn.commit()
        return self._get_subtopic(subtopic_id)

    def delete_study(self, id: int) -> Dict[str, Any]:
        self._soft_delete("studies", id)
        return {"id": id, "deleted": True}

    def delete_topic(self, id: int) -> Dict[str, Any]:
        self._soft_delete("topics", id)
        return {"id": id, "deleted": True}

    def delete_subtopic(self, id: int) -> Dict[str, Any]:
        self._soft_delete("subtopics", id)
        return {"id": id, "deleted": True}

    def log_attempt(
        self,
        subtopic_id: int,
        score: int,
        model_notes: str,
        question_asked: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_active("subtopics", subtopic_id)
        _require_text(model_notes, "model_notes")
        if score < 1 or score > 5:
            raise ValueError("score must be between 1 and 5")

        current = self._get_state(subtopic_id)
        today = date.today()
        update = update_review_state(
            ReviewState(
                mastery_level=current["mastery_level"],
                ease_factor=current["ease_factor"],
                interval_days=current["interval_days"],
                consecutive_correct=current["consecutive_correct"],
            ),
            score,
            today,
        )

        cur = self.conn.execute(
            """
            INSERT INTO attempts (subtopic_id, score, model_notes, question_asked)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (subtopic_id, score, model_notes.strip(), _clean_optional_text(question_asked)),
        )
        attempt_id = _row_value(cur.fetchone(), "id")
        self.conn.execute(
            """
            UPDATE subtopic_state
            SET mastery_level = ?,
                ease_factor = ?,
                interval_days = ?,
                next_review_date = ?,
                last_reviewed_at = CURRENT_TIMESTAMP,
                consecutive_correct = ?
            WHERE subtopic_id = ?
            """,
            (
                update.mastery_level,
                update.ease_factor,
                update.interval_days,
                update.next_review_date.isoformat(),
                update.consecutive_correct,
                subtopic_id,
            ),
        )
        self.conn.commit()
        return {
            "attempt_id": attempt_id,
            "subtopic_id": subtopic_id,
            "score": score,
            "mastery_level": update.mastery_level,
            "ease_factor": update.ease_factor,
            "interval_days": update.interval_days,
            "next_review_date": update.next_review_date.isoformat(),
            "consecutive_correct": update.consecutive_correct,
            "summary": update.next_review_summary,
        }

    def get_due_subtopics(
        self, study_id: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        today = date.today().isoformat()
        params: List[Any] = [today, today, self.owner_subject]
        study_filter = ""
        if study_id is not None:
            self._ensure_active("studies", study_id)
            study_filter = "AND topics.study_id = ?"
            params.append(study_id)

        limit_clause = ""
        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be at least 1")
            limit_clause = "LIMIT ?"
            params.append(limit)

        if self.conn.dialect == "postgres":
            overdue_expr = "((?::date) - st.next_review_date)::int"
        else:
            overdue_expr = "CAST(julianday(?) - julianday(st.next_review_date) AS INTEGER)"

        rows = self.conn.execute(
            f"""
            SELECT subtopics.id AS subtopic_id,
                   subtopics.name AS subtopic_name,
                   subtopics.description,
                   topics.id AS topic_id,
                   topics.name AS topic_name,
                   studies.id AS study_id,
                   studies.name AS study_name,
                   st.mastery_level,
                   st.interval_days,
                   st.next_review_date,
                   {overdue_expr} AS overdue_days
            FROM subtopic_state st
            JOIN subtopics ON subtopics.id = st.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE st.next_review_date <= ?
              AND subtopics.deleted_at IS NULL
              AND topics.deleted_at IS NULL
              AND studies.deleted_at IS NULL
              AND studies.owner_subject = ?
              {study_filter}
            ORDER BY overdue_days DESC, st.next_review_date ASC, st.mastery_level ASC, subtopics.id
            {limit_clause}
            """,
            params,
        ).fetchall()
        return [_dict(row) for row in rows]

    def get_subtopic_history(self, subtopic_id: int) -> Dict[str, Any]:
        subtopic = self._get_subtopic(subtopic_id)
        attempts = self.conn.execute(
            """
            SELECT attempts.id, attempts.timestamp, attempts.score, attempts.model_notes, attempts.question_asked
            FROM attempts
            JOIN subtopics ON subtopics.id = attempts.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE attempts.subtopic_id = ? AND studies.owner_subject = ?
            ORDER BY attempts.timestamp DESC, attempts.id DESC
            """,
            (subtopic_id, self.owner_subject),
        ).fetchall()
        scores = [row["score"] for row in attempts]
        trend = {
            "attempt_count": len(scores),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "latest_score": scores[0] if scores else None,
        }
        return {
            "subtopic": subtopic,
            "state": self._get_state(subtopic_id),
            "trend": trend,
            "attempts": [_dict(row) for row in attempts],
        }

    def export_my_data(self) -> Dict[str, Any]:
        """Return all study data owned by the current subject."""

        studies = self.conn.execute(
            """
            SELECT id, owner_subject, name, created_at, deleted_at
            FROM studies
            WHERE owner_subject = ?
            ORDER BY created_at, id
            """,
            (self.owner_subject,),
        ).fetchall()
        topics = self.conn.execute(
            """
            SELECT topics.id, topics.study_id, topics.name, topics.order_index,
                   topics.created_at, topics.deleted_at
            FROM topics
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            ORDER BY topics.study_id, topics.order_index, topics.id
            """,
            (self.owner_subject,),
        ).fetchall()
        subtopics = self.conn.execute(
            """
            SELECT subtopics.id, subtopics.topic_id, subtopics.name, subtopics.description,
                   subtopics.created_at, subtopics.deleted_at
            FROM subtopics
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            ORDER BY subtopics.topic_id, subtopics.id
            """,
            (self.owner_subject,),
        ).fetchall()
        attempts = self.conn.execute(
            """
            SELECT attempts.id, attempts.subtopic_id, attempts.timestamp, attempts.score,
                   attempts.model_notes, attempts.question_asked
            FROM attempts
            JOIN subtopics ON subtopics.id = attempts.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            ORDER BY attempts.timestamp, attempts.id
            """,
            (self.owner_subject,),
        ).fetchall()
        states = self.conn.execute(
            """
            SELECT subtopic_state.subtopic_id, subtopic_state.mastery_level,
                   subtopic_state.ease_factor, subtopic_state.interval_days,
                   subtopic_state.next_review_date, subtopic_state.last_reviewed_at,
                   subtopic_state.consecutive_correct
            FROM subtopic_state
            JOIN subtopics ON subtopics.id = subtopic_state.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            ORDER BY subtopic_state.subtopic_id
            """,
            (self.owner_subject,),
        ).fetchall()
        return {
            "owner_subject": self.owner_subject,
            "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "studies": [_dict(row) for row in studies],
            "topics": [_dict(row) for row in topics],
            "subtopics": [_dict(row) for row in subtopics],
            "attempts": [_dict(row) for row in attempts],
            "subtopic_state": [_dict(row) for row in states],
        }

    def delete_my_data(self, confirmation: str) -> Dict[str, Any]:
        """Hard-delete all study data owned by the current subject."""

        if confirmation != "DELETE MY STUDY DATA":
            raise ValueError('confirmation must be exactly "DELETE MY STUDY DATA"')

        counts = self._owner_counts()
        subtopic_ids = self._owned_subtopic_ids()
        topic_ids = self._owned_topic_ids()
        study_ids = self._owned_study_ids()

        self._delete_by_ids("attempts", "subtopic_id", subtopic_ids)
        self._delete_by_ids("subtopic_state", "subtopic_id", subtopic_ids)
        self._delete_by_ids("subtopics", "id", subtopic_ids)
        self._delete_by_ids("topics", "id", topic_ids)
        self._delete_by_ids("studies", "id", study_ids)
        self.conn.commit()
        return {
            "deleted": True,
            "deleted_counts": counts,
        }

    def _get_study(self, id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT id, name, created_at
            FROM studies
            WHERE id = ? AND owner_subject = ? AND deleted_at IS NULL
            """,
            (id, self.owner_subject),
        ).fetchone()
        if row is None:
            raise ValueError(f"study not found: {id}")
        return _dict(row)

    def _get_topic(self, id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT topics.id, topics.study_id, topics.name, topics.order_index
            FROM topics
            JOIN studies ON studies.id = topics.study_id
            WHERE topics.id = ?
              AND studies.owner_subject = ?
              AND topics.deleted_at IS NULL
              AND studies.deleted_at IS NULL
            """,
            (id, self.owner_subject),
        ).fetchone()
        if row is None:
            raise ValueError(f"topic not found: {id}")
        return _dict(row)

    def _get_subtopic(self, id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT s.id, s.topic_id, s.name, s.description, st.mastery_level,
                   st.ease_factor, st.interval_days, st.next_review_date,
                   st.last_reviewed_at, st.consecutive_correct
            FROM subtopics s
            JOIN subtopic_state st ON st.subtopic_id = s.id
            JOIN topics t ON t.id = s.topic_id
            JOIN studies st_parent ON st_parent.id = t.study_id
            WHERE s.id = ?
              AND st_parent.owner_subject = ?
              AND s.deleted_at IS NULL
              AND t.deleted_at IS NULL
              AND st_parent.deleted_at IS NULL
            """,
            (id, self.owner_subject),
        ).fetchone()
        if row is None:
            raise ValueError(f"subtopic not found: {id}")
        return _dict(row)

    def _get_state(self, subtopic_id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT subtopic_id, mastery_level, ease_factor, interval_days,
                   next_review_date, last_reviewed_at, consecutive_correct
            FROM subtopic_state
            JOIN subtopics ON subtopics.id = subtopic_state.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE subtopic_state.subtopic_id = ?
              AND studies.owner_subject = ?
              AND subtopics.deleted_at IS NULL
              AND topics.deleted_at IS NULL
              AND studies.deleted_at IS NULL
            """,
            (subtopic_id, self.owner_subject),
        ).fetchone()
        if row is None:
            raise ValueError(f"subtopic state not found: {subtopic_id}")
        return _dict(row)

    def _ensure_active(self, table: str, id: int) -> None:
        if table == "studies":
            sql = "SELECT id FROM studies WHERE id = ? AND owner_subject = ? AND deleted_at IS NULL"
        elif table == "topics":
            sql = """
            SELECT topics.id
            FROM topics
            JOIN studies ON studies.id = topics.study_id
            WHERE topics.id = ?
              AND studies.owner_subject = ?
              AND topics.deleted_at IS NULL
              AND studies.deleted_at IS NULL
            """
        elif table == "subtopics":
            sql = """
            SELECT subtopics.id
            FROM subtopics
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE subtopics.id = ?
              AND studies.owner_subject = ?
              AND subtopics.deleted_at IS NULL
              AND topics.deleted_at IS NULL
              AND studies.deleted_at IS NULL
            """
        else:
            raise ValueError(f"unsupported table: {table}")
        row = self.conn.execute(sql, (id, self.owner_subject)).fetchone()
        if row is None:
            singular = table[:-1] if table.endswith("s") else table
            raise ValueError(f"{singular} not found: {id}")

    def _soft_delete(self, table: str, id: int) -> None:
        self._ensure_active(table, id)
        self.conn.execute(
            f"UPDATE {table} SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (id,),
        )
        self.conn.commit()

    def _owner_counts(self) -> Dict[str, int]:
        return {
            "studies": len(self._owned_study_ids()),
            "topics": len(self._owned_topic_ids()),
            "subtopics": len(self._owned_subtopic_ids()),
            "attempts": self._count_owned_attempts(),
            "subtopic_state": len(self._owned_subtopic_ids()),
        }

    def _owned_study_ids(self) -> List[int]:
        rows = self.conn.execute("SELECT id FROM studies WHERE owner_subject = ?", (self.owner_subject,)).fetchall()
        return [_row_value(row, "id") for row in rows]

    def _owned_topic_ids(self) -> List[int]:
        rows = self.conn.execute(
            """
            SELECT topics.id
            FROM topics
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            """,
            (self.owner_subject,),
        ).fetchall()
        return [_row_value(row, "id") for row in rows]

    def _owned_subtopic_ids(self) -> List[int]:
        rows = self.conn.execute(
            """
            SELECT subtopics.id
            FROM subtopics
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            """,
            (self.owner_subject,),
        ).fetchall()
        return [_row_value(row, "id") for row in rows]

    def _count_owned_attempts(self) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM attempts
            JOIN subtopics ON subtopics.id = attempts.subtopic_id
            JOIN topics ON topics.id = subtopics.topic_id
            JOIN studies ON studies.id = topics.study_id
            WHERE studies.owner_subject = ?
            """,
            (self.owner_subject,),
        ).fetchone()
        return int(_row_value(row, "count"))

    def _delete_by_ids(self, table: str, column: str, ids: List[int]) -> None:
        if not ids:
            return
        placeholders = ", ".join("?" for _ in ids)
        self.conn.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", ids)


def _dict(row) -> Dict[str, Any]:
    values = row if isinstance(row, dict) else {key: row[key] for key in row.keys()}
    return {key: _serialize_value(value) for key, value in values.items()}


def _row_value(row, key: str) -> Any:
    if isinstance(row, dict):
        return row[key]
    if hasattr(row, "keys") and key in row.keys():
        return row[key]
    return row[0]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _require_text(value: str, field_name: str) -> None:
    if value is None or not value.strip():
        raise ValueError(f"{field_name} is required")


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalize_subject(value: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError("owner subject is required")
    return str(value).strip()
