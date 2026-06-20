"""Single-user bearer token verification for hosted MCP transports."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional


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


def build_auth_components(settings) -> tuple[Optional[object], Optional[object]]:
    """Return FastMCP auth settings and token verifier when auth is configured."""

    if not settings.bearer_token:
        return None, None

    from mcp.server.auth.settings import AuthSettings

    auth = AuthSettings(
        issuer_url=settings.public_base_url,
        resource_server_url=settings.resource_server_url,
        required_scopes=["study:read", "study:write"],
    )
    return auth, StaticBearerTokenVerifier(settings.bearer_token)
