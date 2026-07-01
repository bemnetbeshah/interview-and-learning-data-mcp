import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interview_prep_mcp.server import build_mcp


class McpContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_registered_tools_match_prd_surface(self):
        expected_tools = {
            "list_studies",
            "list_topics",
            "list_subtopics",
            "get_due_subtopics",
            "get_subtopic_history",
            "export_my_data",
            "delete_my_data",
            "log_attempt",
            "create_study",
            "create_topic",
            "create_subtopic",
            "update_subtopic",
            "delete_study",
            "delete_topic",
            "delete_subtopic",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict("os.environ", {"INTERVIEW_PREP_DB_PATH": db_path}, clear=True):
                mcp = build_mcp()

        tool_names = {tool.name for tool in await mcp.list_tools()}
        self.assertEqual(tool_names, expected_tools)

    async def test_tools_include_review_relevant_annotations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict("os.environ", {"INTERVIEW_PREP_DB_PATH": db_path}, clear=True):
                mcp = build_mcp()

        tools = {tool.name: tool for tool in await mcp.list_tools()}

        for name in [
            "list_studies",
            "list_topics",
            "list_subtopics",
            "get_due_subtopics",
            "get_subtopic_history",
            "export_my_data",
        ]:
            self.assertTrue(tools[name].annotations.readOnlyHint, name)
            self.assertFalse(tools[name].annotations.destructiveHint, name)
            self.assertFalse(tools[name].annotations.openWorldHint, name)

        for name in [
            "create_study",
            "create_topic",
            "create_subtopic",
            "update_subtopic",
            "log_attempt",
            "delete_study",
            "delete_topic",
            "delete_subtopic",
        ]:
            self.assertFalse(tools[name].annotations.readOnlyHint, name)
            self.assertFalse(tools[name].annotations.destructiveHint, name)
            self.assertFalse(tools[name].annotations.openWorldHint, name)

        self.assertFalse(tools["delete_my_data"].annotations.readOnlyHint)
        self.assertTrue(tools["delete_my_data"].annotations.destructiveHint)
        self.assertFalse(tools["delete_my_data"].annotations.openWorldHint)

    async def test_tool_input_schemas_are_minimal_and_review_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict("os.environ", {"INTERVIEW_PREP_DB_PATH": db_path}, clear=True):
                mcp = build_mcp()

        forbidden_args = {"user_id", "owner_subject", "subject", "access_token", "token", "password", "api_key"}
        expected_args = {
            "list_studies": set(),
            "list_topics": {"study_id"},
            "list_subtopics": {"topic_id"},
            "get_due_subtopics": {"study_id", "limit"},
            "get_subtopic_history": {"subtopic_id"},
            "export_my_data": set(),
            "delete_my_data": {"confirmation"},
            "log_attempt": {"subtopic_id", "score", "model_notes", "question_asked"},
            "create_study": {"name"},
            "create_topic": {"study_id", "name"},
            "create_subtopic": {"topic_id", "name", "description"},
            "update_subtopic": {"subtopic_id", "name", "description"},
            "delete_study": {"id"},
            "delete_topic": {"id"},
            "delete_subtopic": {"id"},
        }

        tools = {tool.name: tool for tool in await mcp.list_tools()}
        for name, expected in expected_args.items():
            schema = tools[name].inputSchema
            actual = set(schema.get("properties", {}))
            self.assertEqual(actual, expected, name)
            self.assertFalse(actual & forbidden_args, name)

        delete_confirmation = tools["delete_my_data"].inputSchema["properties"]["confirmation"]["description"]
        score_schema = tools["log_attempt"].inputSchema["properties"]["score"]
        study_id_description = tools["list_topics"].inputSchema["properties"]["study_id"]["description"]

        self.assertIn("DELETE MY STUDY DATA", delete_confirmation)
        self.assertEqual(score_schema["minimum"], 1)
        self.assertEqual(score_schema["maximum"], 5)
        self.assertIn("never a user id", study_id_description)

    async def test_server_initialization_metadata_guides_public_clients(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict(
                "os.environ",
                {
                    "INTERVIEW_PREP_DB_PATH": db_path,
                    "MCP_PUBLIC_BASE_URL": "https://study.example.com",
                },
                clear=True,
            ):
                mcp = build_mcp()

        self.assertEqual(str(mcp.website_url).rstrip("/"), "https://study.example.com")
        self.assertIn("get_due_subtopics", mcp.instructions)
        self.assertIn("log_attempt", mcp.instructions)
        self.assertIn("Do not ask for or pass a user id", mcp.instructions)
        self.assertIn("delete_my_data", mcp.instructions)

    async def test_registered_prompts_cover_primary_workflows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict("os.environ", {"INTERVIEW_PREP_DB_PATH": db_path}, clear=True):
                mcp = build_mcp()

        prompts = {prompt.name: prompt for prompt in await mcp.list_prompts()}

        self.assertEqual(
            set(prompts),
            {"review_due_items", "create_study_plan", "review_progress", "account_data_request"},
        )
        self.assertEqual([arg.name for arg in prompts["create_study_plan"].arguments], ["study_name"])
        self.assertTrue(prompts["create_study_plan"].arguments[0].required)
        self.assertEqual([arg.name for arg in prompts["account_data_request"].arguments], ["action"])

    async def test_prompts_render_public_safe_tool_guidance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.sqlite3")
            with patch.dict("os.environ", {"INTERVIEW_PREP_DB_PATH": db_path}, clear=True):
                mcp = build_mcp()

        review_prompt = await mcp.get_prompt("review_due_items", {"study_name": "AI Engineering"})
        account_prompt = await mcp.get_prompt("account_data_request", {"action": "delete my data"})

        review_text = review_prompt.messages[0].content.text
        account_text = account_prompt.messages[0].content.text
        self.assertIn("get_due_subtopics", review_text)
        self.assertIn("log_attempt", review_text)
        self.assertIn("1-5 SM-2", review_text)
        self.assertIn("export_my_data", account_text)
        self.assertIn("DELETE MY STUDY DATA", account_text)
        self.assertNotIn("owner_subject", review_text + account_text)
