#!/usr/bin/env python3
"""Compare two MCP contract snapshots and flag breaking changes."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContractDiff:
    severity: str
    path: str
    detail: str

    @property
    def breaking(self) -> bool:
        return self.severity == "breaking"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two generated MCP contract snapshots.")
    parser.add_argument("old_snapshot", type=Path, help="Previous reviewed mcp-contract-snapshot.json")
    parser.add_argument("new_snapshot", type=Path, help="New mcp-contract-snapshot.json")
    args = parser.parse_args()

    old = _read_json(args.old_snapshot)
    new = _read_json(args.new_snapshot)
    diffs = diff_contracts(old, new)
    if not diffs:
        print("ok: mcp contract diff: no contract changes")
        return 0

    for diff in diffs:
        print(f"{diff.severity}: {diff.path}: {diff.detail}")
    return 1 if any(diff.breaking for diff in diffs) else 0


def diff_contracts(old: dict, new: dict) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    diffs.extend(_diff_server(old.get("server", {}), new.get("server", {})))
    diffs.extend(_diff_tools(_by_name(old.get("tools", [])), _by_name(new.get("tools", []))))
    diffs.extend(_diff_prompts(_by_name(old.get("prompts", [])), _by_name(new.get("prompts", []))))
    return diffs


def _diff_server(old: dict, new: dict) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    if old.get("website_url") != new.get("website_url"):
        diffs.append(
            ContractDiff(
                "breaking",
                "server.website_url",
                "published app base URL changed; OpenAI requires a new app for base MCP URL changes",
            )
        )
    old_instructions = old.get("instructions") or ""
    new_instructions = new.get("instructions") or ""
    for phrase in ["get_due_subtopics", "log_attempt", "delete_my_data"]:
        if phrase in old_instructions and phrase not in new_instructions:
            diffs.append(ContractDiff("breaking", "server.instructions", f"removed required workflow phrase {phrase}"))
    if old_instructions != new_instructions and not any(diff.path == "server.instructions" for diff in diffs):
        diffs.append(ContractDiff("review", "server.instructions", "instructions changed; rescan and review behavior"))
    return diffs


def _diff_tools(old_tools: dict[str, dict], new_tools: dict[str, dict]) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    for name in sorted(set(old_tools) - set(new_tools)):
        diffs.append(ContractDiff("breaking", f"tools.{name}", "tool was removed"))
    for name in sorted(set(new_tools) - set(old_tools)):
        diffs.append(ContractDiff("review", f"tools.{name}", "tool was added"))

    for name in sorted(set(old_tools) & set(new_tools)):
        old_tool = old_tools[name]
        new_tool = new_tools[name]
        if old_tool.get("description") != new_tool.get("description"):
            diffs.append(ContractDiff("review", f"tools.{name}.description", "tool description changed"))
        diffs.extend(_diff_annotations(name, old_tool.get("annotations", {}), new_tool.get("annotations", {})))
        diffs.extend(
            _diff_input_schema(
                f"tools.{name}.input_schema",
                old_tool.get("input_schema", {}),
                new_tool.get("input_schema", {}),
            )
        )
    return diffs


def _diff_annotations(name: str, old: dict, new: dict) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    for key in ["readOnlyHint", "destructiveHint", "openWorldHint", "idempotentHint"]:
        if old.get(key) != new.get(key):
            severity = "breaking" if key in {"readOnlyHint", "destructiveHint", "openWorldHint"} else "review"
            diffs.append(ContractDiff(severity, f"tools.{name}.annotations.{key}", f"{old.get(key)} -> {new.get(key)}"))
    return diffs


def _diff_input_schema(path: str, old: dict, new: dict) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    old_props = old.get("properties", {})
    new_props = new.get("properties", {})
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))

    for prop in sorted(set(old_props) - set(new_props)):
        diffs.append(ContractDiff("breaking", f"{path}.properties.{prop}", "input field was removed"))
    for prop in sorted(set(new_props) - set(old_props)):
        severity = "breaking" if prop in new_required else "review"
        diffs.append(ContractDiff(severity, f"{path}.properties.{prop}", "input field was added"))
    for prop in sorted(new_required - old_required):
        if prop in old_props:
            diffs.append(ContractDiff("breaking", f"{path}.required.{prop}", "existing field became required"))
    for prop in sorted(old_required - new_required):
        diffs.append(ContractDiff("review", f"{path}.required.{prop}", "required field became optional"))

    for prop in sorted(set(old_props) & set(new_props)):
        old_prop = old_props[prop]
        new_prop = new_props[prop]
        if _schema_type(old_prop) != _schema_type(new_prop):
            diffs.append(ContractDiff("breaking", f"{path}.properties.{prop}.type", "input field type changed"))
        if old_prop.get("description") != new_prop.get("description"):
            diffs.append(ContractDiff("review", f"{path}.properties.{prop}.description", "input field description changed"))
        for bound in ["minimum", "maximum"]:
            if old_prop.get(bound) != new_prop.get(bound):
                diffs.append(ContractDiff("breaking", f"{path}.properties.{prop}.{bound}", "numeric bound changed"))
    return diffs


def _diff_prompts(old_prompts: dict[str, dict], new_prompts: dict[str, dict]) -> list[ContractDiff]:
    diffs: list[ContractDiff] = []
    for name in sorted(set(old_prompts) - set(new_prompts)):
        diffs.append(ContractDiff("breaking", f"prompts.{name}", "prompt was removed"))
    for name in sorted(set(new_prompts) - set(old_prompts)):
        diffs.append(ContractDiff("review", f"prompts.{name}", "prompt was added"))
    for name in sorted(set(old_prompts) & set(new_prompts)):
        if old_prompts[name].get("title") != new_prompts[name].get("title"):
            diffs.append(ContractDiff("review", f"prompts.{name}.title", "prompt title changed"))
        if old_prompts[name].get("description") != new_prompts[name].get("description"):
            diffs.append(ContractDiff("review", f"prompts.{name}.description", "prompt description changed"))
        old_args = _args_by_name(old_prompts[name].get("arguments", []))
        new_args = _args_by_name(new_prompts[name].get("arguments", []))
        for arg in sorted(set(old_args) - set(new_args)):
            diffs.append(ContractDiff("breaking", f"prompts.{name}.arguments.{arg}", "prompt argument was removed"))
        for arg in sorted(set(new_args) - set(old_args)):
            severity = "breaking" if new_args[arg].get("required") else "review"
            diffs.append(ContractDiff(severity, f"prompts.{name}.arguments.{arg}", "prompt argument was added"))
        for arg in sorted(set(old_args) & set(new_args)):
            if bool(old_args[arg].get("required")) != bool(new_args[arg].get("required")):
                diffs.append(
                    ContractDiff(
                        "breaking",
                        f"prompts.{name}.arguments.{arg}.required",
                        f"{old_args[arg].get('required')} -> {new_args[arg].get('required')}",
                    )
                )
    return diffs


def _by_name(items: list[dict]) -> dict[str, dict]:
    return {item["name"]: item for item in items if item.get("name")}


def _args_by_name(items: list[dict]) -> dict[str, dict]:
    return {item["name"]: item for item in items if item.get("name")}


def _schema_type(schema: dict[str, Any]) -> Any:
    if "type" in schema:
        return schema["type"]
    if "anyOf" in schema:
        return sorted(item.get("type") for item in schema["anyOf"])
    return None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"fail: mcp contract diff: {exc}", file=sys.stderr)
        sys.exit(2)
