import unittest
from unittest.mock import patch

from interview_prep_mcp.auth import OidcJwtTokenVerifier, StaticBearerTokenVerifier, _extract_scopes, build_auth_components
from interview_prep_mcp.config import load_settings


class ConfigAndAuthTests(unittest.IsolatedAsyncioTestCase):
    def test_blank_auth_environment_is_treated_as_unset(self):
        with patch.dict(
            "os.environ",
            {"MCP_BEARER_TOKEN": "", "MCP_PUBLIC_BASE_URL": "", "MCP_PORT": "8010"},
            clear=True,
        ):
            settings = load_settings()

        self.assertIsNone(settings.bearer_token)
        self.assertEqual(settings.public_base_url, "http://127.0.0.1:8010")
        self.assertEqual(settings.resource_server_url, "http://127.0.0.1:8010/mcp")
        self.assertFalse(settings.allow_unauthenticated_http)
        self.assertIsNone(settings.oidc_issuer_url)
        self.assertEqual(settings.oidc_required_scopes, ["study:read", "study:write"])

    async def test_static_bearer_token_verifier_accepts_only_exact_token(self):
        verifier = StaticBearerTokenVerifier("secret-token")

        self.assertIsNone(await verifier.verify_token("wrong-token"))
        access_token = await verifier.verify_token("secret-token")

        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.client_id, "single-user")
        self.assertEqual(access_token.scopes, ["study:read", "study:write"])
        self.assertEqual(access_token.subject, "bem")

    async def test_static_bearer_token_verifier_uses_configured_subject(self):
        verifier = StaticBearerTokenVerifier("secret-token", subject="public-user")
        access_token = await verifier.verify_token("secret-token")

        self.assertEqual(access_token.subject, "public-user")

    def test_auth_components_are_enabled_only_when_token_exists(self):
        with patch.dict("os.environ", {}, clear=True):
            no_auth_settings = load_settings()
        self.assertEqual(build_auth_components(no_auth_settings), (None, None, None))

        with patch.dict(
            "os.environ",
            {
                "MCP_BEARER_TOKEN": "secret-token",
                "MCP_PUBLIC_BASE_URL": "https://study.example.com",
                "MCP_DEFAULT_SUBJECT": "public-user",
            },
            clear=True,
        ):
            auth_settings = load_settings()
        auth, verifier, provider = build_auth_components(auth_settings)

        self.assertIsNotNone(auth)
        self.assertIsNotNone(verifier)
        self.assertIsNone(provider)
        self.assertEqual(str(auth.resource_server_url), "https://study.example.com/mcp")

    def test_http_transport_requires_auth_unless_explicitly_allowed(self):
        with patch.dict(
            "os.environ",
            {
                "MCP_TRANSPORT": "streamable-http",
                "MCP_PUBLIC_BASE_URL": "https://study.example.com",
            },
            clear=True,
        ):
            settings = load_settings()

        with self.assertRaisesRegex(ValueError, "HTTP MCP transports require auth"):
            build_auth_components(settings)

        with patch.dict(
            "os.environ",
            {
                "MCP_TRANSPORT": "streamable-http",
                "MCP_PUBLIC_BASE_URL": "https://study.example.com",
                "MCP_ALLOW_UNAUTHENTICATED_HTTP": "true",
            },
            clear=True,
        ):
            allowed_settings = load_settings()

        self.assertEqual(build_auth_components(allowed_settings), (None, None, None))

    def test_oidc_auth_components_use_external_issuer(self):
        with patch.dict(
            "os.environ",
            {
                "MCP_TRANSPORT": "streamable-http",
                "MCP_PUBLIC_BASE_URL": "https://study.example.com",
                "OIDC_ISSUER_URL": "https://issuer.example.com",
                "OIDC_JWKS_URL": "https://issuer.example.com/keys",
                "OIDC_AUDIENCE": "interview-prep-mcp",
                "OIDC_SUBJECT_CLAIM": "sub",
                "OIDC_REQUIRED_SCOPES": "study:read,study:write",
            },
            clear=True,
        ):
            settings = load_settings()

        auth, verifier, provider = build_auth_components(settings)

        self.assertIsNotNone(auth)
        self.assertIsInstance(verifier, OidcJwtTokenVerifier)
        self.assertIsNone(provider)
        self.assertEqual(str(auth.issuer_url).rstrip("/"), "https://issuer.example.com")
        self.assertEqual(verifier.jwks_url, "https://issuer.example.com/keys")
        self.assertEqual(verifier.audience, "interview-prep-mcp")
        self.assertEqual(verifier.required_scopes, ["study:read", "study:write"])

    def test_oidc_scope_extraction_accepts_common_provider_claims(self):
        scopes = _extract_scopes(
            {
                "scope": "openid profile study:read",
                "scp": ["study:write"],
                "permissions": ["study:read", "admin:ignore"],
                "roles": ["reviewer"],
                "role": "authenticated",
            }
        )

        self.assertEqual(
            scopes,
            ["openid", "profile", "study:read", "study:write", "admin:ignore", "reviewer", "authenticated"],
        )
