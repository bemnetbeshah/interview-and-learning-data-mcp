"""Runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    database_url: str | None
    transport: str
    host: str
    port: int
    bearer_token: str | None
    oauth_login_secret: str | None
    oauth_token_ttl_seconds: int
    oauth_refresh_token_ttl_seconds: int
    public_base_url: str
    resource_server_url: str
    default_subject: str
    allow_unauthenticated_http: bool
    oidc_issuer_url: str | None
    oidc_jwks_url: str | None
    oidc_audience: str | None
    oidc_subject_claim: str
    oidc_required_scopes: list[str]
    public_contact_email: str
    public_service_name: str
    rate_limit_per_minute: int


def load_settings() -> Settings:
    db_path = Path(_env("INTERVIEW_PREP_DB_PATH", "data/interview_prep.sqlite3"))
    database_url = _env("DATABASE_URL", "")
    transport = _env("MCP_TRANSPORT", "stdio")
    host = _env("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    bearer_token = _env("MCP_BEARER_TOKEN", "")
    oauth_login_secret = _env("OAUTH_LOGIN_SECRET", "")
    oauth_token_ttl_seconds = int(_env("OAUTH_TOKEN_TTL_SECONDS", "3600"))
    oauth_refresh_token_ttl_seconds = int(_env("OAUTH_REFRESH_TOKEN_TTL_SECONDS", "2592000"))
    public_base_url = _env("MCP_PUBLIC_BASE_URL", f"http://{host}:{port}")
    resource_server_url = _env("MCP_RESOURCE_SERVER_URL", f"{public_base_url.rstrip('/')}/mcp")
    default_subject = _env("MCP_DEFAULT_SUBJECT", "bem")
    allow_unauthenticated_http = _env_bool("MCP_ALLOW_UNAUTHENTICATED_HTTP", False)
    oidc_issuer_url = _env("OIDC_ISSUER_URL", "")
    oidc_jwks_url = _env("OIDC_JWKS_URL", "")
    oidc_audience = _env("OIDC_AUDIENCE", "")
    oidc_subject_claim = _env("OIDC_SUBJECT_CLAIM", "sub")
    oidc_required_scopes = _env_list("OIDC_REQUIRED_SCOPES", "study:read study:write")
    public_contact_email = _env("PUBLIC_CONTACT_EMAIL", "support@example.com")
    public_service_name = _env("PUBLIC_SERVICE_NAME", "Interview Prep MCP")
    rate_limit_per_minute = int(_env("RATE_LIMIT_PER_MINUTE", "120"))
    return Settings(
        db_path=db_path,
        database_url=database_url or None,
        transport=transport,
        host=host,
        port=port,
        bearer_token=bearer_token or None,
        oauth_login_secret=oauth_login_secret or None,
        oauth_token_ttl_seconds=oauth_token_ttl_seconds,
        oauth_refresh_token_ttl_seconds=oauth_refresh_token_ttl_seconds,
        public_base_url=public_base_url,
        resource_server_url=resource_server_url,
        default_subject=default_subject,
        allow_unauthenticated_http=allow_unauthenticated_http,
        oidc_issuer_url=oidc_issuer_url or None,
        oidc_jwks_url=oidc_jwks_url or None,
        oidc_audience=oidc_audience or None,
        oidc_subject_claim=oidc_subject_claim,
        oidc_required_scopes=oidc_required_scopes,
        public_contact_email=public_contact_email,
        public_service_name=public_service_name,
        rate_limit_per_minute=rate_limit_per_minute,
    )


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    value = _env(name, default)
    return [item for item in value.replace(",", " ").split() if item]
