import unittest
from pathlib import Path

from interview_prep_mcp.config import Settings

from scripts.check_production_config import check_settings


class ProductionConfigCheckTests(unittest.TestCase):
    def test_public_oidc_config_passes_with_custom_domain(self):
        checks = check_settings(_settings())

        self.assertFalse([check for check in checks if check.level == "fail"])

    def test_missing_oidc_and_placeholder_contact_fail(self):
        settings = _settings(
            oidc_issuer_url=None,
            public_contact_email="support@example.com",
            allow_unauthenticated_http=True,
            database_url=None,
        )

        failures = {check.name for check in check_settings(settings) if check.level == "fail"}

        self.assertIn("auth_mode", failures)
        self.assertIn("contact", failures)
        self.assertIn("auth_required", failures)
        self.assertIn("database", failures)
        self.assertIn("contact_domain", failures)

    def test_private_oauth_can_be_allowed_for_review(self):
        settings = _settings(oidc_issuer_url=None, oauth_login_secret="secret")

        strict_failures = {check.name for check in check_settings(settings) if check.level == "fail"}
        review_failures = {check.name for check in check_settings(settings, allow_private_oauth=True) if check.level == "fail"}
        review_warnings = {check.name for check in check_settings(settings, allow_private_oauth=True) if check.level == "warn"}

        self.assertIn("auth_mode", strict_failures)
        self.assertIn("private_oauth", strict_failures)
        self.assertNotIn("auth_mode", review_failures)
        self.assertNotIn("private_oauth", review_failures)
        self.assertIn("auth_mode", review_warnings)

    def test_public_urls_must_match(self):
        settings = _settings(resource_server_url="https://api.bem.dev/mcp")

        failures = {check.name for check in check_settings(settings) if check.level == "fail"}

        self.assertIn("resource_matches_base", failures)

    def test_public_launch_rejects_static_bearer_and_weak_oidc(self):
        settings = _settings(
            bearer_token="secret",
            oidc_audience=None,
            oidc_jwks_url="http://issuer.bem.dev/keys",
            oidc_subject_claim="",
        )

        failures = {check.name for check in check_settings(settings) if check.level == "fail"}

        self.assertIn("static_bearer", failures)
        self.assertIn("oidc_audience", failures)
        self.assertIn("oidc_jwks", failures)
        self.assertIn("oidc_subject_claim", failures)

    def test_database_must_be_postgres(self):
        settings = _settings(database_url="sqlite:///tmp/dev.db")

        failures = {check.name for check in check_settings(settings) if check.level == "fail"}

        self.assertIn("database", failures)


def _settings(**overrides):
    values = {
        "db_path": Path("data/interview_prep.sqlite3"),
        "database_url": "postgresql://user:pass@db.bem.dev:5432/app",
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 8000,
        "bearer_token": None,
        "oauth_login_secret": None,
        "oauth_token_ttl_seconds": 3600,
        "oauth_refresh_token_ttl_seconds": 2592000,
        "public_base_url": "https://study.bem.dev",
        "resource_server_url": "https://study.bem.dev/mcp",
        "default_subject": "bem",
        "allow_unauthenticated_http": False,
        "oidc_issuer_url": "https://issuer.bem.dev",
        "oidc_jwks_url": "https://issuer.bem.dev/keys",
        "oidc_audience": "interview-prep-mcp",
        "oidc_subject_claim": "sub",
        "oidc_required_scopes": ["study:read", "study:write"],
        "public_contact_email": "support@study.bem.dev",
        "public_service_name": "Interview Prep MCP",
        "rate_limit_per_minute": 120,
    }
    values.update(overrides)
    return Settings(**values)
