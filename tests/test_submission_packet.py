import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_submission_packet import build_submission_packet, validate_submission_packet


class SubmissionPacketTests(unittest.TestCase):
    def test_build_submission_packet_contains_review_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            packet_path = build_submission_packet(Path(temp_dir))
            packet = json.loads(packet_path.read_text(encoding="utf-8"))

        validate_submission_packet(packet)
        self.assertEqual(packet["app"]["name"], "Interview Prep MCP")
        self.assertTrue(packet["app"]["mcp_url"].endswith("/mcp"))
        self.assertIn("study:read", packet["app"]["scopes"])
        self.assertIn("study:write", packet["app"]["scopes"])
        self.assertGreaterEqual(len(packet["review"]["test_prompts"]), 5)
        self.assertTrue(packet["review"]["reviewer_credentials_requirements"])
        self.assertTrue(
            any("verify_authenticated_mcp.py" in command for command in packet["review"]["pre_submission_commands"])
        )
        self.assertTrue(
            any("build_mcp_contract_snapshot.py" in command for command in packet["review"]["pre_submission_commands"])
        )
        self.assertEqual(packet["auth"]["setup_runbook"], "docs/oidc-provider-setup.md")
        self.assertIn("study:read", packet["auth"]["required_scopes"])
        self.assertIn("study:write", packet["auth"]["required_scopes"])
        self.assertIn("delete_my_data", packet["tool_contract"]["destructive_tools"])
        self.assertIn("review_due_items", packet["tool_contract"]["prompts"])

    def test_validate_submission_packet_rejects_missing_scope(self):
        packet = {
            "app": {
                "name": "Interview Prep MCP",
                "category": "Education",
                "short_description": "Study progress.",
                "homepage_url": "https://study.example.com",
                "privacy_policy_url": "https://study.example.com/privacy",
                "terms_of_service_url": "https://study.example.com/terms",
                "support_url": "https://study.example.com/support",
                "mcp_url": "https://study.example.com/mcp",
                "scopes": ["study:read"],
            },
            "review": {
                "test_prompts": [{"prompt": str(i), "expected_behavior": str(i)} for i in range(5)],
                "reviewer_credentials_requirements": ["seeded account"],
                "pre_submission_commands": [
                    "MCP_AUTH_TOKEN=... python3 scripts/verify_authenticated_mcp.py https://study.example.com/mcp",
                    "python3 scripts/build_mcp_contract_snapshot.py --check",
                ],
            },
            "auth": {
                "required_scopes": ["study:read", "study:write"],
                "setup_runbook": "docs/oidc-provider-setup.md",
            },
            "tool_contract": {"destructive_tools": ["delete_my_data"]},
        }

        with self.assertRaisesRegex(ValueError, "study:read and study:write"):
            validate_submission_packet(packet)

    def test_validate_submission_packet_requires_auth_and_verification_details(self):
        packet = {
            "app": {
                "name": "Interview Prep MCP",
                "category": "Education",
                "short_description": "Study progress.",
                "homepage_url": "https://study.example.com",
                "privacy_policy_url": "https://study.example.com/privacy",
                "terms_of_service_url": "https://study.example.com/terms",
                "support_url": "https://study.example.com/support",
                "mcp_url": "https://study.example.com/mcp",
                "scopes": ["study:read", "study:write"],
            },
            "review": {"test_prompts": [{"prompt": str(i), "expected_behavior": str(i)} for i in range(5)]},
            "auth": {"required_scopes": ["study:read"], "setup_runbook": "README.md"},
            "tool_contract": {"destructive_tools": ["delete_my_data"]},
        }

        with self.assertRaisesRegex(ValueError, "reviewer credential requirements"):
            validate_submission_packet(packet)
