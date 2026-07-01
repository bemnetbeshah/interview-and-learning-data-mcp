import unittest
from pathlib import Path


class DockerfileTests(unittest.TestCase):
    def test_dockerfile_has_healthcheck_for_hosted_deployments(self):
        dockerfile = Path("Dockerfile").read_text()

        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("/healthz", dockerfile)
        self.assertIn("PORT", dockerfile)
