#!/usr/bin/env python3
"""Run local release gates for the public/plugin MCP package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "interview-prep-mcp"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local release checks for Interview Prep MCP.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the unittest suite.")
    parser.add_argument(
        "--production-config",
        action="store_true",
        help="Also run scripts/check_production_config.py against the current environment.",
    )
    parser.add_argument(
        "--allow-private-oauth",
        action="store_true",
        help="Pass --allow-private-oauth to the production config checker.",
    )
    args = parser.parse_args()

    results = run_release_checks(
        skip_tests=args.skip_tests,
        production_config=args.production_config,
        allow_private_oauth=args.allow_private_oauth,
    )
    for result in results:
        status = "ok" if result.ok else "fail"
        print(f"{status}: {result.name}: {result.detail}")
    return 0 if all(result.ok for result in results) else 1


def run_release_checks(
    skip_tests: bool = False,
    production_config: bool = False,
    allow_private_oauth: bool = False,
) -> list[CheckResult]:
    checks: list[CheckResult] = [
        check_plugin_bundle(PLUGIN_ROOT),
        check_public_launch_docs(),
        check_railway_config(),
        check_folder_indexes(),
    ]

    scripts = [
        "scripts/build_mcp_contract_snapshot.py",
        "scripts/build_submission_packet.py",
        "scripts/check_database_schema.py",
        "scripts/check_production_config.py",
        "scripts/diff_mcp_contract.py",
        "scripts/manage_public_urls.py",
        "scripts/package_plugin.py",
        "scripts/seed_demo_data.py",
        "scripts/verify_authenticated_mcp.py",
        "scripts/verify_public_deployment.py",
        "scripts/release_check.py",
    ]
    checks.append(
        _run_command(
            "script_compile",
            [sys.executable, "-m", "py_compile", *scripts],
            "operational scripts compile",
        )
    )
    checks.append(
        _run_command(
            "plugin_package",
            [sys.executable, "scripts/package_plugin.py", "--check"],
            "plugin archive can be built and verified",
        )
    )
    checks.append(
        _run_command(
            "submission_packet",
            [sys.executable, "scripts/build_submission_packet.py", "--check"],
            "OpenAI submission packet can be built and verified",
        )
    )
    checks.append(
        _run_command(
            "mcp_contract_snapshot",
            [sys.executable, "scripts/build_mcp_contract_snapshot.py", "--check"],
            "MCP contract snapshot can be built and verified",
        )
    )
    checks.append(
        _run_command(
            "public_urls",
            [sys.executable, "scripts/manage_public_urls.py", "--check"],
            "public plugin and MCP URLs are internally consistent",
        )
    )

    if not skip_tests:
        checks.append(
            _run_command(
                "unit_tests",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                "unit test suite passes",
            )
        )

    if production_config:
        command = [sys.executable, "scripts/check_production_config.py"]
        if allow_private_oauth:
            command.append("--allow-private-oauth")
        checks.append(_run_command("production_config", command, "production environment settings pass"))

    return checks


def check_railway_config() -> CheckResult:
    path = REPO_ROOT / "railway.json"
    if not path.is_file():
        return CheckResult("railway_config", False, "railway.json is required for public deployment config-as-code")
    try:
        config = _read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult("railway_config", False, f"invalid railway.json: {exc}")

    errors = []
    if config.get("$schema") != "https://railway.com/railway.schema.json":
        errors.append("schema must be https://railway.com/railway.schema.json")
    if config.get("build", {}).get("builder") != "DOCKERFILE":
        errors.append("build.builder must be DOCKERFILE")
    if config.get("build", {}).get("dockerfilePath") != "Dockerfile":
        errors.append("build.dockerfilePath must be Dockerfile")
    deploy = config.get("deploy", {})
    if deploy.get("healthcheckPath") != "/healthz":
        errors.append("deploy.healthcheckPath must be /healthz")
    if int(deploy.get("healthcheckTimeout", 0)) < 30:
        errors.append("deploy.healthcheckTimeout must be at least 30")
    if deploy.get("restartPolicyType") != "ON_FAILURE":
        errors.append("deploy.restartPolicyType must be ON_FAILURE")
    if int(deploy.get("restartPolicyMaxRetries", 0)) < 1:
        errors.append("deploy.restartPolicyMaxRetries must be positive")

    if errors:
        return CheckResult("railway_config", False, "; ".join(errors))
    return CheckResult("railway_config", True, "Railway config-as-code pins builder, healthcheck, and restart policy")


def check_public_launch_docs() -> CheckResult:
    required_files = [
        "README.md",
        "docs/public-launch.md",
        "docs/deployment.md",
        "docs/openai-submission.md",
        "docs/public-auth.md",
        "docs/oidc-provider-setup.md",
        "docs/production-env.example",
    ]
    missing = [path for path in required_files if not (REPO_ROOT / path).is_file()]
    if missing:
        return CheckResult("public_launch_docs", False, f"missing required files: {', '.join(missing)}")

    env_template = (REPO_ROOT / "docs" / "production-env.example").read_text(encoding="utf-8")
    required_env = [
        "DATABASE_URL=",
        "MCP_TRANSPORT=streamable-http",
        "MCP_HOST=0.0.0.0",
        "MCP_PUBLIC_BASE_URL=https://",
        "MCP_RESOURCE_SERVER_URL=https://",
        "MCP_ALLOW_UNAUTHENTICATED_HTTP=false",
        "OIDC_ISSUER_URL=https://",
        "OIDC_AUDIENCE=interview-prep-mcp",
        "OIDC_REQUIRED_SCOPES=study:read study:write",
        "PUBLIC_CONTACT_EMAIL=",
    ]
    missing_env = [item for item in required_env if item not in env_template]
    if missing_env:
        return CheckResult("public_launch_docs", False, f"production env template missing: {', '.join(missing_env)}")

    auth_doc = (REPO_ROOT / "docs" / "public-auth.md").read_text(encoding="utf-8")
    required_phrases = ["Provider Contract", "study:read", "study:write", "JWKS", "reviewer access token"]
    missing_phrases = [phrase for phrase in required_phrases if phrase not in auth_doc]
    if missing_phrases:
        return CheckResult("public_launch_docs", False, f"public auth doc missing: {', '.join(missing_phrases)}")

    oidc_runbook = (REPO_ROOT / "docs" / "oidc-provider-setup.md").read_text(encoding="utf-8")
    required_oidc_phrases = [
        "Provider Dashboard Checklist",
        "Railway Environment",
        "Token Inspection",
        "Hosted Verification",
        "OIDC_AUDIENCE=interview-prep-mcp",
        "scripts/check_production_config.py",
        "scripts/verify_authenticated_mcp.py",
    ]
    missing_oidc_phrases = [phrase for phrase in required_oidc_phrases if phrase not in oidc_runbook]
    if missing_oidc_phrases:
        return CheckResult("public_launch_docs", False, f"OIDC provider runbook missing: {', '.join(missing_oidc_phrases)}")

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    required_readme_phrases = [
        "docs/oidc-provider-setup.md",
        "OpenAI submission packet",
        "MCP contract snapshot",
        "public launch docs",
        "scripts/verify_authenticated_mcp.py",
        "JWT audience required for public OIDC launch",
    ]
    missing_readme_phrases = [phrase for phrase in required_readme_phrases if phrase not in readme]
    if missing_readme_phrases:
        return CheckResult("public_launch_docs", False, f"README public launch guidance missing: {', '.join(missing_readme_phrases)}")

    deployment_doc = (REPO_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
    if "OIDC_AUDIENCE` | `interview-prep-mcp` | JWT audience required for public OIDC launch" not in deployment_doc:
        return CheckResult("public_launch_docs", False, "deployment doc must describe OIDC_AUDIENCE as required for public launch")

    return CheckResult("public_launch_docs", True, "public auth and production environment docs are present")


def check_plugin_bundle(plugin_root: Path) -> CheckResult:
    required_files = [
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "skills/interview-prep/SKILL.md",
        "index.md",
        ".codex-plugin/index.md",
        "skills/index.md",
        "skills/interview-prep/index.md",
    ]
    missing = [path for path in required_files if not (plugin_root / path).is_file()]
    if missing:
        return CheckResult("plugin_bundle", False, f"missing required files: {', '.join(missing)}")

    try:
        manifest = _read_json(plugin_root / ".codex-plugin" / "plugin.json")
        mcp_config = _read_json(plugin_root / ".mcp.json")
        marketplace = _read_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult("plugin_bundle", False, f"invalid plugin JSON: {exc}")

    errors: list[str] = []
    if manifest.get("name") != "interview-prep-mcp":
        errors.append("plugin name must be interview-prep-mcp")
    if manifest.get("mcpServers") != "./.mcp.json":
        errors.append("manifest mcpServers must point at ./.mcp.json")
    if manifest.get("skills") != "./skills/":
        errors.append("manifest skills must point at ./skills/")

    interface = manifest.get("interface", {})
    for key in ["displayName", "shortDescription", "websiteURL", "privacyPolicyURL", "termsOfServiceURL"]:
        if not interface.get(key):
            errors.append(f"manifest interface.{key} is required")

    servers = mcp_config.get("mcpServers", {})
    interview_server = servers.get("interview_prep", {})
    server_url = interview_server.get("url", "")
    if not server_url.startswith("https://") or not server_url.endswith("/mcp"):
        errors.append("interview_prep MCP URL must be an https /mcp endpoint")
    if not {"study:read", "study:write"}.issubset(set(interview_server.get("scopes", []))):
        errors.append("interview_prep scopes must include study:read and study:write")

    entries = marketplace.get("plugins", [])
    if not any(entry.get("name") == "interview-prep-mcp" for entry in entries):
        errors.append("repo marketplace must include interview-prep-mcp")

    skill_text = (plugin_root / "skills" / "interview-prep" / "SKILL.md").read_text(encoding="utf-8")
    if "[TODO" in skill_text or "TODO]" in skill_text:
        errors.append("skill file contains TODO placeholder text")
    required_skill_phrases = [
        "get_due_subtopics",
        "log_attempt",
        "list_studies",
        "delete_my_data",
        "DELETE MY STUDY DATA",
        "Do not ask for, invent, or pass a user id",
        "Do not call `log_attempt` before the user has answered",
        "soft deletes",
    ]
    missing_skill_phrases = [phrase for phrase in required_skill_phrases if phrase not in skill_text]
    if missing_skill_phrases:
        errors.append(f"skill file missing guidance: {', '.join(missing_skill_phrases)}")

    if errors:
        return CheckResult("plugin_bundle", False, "; ".join(errors))
    return CheckResult("plugin_bundle", True, "repo-local Codex plugin bundle is complete")


def check_folder_indexes() -> CheckResult:
    ignored_parts = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".venv311",
        "__pycache__",
        "data",
        "interview_prep_mcp.egg-info",
    }
    missing: list[str] = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_dir():
            continue
        relative = path.relative_to(REPO_ROOT)
        if any(part in ignored_parts for part in relative.parts):
            continue
        if not (path / "index.md").is_file():
            missing.append(str(relative))

    if missing:
        return CheckResult("folder_indexes", False, f"missing index.md in: {', '.join(missing)}")
    return CheckResult("folder_indexes", True, "every tracked project folder has an index.md")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_command(name: str, command: list[str], success_detail: str) -> CheckResult:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if completed.returncode == 0:
        return CheckResult(name, True, success_detail)

    output = "\n".join(part.strip() for part in [completed.stdout, completed.stderr] if part.strip())
    if len(output) > 700:
        output = output[-700:]
    return CheckResult(name, False, output or f"command exited {completed.returncode}")


if __name__ == "__main__":
    sys.exit(main())
