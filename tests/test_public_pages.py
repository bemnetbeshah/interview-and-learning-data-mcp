import json
import unittest

from interview_prep_mcp.config import Settings
from interview_prep_mcp.public_pages import (
    render_health,
    render_home,
    render_privacy,
    render_support,
    render_terms,
)


class PublicPagesTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            db_path=":memory:",
            database_url=None,
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
            bearer_token=None,
            oauth_login_secret=None,
            oauth_token_ttl_seconds=3600,
            oauth_refresh_token_ttl_seconds=86400,
            public_base_url="https://study.example.com",
            resource_server_url="https://study.example.com/mcp",
            default_subject="bem",
            allow_unauthenticated_http=False,
            oidc_issuer_url="https://issuer.example.com",
            oidc_jwks_url="https://issuer.example.com/keys",
            oidc_audience="interview-prep-mcp",
            oidc_subject_claim="sub",
            oidc_required_scopes=["study:read", "study:write"],
            public_contact_email="support@study.example.com",
            public_service_name="Interview Prep MCP",
            rate_limit_per_minute=120,
        )

    def test_public_pages_include_required_review_links_and_contact(self):
        home_response = render_home(self.settings)
        home = home_response.body.decode()
        privacy = render_privacy(self.settings).body.decode()
        terms = render_terms(self.settings).body.decode()
        support = render_support(self.settings).body.decode()

        self.assertIn("https://study.example.com/mcp", home)
        self.assertIn("https://study.example.com/privacy", home)
        self.assertIn("support@study.example.com", privacy)
        self.assertIn("export_my_data", privacy)
        self.assertIn("delete_my_data", privacy)
        self.assertIn("Acceptable use", terms)
        self.assertIn("Do not send access tokens", support)
        self.assertIn("delete_my_data", support)
        self.assertIn("default-src 'none'", home_response.headers["content-security-policy"])
        self.assertEqual(home_response.headers["x-content-type-options"], "nosniff")

    def test_health_route_reports_non_secret_auth_modes(self):
        health = render_health(self.settings)
        payload = json.loads(health.body)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mcp_endpoint"], "https://study.example.com/mcp")
        self.assertTrue(payload["auth_modes"]["oidc"])
        self.assertFalse(payload["auth_modes"]["private_oauth"])
        self.assertNotIn("support@study.example.com", json.dumps(payload))
        self.assertEqual(health.headers["cache-control"], "no-store")
