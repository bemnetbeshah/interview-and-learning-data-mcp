#!/usr/bin/env python3
"""Verify public launch endpoints for a hosted deployment."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from email.message import Message
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public Interview Prep MCP deployment endpoints.")
    parser.add_argument("base_url", help="Public base URL, for example https://interview-prep.example.com")
    parser.add_argument(
        "--allow-private-oauth",
        action="store_true",
        help="Allow approval-secret OAuth for private reviewer deployments. Public launch should use OIDC.",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    checks = [
        check_public_page(base_url, "/"),
        check_public_page(base_url, "/privacy"),
        check_public_page(base_url, "/terms"),
        check_public_page(base_url, "/support"),
        check_health(base_url, allow_private_oauth=args.allow_private_oauth),
        check_protected_resource_metadata(base_url),
        check_mcp_rejects_unauthenticated(base_url),
    ]

    for check in checks:
        status = "ok" if check.ok else "FAIL"
        print(f"{status}: {check.name}: {check.detail}")

    return 0 if all(check.ok for check in checks) else 1


def check_public_page(base_url: str, path: str) -> CheckResult:
    status, body, headers = fetch(base_url + path)
    header_errors = validate_security_headers(headers)
    ok = status == 200 and "Interview Prep MCP" in body and not header_errors
    detail = f"HTTP {status}"
    if header_errors:
        detail += f", headers: {'; '.join(header_errors)}"
    return CheckResult(path, ok, detail)


def check_health(base_url: str, allow_private_oauth: bool = False) -> CheckResult:
    status, body, headers = fetch(base_url + "/healthz")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult("/healthz", False, f"HTTP {status}, invalid JSON")
    header_errors = validate_security_headers(headers)
    payload_errors = validate_health_payload(payload, base_url, allow_private_oauth=allow_private_oauth)
    ok = status == 200 and not header_errors and not payload_errors
    detail = f"HTTP {status}, status={payload.get('status')}"
    if header_errors:
        detail += f", headers: {'; '.join(header_errors)}"
    if payload_errors:
        detail += f", payload: {'; '.join(payload_errors)}"
    return CheckResult("/healthz", ok, detail)


def check_mcp_rejects_unauthenticated(base_url: str) -> CheckResult:
    status, _body, _headers = fetch(base_url + "/mcp")
    ok = status in {401, 403, 405}
    return CheckResult("/mcp unauthenticated", ok, f"HTTP {status}")


def check_protected_resource_metadata(base_url: str) -> CheckResult:
    metadata_path = "/.well-known/oauth-protected-resource/mcp"
    status, body, _headers = fetch(base_url + metadata_path)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return CheckResult(metadata_path, False, f"HTTP {status}, invalid JSON")

    errors = validate_protected_resource_metadata(payload, base_url)
    ok = status == 200 and not errors
    detail = f"HTTP {status}"
    if errors:
        detail += f", {'; '.join(errors)}"
    return CheckResult(metadata_path, ok, detail)


def validate_protected_resource_metadata(payload: dict, base_url: str) -> list[str]:
    expected_resource = f"{base_url.rstrip('/')}/mcp"
    errors: list[str] = []
    if payload.get("resource") != expected_resource:
        errors.append(f"resource must be {expected_resource}")

    authorization_servers = payload.get("authorization_servers")
    if not isinstance(authorization_servers, list) or not authorization_servers:
        errors.append("authorization_servers must be a non-empty list")
    else:
        invalid_servers = [server for server in authorization_servers if urlparse(str(server)).scheme != "https"]
        if invalid_servers:
            errors.append("authorization_servers must be https URLs")

    scopes = set(payload.get("scopes_supported") or [])
    missing_scopes = {"study:read", "study:write"} - scopes
    if missing_scopes:
        errors.append(f"scopes_supported missing {', '.join(sorted(missing_scopes))}")

    bearer_methods = payload.get("bearer_methods_supported") or []
    if bearer_methods and "header" not in bearer_methods:
        errors.append("bearer_methods_supported must include header when present")

    return errors


def validate_health_payload(payload: dict, base_url: str, allow_private_oauth: bool = False) -> list[str]:
    expected_endpoint = f"{base_url.rstrip('/')}/mcp"
    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append("status must be ok")
    if payload.get("mcp_endpoint") != expected_endpoint:
        errors.append(f"mcp_endpoint must be {expected_endpoint}")

    auth_modes = payload.get("auth_modes")
    if not isinstance(auth_modes, dict):
        errors.append("auth_modes must be an object")
        return errors

    if auth_modes.get("unauthenticated_http_allowed"):
        errors.append("unauthenticated_http_allowed must be false")
    if auth_modes.get("static_bearer"):
        errors.append("static_bearer must be false for public deployment")
    if allow_private_oauth:
        if not (auth_modes.get("oidc") or auth_modes.get("private_oauth")):
            errors.append("oidc or private_oauth must be true")
    elif not auth_modes.get("oidc"):
        errors.append("oidc must be true for public deployment")
    if auth_modes.get("private_oauth") and not allow_private_oauth:
        errors.append("private_oauth must be false for public deployment")

    return errors


def validate_security_headers(headers: Message | dict[str, str]) -> list[str]:
    required = {
        "content-security-policy": "default-src 'none'",
        "cache-control": "no-store",
        "referrer-policy": "no-referrer",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
    }
    errors = []
    normalized = {key.lower(): value for key, value in headers.items()}
    for name, expected in required.items():
        value = normalized.get(name, "")
        if expected.lower() not in value.lower():
            errors.append(f"{name} missing {expected}")
    return errors


def fetch(url: str) -> tuple[int, str, Message | dict[str, str]]:
    request = Request(url, headers={"User-Agent": "interview-prep-mcp-verifier/0.1"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), response.headers
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), exc.headers
    except URLError as exc:
        return 0, str(exc), {}


if __name__ == "__main__":
    sys.exit(main())
