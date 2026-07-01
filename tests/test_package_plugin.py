import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_plugin import PLUGIN_ROOT, build_plugin_archive, list_archive_entries, validate_archive, validate_archive_entries


class PackagePluginTests(unittest.TestCase):
    def test_build_plugin_archive_contains_required_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = build_plugin_archive(PLUGIN_ROOT, Path(temp_dir))
            entries = list_archive_entries(archive_path)
            validate_archive_entries(entries)
            validate_archive(archive_path)

            self.assertIn("interview-prep-mcp/.codex-plugin/plugin.json", entries)
            self.assertIn("interview-prep-mcp/.mcp.json", entries)
            self.assertIn("interview-prep-mcp/skills/interview-prep/SKILL.md", entries)
            self.assertIn("interview-prep-mcp/assets/index.md", entries)

    def test_archive_is_readable_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = build_plugin_archive(PLUGIN_ROOT, Path(temp_dir))

            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())

    def test_validate_archive_entries_rejects_missing_indexes(self):
        entries = [
            "interview-prep-mcp/.codex-plugin/plugin.json",
            "interview-prep-mcp/.mcp.json",
            "interview-prep-mcp/skills/interview-prep/SKILL.md",
        ]

        with self.assertRaisesRegex(ValueError, "missing required entries"):
            validate_archive_entries(entries)

    def test_validate_archive_entries_rejects_excluded_files(self):
        entries = [
            "interview-prep-mcp/.codex-plugin/plugin.json",
            "interview-prep-mcp/.mcp.json",
            "interview-prep-mcp/skills/interview-prep/SKILL.md",
            "interview-prep-mcp/index.md",
            "interview-prep-mcp/.codex-plugin/index.md",
            "interview-prep-mcp/assets/index.md",
            "interview-prep-mcp/skills/index.md",
            "interview-prep-mcp/skills/interview-prep/index.md",
            "interview-prep-mcp/__pycache__/x.pyc",
        ]

        with self.assertRaisesRegex(ValueError, "excluded entries"):
            validate_archive_entries(entries)
