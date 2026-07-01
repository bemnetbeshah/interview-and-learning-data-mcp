"""Bearer token verification for hosted MCP transports."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Optional

from .oauth import PersonalOAuthProvider, VALID_SCOPES


@dataclass(frozen=True)
class StaticBearerTokenVerifier:
    """Validate one deployment secret as an MCP bearer token."""

    expected_token: str
    subject: str = "bem"

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
            subject=self.subject,
        )


@dataclass(frozen=True)
class OidcJwtTokenVerifier:
    """Validate JWT access tokens issued by an external OIDC provider."""

    issuer_url: str
    jwks_url: str
    audience: str | None
    subject_claim: str
    required_scopes: list[str]

    def __post_init__(self) -> None:
        import jwt

        object.__setattr__(self, "_jwks_client", jwt.PyJWKClient(self.jwks_url))

    async def verify_token(self, token: str):
        import jwt
        from jwt import PyJWTError
        from mcp.server.auth.provider import AccessToken

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            decode_kwargs = {
                "key": signing_key,
                "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                "issuer": self.issuer_url,
                "options": {"verify_aud": bool(self.audience)},
            }
            if self.audience:
                decode_kwargs["audience"] = self.audience
            claims = jwt.decode(token, **decode_kwargs)
        except PyJWTError:
            return None

        granted_scopes = _extract_scopes(claims)
        if not set(self.required_scopes).issubset(set(granted_scopes)):
            return None

        subject = claims.get(self.subject_claim)
        if not subject:
            return None

        client_id = claims.get("azp") or claims.get("client_id") or claims.get("aud") or "oidc-client"
        if isinstance(client_id, list):
            client_id = client_id[0] if client_id else "oidc-client"

        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=granted_scopes,
            resource=None,
            subject=str(subject),
            expires_at=claims.get("exp"),
        )


def build_auth_components(settings, db=None) -> tuple[Optional[object], Optional[object], Optional[object]]:
    """Return FastMCP auth settings and token verifier when auth is configured."""

    _validate_remote_auth_settings(settings)

    if settings.oidc_issuer_url:
        from mcp.server.auth.settings import AuthSettings

        jwks_url = settings.oidc_jwks_url or f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/jwks.json"
        auth = AuthSettings(
            issuer_url=settings.oidc_issuer_url,
            resource_server_url=settings.resource_server_url,
            required_scopes=settings.oidc_required_scopes,
        )
        verifier = OidcJwtTokenVerifier(
            issuer_url=settings.oidc_issuer_url,
            jwks_url=jwks_url,
            audience=settings.oidc_audience,
            subject_claim=settings.oidc_subject_claim,
            required_scopes=settings.oidc_required_scopes,
        )
        return auth, verifier, None

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
    return auth, StaticBearerTokenVerifier(settings.bearer_token, settings.default_subject), None


def _validate_remote_auth_settings(settings) -> None:
    """Prevent accidental unauthenticated public HTTP deployments."""

    if settings.transport == "stdio":
        return
    if settings.allow_unauthenticated_http:
        return
    if settings.oidc_issuer_url or settings.oauth_login_secret or settings.bearer_token:
        return
    raise ValueError(
        "HTTP MCP transports require auth. Set OIDC_ISSUER_URL for public OAuth/OIDC, "
        "OAUTH_LOGIN_SECRET for private OAuth, MCP_BEARER_TOKEN for static bearer mode, "
        "or MCP_ALLOW_UNAUTHENTICATED_HTTP=true only for non-public development."
    )


def _extract_scopes(claims: dict) -> list[str]:
    scopes: list[str] = []
    for claim_name in ["scope", "scp", "permissions", "roles", "role"]:
        scopes.extend(_claim_values(claims.get(claim_name)))
    return list(dict.fromkeys(scopes))


def _claim_values(value) -> list[str]:
    if isinstance(value, str):
        return [item for item in value.replace(",", " ").split() if item]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []
