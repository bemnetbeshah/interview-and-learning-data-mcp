#!/usr/bin/env python3
"""Validate production configuration before public deployment."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from interview_prep_mcp.config import Settings, load_settings  # noqa: E402


@dataclass(frozen=True)
class ConfigCheck:
    level: str
    name: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.level != "fail"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check production readiness of Interview Prep MCP config.")
    parser.add_argument(
        "--allow-private-oauth",
        action="store_true",
        help="Allow approval-secret OAuth for private review deployments. Public launch should use OIDC.",
    )
    args = parser.parse_args()

    checks = check_settings(load_settings(), allow_private_oauth=args.allow_private_oauth)
    for check in checks:
        print(f"{check.level}: {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


def check_settings(settings: Settings, allow_private_oauth: bool = False) -> list[ConfigCheck]:
    checks: list[ConfigCheck] = []
    parsed_base = urlparse(settings.public_base_url)
    parsed_resource = urlparse(settings.resource_server_url)
    expected_resource_url = f"{settings.public_base_url.rstrip('/')}/mcp"

    checks.append(_expect(settings.transport == "streamable-http", "transport", "MCP_TRANSPORT must be streamable-http"))
    checks.append(_expect(settings.host == "0.0.0.0", "host", "MCP_HOST must be 0.0.0.0 for hosted deployments"))
    checks.append(_expect(_is_postgres_url(settings.database_url), "database", "DATABASE_URL must point at production Postgres"))
    checks.append(_expect(parsed_base.scheme == "https", "public_base_url", "MCP_PUBLIC_BASE_URL must be https"))
    checks.append(_expect(bool(parsed_base.netloc), "public_base_url_host", "MCP_PUBLIC_BASE_URL must include a host"))
    checks.append(_expect(parsed_resource.scheme == "https", "resource_server_url", "MCP_RESOURCE_SERVER_URL must be https"))
    checks.append(_expect(settings.resource_server_url.rstrip("/").endswith("/mcp"), "mcp_endpoint", "resource URL must end with /mcp"))
    checks.append(
        _expect(
            settings.resource_server_url.rstrip("/") == expected_resource_url,
            "resource_matches_base",
            "MCP_RESOURCE_SERVER_URL must be MCP_PUBLIC_BASE_URL plus /mcp",
        )
    )
    checks.append(
        _expect(not settings.allow_unauthenticated_http, "auth_required", "MCP_ALLOW_UNAUTHENTICATED_HTTP must be false")
    )
    checks.append(_expect(settings.bearer_token is None, "static_bearer", "MCP_BEARER_TOKEN must be unset for public launch"))

    if settings.oidc_issuer_url:
        checks.append(_pass("auth_mode", "OIDC/JWT verification is configured"))
        checks.append(_expect(urlparse(settings.oidc_issuer_url).scheme == "https", "oidc_issuer", "OIDC issuer must be https"))
        if settings.oidc_jwks_url:
            checks.append(_expect(urlparse(settings.oidc_jwks_url).scheme == "https", "oidc_jwks", "OIDC JWKS URL must be https"))
        checks.append(_expect(bool(settings.oidc_audience), "oidc_audience", "OIDC_AUDIENCE must be set"))
        checks.append(_expect(bool(settings.oidc_subject_claim), "oidc_subject_claim", "OIDC_SUBJECT_CLAIM must be set"))
        checks.append(
            _expect(
                {"study:read", "study:write"}.issubset(set(settings.oidc_required_scopes)),
                "oidc_scopes",
                "OIDC_REQUIRED_SCOPES must include study:read and study:write",
            )
        )
    elif allow_private_oauth and settings.oauth_login_secret:
        checks.append(_warn("auth_mode", "private approval-secret OAuth is allowed for review only"))
    else:
        checks.append(_fail("auth_mode", "public deployment requires OIDC_ISSUER_URL"))

    if not allow_private_oauth:
        checks.append(_expect(settings.oauth_login_secret is None, "private_oauth", "OAUTH_LOGIN_SECRET must be unset for public launch"))

    checks.append(_expect(settings.public_contact_email != "support@example.com", "contact", "PUBLIC_CONTACT_EMAIL is a placeholder"))
    checks.append(_expect("@" in settings.public_contact_email, "contact_format", "PUBLIC_CONTACT_EMAIL must be an email address"))
    checks.append(_expect(not _uses_example_domain(settings.public_contact_email), "contact_domain", "PUBLIC_CONTACT_EMAIL must not use an example domain"))
    checks.append(_expect(settings.rate_limit_per_minute > 0, "rate_limit", "RATE_LIMIT_PER_MINUTE must be positive"))

    if parsed_base.netloc.endswith(".up.railway.app"):
        checks.append(_warn("domain", "Railway subdomain is usable for testing; prefer a stable custom domain before public submission"))
    else:
        checks.append(_pass("domain", "public base URL is not the default Railway subdomain"))

    return checks


def _is_postgres_url(database_url: str | None) -> bool:
    if not database_url:
        return False
    return urlparse(database_url).scheme in {"postgres", "postgresql"}


def _uses_example_domain(email: str) -> bool:
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return domain in {"example.com", "example.org", "example.net"} or domain.endswith(".example.com")


def _expect(condition: bool, name: str, detail: str) -> ConfigCheck:
    return _pass(name, detail) if condition else _fail(name, detail)


def _pass(name: str, detail: str) -> ConfigCheck:
    return ConfigCheck("ok", name, detail)


def _warn(name: str, detail: str) -> ConfigCheck:
    return ConfigCheck("warn", name, detail)


def _fail(name: str, detail: str) -> ConfigCheck:
    return ConfigCheck("fail", name, detail)


if __name__ == "__main__":
    sys.exit(main())
