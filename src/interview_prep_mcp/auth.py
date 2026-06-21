"""Single-user bearer token verification for hosted MCP transports."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional

from .oauth import PersonalOAuthProvider, VALID_SCOPES


@dataclass(frozen=True)
class StaticBearerTokenVerifier:
    """Validate one deployment secret as an MCP bearer token."""

    expected_token: str

    async def verify_token(self, token: str):
        if not self.expected_token:
            return None
        if not hmac.compare_digest(token, self.expected_token):
            return None

        from mcp.server.auth.provider import AccessToken

        return AccessToken(
            token=token,
            client_id="single-user",
            scopes=["study:read", "study:write"],
            resource=None,
            subject="bem",
        )


def build_auth_components(settings, db=None) -> tuple[Optional[object], Optional[object], Optional[object]]:
    """Return FastMCP auth settings and token verifier when auth is configured."""

    if settings.oauth_login_secret:
        if db is None:
            raise ValueError("OAuth auth requires a database connection")
        from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

        provider = PersonalOAuthProvider(db, settings)
        auth = AuthSettings(
            issuer_url=settings.public_base_url,
            resource_server_url=settings.resource_server_url,
            required_scopes=VALID_SCOPES,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=VALID_SCOPES,
                default_scopes=VALID_SCOPES,
            ),
            revocation_options=RevocationOptions(enabled=True),
        )
        return auth, None, provider

    if not settings.bearer_token:
        return None, None, None

    from mcp.server.auth.settings import AuthSettings

    auth = AuthSettings(
        issuer_url=settings.public_base_url,
        resource_server_url=settings.resource_server_url,
        required_scopes=["study:read", "study:write"],
    )
    return auth, StaticBearerTokenVerifier(settings.bearer_token), None
