import unittest
from pathlib import Path


class GithubWorkflowTests(unittest.TestCase):
    def test_release_check_workflow_runs_required_gates(self):
        workflow = Path(".github/workflows/release-check.yml").read_text(encoding="utf-8")

        self.assertIn("python-version: \"3.11\"", workflow)
        self.assertIn("permissions:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn("python -m pip install -e \".[dev]\"", workflow)
        self.assertIn("python scripts/release_check.py", workflow)
        self.assertIn("python scripts/package_plugin.py", workflow)
        self.assertIn("python scripts/build_submission_packet.py", workflow)
        self.assertIn("python scripts/build_mcp_contract_snapshot.py", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("dist/*.plugin.zip", workflow)
        self.assertIn("dist/openai-submission-packet.json", workflow)
        self.assertIn("dist/mcp-contract-snapshot.json", workflow)
        self.assertIn("name: public-launch-docs", workflow)
        self.assertIn("docs/oidc-provider-setup.md", workflow)
        self.assertIn("docs/production-env.example", workflow)
        self.assertIn("retention-days: 14", workflow)
