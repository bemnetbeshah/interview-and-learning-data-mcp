import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from interview_prep_mcp.auth import OidcJwtTokenVerifier


class OidcJwtVerifierTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        self.verifier = OidcJwtTokenVerifier(
            issuer_url="https://issuer.example.com",
            jwks_url="https://issuer.example.com/.well-known/jwks.json",
            audience="interview-prep-mcp",
            subject_claim="sub",
            required_scopes=["study:read", "study:write"],
        )
        object.__setattr__(self.verifier, "_jwks_client", _FakeJwksClient(self.public_key))

    async def test_valid_oidc_jwt_returns_access_token(self):
        token = self._token(
            {
                "sub": "user-123",
                "scope": "openid profile study:read study:write",
                "azp": "chatgpt-review-client",
            }
        )

        access_token = await self.verifier.verify_token(token)

        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.subject, "user-123")
        self.assertEqual(access_token.client_id, "chatgpt-review-client")
        self.assertIn("study:read", access_token.scopes)
        self.assertIn("study:write", access_token.scopes)
        self.assertGreater(access_token.expires_at, int(time.time()))

    async def test_permissions_claim_can_satisfy_required_scopes(self):
        token = self._token(
            {
                "sub": "user-123",
                "permissions": ["study:read", "study:write"],
                "client_id": "provider-client",
            }
        )

        access_token = await self.verifier.verify_token(token)

        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.scopes, ["study:read", "study:write"])
        self.assertEqual(access_token.client_id, "provider-client")

    async def test_missing_required_scope_is_rejected(self):
        token = self._token({"sub": "user-123", "scope": "study:read"})

        self.assertIsNone(await self.verifier.verify_token(token))

    async def test_wrong_issuer_is_rejected(self):
        token = self._token({"sub": "user-123", "scope": "study:read study:write"}, issuer="https://evil.example.com")

        self.assertIsNone(await self.verifier.verify_token(token))

    async def test_missing_subject_is_rejected(self):
        token = self._token({"scope": "study:read study:write"})

        self.assertIsNone(await self.verifier.verify_token(token))

    async def test_expired_token_is_rejected(self):
        token = self._token({"sub": "user-123", "scope": "study:read study:write"}, exp=int(time.time()) - 10)

        self.assertIsNone(await self.verifier.verify_token(token))

    def _token(self, claims, issuer="https://issuer.example.com", exp=None):
        now = int(time.time())
        payload = {
            "iss": issuer,
            "aud": "interview-prep-mcp",
            "iat": now,
            "exp": exp if exp is not None else now + 3600,
        }
        payload.update(claims)
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": "test-key"})


class _FakeJwksClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self.public_key)


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key
