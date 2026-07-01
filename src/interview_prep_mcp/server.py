"""FastMCP server entrypoint."""

from __future__ import annotations

from typing import Annotated, Optional

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.types import ToolAnnotations
from pydantic import Field

from .auth import build_auth_components
from .config import load_settings
from .db import connect
from .oauth import handle_oauth_approval
from .public_pages import render_health, render_home, render_privacy, render_support, render_terms
from .rate_limit import InMemoryRateLimiter
from .service import InterviewPrepService

READ_ONLY_TOOL = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE_TOOL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
SOFT_DELETE_TOOL = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
HARD_DELETE_TOOL = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
StudyId = Annotated[int, Field(description="Study id returned by list_studies or create_study; never a user id.")]
TopicId = Annotated[int, Field(description="Topic id returned by list_topics or create_topic; never a user id.")]
SubtopicId = Annotated[int, Field(description="Subtopic id returned by list_subtopics or create_subtopic; never a user id.")]
EntityId = Annotated[int, Field(description="Id of the study, topic, or subtopic to soft-delete for the authenticated user.")]
StudyName = Annotated[str, Field(description="Human-readable study name.")]
TopicName = Annotated[str, Field(description="Human-readable topic name.")]
SubtopicName = Annotated[str, Field(description="Human-readable subtopic name.")]
SubtopicDescription = Annotated[Optional[str], Field(description="Optional description of what mastery looks like.")]
ReviewLimit = Annotated[Optional[int], Field(description="Optional maximum number of due subtopics to return.")]
AttemptScore = Annotated[int, Field(ge=1, le=5, description="SM-2 recall score: 1 blackout, 2 incorrect/familiar, 3 effortful correct, 4 mostly correct, 5 fluent.")]
ModelNotes = Annotated[str, Field(description="Concise grading notes from the reviewing assistant.")]
QuestionAsked = Annotated[Optional[str], Field(description="Optional exact question or prompt used for the attempt.")]
DeleteConfirmation = Annotated[str, Field(description='Must be exactly "DELETE MY STUDY DATA" to hard-delete all study data for the authenticated user.')]
SERVER_INSTRUCTIONS = """Use this server as the source of truth for the authenticated user's study progress.

Start review sessions by calling get_due_subtopics unless the user asks for a specific study, topic, or subtopic. Quiz one subtopic at a time. After each answer, grade recall on the 1-5 SM-2 scale and call log_attempt with concise notes and the question asked.

Use create_study, create_topic, create_subtopic, and update_subtopic when the user asks to manage study material. Use get_subtopic_history before making claims about long-term progress or repeated weak spots.

Do not ask for or pass a user id. The server derives account scope from authentication. Routine responses should not expose auth subjects, tokens, secrets, request ids, or internal diagnostics. Use export_my_data for explicit account export requests. Use delete_my_data only when the user explicitly asks to delete all stored study data and confirms the required phrase."""


def build_service() -> InterviewPrepService:
    settings = load_settings()
    return InterviewPrepService(
        connect(settings.db_path, settings.database_url),
        owner_subject=settings.default_subject,
    )


