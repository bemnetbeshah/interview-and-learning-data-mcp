import copy
import unittest

from scripts.diff_mcp_contract import diff_contracts


class McpContractDiffTests(unittest.TestCase):
    def test_added_optional_tool_field_requires_review_but_is_not_breaking(self):
        old = _snapshot()
        new = copy.deepcopy(old)
        new["tools"][0]["input_schema"]["properties"]["limit"] = {
            "anyOf": [{"type": "integer"}, {"type": "null"}],
            "default": None,
            "description": "Optional limit.",
        }

        diffs = diff_contracts(old, new)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].severity, "review")
        self.assertFalse(diffs[0].breaking)

    def test_removed_tool_is_breaking(self):
        old = _snapshot()
        new = copy.deepcopy(old)
        new["tools"] = []

        diffs = diff_contracts(old, new)

        self.assertTrue(any(diff.breaking and diff.path == "tools.list_studies" for diff in diffs))

    def test_existing_optional_field_becoming_required_is_breaking(self):
        old = _snapshot()
        old["tools"][0]["input_schema"]["properties"]["limit"] = {"type": "integer"}
        new = copy.deepcopy(old)
        new["tools"][0]["input_schema"]["required"] = ["limit"]

        diffs = diff_contracts(old, new)

        self.assertTrue(any(diff.breaking and diff.path.endswith("required.limit") for diff in diffs))

    def test_base_url_change_is_breaking(self):
        old = _snapshot()
        new = copy.deepcopy(old)
        new["server"]["website_url"] = "https://new.example.com"

        diffs = diff_contracts(old, new)

        self.assertTrue(any(diff.breaking and diff.path == "server.website_url" for diff in diffs))

    def test_prompt_title_and_description_changes_require_review(self):
        old = _snapshot()
        new = copy.deepcopy(old)
        new["prompts"][0]["title"] = "Review Due Items"
        new["prompts"][0]["description"] = "Changed description."

        diffs = diff_contracts(old, new)

        self.assertTrue(any(diff.severity == "review" and diff.path == "prompts.review_due_items.title" for diff in diffs))
        self.assertTrue(
            any(diff.severity == "review" and diff.path == "prompts.review_due_items.description" for diff in diffs)
        )


def _snapshot():
    return {
        "server": {
            "website_url": "https://study.example.com",
            "instructions": "Use get_due_subtopics, log_attempt, and delete_my_data.",
        },
        "tools": [
            {
                "name": "list_studies",
                "description": "Return studies.",
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "openWorldHint": False,
                    "idempotentHint": True,
                },
                "input_schema": {"properties": {}, "required": []},
            }
        ],
        "prompts": [
            {
                "name": "review_due_items",
                "title": "Review Due Study Items",
                "description": "Start a review session.",
                "arguments": [{"name": "study_name", "required": False}],
            }
        ],
    }
