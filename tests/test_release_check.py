import tempfile
import unittest
import json
from pathlib import Path

from scripts.release_check import (
    PLUGIN_ROOT,
    check_folder_indexes,
    check_plugin_bundle,
    check_public_launch_docs,
    check_railway_config,
)


class ReleaseCheckTests(unittest.TestCase):
    def test_current_plugin_bundle_passes(self):
        result = check_plugin_bundle(PLUGIN_ROOT)

        self.assertTrue(result.ok, result.detail)

    def test_public_launch_docs_pass(self):
        result = check_public_launch_docs()

        self.assertTrue(result.ok, result.detail)

    def test_railway_config_passes(self):
        result = check_railway_config()

        self.assertTrue(result.ok, result.detail)

    def test_folder_indexes_pass(self):
        result = check_folder_indexes()

        self.assertTrue(result.ok, result.detail)

    def test_missing_plugin_file_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = check_plugin_bundle(Path(temp_dir))

        self.assertFalse(result.ok)
        self.assertIn("missing required files", result.detail)

    def test_plugin_skill_missing_required_guidance_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = Path(temp_dir)
            (plugin_root / ".codex-plugin").mkdir(parents=True)
            (plugin_root / "skills" / "interview-prep").mkdir(parents=True)
            (plugin_root / "skills").mkdir(exist_ok=True)
            for path in [
                "index.md",
                ".codex-plugin/index.md",
                "skills/index.md",
                "skills/interview-prep/index.md",
            ]:
                (plugin_root / path).write_text("# Index\n", encoding="utf-8")
            (plugin_root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "interview-prep-mcp",
                        "mcpServers": "./.mcp.json",
                        "skills": "./skills/",
                        "interface": {
                            "displayName": "Interview Prep MCP",
                            "shortDescription": "Study review.",
                            "websiteURL": "https://study.example.com/",
                            "privacyPolicyURL": "https://study.example.com/privacy",
                            "termsOfServiceURL": "https://study.example.com/terms",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (plugin_root / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "interview_prep": {
                                "url": "https://study.example.com/mcp",
                                "scopes": ["study:read", "study:write"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (plugin_root / "skills" / "interview-prep" / "SKILL.md").write_text(
                "Use the MCP server for study review.\n",
                encoding="utf-8",
            )

            result = check_plugin_bundle(plugin_root)

        self.assertFalse(result.ok)
        self.assertIn("skill file missing guidance", result.detail)

    def test_missing_folder_index_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "child").mkdir()
            module = __import__("scripts.release_check", fromlist=["REPO_ROOT"])
            original_root = module.REPO_ROOT
            try:
                module.REPO_ROOT = root
                result = module.check_folder_indexes()
            finally:
                module.REPO_ROOT = original_root

        self.assertFalse(result.ok)
        self.assertIn("child", result.detail)
