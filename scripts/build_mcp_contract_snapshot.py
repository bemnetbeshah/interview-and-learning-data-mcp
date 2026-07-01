#!/usr/bin/env python3
"""Build a machine-readable snapshot of the registered MCP contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
DIST_ROOT = REPO_ROOT / "dist"
SNAPSHOT_NAME = "mcp-contract-snapshot.json"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SRC_ROOT))

from scripts.manage_public_urls import current_public_base_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Interview Prep MCP contract snapshot.")
    parser.add_argument("--output-dir", type=Path, default=DIST_ROOT, help="Directory for the snapshot.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build into a temporary directory and verify required contract fields without keeping the artifact.",
    )
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = asyncio.run(build_contract_snapshot(Path(temp_dir)))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            validate_contract_snapshot(snapshot)
            print(f"ok: MCP contract snapshot check: {snapshot_path.name}")
        return 0

    snapshot_path = asyncio.run(build_contract_snapshot(args.output_dir))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validate_contract_snapshot(snapshot)
    print(snapshot_path)
    return 0


async def build_contract_snapshot(output_dir: Path) -> Path:
    from interview_prep_mcp.server import build_mcp

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "contract.sqlite3")
        env = {
            "INTERVIEW_PREP_DB_PATH": db_path,
            "MCP_PUBLIC_BASE_URL": current_public_base_url(),
        }
        with patch.dict(os.environ, env, clear=True):
            mcp = build_mcp()

    tools = []
    for tool in sorted(await mcp.list_tools(), key=lambda item: item.name):
        tools.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
                "annotations": _jsonable(tool.annotations),
            }
        )

    prompts = []
    for prompt in sorted(await mcp.list_prompts(), key=lambda item: item.name):
        prompts.append(
            {
                "name": prompt.name,
                "title": prompt.title,
                "description": prompt.description,
                "arguments": [_jsonable(argument) for argument in (prompt.arguments or [])],
            }
        )

    snapshot = {
        "server": {
            "name": "Interview Prep MCP",
            "website_url": str(mcp.website_url),
            "instructions": mcp.instructions,
        },
        "tools": tools,
        "prompts": prompts,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / SNAPSHOT_NAME
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot_path


def validate_contract_snapshot(snapshot: dict) -> None:
    tool_names = {tool.get("name") for tool in snapshot.get("tools", [])}
    prompt_names = {prompt.get("name") for prompt in snapshot.get("prompts", [])}
    required_tools = {
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
    required_prompts = {"review_due_items", "create_study_plan", "review_progress", "account_data_request"}
    if tool_names != required_tools:
        raise ValueError(f"unexpected tool contract: {sorted(tool_names)}")
    if prompt_names != required_prompts:
        raise ValueError(f"unexpected prompt contract: {sorted(prompt_names)}")
    instructions = str(snapshot.get("server", {}).get("instructions", ""))
    for phrase in ["get_due_subtopics", "log_attempt", "export_my_data", "delete_my_data", "Do not ask for or pass a user id"]:
        if phrase not in instructions:
            raise ValueError(f"server instructions must mention {phrase}")

    tools = {tool["name"]: tool for tool in snapshot["tools"]}
    delete_schema = tools["delete_my_data"]["input_schema"]["properties"]["confirmation"]
    score_schema = tools["log_attempt"]["input_schema"]["properties"]["score"]
    if "DELETE MY STUDY DATA" not in delete_schema.get("description", ""):
        raise ValueError("delete_my_data confirmation schema must include the exact phrase")
    if score_schema.get("minimum") != 1 or score_schema.get("maximum") != 5:
        raise ValueError("log_attempt score schema must be bounded 1-5")

    forbidden_input_names = {"user_id", "owner_subject", "subject", "token", "access_token", "bearer_token"}
    read_tools = {
        "list_studies",
        "list_topics",
        "list_subtopics",
        "get_due_subtopics",
        "get_subtopic_history",
        "export_my_data",
    }
    for tool_name, tool in tools.items():
        properties = set(tool.get("input_schema", {}).get("properties", {}))
        forbidden = sorted(properties & forbidden_input_names)
        if forbidden:
            raise ValueError(f"{tool_name} exposes forbidden auth/account inputs: {', '.join(forbidden)}")

        annotations = tool.get("annotations", {})
        if tool_name in read_tools and not annotations.get("readOnlyHint"):
            raise ValueError(f"{tool_name} must be marked read-only")
        if annotations.get("openWorldHint"):
            raise ValueError(f"{tool_name} must not be marked open-world")

    if not tools["delete_my_data"]["annotations"].get("destructiveHint"):
        raise ValueError("delete_my_data must be marked destructive")
    for soft_delete_tool in ["delete_study", "delete_topic", "delete_subtopic"]:
        if tools[soft_delete_tool]["annotations"].get("destructiveHint"):
            raise ValueError(f"{soft_delete_tool} must not be marked destructive")


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True, by_alias=True)
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=str))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fail: MCP contract snapshot: {exc}", file=sys.stderr)
        sys.exit(1)
