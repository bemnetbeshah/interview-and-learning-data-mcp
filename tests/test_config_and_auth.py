import unittest
from unittest.mock import patch

from interview_prep_mcp.auth import StaticBearerTokenVerifier, build_auth_components
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

    async def test_static_bearer_token_verifier_accepts_only_exact_token(self):
        verifier = StaticBearerTokenVerifier("secret-token")

        self.assertIsNone(await verifier.verify_token("wrong-token"))
        access_token = await verifier.verify_token("secret-token")

        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.client_id, "single-user")
        self.assertEqual(access_token.scopes, ["study:read", "study:write"])

    def test_auth_components_are_enabled_only_when_token_exists(self):
        with patch.dict("os.environ", {}, clear=True):
            no_auth_settings = load_settings()
        self.assertEqual(build_auth_components(no_auth_settings), (None, None))

        with patch.dict(
            "os.environ",
            {
                "MCP_BEARER_TOKEN": "secret-token",
                "MCP_PUBLIC_BASE_URL": "https://study.example.com",
            },
            clear=True,
        ):
            auth_settings = load_settings()
        auth, verifier = build_auth_components(auth_settings)

        self.assertIsNotNone(auth)
        self.assertIsNotNone(verifier)
        self.assertEqual(str(auth.resource_server_url), "https://study.example.com/mcp")
