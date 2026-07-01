import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import manage_public_urls
from scripts.manage_public_urls import check_public_url_consistency, current_public_base_url, update_public_base_url


class ManagePublicUrlsTests(unittest.TestCase):
    def test_current_plugin_public_urls_are_consistent(self):
        checks = check_public_url_consistency()

        self.assertTrue(all(check.ok for check in checks), checks)

    def test_update_public_base_url_rewrites_plugin_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = Path(temp_dir) / "interview-prep-mcp"
            (plugin_root / ".codex-plugin").mkdir(parents=True)
            plugin_root.joinpath(".codex-plugin/plugin.json").write_text(
                json.dumps(
                    {
                        "homepage": "https://old.example.com",
                        "interface": {
                            "websiteURL": "https://old.example.com/",
                            "privacyPolicyURL": "https://old.example.com/privacy",
                            "termsOfServiceURL": "https://old.example.com/terms",
                        },
                    }
                ),
                encoding="utf-8",
            )
            plugin_root.joinpath(".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "interview_prep": {
                                "url": "https://old.example.com/mcp",
                                "oauth_resource": "https://old.example.com/mcp",
                                "scopes": ["study:read", "study:write"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(manage_public_urls, "PLUGIN_MANIFEST", plugin_root / ".codex-plugin/plugin.json"), patch.object(
                manage_public_urls, "MCP_CONFIG", plugin_root / ".mcp.json"
            ):
                update_public_base_url("https://new.example.com")
                checks = check_public_url_consistency("https://new.example.com")

                manifest = json.loads((plugin_root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
                mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))

        self.assertTrue(all(check.ok for check in checks), checks)
        self.assertEqual(manifest["interface"]["privacyPolicyURL"], "https://new.example.com/privacy")
        self.assertEqual(mcp_config["mcpServers"]["interview_prep"]["url"], "https://new.example.com/mcp")

    def test_current_public_base_url_comes_from_mcp_config(self):
        self.assertTrue(current_public_base_url().startswith("https://"))
