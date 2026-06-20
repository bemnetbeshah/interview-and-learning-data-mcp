"""FastMCP server entrypoint."""

from __future__ import annotations

from typing import Optional

from .config import load_settings
from .db import connect
from .service import InterviewPrepService


def build_service() -> InterviewPrepService:
    settings = load_settings()
    return InterviewPrepService(connect(settings.db_path))


def build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP SDK is not installed. Run `python -m pip install -e .` first."
        ) from exc

    service = build_service()
    mcp = FastMCP("Interview Prep MCP")

    @mcp.tool()
    def list_studies():
        """Return all active study areas."""
        return service.list_studies()

    @mcp.tool()
    def list_topics(study_id: int):
        """Return active topics within a study."""
        return service.list_topics(study_id)

    @mcp.tool()
    def list_subtopics(topic_id: int):
        """Return active subtopics within a topic with current mastery state."""
        return service.list_subtopics(topic_id)

    @mcp.tool()
    def get_due_subtopics(study_id: Optional[int] = None, limit: Optional[int] = None):
        """Return the spaced-repetition queue sorted by overdue-ness."""
        return service.get_due_subtopics(study_id=study_id, limit=limit)

    @mcp.tool()
    def get_subtopic_history(subtopic_id: int):
        """Return attempts, trend, and state for one subtopic."""
        return service.get_subtopic_history(subtopic_id)

    @mcp.tool()
    def log_attempt(
        subtopic_id: int,
        score: int,
        model_notes: str,
        question_asked: Optional[str] = None,
    ):
        """Record a quiz attempt and update SM-2 scheduling state."""
        return service.log_attempt(
            subtopic_id=subtopic_id,
            score=score,
            model_notes=model_notes,
            question_asked=question_asked,
        )

    @mcp.tool()
    def create_study(name: str):
        """Add a new study area."""
        return service.create_study(name)

    @mcp.tool()
    def create_topic(study_id: int, name: str):
        """Add a topic under a study."""
        return service.create_topic(study_id, name)

    @mcp.tool()
    def create_subtopic(topic_id: int, name: str, description: Optional[str] = None):
        """Add a subtopic under a topic."""
        return service.create_subtopic(topic_id, name, description)

    @mcp.tool()
    def update_subtopic(
        subtopic_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Edit a subtopic's name or description."""
        return service.update_subtopic(subtopic_id, name, description)

    @mcp.tool()
    def delete_study(id: int):
        """Soft-delete a study while preserving history."""
        return service.delete_study(id)

    @mcp.tool()
    def delete_topic(id: int):
        """Soft-delete a topic while preserving history."""
        return service.delete_topic(id)

    @mcp.tool()
    def delete_subtopic(id: int):
        """Soft-delete a subtopic while preserving history."""
        return service.delete_subtopic(id)

    return mcp


def main() -> None:
    settings = load_settings()
    mcp = build_mcp()
    mcp.run(transport=settings.transport)


if __name__ == "__main__":
    main()
