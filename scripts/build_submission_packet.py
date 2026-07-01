#!/usr/bin/env python3
"""Build a machine-readable OpenAI app submission packet."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "interview-prep-mcp"
DIST_ROOT = REPO_ROOT / "dist"
PACKET_NAME = "openai-submission-packet.json"


TEST_PROMPTS = [
    {
        "prompt": "Show my due study reviews.",
        "expected_behavior": "Calls get_due_subtopics and returns only demo-account due subtopics.",
    },
    {
        "prompt": "Create a study called AI Engineering Interview.",
        "expected_behavior": "Calls create_study and confirms the created study.",
    },
    {
        "prompt": "Add Transformers as a topic under AI Engineering Interview.",
        "expected_behavior": "Calls create_topic using the demo study id.",
    },
    {
        "prompt": "Add Multi-head Attention as a subtopic.",
        "expected_behavior": "Calls create_subtopic using the demo topic id.",
    },
    {
        "prompt": "Quiz me on Multi-head Attention.",
        "expected_behavior": "Asks a question, then calls log_attempt with score and notes after the answer.",
    },
    {
        "prompt": "Show my history for Multi-head Attention.",
        "expected_behavior": "Calls get_subtopic_history and summarizes attempts, trend, and next review date.",
    },
    {
        "prompt": "Export my study data.",
        "expected_behavior": "Calls export_my_data and summarizes included categories without exposing another account.",
    },
]

READ_TOOLS = [
    "list_studies",
    "list_topics",
    "list_subtopics",
    "get_due_subtopics",
    "get_subtopic_history",
    "export_my_data",
]
WRITE_TOOLS = [
    "create_study",
    "create_topic",
    "create_subtopic",
    "update_subtopic",
    "delete_study",
    "delete_topic",
    "delete_subtopic",
    "log_attempt",
    "delete_my_data",
]
PROMPTS = ["review_due_items", "create_study_plan", "review_progress", "account_data_request"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the OpenAI app submission packet.")
    parser.add_argument("--output-dir", type=Path, default=DIST_ROOT, help="Directory for the packet.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build into a temporary directory and verify required fields without keeping the artifact.",
    )
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet_path = build_submission_packet(Path(temp_dir))
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            validate_submission_packet(packet)
            print(f"ok: submission packet check: {packet_path.name}")
        return 0

    packet_path = build_submission_packet(args.output_dir)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    validate_submission_packet(packet)
    print(packet_path)
    return 0


def build_submission_packet(output_dir: Path) -> Path:
    manifest = _read_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
    mcp_config = _read_json(PLUGIN_ROOT / ".mcp.json")
    interface = manifest["interface"]
    server = mcp_config["mcpServers"]["interview_prep"]

    packet = {
        "app": {
            "name": interface["displayName"],
            "category": interface["category"],
            "short_description": interface["shortDescription"],
            "long_description": interface["longDescription"],
            "developer_name": interface["developerName"],
            "homepage_url": interface["websiteURL"],
            "privacy_policy_url": interface["privacyPolicyURL"],
            "terms_of_service_url": interface["termsOfServiceURL"],
            "support_url": interface["websiteURL"].rstrip("/") + "/support",
            "mcp_url": server["url"],
            "oauth_resource": server.get("oauth_resource", server["url"]),
            "scopes": server["scopes"],
        },
        "review": {
            "reviewer_credentials_requirements": [
                "Reviewer account must be fully featured and seeded with sample study data.",
                "Reviewer login must not require MFA, SMS, email verification, manual approval, or out-of-band support.",
                "Reviewer access token subject must match the subject used by the demo seed command.",
                "Reviewer access token must include study:read and study:write.",
            ],
            "demo_subject_seed_command": "DATABASE_URL=... python3 scripts/seed_demo_data.py --subject <reviewer-subject> --with-attempts",
            "test_prompts": TEST_PROMPTS,
            "pre_submission_commands": [
                "python3 scripts/release_check.py",
                "python3 scripts/check_production_config.py",
                "python3 scripts/verify_public_deployment.py https://your-app.example.com",
                "MCP_AUTH_TOKEN=<reviewer-access-token> python3 scripts/verify_authenticated_mcp.py https://your-app.example.com/mcp",
                "python3 scripts/package_plugin.py --check",
                "python3 scripts/build_submission_packet.py --check",
                "python3 scripts/build_mcp_contract_snapshot.py --check",
            ],
        },
        "auth": {
            "mode": "External OIDC/JWT for public launch",
            "issuer_url_env": "OIDC_ISSUER_URL",
            "jwks_url_env": "OIDC_JWKS_URL",
            "audience_env": "OIDC_AUDIENCE",
            "subject_claim_env": "OIDC_SUBJECT_CLAIM",
            "required_scopes_env": "OIDC_REQUIRED_SCOPES",
            "required_scopes": ["study:read", "study:write"],
            "accepted_grant_claims": ["scope", "scp", "permissions", "roles", "role"],
            "setup_runbook": "docs/oidc-provider-setup.md",
        },
        "tool_contract": {
            "read_tools": READ_TOOLS,
            "write_tools": WRITE_TOOLS,
            "destructive_tools": ["delete_my_data"],
            "soft_delete_tools": ["delete_study", "delete_topic", "delete_subtopic"],
            "prompts": PROMPTS,
            "required_confirmation_phrase": "DELETE MY STUDY DATA",
            "routine_responses_exclude": [
                "auth subjects",
                "access tokens",
                "secrets",
                "raw OAuth records",
                "request ids",
                "internal trace ids",
            ],
        },
        "distribution": {
            "public_path": "OpenAI app submission creates ChatGPT Apps Directory and Codex Plugin Directory distribution after approval and publish.",
            "local_plugin_path": "plugins/interview-prep-mcp",
            "local_plugin_archive_command": "python3 scripts/package_plugin.py",
        },
        "maintenance": {
            "versioning_rule": "Treat scanned MCP metadata as a versioned contract. Do not remove or rename published tools without a reviewed replacement version and rollback plan.",
            "base_url_rule": "Changing the published base MCP URL requires creating a new app instead of a version update.",
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = output_dir / PACKET_NAME
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def validate_submission_packet(packet: dict) -> None:
    app = packet.get("app", {})
    review = packet.get("review", {})
    auth = packet.get("auth", {})
    required_app_fields = [
        "name",
        "category",
        "short_description",
        "homepage_url",
        "privacy_policy_url",
        "terms_of_service_url",
        "support_url",
        "mcp_url",
        "scopes",
    ]
    missing = [field for field in required_app_fields if not app.get(field)]
    if missing:
        raise ValueError(f"submission packet app missing: {', '.join(missing)}")
    if not str(app["mcp_url"]).startswith("https://") or not str(app["mcp_url"]).endswith("/mcp"):
        raise ValueError("submission packet mcp_url must be an https /mcp endpoint")
    if not {"study:read", "study:write"}.issubset(set(app["scopes"])):
        raise ValueError("submission packet scopes must include study:read and study:write")
    if len(review.get("test_prompts", [])) < 5:
        raise ValueError("submission packet must include reviewer test prompts")
    if not review.get("reviewer_credentials_requirements"):
        raise ValueError("submission packet must include reviewer credential requirements")
    pre_submission_commands = review.get("pre_submission_commands", [])
    if not any("verify_authenticated_mcp.py" in command for command in pre_submission_commands):
        raise ValueError("submission packet must include authenticated MCP verification")
    if not any("build_mcp_contract_snapshot.py" in command for command in pre_submission_commands):
        raise ValueError("submission packet must include MCP contract snapshot verification")
    if not {"study:read", "study:write"}.issubset(set(auth.get("required_scopes", []))):
        raise ValueError("submission packet auth must require study:read and study:write")
    if auth.get("setup_runbook") != "docs/oidc-provider-setup.md":
        raise ValueError("submission packet auth must reference docs/oidc-provider-setup.md")
    if "delete_my_data" not in packet.get("tool_contract", {}).get("destructive_tools", []):
        raise ValueError("submission packet must identify delete_my_data as destructive")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fail: submission packet: {exc}", file=sys.stderr)
        sys.exit(1)
