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
