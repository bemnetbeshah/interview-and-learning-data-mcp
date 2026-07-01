import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_mcp_contract_snapshot import build_contract_snapshot, validate_contract_snapshot
from scripts.manage_public_urls import current_public_base_url


class McpContractSnapshotTests(unittest.TestCase):
    def test_contract_snapshot_contains_tools_prompts_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = asyncio.run(build_contract_snapshot(Path(temp_dir)))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        validate_contract_snapshot(snapshot)
        self.assertIn("get_due_subtopics", snapshot["server"]["instructions"])
        self.assertEqual(snapshot["server"]["website_url"].rstrip("/"), current_public_base_url())
        tool_names = {tool["name"] for tool in snapshot["tools"]}
        prompt_names = {prompt["name"] for prompt in snapshot["prompts"]}
        self.assertIn("delete_my_data", tool_names)
        self.assertIn("review_due_items", prompt_names)

    def test_contract_snapshot_validation_rejects_missing_tool(self):
        snapshot = {
            "server": {"instructions": "get_due_subtopics"},
            "tools": [],
            "prompts": [
                {"name": "review_due_items"},
                {"name": "create_study_plan"},
                {"name": "review_progress"},
                {"name": "account_data_request"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "unexpected tool contract"):
            validate_contract_snapshot(snapshot)

    def test_contract_snapshot_validation_rejects_forbidden_auth_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = asyncio.run(build_contract_snapshot(Path(temp_dir)))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        snapshot["tools"][0]["input_schema"]["properties"]["user_id"] = {"type": "string"}

        with self.assertRaisesRegex(ValueError, "forbidden auth/account inputs"):
            validate_contract_snapshot(snapshot)

    def test_contract_snapshot_validation_rejects_read_tool_without_read_only_hint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = asyncio.run(build_contract_snapshot(Path(temp_dir)))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        for tool in snapshot["tools"]:
            if tool["name"] == "list_studies":
                tool["annotations"]["readOnlyHint"] = False
                break

        with self.assertRaisesRegex(ValueError, "list_studies must be marked read-only"):
            validate_contract_snapshot(snapshot)
