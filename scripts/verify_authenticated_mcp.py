#!/usr/bin/env python3
"""Verify an authenticated hosted MCP endpoint with a real bearer token."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

EXPECTED_TOOLS = {
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
EXPECTED_PROMPTS = {"review_due_items", "create_study_plan", "review_progress", "account_data_request"}


@dataclass(frozen=True)
class SmokeResult:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify authenticated Interview Prep MCP connectivity.")
    parser.add_argument("mcp_url", help="Hosted MCP URL, for example https://interview-prep.example.com/mcp")
    parser.add_argument(
        "--bearer-token",
        default=os.getenv("MCP_AUTH_TOKEN", ""),
        help="Bearer token for the reviewer/user account. Defaults to MCP_AUTH_TOKEN.",
    )
    args = parser.parse_args()

    if not args.bearer_token:
        print("fail: auth: provide --bearer-token or MCP_AUTH_TOKEN", file=sys.stderr)
        return 2

    results = asyncio.run(run_smoke(args.mcp_url, args.bearer_token))
    for result in results:
        status = "ok" if result.ok else "fail"
        print(f"{status}: {result.name}: {result.detail}")
    return 0 if all(result.ok for result in results) else 1


async def run_smoke(mcp_url: str, bearer_token: str) -> list[SmokeResult]:
    import httpx
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    headers = {"Authorization": f"Bearer {bearer_token}"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read_stream, write_stream, _session_id):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()
                prompts_result = await session.list_prompts()
                review_prompt = await session.get_prompt("review_due_items", {"study_name": "AI Engineering"})

    return validate_smoke_results(init_result, tools_result.tools, prompts_result.prompts, review_prompt)


def validate_smoke_results(init_result: Any, tools: list[Any], prompts: list[Any], review_prompt: Any) -> list[SmokeResult]:
    results = [
        _validate_initialization(init_result),
        _validate_tools(tools),
        _validate_prompts(prompts),
        _validate_review_prompt(review_prompt),
    ]
    return results


def _validate_initialization(init_result: Any) -> SmokeResult:
    instructions = getattr(init_result, "instructions", "") or ""
    website_url = getattr(getattr(init_result, "serverInfo", None), "websiteUrl", None)
    if "get_due_subtopics" not in instructions or "log_attempt" not in instructions:
        return SmokeResult("initialize", False, "server instructions do not include review workflow guidance")
    if website_url and not str(website_url).startswith("https://"):
        return SmokeResult("initialize", False, "server website URL is not HTTPS")
    return SmokeResult("initialize", True, "server initialized with public workflow instructions")


def _validate_tools(tools: list[Any]) -> SmokeResult:
    tool_names = {tool.name for tool in tools}
    if tool_names != EXPECTED_TOOLS:
        return SmokeResult("tools", False, f"unexpected tools: {sorted(tool_names)}")

    by_name = {tool.name: tool for tool in tools}
    delete_annotations = getattr(by_name["delete_my_data"], "annotations", None)
    if not getattr(delete_annotations, "destructiveHint", False):
        return SmokeResult("tools", False, "delete_my_data is not marked destructive")
    score_schema = by_name["log_attempt"].inputSchema["properties"]["score"]
    if score_schema.get("minimum") != 1 or score_schema.get("maximum") != 5:
        return SmokeResult("tools", False, "log_attempt score is not bounded 1-5")
    return SmokeResult("tools", True, f"{len(tool_names)} expected tools exposed")


def _validate_prompts(prompts: list[Any]) -> SmokeResult:
    prompt_names = {prompt.name for prompt in prompts}
    if prompt_names != EXPECTED_PROMPTS:
        return SmokeResult("prompts", False, f"unexpected prompts: {sorted(prompt_names)}")
    return SmokeResult("prompts", True, f"{len(prompt_names)} expected prompts exposed")


def _validate_review_prompt(review_prompt: Any) -> SmokeResult:
    messages = getattr(review_prompt, "messages", [])
    if not messages:
        return SmokeResult("review_prompt", False, "review_due_items returned no messages")
    text = getattr(getattr(messages[0], "content", None), "text", "")
    if "get_due_subtopics" not in text or "log_attempt" not in text:
        return SmokeResult("review_prompt", False, "review_due_items does not guide the review/log loop")
    return SmokeResult("review_prompt", True, "review_due_items renders workflow guidance")


if __name__ == "__main__":
    sys.exit(main())
