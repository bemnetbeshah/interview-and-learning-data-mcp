#!/usr/bin/env python3
"""Package the repo-local Codex plugin for sharing or review."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "interview-prep-mcp"
DIST_ROOT = REPO_ROOT / "dist"
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the Interview Prep MCP Codex plugin.")
    parser.add_argument("--output-dir", type=Path, default=DIST_ROOT, help="Directory for the plugin archive.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build into a temporary directory and verify archive contents without keeping the artifact.",
    )
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = build_plugin_archive(PLUGIN_ROOT, Path(temp_dir))
            validate_archive(archive)
            entries = list_archive_entries(archive)
            print(f"ok: packaged plugin check: {archive.name} contains {len(entries)} files")
        return 0

    archive = build_plugin_archive(PLUGIN_ROOT, args.output_dir)
    validate_archive(archive)
    print(archive)
    return 0


def build_plugin_archive(plugin_root: Path, output_dir: Path) -> Path:
    manifest = _read_manifest(plugin_root)
    name = manifest["name"]
    version = manifest["version"]
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{name}-{version}.plugin.zip"

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _iter_plugin_files(plugin_root):
            relative_path = path.relative_to(plugin_root)
            archive.write(path, Path(name) / relative_path)

    return archive_path


def list_archive_entries(archive_path: Path) -> list[str]:
    with zipfile.ZipFile(archive_path) as archive:
        return sorted(archive.namelist())


def validate_archive(archive_path: Path) -> None:
    entries = list_archive_entries(archive_path)
    validate_archive_entries(entries)

    root = _archive_root(entries)
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read(f"{root}/.codex-plugin/plugin.json").decode("utf-8"))
        mcp_config = json.loads(archive.read(f"{root}/.mcp.json").decode("utf-8"))
        skill_text = archive.read(f"{root}/skills/interview-prep/SKILL.md").decode("utf-8")

    if manifest.get("name") != root:
        raise ValueError("plugin archive root must match manifest name")
    if manifest.get("mcpServers") != "./.mcp.json":
        raise ValueError("plugin manifest mcpServers must point at ./.mcp.json")
    if manifest.get("skills") != "./skills/":
        raise ValueError("plugin manifest skills must point at ./skills/")

    server = mcp_config.get("mcpServers", {}).get("interview_prep", {})
    if not str(server.get("url", "")).startswith("https://") or not str(server.get("url", "")).endswith("/mcp"):
        raise ValueError("plugin MCP server URL must be an https /mcp endpoint")
    if not {"study:read", "study:write"}.issubset(set(server.get("scopes", []))):
        raise ValueError("plugin MCP server scopes must include study:read and study:write")

    for phrase in ["get_due_subtopics", "log_attempt", "DELETE MY STUDY DATA", "Do not ask for, invent, or pass a user id"]:
        if phrase not in skill_text:
            raise ValueError(f"plugin skill missing required guidance: {phrase}")


def validate_archive_entries(entries: list[str]) -> None:
    required_suffixes = [
        "/.codex-plugin/plugin.json",
        "/.mcp.json",
        "/skills/interview-prep/SKILL.md",
        "/index.md",
        "/.codex-plugin/index.md",
        "/assets/index.md",
        "/skills/index.md",
        "/skills/interview-prep/index.md",
    ]
    missing = [suffix for suffix in required_suffixes if not any(entry.endswith(suffix) for entry in entries)]
    if missing:
        raise ValueError(f"plugin archive missing required entries: {', '.join(missing)}")
    forbidden = [
        entry
        for entry in entries
        if any(part in EXCLUDED_PARTS for part in Path(entry).parts) or Path(entry).suffix in EXCLUDED_SUFFIXES
    ]
    if forbidden:
        raise ValueError(f"plugin archive contains excluded entries: {', '.join(forbidden)}")


def _read_manifest(plugin_root: Path) -> dict:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ["name", "version"]:
        if not manifest.get(key):
            raise ValueError(f"plugin manifest missing {key}")
    return manifest


def _iter_plugin_files(plugin_root: Path) -> list[Path]:
    return sorted(
        path
        for path in plugin_root.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and path.suffix not in EXCLUDED_SUFFIXES
    )


def _archive_root(entries: list[str]) -> str:
    roots = {entry.split("/", 1)[0] for entry in entries if "/" in entry}
    if len(roots) != 1:
        raise ValueError("plugin archive must contain exactly one root directory")
    return next(iter(roots))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"fail: package plugin: {exc}", file=sys.stderr)
        sys.exit(1)
