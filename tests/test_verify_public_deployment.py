import unittest

from scripts.verify_public_deployment import (
    validate_health_payload,
    validate_protected_resource_metadata,
    validate_security_headers,
)


class VerifyPublicDeploymentTests(unittest.TestCase):
    def test_security_header_validation_accepts_required_headers(self):
        errors = validate_security_headers(
            {
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            }
        )

        self.assertEqual(errors, [])

    def test_security_header_validation_reports_missing_headers(self):
        errors = validate_security_headers({"Cache-Control": "public"})

        self.assertIn("content-security-policy missing default-src 'none'", errors)
        self.assertIn("cache-control missing no-store", errors)

    def test_protected_resource_metadata_validation_accepts_expected_metadata(self):
        errors = validate_protected_resource_metadata(
            {
                "resource": "https://study.example.com/mcp",
                "authorization_servers": ["https://issuer.example.com"],
                "scopes_supported": ["study:read", "study:write"],
                "bearer_methods_supported": ["header"],
            },
            "https://study.example.com",
        )

        self.assertEqual(errors, [])

    def test_protected_resource_metadata_validation_reports_review_blockers(self):
        errors = validate_protected_resource_metadata(
            {
                "resource": "https://wrong.example.com/mcp",
                "authorization_servers": ["http://issuer.example.com"],
                "scopes_supported": ["study:read"],
                "bearer_methods_supported": ["body"],
            },
            "https://study.example.com",
        )

        self.assertIn("resource must be https://study.example.com/mcp", errors)
        self.assertIn("authorization_servers must be https URLs", errors)
        self.assertIn("scopes_supported missing study:write", errors)
        self.assertIn("bearer_methods_supported must include header when present", errors)

    def test_health_payload_validation_accepts_public_oidc(self):
        errors = validate_health_payload(
            {
                "status": "ok",
                "mcp_endpoint": "https://study.example.com/mcp",
                "auth_modes": {
                    "oidc": True,
                    "private_oauth": False,
                    "static_bearer": False,
                    "unauthenticated_http_allowed": False,
                },
            },
            "https://study.example.com",
        )

        self.assertEqual(errors, [])

    def test_health_payload_validation_reports_public_auth_blockers(self):
        errors = validate_health_payload(
            {
                "status": "ok",
                "mcp_endpoint": "https://wrong.example.com/mcp",
                "auth_modes": {
                    "oidc": False,
                    "private_oauth": True,
                    "static_bearer": True,
                    "unauthenticated_http_allowed": True,
                },
            },
            "https://study.example.com",
        )

        self.assertIn("mcp_endpoint must be https://study.example.com/mcp", errors)
        self.assertIn("unauthenticated_http_allowed must be false", errors)
        self.assertIn("static_bearer must be false for public deployment", errors)
        self.assertIn("oidc must be true for public deployment", errors)
        self.assertIn("private_oauth must be false for public deployment", errors)

    def test_health_payload_validation_allows_private_review_oauth_when_requested(self):
        errors = validate_health_payload(
            {
                "status": "ok",
                "mcp_endpoint": "https://study.example.com/mcp",
                "auth_modes": {
                    "oidc": False,
                    "private_oauth": True,
                    "static_bearer": False,
                    "unauthenticated_http_allowed": False,
                },
            },
            "https://study.example.com",
            allow_private_oauth=True,
        )

        self.assertEqual(errors, [])
