#!/usr/bin/env python3
"""Check or update public URLs used by plugin distribution metadata."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "interview-prep-mcp"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
MCP_CONFIG = PLUGIN_ROOT / ".mcp.json"


@dataclass(frozen=True)
class UrlCheck:
    ok: bool
    detail: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or update public plugin/MCP URLs.")
    parser.add_argument("--base-url", help="Public HTTPS base URL, for example https://interview-prep.example.com")
    parser.add_argument("--write", action="store_true", help="Update plugin metadata to --base-url.")
    parser.add_argument("--check", action="store_true", help="Check URL consistency after optional update.")
    args = parser.parse_args()

    if args.write and not args.base_url:
        parser.error("--write requires --base-url")
    if args.base_url:
        validate_base_url(args.base_url)
    if args.write:
        update_public_base_url(args.base_url)
        print(f"ok: public URLs updated to {args.base_url.rstrip('/')}")

    if args.check or not args.write:
        checks = check_public_url_consistency(expected_base_url=args.base_url)
        for check in checks:
            status = "ok" if check.ok else "fail"
            print(f"{status}: public_urls: {check.detail}")
        return 0 if all(check.ok for check in checks) else 1
    return 0


def check_public_url_consistency(expected_base_url: str | None = None) -> list[UrlCheck]:
    manifest = _read_json(PLUGIN_MANIFEST)
    mcp_config = _read_json(MCP_CONFIG)
    server = mcp_config["mcpServers"]["interview_prep"]
    interface = manifest["interface"]

    base_url = expected_base_url.rstrip("/") if expected_base_url else _base_from_mcp_url(server["url"])
    checks = [
        _expect(manifest.get("homepage", "").rstrip("/") == base_url, f"manifest homepage matches {base_url}"),
        _expect(interface.get("websiteURL", "").rstrip("/") == base_url, f"interface websiteURL matches {base_url}"),
        _expect(interface.get("privacyPolicyURL") == f"{base_url}/privacy", "privacy URL matches base"),
        _expect(interface.get("termsOfServiceURL") == f"{base_url}/terms", "terms URL matches base"),
        _expect(server.get("url") == f"{base_url}/mcp", "MCP URL matches base"),
        _expect(server.get("oauth_resource") == f"{base_url}/mcp", "OAuth resource matches base"),
        _expect({"study:read", "study:write"}.issubset(set(server.get("scopes", []))), "MCP scopes include study grants"),
    ]
    return checks


def update_public_base_url(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    manifest = _read_json(PLUGIN_MANIFEST)
    mcp_config = _read_json(MCP_CONFIG)

    manifest["homepage"] = base_url
    manifest["interface"]["websiteURL"] = f"{base_url}/"
    manifest["interface"]["privacyPolicyURL"] = f"{base_url}/privacy"
    manifest["interface"]["termsOfServiceURL"] = f"{base_url}/terms"

    server = mcp_config["mcpServers"]["interview_prep"]
    server["url"] = f"{base_url}/mcp"
    server["oauth_resource"] = f"{base_url}/mcp"

    _write_json(PLUGIN_MANIFEST, manifest)
    _write_json(MCP_CONFIG, mcp_config)


def current_public_base_url() -> str:
    mcp_config = _read_json(MCP_CONFIG)
    return _base_from_mcp_url(mcp_config["mcpServers"]["interview_prep"]["url"])


def validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("base URL must be an HTTPS origin without a path")


def _base_from_mcp_url(mcp_url: str) -> str:
    if not mcp_url.endswith("/mcp"):
        raise ValueError("MCP URL must end with /mcp")
    return mcp_url[: -len("/mcp")].rstrip("/")


def _expect(condition: bool, detail: str) -> UrlCheck:
    return UrlCheck(condition, detail)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fail: public_urls: {exc}", file=sys.stderr)
        sys.exit(2)
