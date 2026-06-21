import asyncio
import unittest
from urllib.parse import parse_qs, urlparse

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from interview_prep_mcp.config import Settings
from interview_prep_mcp.db import connect_sqlite
from interview_prep_mcp.oauth import PersonalOAuthProvider


class OAuthProviderTests(unittest.TestCase):
    def test_register_approve_exchange_and_verify_token(self):
        async def run_flow():
            settings = Settings(
                db_path=":memory:",
                database_url=None,
                transport="streamable-http",
                host="127.0.0.1",
                port=8000,
                bearer_token=None,
                oauth_login_secret="login-secret",
                oauth_token_ttl_seconds=3600,
                oauth_refresh_token_ttl_seconds=86400,
                public_base_url="https://study.example.com",
                resource_server_url="https://study.example.com/mcp",
            )
            provider = PersonalOAuthProvider(connect_sqlite(":memory:"), settings)
            client = OAuthClientInformationFull(
                client_id="client-1",
                client_secret="client-secret",
                redirect_uris=[AnyUrl("https://chat.openai.com/callback")],
                token_endpoint_auth_method="client_secret_post",
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope="study:read study:write",
            )
            await provider.register_client(client)

            approval_url = await provider.authorize(
                client,
                AuthorizationParams(
                    state="state-1",
                    scopes=["study:read", "study:write"],
                    code_challenge="challenge",
                    redirect_uri=AnyUrl("https://chat.openai.com/callback"),
                    redirect_uri_provided_explicitly=True,
                    resource="https://study.example.com/mcp",
                ),
            )
            request_id = parse_qs(urlparse(approval_url).query)["request_id"][0]
            pending = provider.get_pending_authorization(request_id)
            self.assertIsNotNone(pending)

            redirect_url = provider.approve_pending_authorization(pending)
            code = parse_qs(urlparse(redirect_url).query)["code"][0]
            auth_code = await provider.load_authorization_code(client, code)
            self.assertIsNotNone(auth_code)

            token_response = await provider.exchange_authorization_code(client, auth_code)
            access_token = await provider.load_access_token(token_response.access_token)

            self.assertIsNotNone(access_token)
            self.assertEqual(access_token.client_id, "client-1")
            self.assertEqual(access_token.scopes, ["study:read", "study:write"])
            self.assertEqual(access_token.resource, "https://study.example.com/mcp")

        asyncio.run(run_flow())