def build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP SDK is not installed. Run `python -m pip install -e .` first."
        ) from exc

    settings = load_settings()
    db = connect(settings.db_path, settings.database_url)
    service = InterviewPrepService(db, owner_subject=settings.default_subject)
    rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)
    auth, token_verifier, oauth_provider = build_auth_components(settings, db)
    mcp = FastMCP(
        "Interview Prep MCP",
        instructions=SERVER_INSTRUCTIONS,
        website_url=settings.public_base_url,
        host=settings.host,
        port=settings.port,
        auth=auth,
        token_verifier=token_verifier,
        auth_server_provider=oauth_provider,
    )

    if oauth_provider is not None:

        @mcp.custom_route("/oauth/approve", methods=["GET", "POST"], include_in_schema=False)
        async def oauth_approval(request):
            return await handle_oauth_approval(request, oauth_provider)

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    async def public_home(request):
        return render_home(settings)

    @mcp.custom_route("/privacy", methods=["GET"], include_in_schema=False)
    async def public_privacy(request):
        return render_privacy(settings)

    @mcp.custom_route("/terms", methods=["GET"], include_in_schema=False)
    async def public_terms(request):
        return render_terms(settings)

    @mcp.custom_route("/support", methods=["GET"], include_in_schema=False)
    async def public_support(request):
        return render_support(settings)

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def public_health(request):
        return render_health(settings)

    @mcp.prompt(
        title="Review Due Study Items",
        description="Start a spaced-repetition review session using due subtopics.",
    )
    def review_due_items(study_name: Optional[str] = None):
        """Prompt a client to run the due-review workflow."""
        scope = f" for the study named {study_name!r}" if study_name else ""
        return (
            f"Start an Interview Prep MCP review session{scope}. "
            "Call get_due_subtopics first, choose one due subtopic at a time, quiz me conversationally, "
            "then call log_attempt after each answer with a 1-5 SM-2 score, concise model_notes, "
            "and the question_asked. Use get_subtopic_history when you need trend context."
        )

    @mcp.prompt(
        title="Create Study Plan",
        description="Create or extend a study hierarchy through MCP tools.",
    )
    def create_study_plan(study_name: str):
        """Prompt a client to create a study plan using hierarchy tools."""
        return (
            f"Help me create or extend the study plan for {study_name!r}. "
            "First call list_studies to see whether it already exists. If needed, use create_study. "
            "Then propose a concise topic and subtopic hierarchy and use create_topic and create_subtopic "
            "only for items I approve. Do not pass a user id."
        )

    @mcp.prompt(
        title="Review Progress",
        description="Inspect study progress and weak spots without changing data.",
    )
    def review_progress(study_name: Optional[str] = None):
        """Prompt a client to summarize progress from read-only tools."""
        scope = f" for {study_name!r}" if study_name else ""
        return (
            f"Summarize my study progress{scope}. Use list_studies, list_topics, list_subtopics, "
            "get_due_subtopics, and get_subtopic_history as needed. Do not invent trends from memory; "
            "base claims on tool results and keep the summary focused on due work, weak spots, and recent improvement."
        )

    @mcp.prompt(
        title="Account Data Request",
        description="Handle export or deletion requests with the correct account-data tools.",
    )
    def account_data_request(action: str):
        """Prompt a client to handle export and deletion requests safely."""
        return (
            f"Handle this account data request: {action!r}. "
            "If the user wants an export, call export_my_data and summarize the categories returned. "
            "If the user wants deletion, explain that delete_my_data hard-deletes all study data for the authenticated "
            "account and requires the exact confirmation phrase DELETE MY STUDY DATA. Only call delete_my_data after "
            "the user provides that exact phrase."
        )

    def current_service() -> InterviewPrepService:
        token = get_access_token()
        subject = token.subject if token and token.subject else settings.default_subject
        limit = rate_limiter.check(subject)
        if not limit.allowed:
            raise ValueError(f"rate limit exceeded; retry after {limit.retry_after_seconds} seconds")
        return service.for_subject(subject)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def list_studies():
        """Return all active study areas."""
        return current_service().list_studies()

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def list_topics(study_id: StudyId):
        """Return active topics within a study."""
        return current_service().list_topics(study_id)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def list_subtopics(topic_id: TopicId):
        """Return active subtopics within a topic with current mastery state."""
        return current_service().list_subtopics(topic_id)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def get_due_subtopics(study_id: Annotated[Optional[int], Field(description="Optional study id returned by list_studies or create_study; never a user id.")] = None, limit: ReviewLimit = None):
        """Return the spaced-repetition queue sorted by overdue-ness."""
        return current_service().get_due_subtopics(study_id=study_id, limit=limit)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def get_subtopic_history(subtopic_id: SubtopicId):
        """Return attempts, trend, and state for one subtopic."""
        return current_service().get_subtopic_history(subtopic_id)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def export_my_data():
        """Export all study data for the authenticated user."""
        return current_service().export_my_data()

    @mcp.tool(annotations=HARD_DELETE_TOOL)
    def delete_my_data(confirmation: DeleteConfirmation):
        """Hard-delete all study data for the authenticated user after explicit confirmation."""
        return current_service().delete_my_data(confirmation)

    @mcp.tool(annotations=WRITE_TOOL)
    def log_attempt(
        subtopic_id: SubtopicId,
        score: AttemptScore,
        model_notes: ModelNotes,
        question_asked: QuestionAsked = None,
    ):
        """Record a quiz attempt and update SM-2 scheduling state."""
        return current_service().log_attempt(
            subtopic_id=subtopic_id,
            score=score,
            model_notes=model_notes,
            question_asked=question_asked,
        )

    @mcp.tool(annotations=WRITE_TOOL)
    def create_study(name: StudyName):
        """Add a new study area."""
        return current_service().create_study(name)

    @mcp.tool(annotations=WRITE_TOOL)
    def create_topic(study_id: StudyId, name: TopicName):
        """Add a topic under a study."""
        return current_service().create_topic(study_id, name)

    @mcp.tool(annotations=WRITE_TOOL)
    def create_subtopic(topic_id: TopicId, name: SubtopicName, description: SubtopicDescription = None):
        """Add a subtopic under a topic."""
        return current_service().create_subtopic(topic_id, name, description)

    @mcp.tool(annotations=WRITE_TOOL)
    def update_subtopic(
        subtopic_id: SubtopicId,
        name: Annotated[Optional[str], Field(description="Optional replacement subtopic name.")] = None,
        description: SubtopicDescription = None,
    ):
        """Edit a subtopic's name or description."""
        return current_service().update_subtopic(subtopic_id, name, description)

    @mcp.tool(annotations=SOFT_DELETE_TOOL)
    def delete_study(id: EntityId):
        """Soft-delete a study while preserving history."""
        return current_service().delete_study(id)

    @mcp.tool(annotations=SOFT_DELETE_TOOL)
    def delete_topic(id: EntityId):
        """Soft-delete a topic while preserving history."""
        return current_service().delete_topic(id)

    @mcp.tool(annotations=SOFT_DELETE_TOOL)
    def delete_subtopic(id: EntityId):
        """Soft-delete a subtopic while preserving history."""
        return current_service().delete_subtopic(id)

    return mcp


def main() -> None:
    settings = load_settings()
    mcp = build_mcp()
    mcp.run(transport=settings.transport)


if __name__ == "__main__":
    main()
